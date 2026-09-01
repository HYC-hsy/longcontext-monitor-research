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
    assert monitor.review("Initialize.").payload == {"after_turns": 4}
    first_size = len(client.history)
    assert monitor.review("Cursor advanced.").payload == {"after_turns": 1}
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


def test_analysis_code_mutates_only_disposable_snapshot(roots):
    evidence, private = roots
    script = "from pathlib import Path\np=Path('.task_view/original_task.txt')\np.write_text('changed')"
    client = SequenceClient([
        response("code_run", {"code": script, "type": "python"}),
        response("wait", {"after_turns": 1}),
    ])
    monitor = MonitorAgent(client, MonitorWorkspace(evidence, private))
    monitor.review("Analyze evidence.")
    assert (evidence / "original_task.txt").read_text(encoding="utf-8") == "Preserve the literal wildcard.\n"
    assert (private / ".task_view" / "original_task.txt").read_text(encoding="utf-8") == "changed"


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
