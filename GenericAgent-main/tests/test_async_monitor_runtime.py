import time
import json
import queue
import pytest
from pathlib import Path
from types import SimpleNamespace

from async_monitor_runtime import (
    AsyncMonitorRuntime, _IncrementalArchiveReader, _adaptive_review_reason, _load_review_cursor,
    _max_archive_sequence, _read_archive, _reconciled_review_cursor, _resume_archive,
    _review_with_one_freshness_pass, _save_review_cursor,
)
import m0_deliberative_monitor as m0


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


def failing_completion_worker(_kwargs, requests, responses, wake_event):
    item = requests.get()
    responses.put({"kind": "started", "request_id": item["request_id"]})
    responses.put({
        "kind": "error", "request_id": item["request_id"],
        "error_type": "RuntimeError", "error": "monitor audit failed",
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
        max_poll_latency = 0.0
        initial_generation = runtime.generation
        deadline = time.monotonic() + 2.5
        while runtime.generation == initial_generation and time.monotonic() < deadline:
            task_turns += 1
            poll_started = time.monotonic()
            assert runtime.consume_interventions() == []
            max_poll_latency = max(max_poll_latency, time.monotonic() - poll_started)
            time.sleep(0.05)
        assert task_turns >= 5
        assert max_poll_latency < 0.25
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


def test_archive_runtime_identity_cannot_be_overridden_by_packet(tmp_path):
    runtime = AsyncMonitorRuntime(
        {"artifact_dir": str(tmp_path)}, worker_target=blocking_worker,
    )
    try:
        runtime.archive_boundary({
            "boundary": "post_tool_pre_next_llm", "internal_turn": 1,
            "archive_sequence": 999, "archive_event_id": "caller-supplied",
        })
        row = _read_archive(runtime.boundary_archive)[-1]
        assert row["archive_sequence"] == 1
        assert row["archive_event_id"] != "caller-supplied"
    finally:
        runtime.close()


def test_newer_revision_supersedes_undelivered_intervention_from_same_episode():
    from collections import deque
    runtime = object.__new__(AsyncMonitorRuntime)
    runtime.interventions = deque()
    assert runtime._enqueue_intervention({
        "request_id": "r1", "message": "old", "episode_id": "episode-a",
        "episode_revision": 1,
    })
    assert runtime._enqueue_intervention({
        "request_id": "r2", "message": "refined", "episode_id": "episode-a",
        "episode_revision": 2,
    })
    assert [(item["request_id"], item["message"])
            for item in runtime.interventions] == [("r2", "refined")]


def test_distinct_repair_episodes_remain_independently_deliverable():
    from collections import deque
    runtime = object.__new__(AsyncMonitorRuntime)
    runtime.interventions = deque()
    runtime._enqueue_intervention({
        "request_id": "r1", "message": "repair A", "episode_id": "episode-a",
        "episode_revision": 1,
    })
    runtime._enqueue_intervention({
        "request_id": "r2", "message": "repair B", "episode_id": "episode-b",
        "episode_revision": 1,
    })
    assert [item["request_id"] for item in runtime.interventions] == ["r1", "r2"]


def test_late_old_revision_cannot_replace_newer_ready_intervention():
    from collections import deque
    runtime = object.__new__(AsyncMonitorRuntime)
    runtime.interventions = deque([{
        "request_id": "r2", "message": "new", "episode_id": "episode-a",
        "episode_revision": 2,
    }, {
        "request_id": "other", "message": "other", "episode_id": "episode-b",
        "episode_revision": 1,
    }])
    assert not runtime._enqueue_intervention({
        "request_id": "r1", "message": "old", "episode_id": "episode-a",
        "episode_revision": 1,
    })
    assert [item["request_id"] for item in runtime.interventions] == ["r2", "other"]


def test_same_episode_cannot_redeliver_before_task_agent_has_a_later_turn():
    from collections import deque
    runtime = object.__new__(AsyncMonitorRuntime)
    runtime.interventions = deque()
    runtime.delivered_episode_turns = {"episode-a": 17}
    runtime.delivered_episode_sequences = {"episode-a": 40}

    assert not runtime._enqueue_intervention({
        "request_id": "same-turn-rewording", "message": "new wording",
        "episode_id": "episode-a", "episode_revision": 4, "internal_turn": 17,
        "reviewed_through_sequence": 40,
    })
    assert runtime._enqueue_intervention({
        "request_id": "after-uptake-window", "message": "new observed residual",
        "episode_id": "episode-a", "episode_revision": 5, "internal_turn": 18,
    })
    assert [item["request_id"] for item in runtime.interventions] == [
        "after-uptake-window"
    ]


def test_same_turn_tool_evidence_is_not_coalesced_with_pre_tool_correction():
    from collections import deque
    runtime = object.__new__(AsyncMonitorRuntime)
    runtime.interventions = deque()
    runtime.delivered_episode_turns = {"episode-a": 17}
    runtime.delivered_episode_sequences = {"episode-a": 40}

    assert runtime._enqueue_intervention({
        "request_id": "post-tool-evidence", "message": "The tool result adds a conflict.",
        "episode_id": "episode-a", "episode_revision": 5, "internal_turn": 17,
        "reviewed_through_sequence": 41,
    })
    assert [item["request_id"] for item in runtime.interventions] == [
        "post-tool-evidence"
    ]


def test_new_uptake_reaches_same_monitor_before_old_intervention_is_published(tmp_path):
    archive = tmp_path / "async_public_boundaries.jsonl"
    archive.write_text(json.dumps(boundary(1)) + "\n", encoding="utf-8")

    class Monitor:
        attention_mode = "focused"
        observation_plan = {"review_after_turns": 1}

        def __init__(self):
            self.packets = []
            self.observed = []

        def review(self, packet):
            self.packets.append(packet)
            if len(self.packets) == 1:
                with archive.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps({
                        **boundary(2),
                        "response_content": "I accepted the correction and started repair.",
                    }) + "\n")
                return "Repeat the old correction."
            return ""

        def observe_archived_boundaries(self, rows):
            self.observed.extend(rows)

        def baseline_observation(self, count):
            return {"observed_boundaries": count}

    monitor = Monitor()
    message, cursor, reviewed_turn, rechecked = _review_with_one_freshness_pass(
        monitor, archive, {
            "archive_wake_only": True, "internal_turn": 1,
            "boundary": "autonomous_archive_observation",
        }, 2,
    )

    assert message == ""
    assert cursor == 4
    assert reviewed_turn == 2
    assert rechecked is True
    assert len(monitor.packets) == 2
    assert monitor.packets[1]["archive_delta"]["review_trigger"] == (
        "prepublish_intervention_freshness"
    )
    assert monitor.observed[-1]["response_content"].startswith("I accepted")


def test_h4_f1_f2_f3_compose_in_one_persistent_monitor_review(
        monkeypatch, tmp_path):
    archive = tmp_path / "async_public_boundaries.jsonl"
    initial = [
        {
            **boundary(index), "archive_event_id": f"old-{index}",
            "archive_sequence": index,
            "response_content": f"OLD_WIDE_PAYLOAD_{index}_" + ("X" * 7000),
        }
        for index in range(1, 5)
    ] + [{
        **boundary(5), "archive_event_id": "conflict", "archive_sequence": 5,
        "response_content": "I will close B using the self-authored green test.",
    }]
    archive.write_text(
        "".join(json.dumps(row) + "\n" for row in initial), encoding="utf-8"
    )

    def final(intervention="", attention="patrol"):
        return {
            "intervention_message": intervention,
            "attention": {"mode": attention, "reason": "fixture judgment"},
            "termination_decision": "continue_task" if intervention else "allow_complete",
            "epistemic_status": "confirmed_conflict" if intervention else "watch",
            "intervention_mode": "repair" if intervention else "none",
            "imminent_action_anchor": "", "reason": "public evidence reviewed",
            "public_anchors": ["turn 2 B claim"],
            "discrepancy": "B closure is unsupported" if intervention else "",
            "exit_condition": "observe a discriminating B probe" if intervention else "",
            "authority_basis": "correctness_evidence" if intervention else "none",
            "material_task_impact": "B may close incorrectly" if intervention else "",
            "why_silence_is_insufficient": "The next inference may close B" if intervention else "",
            "evidence_availability": "obtainable_now" if intervention else "not_applicable",
            "next_safe_action": "Run the discriminating B probe" if intervention else "",
            "unresolved_unknown": "", "notes": "same persistent monitor",
        }

    responses = [
        {"action": "INSPECT", "reason": "read newest activity", "inspection": {
            "operation": "read_recent_delta", "limit": 1,
        }},
        {"action": "INSPECT", "reason": "inspect exact public evidence", "inspection": {
            "operation": "read_public_trajectory", "limit": 5,
        }},
        final("Do not close B until the discriminating public probe runs.", "focused"),
        {"action": "INSPECT", "reason": "check activity since my judgment", "inspection": {
            "operation": "read_recent_delta", "limit": 10,
        }},
        final(),
    ]

    class Session:
        max_tokens = 1024
        reasoning_effort = "high"

        def __init__(self):
            self.index = 0
            self.prompts = []

        def raw_ask(self, messages):
            self.prompts.append(messages[-1]["content"][0]["text"])
            value = responses[self.index]
            self.index += 1
            if self.index == 3:
                uptake = {
                    **boundary(6), "archive_event_id": "uptake", "archive_sequence": 6,
                    "response_content": "I accepted the correction and will run the B probe.",
                }
                with archive.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(uptake) + "\n")
            yield json.dumps(value)

    session = Session()
    monkeypatch.setattr(m0, "resolve_session", lambda _: session)
    monitor = m0.M0DeliberativeMonitor(
        public_task="Implement A and B; demonstrate both.", workspace=tmp_path,
        config_name="fake", artifact_dir=tmp_path / "monitor",
        m1_workspace_enabled=True, active_reconstruction_enabled=True,
        m2_semantic_impact_enabled=True, m3_human_loop_enabled=True,
        m3_decision_value_enabled=True, adaptive_review_planning_enabled=True,
        m35_continuity_enabled=True, m35_history_compaction_enabled=True,
        m35_minimal_frontstage_enabled=True,
    )
    monitor.root_obligation_audit = [
        {"obligation": "Implement A", "status": "supported", "public_evidence": ["A"]},
        {"obligation": "Implement B", "status": "unknown", "public_evidence": []},
    ]
    monitor.observe_archived_boundaries(initial)

    message, cursor, reviewed_turn, rechecked = _review_with_one_freshness_pass(
        monitor, archive, {
            "archive_wake_only": True, "boundary": "autonomous_archive_observation",
            "internal_turn": 5, "archive_delta": {"last_sequence": 5},
        }, 5,
    )

    assert message == ""
    assert (cursor, reviewed_turn, rechecked) == (6, 6, True)
    assert "close B using" in session.prompts[1]
    assert "accepted the correction" in session.prompts[4]
    history = json.dumps(monitor.history, ensure_ascii=False)
    assert "CONSUMED EVIDENCE RECEIPT" in history
    assert "read_public_trajectory" in history
    assert "read_inspection_result" in history
    assert monitor.open_episode is None
    assert monitor.semantic_workspace is not None
    assert monitor.m2_semantic_impact_enabled is True


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


