import time
import json
from pathlib import Path
from types import SimpleNamespace

from async_monitor_runtime import AsyncMonitorRuntime


def blocking_worker(_kwargs, requests, responses, wake_event):
    wake_event.wait()
    responses.put({"kind": "started", "request_id": "blocked-observation"})
    while True:
        time.sleep(10)


def intervention_worker(kwargs, requests, responses, wake_event):
    wake_event.wait()
    path = Path(kwargs["_runtime_boundary_archive"])
    row = json.loads(path.read_text(encoding="utf-8").splitlines()[-1])
    request_id = "autonomous-observation"
    responses.put({"kind": "started", "request_id": request_id})
    responses.put({
            "kind": "boundary_result", "request_id": request_id,
            "internal_turn": row["internal_turn"],
            "message": "Re-read the failing test oracle before editing production code.",
        })


def completion_worker(_kwargs, requests, responses, wake_event):
    item = requests.get()
    responses.put({"kind": "started", "request_id": item["request_id"]})
    responses.put({
        "kind": "completion_result", "request_id": item["request_id"],
        "decision": {
            "decision": "CONTINUE", "reason_codes": ["ROOT_UNSUPPORTED"],
            "next_prompt": "Recheck the remaining root obligation.",
            "target_obligation_ids": [], "checker_ids": [],
        },
    })


def wait_until(predicate, timeout=4.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.03)
    raise AssertionError("condition did not become true")


def test_blocked_monitor_never_blocks_task_publisher_and_is_restarted(tmp_path):
    runtime = AsyncMonitorRuntime(
        {"artifact_dir": str(tmp_path)}, request_timeout=1.0, worker_target=blocking_worker,
    )
    try:
        started = time.monotonic()
        assert runtime.archive_boundary({"boundary": "post_tool_pre_next_llm", "internal_turn": 1})
        assert time.monotonic() - started < 0.25

        # Simulate an independently progressing task loop. Polling the monitor
        # must remain bounded even while its child is permanently blocked.
        task_turns = 0
        initial_generation = runtime.generation
        deadline = time.monotonic() + 2.5
        while runtime.generation == initial_generation and time.monotonic() < deadline:
            task_turns += 1
            assert runtime.consume_interventions() == []
            time.sleep(0.05)
        assert task_turns >= 5
        assert runtime.generation == initial_generation + 1
        assert runtime.process.is_alive()
    finally:
        runtime.close()


def test_real_intervention_is_delivered_but_silence_never_blocks(tmp_path):
    runtime = AsyncMonitorRuntime({"artifact_dir": str(tmp_path)}, worker_target=intervention_worker)
    try:
        assert runtime.archive_boundary({"boundary": "post_tool_pre_next_llm", "internal_turn": 7})
        ready = wait_until(lambda: runtime.consume_interventions())
        assert len(ready) == 1
        assert ready[0]["internal_turn"] == 7
        assert "test oracle" in ready[0]["message"]
        assert runtime.consume_interventions() == []
    finally:
        runtime.close()


def proposal():
    return SimpleNamespace(as_payload=lambda: {
        "proposal_id": "p1", "origin": "no_tool", "turn": 9,
        "response_sha256": "abc", "response_preview": "done", "stop_reason": "end_turn",
    })


def test_root_completion_control_returns_a_normal_monitor_decision(tmp_path):
    runtime = AsyncMonitorRuntime({"artifact_dir": str(tmp_path)}, worker_target=completion_worker)
    try:
        result = runtime.review_completion(proposal(), 9, response_content="done")
        assert result.decision == "CONTINUE"
        assert result.next_prompt.startswith("Recheck")
    finally:
        runtime.close()


def test_blocked_root_completion_is_bounded_and_fails_open(tmp_path):
    runtime = AsyncMonitorRuntime(
        {"artifact_dir": str(tmp_path)}, request_timeout=1.0, worker_target=blocking_worker,
    )
    try:
        started = time.monotonic()
        result = runtime.review_completion(proposal(), 9, response_content="done")
        elapsed = time.monotonic() - started
        assert result.decision == "ERROR_FAIL_OPEN"
        assert "MONITOR_TIMEOUT" in result.reason_codes
        assert 0.8 < elapsed < 3.0
    finally:
        runtime.close()
