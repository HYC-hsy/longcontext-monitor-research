import json
import importlib.util
from pathlib import Path

import pytest

from monitor_agent_core.actions import MonitorAction
from monitor_agent_core.probe import IndependentVerifier, ProbeConfig, score_local_result
from monitor_agent_core.provider import ModelResponse, ToolCall
from monitor_agent_core.workspace import MonitorWorkspace


def call(name, arguments, cid):
    return ModelResponse("", [ToolCall(cid, name, json.dumps(arguments))], {})


class SequenceClient:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.history = []
        self.calls = []

    def complete(self, messages, tools):
        self.calls.append((messages, tools))
        self.history.extend(messages)
        response = next(self.responses)
        self.history.append({"role": "assistant", "content": response.content})
        return response

    def record_tool_results(self, results):
        self.history.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": r["tool_use_id"],
             "content": r["content"]} for r in results
        ]})

    def history_measure(self):
        encoded = json.dumps(self.history, ensure_ascii=False).encode()
        return {"items": len(self.history), "characters": len(encoded), "sha256": "fixture"}


def workspace(tmp_path):
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "original_task.txt").write_text("Refresh must preserve ordering.\n", encoding="utf-8")
    (evidence / "events.jsonl").write_text("implementation observed\n", encoding="utf-8")
    return MonitorWorkspace(evidence, tmp_path / "private")


def test_direct_probe_is_local_and_returns_scoped_result(tmp_path):
    client = SequenceClient([
        call("file_read", {"path": "task/original_task.txt"}, "1"),
        call("file_read", {"path": "task/events.jsonl"}, "2"),
        call("finish_probe", {"outcome": "supported_in_scope", "conclusion": "ordering observed"}, "3"),
    ])
    probe = IndependentVerifier(client, workspace(tmp_path), ProbeConfig(
        mode="direct", evidence_paths=("task/events.jsonl",), max_requests=3,
    ))
    result = probe.run("Does the observed change support ordering?")
    assert result.outcome == "supported_in_scope"
    assert result.status == "completed"
    assert result.phases == ["evidence"]
    assert result.requests == 3
    assert all(call_name not in {"intervene", "wait", "allow_complete"}
               for _, tools in client.calls
               for call_name in [item["function"]["name"] for item in tools])


def test_expectation_first_blocks_evidence_until_expectation_committed(tmp_path):
    audit = []
    client = SequenceClient([
        call("file_read", {"path": "task/events.jsonl"}, "1"),
        call("commit_expectation", {"expectation": "ordering is preserved"}, "2"),
        call("file_read", {"path": "task/events.jsonl"}, "3"),
        call("finish_probe", {"outcome": "contradicted", "conclusion": "event does not establish order"}, "4"),
    ])
    probe = IndependentVerifier(client, workspace(tmp_path), ProbeConfig(
        mode="expectation_first", evidence_paths=("task/events.jsonl",), max_requests=4,
    ), audit=lambda event, **fields: audit.append((event, fields)))
    result = probe.run("Is ordering supported?")
    assert result.expectation == "ordering is preserved"
    assert result.outcome == "contradicted"
    assert result.phases == ["expectation", "evidence"]
    # The first evidence read is denied by the phase-specific dispatch.
    denied = [fields for event, fields in audit
              if event == "tool_result" and "outside this probe phase"
              in json.dumps(fields, ensure_ascii=False)]
    assert denied


def test_probe_does_not_share_parent_history(tmp_path):
    parent = SequenceClient([])
    parent.history.append({"role": "assistant", "content": "TASK COMPLETE"})
    child = SequenceClient([call("finish_probe", {
        "outcome": "unresolved", "conclusion": "No behavior evidence was provided."}, "1")])
    result = IndependentVerifier(child, workspace(tmp_path), ProbeConfig(max_requests=1)).run("Question")
    assert result.history_before["items"] == 0
    assert parent.history == [{"role": "assistant", "content": "TASK COMPLETE"}]


def test_probe_budget_is_explicit_and_returns_unresolved(tmp_path):
    client = SequenceClient([
        call("file_read", {"path": "task/original_task.txt"}, "1"),
        call("file_read", {"path": "task/original_task.txt"}, "2"),
    ])
    result = IndependentVerifier(client, workspace(tmp_path), ProbeConfig(
        max_requests=2, max_turns=4,
    )).run("Question")
    assert result.outcome is None
    assert result.status == "probe_budget_exhausted"
    assert result.limitation == "probe_budget_exhausted"
    assert result.requests == 2


def test_expectation_phase_rejects_code_run_even_when_enabled(tmp_path):
    ran = []
    client = SequenceClient([
        call("code_run", {"code": "read evidence"}, "1"),
        call("commit_expectation", {"expectation": "ordered output"}, "2"),
        call("finish_probe", {"outcome": "unresolved",
                              "conclusion": "No observable behavior is available."}, "3"),
    ])
    result = IndependentVerifier(
        client, workspace(tmp_path),
        ProbeConfig(mode="expectation_first", allow_code_run=True, max_requests=3),
        code_runner=lambda args: ran.append(args),
    ).run("Question")
    assert result.phases == ["expectation", "evidence"]
    assert ran == []


def test_empty_finish_requires_explicit_verdict_and_reason(tmp_path):
    audit = []
    client = SequenceClient([
        call("finish_probe", {}, "1"),
        call("finish_probe", {"outcome": "unresolved"}, "2"),
        call("finish_probe", {"outcome": "unresolved",
                              "conclusion": "Only a build result is available."}, "3"),
    ])
    result = IndependentVerifier(client, workspace(tmp_path), ProbeConfig(
        max_requests=3,
    ), audit=lambda event, **fields: audit.append((event, fields))).run("Question")
    assert result.status == "completed"
    assert result.outcome == "unresolved"
    errors = [fields for event, fields in audit if event == "tool_result"
              and isinstance(fields.get("data"), dict)
              and fields["data"].get("status") == "error"]
    assert len(errors) == 2


def test_unfinished_probe_is_not_correct_unresolved(tmp_path):
    client = SequenceClient([call("file_read", {"path": "task/original_task.txt"}, "1")])
    result = IndependentVerifier(client, workspace(tmp_path), ProbeConfig(
        max_requests=1,
    )).run("Question")
    assert score_local_result(result, "unresolved") == {
        "score_eligible": False, "correct": None,
    }


def test_failed_provider_call_is_still_counted_as_one_logical_attempt(tmp_path):
    class FailingClient(SequenceClient):
        def complete(self, messages, tools):
            self.calls.append((messages, tools))
            raise ConnectionError("temporary provider failure")

    probe = IndependentVerifier(FailingClient([]), workspace(tmp_path), ProbeConfig())
    with pytest.raises(ConnectionError):
        probe.run("Question")
    assert probe.logical_calls == 1


def test_transport_callback_keeps_lifecycle_and_drops_payloads():
    path = Path(__file__).parents[2] / "method_discovery" / "run_independent_probe_panel.py"
    spec = importlib.util.spec_from_file_location("probe_panel_transport", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    transport_audit_callback = module.transport_audit_callback

    records = []
    callback = transport_audit_callback(records, "case", "C")
    callback("request_finished", request_id="r1", outcome="retryable_error",
             error_chain=[{"type": "ConnectionError", "code": None}],
             secret="must-not-persist", response_body="must-not-persist")
    assert records == [{
        "event": "transport_request_finished", "case": "case", "group": "C",
        "recorded_at": records[0]["recorded_at"],
        "request_id": "r1", "outcome": "retryable_error",
        "error_chain": [{"type": "ConnectionError", "code": None}],
    }]
