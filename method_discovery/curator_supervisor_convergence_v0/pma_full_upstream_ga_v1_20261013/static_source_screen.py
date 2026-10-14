"""Unauthorized-by-default, fixed-public-trace U/S/R shadow entry.

The fake mode calls the pinned upstream PMA through PMAEpisode. It never runs GA,
an evaluator, or a provider transport. This is not a historical PMA restoration.
"""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
VENDOR = HERE / "vendor" / "pma_89e5c0d"
sys.path.insert(0, str(VENDOR / "src"))
sys.path.insert(0, str(VENDOR / "external" / "harbor" / "src"))
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
from harbor.llms.base import LLMResponse

from episode import PMAEpisode, construct_upstream


MANIFEST = HERE / "SOURCE_MEMORY_STATIC_SCREEN_DRAFT.json"
MANIFEST_V2 = HERE / "SOURCE_MEMORY_STATIC_SCREEN_V2_DRAFT.json"
FIELDS = {
    "task_start": ("initial_user_content",),
    "before_actor_call": ("actor_attempt",),
    "actor_step": ("actor_attempt", "step_status", "response", "commands", "observation"),
}


def ordered_slots(manifest: dict) -> list[tuple[str, str]]:
    cases = {case["task"] for case in manifest["cases"]}
    if "planned_order" not in manifest:
        return [(case["task"], variant) for case in manifest["cases"]
                for variant in manifest["conditions"]]
    plan = manifest["planned_order"]
    if (not isinstance(plan, list) or len(plan) != 6 or
            [row.get("order") for row in plan] != list(range(1, 7))):
        raise ValueError("invalid six-slot order")
    slots = [(row["task"], row["variant"]) for row in plan]
    if len(set(slots)) != 6 or set(slots) != {(task, variant) for task in cases
                                               for variant in manifest["conditions"]}:
        raise ValueError("six-slot identity mismatch")
    return slots


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def verify_public_projection(case: dict) -> dict:
    """Match PMA's recorded GA projection to actual public provider history."""
    source = HERE / case["event_file"]
    public = HERE / case["public_event_file"]
    if sha256(source) != case["event_file_sha256"] or sha256(public) != case["public_event_file_sha256"]:
        raise ValueError("frozen public input hash mismatch")
    records = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines()]
    records = [row for row in records if row["event"]["sequence"] <= case["inclusive_event_sequence"]]
    episode = [row["event"] for row in records]
    old_reminders = {row["event"]["actor_attempt"]: row["result"].get("reminder")
                     for row in records if row["event"]["kind"] == "before_actor_call"}
    ready = [row for line in public.read_text(encoding="utf-8").splitlines()
             if (row := json.loads(line))["event_type"] == "provider_request_ready"]
    steps = [e for e in episode if e["kind"] == "actor_step"]
    if len(ready) != len(steps) + 1 or not episode or episode[0]["kind"] != "task_start":
        raise ValueError("public request/episode count mismatch")
    first = ready[0]["payload"]["content"]["messages"][0]["content"][0]["text"]
    if episode[0]["initial_user_content"] != first:
        raise ValueError("public initial Task input differs from PMA projection")
    mapping = [{"sequence": 1, "field": "initial_user_content", "request_event_id": ready[0]["event_id"],
                "sha256": hashlib.sha256(first.encode()).hexdigest()}]
    for index, step in enumerate(steps):
        prior, following = ready[index:index + 2]
        if step.get("request_event_id") != prior["event_id"]:
            raise ValueError(f"actor step {step['sequence']} request identity mismatch")
        messages = following["payload"]["content"]["messages"]
        assistant, user = messages[-2:]
        if assistant["role"] != "assistant" or user["role"] != "user":
            raise ValueError("latest public interaction roles differ")
        response = "\n".join(block["text"] for block in assistant["content"] if block["type"] == "text")
        if step["response"] != response:
            raise ValueError(f"actor step {step['sequence']} response differs")
        commands = [json.loads(item) for item in step["commands"]]
        uses = [block for block in assistant["content"] if block["type"] == "tool_use"]
        if len(commands) != len(uses):
            raise ValueError(f"actor step {step['sequence']} tool count differs")
        for command, use in zip(commands, uses, strict=True):
            args = {k: v for k, v in command["args"].items() if k not in {"_index", "_tool_num"}}
            if (command["id"], command["tool_name"], args) != (use["id"], use["name"], use["input"]):
                raise ValueError(f"actor step {step['sequence']} tool command differs")
        observation = json.loads(step["observation"])
        results = [block for block in user["content"] if block["type"] == "tool_result"]
        text = "".join(block["text"] for block in user["content"] if block["type"] == "text")
        appended = old_reminders.get(step["actor_attempt"] + 1)
        expected_text = observation["content"] + ("\n\n" + appended if appended else "")
        if observation["tool_results"] != [
                {"tool_use_id": result["tool_use_id"], "content": result["content"]}
                for result in results] or expected_text != text:
            raise ValueError(f"actor step {step['sequence']} tool result/observation differs")
        if bool(appended) != bool(following["payload"].get("pma_reminder_event_id")):
            raise ValueError("historical PMA append identity differs")
        mapping.append({"sequence": step["sequence"], "actor_attempt": step["actor_attempt"],
                        "request_event_id": prior["event_id"], "following_request_event_id": following["event_id"],
                        "response_sha256": hashlib.sha256(response.encode()).hexdigest(),
                        "commands": len(commands), "tool_results": len(results),
                        "historical_reminder_suffix": bool(appended),
                        "observation_sha256": hashlib.sha256(step["observation"].encode()).hexdigest()})
    return {"task": case["task"], "source_sha256": sha256(source),
            "public_sha256": sha256(public), "mapping": mapping, "unexplained_differences": []}


