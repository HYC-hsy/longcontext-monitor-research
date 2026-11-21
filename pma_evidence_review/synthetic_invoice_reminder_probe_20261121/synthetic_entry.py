"""One isolated, at-most-four-turn native GA invoice continuation.

This file is an experiment harness, not a task or manager prompt. The model
sees only the frozen GA system, the short task background, one optional
reminder in the normal append envelope, and the unchanged GA tool schema.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import time
from types import SimpleNamespace

from agent_loop import agent_runner_loop
from agentmain import GenericAgent
from ga import GenericAgentHandler
from pma_upstream_bridge import append_reminder


BACKGROUND = "按票据原文提取金额。初稿 CSV 已生成，请接着完成任务。"
REMINDERS = {
    "none": None,
    "general": "交付前，对照任务要求和当前结果，看看还有什么需要核对。",
    "targeted": "交付前，可以把几笔已提取的金额和对应票据原文对一下。",
}


def initial_messages(seed: dict, arm: str) -> list[dict]:
    if arm not in REMINDERS:
        raise ValueError("unknown synthetic arm")
    messages = [{"role": "system", "content": seed["system"]},
                {"role": "user", "content": BACKGROUND}]
    if REMINDERS[arm] is not None:
        messages[-1] = append_reminder(messages[-1], REMINDERS[arm])
    return messages


def preflight(seed_path: Path, arm: str, output: Path) -> dict:
    """Exercise the installed native file tool and request assembly, no model."""
    seed = json.loads(seed_path.read_text(encoding="utf-8-sig"))
    if seed.get("schema") != "synthetic-task-seed-v1":
        raise ValueError("wrong synthetic request seed")
    agent = GenericAgent()
    agent.task_dir = "/app"
    agent.workspace_dir = "/app"
    handler = GenericAgentHandler(agent, [], "/app")
    actual = {name: getattr(agent.llmclient.backend, name, None) for name in
              ("model", "temperature", "max_tokens", "thinking_type",
               "api_mode", "stream")}
    expected = {name: seed["task_model" if name == "model" else name]
                for name in actual}
    if actual != expected:
        raise RuntimeError("native Task model differs from frozen seed")
    receipts = []
    for rel in ("summary.csv", "receipts/INV-2417.txt",
                "receipts/INV-2418.txt", "receipts/INV-2419.txt"):
        call = handler.do_file_read({"path": rel, "show_linenos": False},
                                    SimpleNamespace(content=""))
        try:
            while True:
                next(call)
        except StopIteration as stopped:
            value = stopped.value
        if not isinstance(value.data, str) or value.data.startswith("Error:"):
            raise RuntimeError("native file_read could not read " + rel)
        path = Path("/app") / rel
        receipts.append({"path": rel, "tool": "file_read",
                         "result": value.data,
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    prepared_requests = []

    def simulated_transport(*args, **kwargs):
        prepared_requests.append({"messages": copy.deepcopy(kwargs["messages"]),
                                  "tools": copy.deepcopy(kwargs["tools"])})
        if False:
            yield None
        return SimpleNamespace(content="Offline assembly check.", tool_calls=[])

    agent.llmclient.chat = simulated_transport
    generator = agent_runner_loop(
        agent.llmclient, seed["system"], BACKGROUND, handler, seed["tools"],
        max_turns=1, verbose=False, yield_info=True,
        initial_user_content=initial_messages(seed, arm)[-1]["content"])
    for _ in generator:
        pass
    if len(prepared_requests) != 1:
        raise RuntimeError("simulated native transport did not receive one request")
    if prepared_requests[0] != {"messages": initial_messages(seed, arm),
                                "tools": seed["tools"]}:
        raise RuntimeError("native Task request assembly changed the frozen input")
    result = {"schema": "synthetic-invoice-zero-model-preflight-v1",
              "arm": arm, "model": actual,
              "request_messages": prepared_requests[0]["messages"],
              "request_tools": prepared_requests[0]["tools"],
              "file_receipts": receipts}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    return result


def run(seed_path: Path, arm: str, output: Path) -> dict:
    seed = json.loads(seed_path.read_text(encoding="utf-8-sig"))
    if seed.get("schema") != "synthetic-task-seed-v1":
        raise ValueError("wrong synthetic request seed")
    workspace = Path("/app")
    if not workspace.is_dir() or not (workspace / "summary.csv").is_file():
        raise RuntimeError("independent synthetic Task workspace unavailable")
    if len(list((workspace / "receipts").glob("*.txt"))) != 3:
        raise RuntimeError("synthetic source invoice set changed")
    agent = GenericAgent()
    agent.task_dir = str(workspace)
    agent.workspace_dir = str(workspace)
    agent.history = []
    handler = GenericAgentHandler(agent, agent.history, str(workspace))
    agent.handler = handler
    agent.llmclient.log_path = str(output.parent / "model_responses.txt")
    backend = agent.llmclient.backend
    actual = {name: getattr(backend, name, None) for name in
              ("model", "temperature", "max_tokens", "thinking_type",
               "api_mode", "stream")}
    expected = {name: seed["task_model" if name == "model" else name]
                for name in actual}
    if actual != expected:
        raise RuntimeError("native Task model parameters differ from frozen seed")
    messages = initial_messages(seed, arm)
    events = []
    visible = []
    original_chat = agent.llmclient.chat

    def recording_chat(*args, **kwargs):
        request_messages = kwargs.get("messages", args[0] if args else None)
        request_tools = kwargs.get("tools", args[1] if len(args) > 1 else None)
        events.append({"kind": "task_request_prepared",
                       "messages": copy.deepcopy(request_messages),
                       "tools": copy.deepcopy(request_tools)})
        return (yield from original_chat(*args, **kwargs))

    agent.llmclient.chat = recording_chat
    original_turn_end = handler.turn_end_callback

    def recording_turn_end(response, tool_calls, tool_results, turn,
                           next_prompt, exit_reason):
        result = original_turn_end(response, tool_calls, tool_results, turn,
                                   next_prompt, exit_reason)
        events.append({"kind": "task_turn_result", "turn": turn,
                       "public_response": getattr(response, "content", "") or "",
                       "tool_calls": copy.deepcopy(tool_calls),
                       "tool_results": copy.deepcopy(tool_results),
                       "next_prompt": result,
                       "exit_reason": copy.deepcopy(exit_reason)})
        return result

    handler.turn_end_callback = recording_turn_end
    started = time.time()
    error = None
    generator = agent_runner_loop(
        agent.llmclient, seed["system"], BACKGROUND, handler, seed["tools"],
        max_turns=4, verbose=False, yield_info=True,
        initial_user_content=messages[-1]["content"])
    try:
        while True:
            visible.append(next(generator))
    except StopIteration as stopped:
        terminal = stopped.value
    except BaseException as exc:
        terminal = {"result": "EXCEPTION"}
        error = {"type": type(exc).__name__, "message": str(exc)}
    csv_bytes = (workspace / "summary.csv").read_bytes()
    result = {
        "schema": "synthetic-invoice-arm-result-v1", "arm": arm,
        "background": BACKGROUND, "reminder": REMINDERS[arm],
        "model": actual, "started_epoch": started, "ended_epoch": time.time(),
        "terminal": terminal, "error": error,
        "visible_stream": visible, "visible_events": events,
        "final_csv_sha256": hashlib.sha256(csv_bytes).hexdigest(),
        "final_csv": csv_bytes.decode("utf-8", errors="replace"),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, default=str)
    if error is not None:
        raise RuntimeError("synthetic arm failed; original partial result retained")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=Path, required=True)
    parser.add_argument("--arm", choices=tuple(REMINDERS), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    if args.preflight:
        preflight(args.seed, args.arm, args.output)
    else:
        run(args.seed, args.arm, args.output)


if __name__ == "__main__":
    main()