def test_blocked_root_completion_is_bounded_and_keeps_task_open(tmp_path):
    runtime = AsyncMonitorRuntime(
        {"artifact_dir": str(tmp_path)}, request_timeout=1.0, worker_target=blocking_worker,
    )
    try:
        started = time.monotonic()
        result = runtime.review_completion(proposal(), 9, response_content="done")
        elapsed = time.monotonic() - started
        assert result.decision == "CONTINUE"
        assert "MONITOR_TIMEOUT" in result.reason_codes
        assert "monitor failure" in result.next_prompt
        assert 0.8 < elapsed < 3.0
    finally:
        runtime.close()


def test_root_completion_worker_error_keeps_task_open(tmp_path):
    runtime = AsyncMonitorRuntime(
        {"artifact_dir": str(tmp_path)}, worker_target=failing_completion_worker,
    )
    try:
        result = runtime.review_completion(proposal(), 9, response_content="done")
        assert result.decision == "CONTINUE"
        assert result.reason_codes == ("MONITOR_COMPLETION_ERROR",)
        assert "not treat this monitor failure as completion evidence" in result.next_prompt
    finally:
        runtime.close()


def test_root_completion_queue_full_keeps_task_open(tmp_path):
    class FullQueue:
        def put_nowait(self, _item):
            raise queue.Full

    runtime = AsyncMonitorRuntime(
        {"artifact_dir": str(tmp_path)}, worker_target=completion_worker,
    )
    original_requests = runtime.requests
    try:
        runtime.requests = FullQueue()
        result = runtime.review_completion(proposal(), 9, response_content="done")
        assert result.decision == "CONTINUE"
        assert result.reason_codes == ("MONITOR_QUEUE_FULL",)
        assert "monitor failure" in result.next_prompt
    finally:
        runtime.requests = original_requests
        runtime.close()