def projected_events(case: dict, run_id: str) -> list[dict]:
    source = HERE / case["event_file"]
    if sha256(source) != case["event_file_sha256"]:
        raise ValueError("fixed public event archive identity mismatch")
    public = HERE / case["public_event_file"]
    if sha256(public) != case["public_event_file_sha256"]:
        raise ValueError("fixed public Task event identity mismatch")
    events = []
    for raw_line in source.read_bytes().splitlines(keepends=True):
        original = json.loads(raw_line)["event"]
        if original["sequence"] > case["inclusive_event_sequence"]:
            break
        kind = original["kind"]
        if kind not in FIELDS:
            raise ValueError("unexpected event before frozen cutoff")
        event = {key: original[key] for key in FIELDS[kind] if key in original}
        event.update(kind=kind, task_id=case["task"], run_id=run_id,
                     event_id=f"shadow-{original['sequence']}-{original['event_id']}",
                     sequence=original["sequence"],
                     source_record_sha256=hashlib.sha256(raw_line).hexdigest())
        events.append(event)
    if not events or events[-1]["sequence"] != case["inclusive_event_sequence"]:
        raise ValueError("cutoff sequence missing")
    if [e["sequence"] for e in events] != list(range(1, len(events) + 1)):
        raise ValueError("event sequence not contiguous")
    return events


class FakePublicTransport:
    """Responses use only actual prompt/tool schema; unexpected sends fail closed."""

    def __init__(self, path: Path, *, expected: int):
        self.path = path
        self.expected = expected
        self.calls = 0
        self.saved_once = False

    async def __call__(self, *, prompt, system, tools=None):
        self.calls += 1
        if self.calls > self.expected:
            raise AssertionError("unscripted request; no real transport fallback")
        response = LLMResponse(content="<no_intervention/>")
        if tools is not None:
            response = LLMResponse(content="", tool_calls=[])
            names = {item["function"]["name"] for item in tools}
            if "memory_save_knowledge" in names and not self.saved_once:
                match = re.search(r"## Visible public source handles \(quote exact text above\)\n(\[.*\])", prompt)
                description = re.search(
                    r"\[Task Description\]\n(.+?)(?:\n\n\[Recent Trajectory|\n\n## Your Task)",
                    prompt, re.S)
                numbered = re.search(r"## Numbered visible public source leaves\n(\[.*\])\n## Previous", prompt)
                if numbered:
                    leaves = json.loads(numbered.group(1))
                    task_source = next((leaf for leaf in leaves if leaf["role"] == "task_instruction"), None)
                    if task_source and task_source["numbered_lines"]:
                        function = SimpleNamespace(name="memory_save_knowledge", arguments={
                            "content": "Review the original public task scope",
                            "statement_type": "task_requirement",
                            "source_refs": [{"source_handle": task_source["source_handle"],
                                             "start_line": 1, "end_line": 1}]})
                        response = LLMResponse(content="", tool_calls=[SimpleNamespace(function=function)])
                        self.saved_once = True
                elif match and description:
                    handles = json.loads(match.group(1))
                    task_source = next((h for h in handles if h["role"] == "task_instruction"), None)
                    quote = description.group(1)[:24]
                    if task_source and quote and description.group(1).count(quote) == 1:
                        function = SimpleNamespace(name="memory_save_knowledge", arguments={
                            "content": "Review the original public task scope",
                            "statement_type": "task_requirement",
                            "source_refs": [{"event_id": task_source["event_id"],
                                             "role": "task_instruction", "quote": quote}]})
                        response = LLMResponse(content="", tool_calls=[SimpleNamespace(function=function)])
                        self.saved_once = True
        elif self.saved_once:
            match = re.search(r"\[([A-Za-z0-9_-]+) v(\d+)\]", prompt)
            if match:
                response = LLMResponse(content=(
                    "<context_for_action>Consider the original public task scope.</context_for_action>"
                    f'<memory_refs>[{{"id":"{match.group(1)}","version":{match.group(2)}}}]</memory_refs>'))
        row = {"logical_call": self.calls, "system": system, "prompt": prompt,
               "tools": tools, "response_content": response.content,
               "response_tool_calls": [vars(call.function) for call in (response.tool_calls or [])]}
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        return response


