import json
import threading
import time

import pytest

from clean_monitor_runtime import CleanMonitorRuntime


def scripted_clean_monitor_worker(config, commands, outputs):
    outputs.put({"kind": "ready"})
    while True:
        command = commands.get()
        if command["kind"] == "close":
            return
        if command["kind"] == "boundary":
            outputs.put({
                "kind": "intervention", "message": "Preserve the literal wildcard.",
                "cursor": command["cursor"], "request_id": "test-request",
            })
        elif command["kind"] == "completion":
            outputs.put({
                "kind": "completion", "decision": "allow", "cursor": command["cursor"],
            })


def _runtime(tmp_path, callback):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return CleanMonitorRuntime(
        public_task="Keep the literal wildcard.",
        task_workspace=str(workspace),
        artifact_dir=str(tmp_path / "artifacts"),
        config_name="unused-in-fixture",
        interrupt_callback=callback,
        worker_target=scripted_clean_monitor_worker,
    )


def test_boundary_creates_two_layer_archive_and_delivers_immediate_correction(tmp_path):
    delivered = []
    event = threading.Event()

    def callback(message):
        delivered.append(message)
        event.set()

    runtime = _runtime(tmp_path, callback)
    started = time.monotonic()
    runtime.archive_boundary({
        "boundary": "post_model_pre_tool", "internal_turn": 4,
        "response_content": "<summary>Replace wildcard with request origin</summary>",
        "tool_calls": [{"tool_name": "file_patch", "args": {"path": "cors.py"}}],
        "tool_results": [],
    })
    assert time.monotonic() - started < 0.2
    assert event.wait(2)
    runtime.close()

    synopsis = json.loads(runtime.synopsis_path.read_text(encoding="utf-8").splitlines()[0])
    raw = json.loads(runtime.events_path.read_text(encoding="utf-8").splitlines()[0])
    assert synopsis == {
        "cursor": 1, "task_turn": 4, "boundary": "post_model_pre_tool",
        "intent": "Replace wildcard with request origin",
        "tool_names": ["file_patch"], "outcome_available": False,
        "raw_event": "public_events.jsonl#1",
    }
    assert raw["tool_calls"][0]["args"]["path"] == "cors.py"
    assert delivered == ["Preserve the literal wildcard."]
    assert runtime.consume_interventions() == []


def test_root_completion_uses_distinct_control_boundary(tmp_path):
    runtime = _runtime(tmp_path, lambda _: None)
    decision = runtime.review_completion(None, turn=9)
    runtime.close()

    assert decision.decision == "ALLOW_COMPLETE"
    assert decision.reason_codes == ("MONITOR_ALLOWED",)


def test_artifacts_cannot_be_nested_in_supervised_workspace(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    with pytest.raises(ValueError, match="outside"):
        CleanMonitorRuntime(
            public_task="task", task_workspace=str(workspace),
            artifact_dir=str(workspace / "monitor"), config_name="unused",
            interrupt_callback=lambda _: None,
            worker_target=scripted_clean_monitor_worker,
        )
