import json

import pytest

from monitor_agent_core.agent import MONITOR_SYSTEM_PROMPT, MONITOR_TOOLS, MonitorAgent
from monitor_agent_core.provider import ModelResponse, ToolCall
from monitor_agent_core.workspace import MonitorWorkspace


class SequenceClient:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.history = []

    def complete(self, messages, tools):
        self.history.extend(messages)
        answer = next(self.responses)
        self.history.append({"role": "assistant", "content": answer.content})
        return answer

    def history_measure(self):
        return {"items": len(self.history), "characters": len(json.dumps(self.history)), "sha256": "fake"}

    def export_history(self):
        return list(self.history)


def response(tool, arguments):
    return ModelResponse("", [ToolCall("call", tool, json.dumps(arguments))], {})


@pytest.fixture
def roots(tmp_path):
    evidence = tmp_path / "evidence"
    private = tmp_path / "private"
    evidence.mkdir()
    (evidence / "original_task.txt").write_text("Preserve the literal wildcard.\n", encoding="utf-8")
    return evidence, private


def test_tool_surface_is_monitor_specific_and_small():
    assert [item["function"]["name"] for item in MONITOR_TOOLS] == [
        "file_read", "file_write", "file_patch", "code_run",
        "wait", "intervene", "allow_complete",
    ]
    lowered = MONITOR_SYSTEM_PROMPT.lower()
    assert "global memory" not in lowered
    assert "self-evolution" not in lowered
    assert "ask_user" not in lowered


def test_monitor_inspects_then_intervenes(roots):
    evidence, private = roots
    client = SequenceClient([
        response("file_read", {"path": "task/original_task.txt"}),
        response("intervene", {"message": "Keep the literal wildcard; current intent drops it."}),
    ])
    monitor = MonitorAgent(client, MonitorWorkspace(evidence, private))
    action = monitor.review("The current intent may narrow the wildcard.")
    assert action.kind == "intervene"
    assert "literal wildcard" in action.payload["message"]
    assert (private / "audit" / "provider_history.json").is_file()


def test_same_client_history_continues_across_wakes(roots):
    evidence, private = roots
    client = SequenceClient([
        response("wait", {"after_turns": 4}), response("wait", {"after_turns": 1}),
    ])
    monitor = MonitorAgent(client, MonitorWorkspace(evidence, private))
    assert monitor.review("Initialize.").payload == {"after_turns": 4, "mode": "follow"}
    first_size = len(client.history)
    assert monitor.review("Cursor advanced.").payload == {"after_turns": 1, "mode": "follow"}
    assert len(client.history) > first_size
    assert len((private / "audit" / "reviews.jsonl").read_text(encoding="utf-8").splitlines()) == 2


def test_allow_complete_is_guarded_by_root_boundary(roots):
    evidence, private = roots
    client = SequenceClient([
        response("allow_complete", {}), response("wait", {"after_turns": 2}),
        response("allow_complete", {}),
    ])
    monitor = MonitorAgent(client, MonitorWorkspace(evidence, private))
    assert monitor.review("Ordinary patrol.").kind == "wait"
    assert monitor.review("Root completion.", completion_pending=True).kind == "allow_complete"


def test_analysis_session_survives_review_and_does_not_control_task(roots):
    import threading
    evidence, private = roots
    stop = threading.Event()
    monitor = MonitorAgent(SequenceClient([response('wait', {'after_turns': 1})]),
                           MonitorWorkspace(evidence, private), stop_event=stop)
    try:
        first = monitor.dispatch('code_run', {'code': "import time\nprint('start')\ntime.sleep(30)",
                                               'wait_seconds': 0}).data
        assert first['status'] == 'running'
        assert monitor.review('Same task').kind == 'wait'
        assert monitor.dispatch('code_run', {'session_id': first['session_id'],
                                             'wait_seconds': 0}).data['status'] == 'running'
        stop.set()
        final = monitor.dispatch('code_run', {'session_id': first['session_id']}).data
        assert final['reason'] == 'cancelled'
        assert final['status'] == 'error'
    finally:
        monitor.analysis.close()