def boundary(turn, boundary="post_tool_pre_next_llm", calls=None, results=None):
    return {
        "archive_sequence": turn * 2, "internal_turn": turn, "boundary": boundary,
        "response_content": "ordinary progress", "tool_calls": calls or [],
        "tool_results": results or [],
    }


def test_adaptive_review_executes_the_monitor_authored_turn_distance():
    rows = [boundary(turn) for turn in range(1, 8)]
    assert _adaptive_review_reason(
        rows, focused=False, review_after_turns=8,
    ) is None
    rows.append(boundary(8))
    assert _adaptive_review_reason(
        rows, focused=False, review_after_turns=8,
    ) == "monitor_authored_semantic_patrol"


def test_initial_calibration_observes_small_real_window_then_returns_control():
    rows = [boundary(turn) for turn in range(1, 3)]
    assert _adaptive_review_reason(
        rows, focused=False, review_after_turns=20,
        initial_calibration=True,
    ) is None
    rows.append(boundary(3))
    assert _adaptive_review_reason(
        rows, focused=False, review_after_turns=20,
        initial_calibration=True,
    ) == "initial_monitor_calibration"
    # Once calibrated, the identical short window obeys the monitor-authored
    # distance rather than becoming a permanent frequent polling rule.
    assert _adaptive_review_reason(
        rows, focused=False, review_after_turns=20,
        initial_calibration=False,
    ) is None