async def run_fake(manifest: dict, output: Path) -> list[dict]:
    output.mkdir(parents=True, exist_ok=False)
    results = []
    cases = {case["task"]: case for case in manifest["cases"]}
    for task, variant in ordered_slots(manifest):
            case = cases[task]
            mapping = verify_public_projection(case)
            run_id = f"shadow-{case['task']}-{variant.lower()}"
            slot = output / run_id
            slot.mkdir()
            (slot / "public_mapping.json").write_text(json.dumps(mapping, indent=2), encoding="utf-8")
            events = projected_events(case, run_id)
            expected = (case["estimated_phase1_calls_per_condition"]
                        + case["estimated_phase2_calls_per_condition"])
            agent = construct_upstream(slot / "upstream", research_candidate=variant)
            fake = FakePublicTransport(slot / "requests.jsonl", expected=expected)
            agent._memory_llm.call = fake
            episode = PMAEpisode(agent, run_id=run_id, task_id=case["task"],
                                 archive=slot / "episode")
            for event in events:
                await episode.handle(event)
                fatal = getattr(agent._memory_agent, "_fatal_error", None)
                if fatal is not None:
                    raise RuntimeError("candidate host integrity failure") from fatal
            if fake.calls != expected:
                raise AssertionError(f"logical call count {fake.calls} != {expected}")
            agent.save_memory(str(slot / "memory.json"))
            row = {"run_id": run_id, "task": case["task"], "variant": variant,
                   "events": len(events), "logical_phase_calls": fake.calls,
                   "provider_attempts": 0, "task_calls": 0, "native_evaluator_calls": 0,
                   "task_completed": False, "input_sent": False,
                   "event_sha256": case["event_file_sha256"],
                   "request_sha256": sha256(fake.path)}
            (slot / "result.json").write_text(json.dumps(row, indent=2), encoding="utf-8")
            results.append(row)
    (output / "summary.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=("fake", "live"), default="fake")
    parser.add_argument("--authorization", type=Path)
    parser.add_argument("--profile", type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if args.mode == "live":
        if args.authorization is None or args.profile is None:
            raise PermissionError("real static provider dispatch requires a later authorization and entry; private profile absent")
        from static_source_live import run_authorized
        rows = asyncio.run(run_authorized(args.manifest, args.authorization, args.profile,
                                          args.output))
        print(json.dumps({"slots_finished": len(rows), "results": [r["status"] for r in rows]}))
        return 0 if len(rows) == 6 and all(r["status"] == "static_prefix_complete" for r in rows) else 1
    if manifest.get("execution_authorized") is not False:
        raise ValueError("fake static draft must remain unauthorized")
    rows = asyncio.run(run_fake(manifest, args.output))
    print(json.dumps({"slots": len(rows), "logical_phase_calls": sum(r["logical_phase_calls"] for r in rows),
                      "real_provider_attempts": 0}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