def test_analysis_reads_live_sources_without_copy(roots):
    evidence, private = roots
    script = f"from pathlib import Path\nprint(Path({str(evidence / 'original_task.txt')!r}).read_text())"
    client = SequenceClient([
        response("code_run", {"code": script, "type": "python"}),
        response("wait", {"after_turns": 1}),
    ])
    monitor = MonitorAgent(client, MonitorWorkspace(evidence, private))
    action = monitor.review("Analyze evidence.")
    assert action.kind == "wait"
    assert (evidence / "original_task.txt").read_text(encoding="utf-8") == "Preserve the literal wildcard.\n"
    assert not (private / ".task_view").exists()
    assert json.dumps(str(evidence)) in client.history[1]["content"]
    result = monitor.dispatch("code_run", {"code": script}).data
    assert result["exit_code"] == 0
    assert "literal wildcard" in result["stdout"]
    (evidence / "original_task.txt").write_text("New public progress", encoding="utf-8")
    assert "New public progress" in monitor.dispatch("code_run", {"code": script}).data["stdout"]


def test_handoff_preserves_semantics_and_accounts_for_usage(roots, monkeypatch):
    from monitor_agent_core.provider import MonitorProviderClient
    evidence, private = roots
    client = MonitorProviderClient("openai", {"apikey": "test", "apibase": "https://example.test",
                                            "model": "gpt-test", "monitor_history_char_limit": 100})
    monitor = MonitorAgent(client, MonitorWorkspace(evidence, private))
    client.history = [{"role": "user", "content": [{"type": "text", "text": "evidence " * 100}]}]
    seen = []
    def request(tools):
        seen.append(json.dumps(client.history))
        assert tools == []
        return [{"type": "text", "text": "Cause remains uncertain; wait for the accepted control experiment."}], {"input_tokens": 20}
    monkeypatch.setattr(client, "_request", request)
    note = monitor._prepare_continuation()
    assert "evidence" in seen[0]
    assert "Cause remains uncertain" in (private / "working.md").read_text()
    assert "Cause remains uncertain" in note
    assert client.usage_records[-1]["purpose"] == "pre_compaction_continuation"
    assert len(client.history) == 1  # no temporary maintenance instruction left in history


def test_failed_continuation_never_discards_history(roots, monkeypatch):
    from monitor_agent_core.provider import MonitorProviderClient
    evidence, private = roots
    client = MonitorProviderClient("openai", {"apikey": "test", "apibase": "https://example.test",
                                            "model": "gpt-test", "monitor_history_char_limit": 100})
    monitor = MonitorAgent(client, MonitorWorkspace(evidence, private))
    client.history = [{"role": "user", "content": [{"type": "text", "text": "still open " * 100}]}]
    original = client.export_history()
    monkeypatch.setattr(client, "_request", lambda _: ([], {}))
    with pytest.raises(ValueError, match="Empty continuation"):
        monitor._prepare_continuation()
    assert client.export_history() == original


def test_review_persists_provider_usage_and_history_transform(roots):
    evidence, private = roots

    class TelemetryClient(SequenceClient):
        def drain_telemetry(self):
            return {
                "usage": [{"input_tokens": 12, "output_tokens": 3}],
                "history_transforms": [{"kind": "monitor_history_compaction"}],
            }

    monitor = MonitorAgent(
        TelemetryClient([response("wait", {"after_turns": 2})]),
        MonitorWorkspace(evidence, private),
    )
    monitor.review("Patrol.")

    usage = json.loads((private / "audit" / "provider_usage.jsonl").read_text(encoding="utf-8"))
    transform = json.loads((private / "audit" / "history_transforms.jsonl").read_text(encoding="utf-8"))
    assert usage == {"input_tokens": 12, "output_tokens": 3}
    assert transform["kind"] == "monitor_history_compaction"


def test_terminal_action_closes_every_tool_call_in_same_response(roots):
    evidence, private = roots

    class RecordingSequenceClient(SequenceClient):
        def __init__(self, responses):
            super().__init__(responses)
            self.recorded = []

        def record_tool_results(self, results):
            self.recorded.extend(results)

    client = RecordingSequenceClient([ModelResponse("", [
        ToolCall("read-1", "file_read", json.dumps({"path": "task/original_task.txt"})),
        ToolCall("wait-1", "wait", json.dumps({"after_turns": 2})),
        ToolCall("late-1", "file_read", json.dumps({"path": "task/original_task.txt"})),
    ], {})])
    action = MonitorAgent(client, MonitorWorkspace(evidence, private)).review("Initialize.")

    assert action.kind == "wait"
    assert [result["tool_use_id"] for result in client.recorded] == [
        "read-1", "wait-1", "late-1",
    ]
    assert "not_executed" in client.recorded[-1]["content"]
