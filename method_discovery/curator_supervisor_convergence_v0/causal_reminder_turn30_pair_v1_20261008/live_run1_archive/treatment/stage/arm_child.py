"""Authorized arm process inside the frozen, networkless Fyne task image.

Importing this file is inert. The live entry requires a parent-issued permit
and is never invoked by the zero-model certification tests.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import socket
import subprocess
import time

from continuation_adapter import (FirstSendGuard, TASK_IMAGE, canonical_sha,
    digest, restore_production_objects, validate_child_checkpoint)


STAGE = Path("/opt/causal-stage")
SOURCE = Path("/opt/genericagent")
WORKSPACE = Path("/app")
RAW = Path("/logs/agent")
PYTHON = Path("/opt/m4-runtime/python/cpython-3.12.12-linux-x86_64-gnu/bin/python3.12")


def load_stage(stage: Path = STAGE) -> tuple[dict, dict, str, dict]:
    permit_file = stage / "launch_permit.json"
    if not permit_file.is_file():
        raise RuntimeError("Arm launch permit absent; no provider send allowed")
    permit = json.loads(permit_file.read_text(encoding="utf-8"))
    state = json.loads((stage / "runtime_checkpoint.json").read_text(encoding="utf-8"))
    expected = json.loads((stage / "expected_request.json").read_text(encoding="utf-8"))
    task = (stage / "original_task.txt").read_text(encoding="utf-8")
    if (permit != {"authorized_child": True,
                   "expected_request_sha256": canonical_sha(expected),
                   "runtime_state_file_sha256": digest((stage / "runtime_checkpoint.json").read_bytes()),
                   "original_task_sha256": digest(task.encode("utf-8")),
                   "task_image": TASK_IMAGE,
                   "turn_offset": 30,
                   "max_additional_turns": 270}):
        raise RuntimeError("Arm launch permit/input identity mismatch")
    return state, expected, task, permit


def start_local_transport(source: Path = SOURCE, python: Path = PYTHON):
    if not Path("/run/model-channel/gateway.sock").is_socket():
        raise RuntimeError("Frozen Unix inference gateway socket absent")
    if not python.is_file() or not (source / "isolated_transport.py").is_file():
        raise RuntimeError("Frozen local inference runtime absent")
    process = subprocess.Popen([str(python), str(source / "isolated_transport.py"), "local"],
        stdin=subprocess.DEVNULL, stdout=(RAW / "isolated_transport.log").open("ab"),
        stderr=subprocess.STDOUT)
    for _ in range(100):
        if process.poll() is not None:
            raise RuntimeError("Local inference transport exited before readiness")
        try:
            with socket.create_connection(("127.0.0.1", 18765), timeout=0.2):
                return process
        except OSError:
            time.sleep(0.1)
    process.terminate()
    raise RuntimeError("Local inference transport not ready")


def drive_production_loop(*, stage: Path = STAGE, source: Path = SOURCE,
                          workspace: Path = WORKSPACE, raw: Path = RAW,
                          start_transport=True) -> dict:
    state, expected, original_task, _ = load_stage(stage)
    identity = validate_child_checkpoint(workspace, state, source, expected)
    raw.mkdir(parents=True, exist_ok=True)
    events = raw / "task_raw_events.jsonl"
    if events.exists():
        raise RuntimeError("Raw event destination already exists")
    def capture(kind, payload):
        with events.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps({"kind": kind, "payload": copy.deepcopy(payload)},
                                    ensure_ascii=False, default=str) + "\n")
    task_dir = Path("/run/causal-task-control")
    task_dir.mkdir(parents=True, exist_ok=False)
    agent_loop, _, llmcore, backend, client, handler, wrapper, system_prompt = (
        restore_production_objects(source, state, cwd=workspace, task_dir=task_dir,
                                   original_task=original_task, capture=capture))
    original_transport = llmcore._stream_with_retry
    guard = FirstSendGuard(expected, original_transport, capture)
    llmcore._stream_with_retry = guard
    from research_runtime import JsonlEventSink, wrap_generator
    transport = None
    current_turn = 30
    outcome = None
    try:
        if start_transport:
            transport = start_local_transport(source)
        generator = agent_loop.agent_runner_loop(
            wrapper, system_prompt, original_task, handler, state["tools"],
            max_turns=270, verbose=False, yield_info=True, turn_offset=30)
        generator = wrap_generator(generator, {
            "experiment_id": "turn30-minimal-reminder-causal-pair",
            "condition_id": "task-continuation",
            "task_id": "fyn-2.2.0-roadmap",
            "branch_id": "checkpoint-turn30",
        }, JsonlEventSink(raw / "research_events.jsonl"))
        with (raw / "output.txt").open("w", encoding="utf-8", newline="\n") as output:
            while True:
                try:
                    item = next(generator)
                except StopIteration as finished:
                    outcome = finished.value
                    break
                if isinstance(item, dict) and "turn" in item:
                    current_turn = int(item["turn"])
                    capture("task_turn", item)
                elif isinstance(item, str):
                    output.write(item)
        if guard.mismatch or guard.sends < 1 or wrapper.bootstrap_calls != 1:
            raise RuntimeError("First provider send/production bootstrap did not complete")
        if outcome.get("result") == "PROVIDER_FAILURE":
            reason = "infrastructure_failure"
        elif outcome.get("result") == "MAX_TURNS_EXCEEDED":
            reason = "task_turn_300" if current_turn == 300 else "infrastructure_failure"
        elif outcome.get("result") == "CURRENT_TASK_DONE":
            reason = "normal_completion"
        else:
            reason = "runner_termination"
        result = {"terminal_reason": reason, "termination_turn": current_turn,
                  "accepted_task_responses": wrapper.accepted_responses,
                  "production_loop": "agent_loop.agent_runner_loop", "turn_offset": 30,
                  "max_additional_turns": 270, "first_provider_request_sha256": guard.first_canonical_sha,
                  "provider_sends": guard.sends, "outcome": outcome, "checkpoint_identity": identity,
                  "final_backend_history": backend.history,
                  "final_history_info": handler.history_info, "final_working": handler.working}
        (raw / "arm_result.json").write_text(json.dumps(result, ensure_ascii=False,
                                                indent=2, default=str) + "\n", encoding="utf-8")
        return result
    finally:
        llmcore._stream_with_retry = original_transport
        if transport is not None:
            transport.terminate()
            try:
                transport.wait(timeout=5)
            except subprocess.TimeoutExpired:
                transport.kill()


def validate_bootstrap_before_network(*, stage: Path = STAGE, source: Path = SOURCE,
                                      workspace: Path = WORKSPACE) -> dict:
    """Use deployed request construction and deliberately abort before socket send."""
    state, expected, original_task, _ = load_stage(stage)
    identity = validate_child_checkpoint(workspace, state, source, expected)
    observations = []
    def capture(kind, payload):
        observations.append((kind, copy.deepcopy(payload)))
    agent_loop, ga, llmcore, backend, client, handler, wrapper, system_prompt = (
        restore_production_objects(source, state, cwd=workspace,
            task_dir=Path("/run/causal-task-control"), original_task=original_task,
            capture=capture))
    class StopBeforeNetwork(Exception):
        pass
    def stop_before_network(_session, _url, _headers, _payload, _parse_fn):
        raise StopBeforeNetwork
        yield  # preserve the production generator contract
    original = llmcore._stream_with_retry
    guard = FirstSendGuard(expected, stop_before_network, capture)
    llmcore._stream_with_retry = guard
    try:
        from research_runtime import wrap_generator
        generator = wrapper.chat([{"role": "system", "content": system_prompt},
                                  {"role": "user", "content": original_task}],
                                 tools=state["tools"])
        generator = wrap_generator(generator, {
            "experiment_id": "turn30-minimal-reminder-causal-pair",
            "condition_id": "task-continuation",
            "task_id": "fyn-2.2.0-roadmap",
            "branch_id": "checkpoint-turn30",
        }, lambda _event: None)
        try:
            next(generator)
        except StopBeforeNetwork:
            pass
        else:
            raise RuntimeError("Production bootstrap did not cut before network")
    finally:
        llmcore._stream_with_retry = original
    if (guard.mismatch or guard.sends != 1 or wrapper.bootstrap_calls != 1
            or wrapper.pass_through_calls != 0
            or guard.first_canonical_sha != canonical_sha(expected)):
        raise RuntimeError("Production bootstrap request differs from frozen payload")
    return {"status": "zero_model_before_network", "request_sha256": guard.first_canonical_sha,
            "network_send_count": 0, "task_agent_loop_run_count": 0,
            "production_handler": ga.GenericAgentHandler.__module__ + ".GenericAgentHandler",
            "production_loop": agent_loop.agent_runner_loop.__module__ + ".agent_runner_loop",
            "compression_counter_after_build": llmcore.compress_history_tags._cd,
            "checkpoint_identity": identity}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorized-child", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if args.validate_only:
        os.environ["GA_LANG"] = "en"
        print(json.dumps(validate_bootstrap_before_network(), ensure_ascii=False))
        return
    if not args.authorized_child:
        raise RuntimeError("Arm child is not authorized")
    os.environ["GA_LANG"] = "en"
    os.environ["GA_PMA_ENABLED"] = "0"
    drive_production_loop()


if __name__ == "__main__":
    main()
