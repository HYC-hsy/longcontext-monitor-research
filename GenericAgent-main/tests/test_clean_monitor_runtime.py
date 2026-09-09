import json
import queue
import threading
import time

import pytest

from monitor_agent_core.runtime import MonitorRuntime, _coalesce_wake_command
from monitor_agent_core.runtime import CompletionOutcome
from ga_monitor_adapter import GenericAgentMonitorAdapter


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
                "request_id": command["request_id"],
            })


def _runtime(tmp_path, callback):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return MonitorRuntime(
        public_task="Keep the literal wildcard.",
        task_workspace=str(workspace),
        artifact_dir=str(tmp_path / "artifacts"),
        config_name="unused-in-fixture",
        model_config={},
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
    feedback = (runtime.private_root / 'delivery_feedback.jsonl').read_text(encoding='utf-8')
    assert 'handed_to_task_interrupt_interface' in feedback


def test_failed_interrupt_is_recorded_and_pump_survives(tmp_path):
    def fail(_):
        raise RuntimeError('fixture delivery failure')
    runtime = _runtime(tmp_path, fail)
    try:
        runtime.archive_boundary({'internal_turn': 1, 'response_content': 'test'})
        path = runtime.private_root / 'delivery_feedback.jsonl'
        deadline = time.monotonic() + 3
        while not path.exists() and time.monotonic() < deadline:
            time.sleep(.02)
        assert '"delivery": "failed"' in path.read_text(encoding='utf-8')
        assert runtime._pump.is_alive()
        assert runtime.request_completion({'internal_turn': 2}).allow
    finally:
        runtime.close()


def test_root_completion_uses_distinct_control_boundary(tmp_path):
    runtime = _runtime(tmp_path, lambda _: None)
    decision = runtime.request_completion({
        "boundary": "root_completion_proposal", "internal_turn": 9,
        "response_content": "Implemented the index and all tests pass.",
        "completion_proposal": {"proposal_id": "proposal-1"},
        "tool_calls": [], "tool_results": [],
    })
    runtime.close()

    assert decision.allow is True
    assert decision.reason == "monitor_allowed"
    raw = json.loads(runtime.events_path.read_text(encoding="utf-8").splitlines()[-1])
    assert raw["boundary"] == "root_completion_proposal"
    assert raw["response_content"] == "Implemented the index and all tests pass."
    assert raw["completion_proposal"]["proposal_id"] == "proposal-1"


def test_artifacts_cannot_be_nested_in_supervised_workspace(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    with pytest.raises(ValueError, match="outside"):
        MonitorRuntime(
            public_task="task", task_workspace=str(workspace),
            artifact_dir=str(workspace / "monitor"), config_name="unused",
            model_config={},
            interrupt_callback=lambda _: None,
            worker_target=scripted_clean_monitor_worker,
        )


def test_ga_adapter_is_only_completion_type_conversion_boundary():
    adapter = object.__new__(GenericAgentMonitorAdapter)
    adapter.runtime = type("Runtime", (), {
        "request_completion": lambda self, event: CompletionOutcome(
            False, "Inspect the missing test.", "monitor_correction"
        )
    })()
    decision = adapter.review_completion(None, 3)
    assert decision.decision == "CONTINUE"
    assert decision.next_prompt == "Inspect the missing test."


def test_ga_adapter_does_not_turn_incomplete_review_into_more_work():
    adapter = object.__new__(GenericAgentMonitorAdapter)
    adapter.runtime = type("Runtime", (), {
        "request_completion": lambda self, event: CompletionOutcome(
            False, "Completion review unfinished", "run_budget_exhausted", incomplete=True
        )
    })()
    decision = adapter.review_completion(None, 3)
    assert decision.decision == "ERROR_FAIL_CLOSED"
    assert "MONITOR_REVIEW_INCOMPLETE" in decision.reason_codes


def test_ga_adapter_passes_launcher_deadline(monkeypatch):
    captured = {}
    monkeypatch.setenv('GA_MONITOR_RUN_DEADLINE_EPOCH', '2000000000')
    monkeypatch.setattr('ga_monitor_adapter.MonitorRuntime', lambda **kw: captured.update(kw))
    GenericAgentMonitorAdapter()
    assert captured['run_deadline_epoch'] == 2000000000


def test_patrol_wake_backlog_coalesces_to_latest_cursor():
    commands = queue.Queue()
    commands.put({"kind": "boundary", "cursor": 8, "task_turn": 4})
    commands.put({"kind": "boundary", "cursor": 112, "task_turn": 55})

    selected = _coalesce_wake_command(
        commands, {"kind": "boundary", "cursor": 7, "task_turn": 4}
    )

    assert selected == {"kind": "boundary", "cursor": 112, "task_turn": 55}


def test_completion_preempts_stale_patrol_backlog():
    commands = queue.Queue()
    commands.put({"kind": "boundary", "cursor": 112, "task_turn": 55})
    commands.put({"kind": "completion", "cursor": 113})
    commands.put({"kind": "boundary", "cursor": 114, "task_turn": 56})

    selected = _coalesce_wake_command(
        commands, {"kind": "boundary", "cursor": 7, "task_turn": 4}
    )

    assert selected == {"kind": "completion", "cursor": 113}