def test_ordinary_event_shapes_do_not_override_the_monitor_authored_patrol():
    test_change = boundary(3, calls=[{
        "tool_name": "file_patch", "args": {"path": "pkg/widget_test.go"},
    }])
    assert _adaptive_review_reason(
        [test_change], focused=False, review_after_turns=5,
    ) is None
    failure = boundary(4, calls=[{
        "tool_name": "code_run", "args": {"script": "go test ./..."},
    }], results=["FAIL: expected wildcard"])
    assert _adaptive_review_reason(
        [failure], focused=False, review_after_turns=5,
    ) is None
    assert _adaptive_review_reason([boundary(5)], focused=True) == (
        "focused_result_followup"
    )


def test_focused_attention_reviews_public_intent_without_requiring_a_message():
    repair_intent = boundary(6, "post_model_pre_tool", calls=[{
        "tool_name": "file_patch", "args": {"path": "src/handler.go"},
    }])
    assert _adaptive_review_reason([repair_intent], focused=True) == (
        "focused_intent_followup"
    )
    # The identical intent stays deferred in ordinary patrol operation. This
    # prevents the repair policy from becoming an all-intents interceptor.
    assert _adaptive_review_reason([repair_intent], focused=False) is None


def test_adaptive_review_waits_for_post_tool_boundary_outside_repair():
    intent = boundary(7, "post_model_pre_tool", calls=[{
        "tool_name": "file_patch", "args": {"path": "x_test.go"},
    }])
    assert _adaptive_review_reason([intent], focused=False) is None
    assert _adaptive_review_reason(
        [intent], focused=False, review_after_turns=1,
    ) is None


def test_adaptive_review_cursor_is_atomic_and_survives_restart(tmp_path):
    archive = tmp_path / "async_public_boundaries.jsonl"
    assert _load_review_cursor(archive) == 0
    _save_review_cursor(archive, 37)
    assert _load_review_cursor(archive) == 37
    assert not archive.with_name("adaptive_review_cursor.json.tmp").exists()


def test_incremental_archive_reader_reads_only_complete_appends(tmp_path):
    archive = tmp_path / "async_public_boundaries.jsonl"
    first = json.dumps({"archive_sequence": 1}) + "\n"
    second = json.dumps({"archive_sequence": 2})
    archive.write_text(first + second[:8], encoding="utf-8")
    reader = _IncrementalArchiveReader(archive)

    rows, reset = reader.read_new()
    assert reset is False
    assert [row["archive_sequence"] for row in rows] == [1]

    with archive.open("a", encoding="utf-8") as stream:
        stream.write(second[8:] + "\n" + json.dumps({"archive_sequence": 3}) + "\n")
    rows, reset = reader.read_new()
    assert reset is False
    assert [row["archive_sequence"] for row in rows] == [2, 3]
    assert reader.read_new() == ([], False)


def test_incremental_archive_reader_recovers_after_truncation(tmp_path):
    archive = tmp_path / "async_public_boundaries.jsonl"
    archive.write_text(
        json.dumps({"archive_sequence": 1}) + "\n"
        + json.dumps({"archive_sequence": 2}) + "\n",
        encoding="utf-8",
    )
    reader = _IncrementalArchiveReader(archive)
    assert len(reader.read_new()[0]) == 2

    archive.write_text(json.dumps({"archive_sequence": 1}) + "\n", encoding="utf-8")
    rows, reset = reader.read_new()

    assert reset is True
    assert [row["archive_sequence"] for row in rows] == [1]


def test_archive_resume_uses_max_sequence_and_isolates_crash_tail(tmp_path):
    archive = tmp_path / "async_public_boundaries.jsonl"
    archive.write_bytes(
        json.dumps({"archive_sequence": "damaged"}).encode() + b"\n"
        +
        json.dumps({"archive_sequence": 2}).encode() + b"\n"
        + json.dumps({"archive_sequence": 5}).encode() + b"\n"
        + b'{"archive_sequence":6'
    )

    assert _resume_archive(archive) == 5
    assert archive.read_bytes().endswith(b"\n")

    with archive.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"archive_sequence": 6}) + "\n")
    assert [row["archive_sequence"] for row in _read_archive(archive)] == [
        "damaged", 2, 5, 6
    ]


def test_archive_max_sequence_ignores_invalid_rows_for_cursor_reconciliation():
    assert _max_archive_sequence([
        {"archive_sequence": "damaged"},
        {"archive_sequence": 3},
        {"archive_sequence": 8},
    ]) == 8


def test_review_cursor_ahead_of_replaced_archive_is_reset(tmp_path):
    archive = tmp_path / "async_public_boundaries.jsonl"
    archive.write_text(json.dumps({"archive_sequence": 3}) + "\n", encoding="utf-8")
    _save_review_cursor(archive, 19)

    assert _reconciled_review_cursor(archive) == (0, 19)


def test_freshness_failure_keeps_new_rows_pending_after_reader_advances(tmp_path):
    archive = tmp_path / "async_public_boundaries.jsonl"
    initial = {**boundary(1), "archive_event_id": "one", "archive_sequence": 1}
    archive.write_text(json.dumps(initial) + "\n", encoding="utf-8")
    reader = _IncrementalArchiveReader(archive)
    assert reader.read_new()[0] == [initial]

    class Monitor:
        def review(self, _packet):
            if not hasattr(self, "called"):
                self.called = True
                fresh = {
                    **boundary(2), "archive_event_id": "two", "archive_sequence": 2,
                }
                with archive.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(fresh) + "\n")
                return "candidate correction"
            raise RuntimeError("freshness provider failed")

        def observe_archived_boundaries(self, _rows):
            pass

        def baseline_observation(self, count):
            return {"observed_boundaries": count}

        observation_plan = {}

    pending = []
    with pytest.raises(RuntimeError, match="freshness provider failed"):
        _review_with_one_freshness_pass(
            Monitor(), archive, {
                "archive_wake_only": True, "internal_turn": 1,
                "boundary": "autonomous_archive_observation",
            }, 1, archive_reader=reader, pending_rows=pending,
        )

    assert [row["archive_sequence"] for row in pending] == [2]
    assert reader.read_new() == ([], False)
