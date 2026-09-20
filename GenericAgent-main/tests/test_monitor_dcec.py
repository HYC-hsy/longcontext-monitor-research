"""Deterministic DCEC-v0 contract and production assembly regressions."""

import json
import hashlib
from pathlib import Path

import pytest

from monitor_agent_core.agent import DCEC_CONTINUATION_PROMPT, DCEC_SYSTEM_PROMPT, MonitorAgent
from monitor_agent_core.provider import MonitorProviderClient
from monitor_agent_core.working_context import dcec_working_context
from monitor_agent_core.workspace import MonitorWorkspace
from test_monitor_agent import SequenceClient


def workspace(tmp_path):
    evidence = tmp_path / "evidence"
    evidence.mkdir(parents=True)
    (evidence / "original_task.txt").write_text("Preserve all requested behavior.\n", encoding="utf-8")
    return MonitorWorkspace(evidence, tmp_path / "private")


def provider(config=None):
    return MonitorProviderClient("anthropic", {
        "apikey": "test", "apibase": "https://example.test", "model": "claude-test",
        "max_retries": 0, **(config or {}),
    })


def test_dcec_off_preserves_ordinary_agent_contract(tmp_path):
    left, right = SequenceClient([]), SequenceClient([])
    right.config = {"monitor_dcec": False}
    a = MonitorAgent(left, workspace(tmp_path / "a"))
    b = MonitorAgent(right, workspace(tmp_path / "b"))
    assert a.system_prompt == b.system_prompt
    assert DCEC_SYSTEM_PROMPT not in a.system_prompt
    assert not hasattr(left, "prepare_active_context")
    assert not hasattr(right, "prepare_active_context")


@pytest.mark.parametrize("setting", [
    "monitor_inquiry", "monitor_decision_context", "monitor_pma_memory",
    "monitor_active_working_context", "monitor_grounded_context", "monitor_feedback_focus",
    "monitor_tool_feedback", "monitor_live_awareness", "monitor_advice_revision",
])
def test_dcec_rejects_historical_semantic_candidates(tmp_path, setting):
    client = SequenceClient([])
    client.config = {"monitor_dcec": True, setting: True}
    with pytest.raises(ValueError, match="cannot be stacked"):
        MonitorAgent(client, workspace(tmp_path))


def test_dcec_rejects_independent_c_and_invalid_bound(tmp_path):
    client = SequenceClient([])
    client.config = {"monitor_dcec": True}
    with pytest.raises(ValueError, match="monitor_independent_c"):
        MonitorAgent(client, workspace(tmp_path / "child"), independent_check=lambda *_: None)
    client = SequenceClient([])
    client.config = {"monitor_dcec": True, "monitor_dcec_working_chars": 9000}
    with pytest.raises(ValueError, match="between 512 and 8000"):
        MonitorAgent(client, workspace(tmp_path / "bound"))
    client = SequenceClient([])
    client.config = {"monitor_dcec": True, "monitor_semantic_continuity": False}
    with pytest.raises(ValueError, match="requires the ordinary semantic continuation"):
        MonitorAgent(client, workspace(tmp_path / "continuation"))


def test_bounded_view_is_single_state_and_reports_transport_cost(tmp_path):
    ws = workspace(tmp_path)
    ws.write_text("monitor/working.md", "Current decision\n" + "x" * 6000)
    text, metadata = dcec_working_context(ws, 1000)
    assert text.count("<dcec_working_state>") == 1
    assert "not a fact source or verified truth" in text
    assert "Only the first 1000 characters" in text
    assert metadata == {**metadata, "path": "monitor/working.md", "limit_characters": 1000,
                        "visible_characters": 1000, "truncated": True}
    assert metadata["source_characters"] > metadata["visible_characters"]
    assert metadata["injected_characters"] == len(text)
    assert metadata["estimated_tokens"] > 0
    assert not (ws.private_root / "decision_state.json").exists()


def test_production_request_injects_view_once_and_does_not_persist_copy(tmp_path, monkeypatch):
    ws = workspace(tmp_path)
    ws.write_text("monitor/working.md", "Current decision\n- inspect a material uncertainty")
    client = provider({"monitor_dcec": True, "monitor_dcec_working_chars": 1200})
    monitor = MonitorAgent(client, ws)
    snapshots = []

    def request_once(tools):
        snapshots.append(client.assembled_request_snapshot(tools))
        assert [tool["function"]["name"] for tool in tools] == [
            "file_read", "file_write", "file_patch", "code_run", "wait", "intervene", "allow_complete"]
        wire = json.dumps(client.history, ensure_ascii=False)
        assert wire.count("<dcec_working_state>") == 1
        return ([{"type": "tool_use", "id": "wait", "name": "wait",
                  "input": {"after_turns": 1}}], {})

    monkeypatch.setattr(client, "_request_once", request_once)
    assert monitor.review("Normal wake").kind == "wait"
    assert len(snapshots) == client.complete_calls == 1
    assert "<dcec_working_state>" not in json.dumps(client.history, ensure_ascii=False)
    events = [json.loads(line) for line in
              (ws.private_root / "audit/progress.jsonl").read_text(encoding="utf-8").splitlines()]
    view = next(event for event in events if event["event"] == "dcec_working_view")
    assert view["limit_characters"] == 1200 and view["injected_characters"] > 0


def test_lifecycle_revision_replaces_active_concern_and_can_reopen(tmp_path):
    client = SequenceClient([])
    client.config = {"monitor_dcec": True}
    monitor = MonitorAgent(client, workspace(tmp_path))
    open_state = "Current decision\n- local repair\nActive concern\n- open: wrong API\nCurrent grounds\n- task claim only"
    assert monitor.dispatch("file_write", {"path": "monitor/working.md", "content": open_state}).data["characters"]
    monitor.dispatch("file_patch", {"path": "monitor/working.md", "old_text": "open: wrong API",
                                    "new_text": "recovering: intervention sent; uptake not yet observed"})
    monitor.dispatch("file_patch", {"path": "monitor/working.md",
                                    "old_text": "recovering: intervention sent; uptake not yet observed",
                                    "new_text": "resolved locally after direct post-repair observation; not whole-task support"})
    current = (monitor.workspace.private_root / "working.md").read_text(encoding="utf-8")
    assert "open: wrong API" not in current and "resolved locally" in current
    assert "not whole-task support" in current
    monitor.dispatch("file_patch", {"path": "monitor/working.md", "old_text": "resolved locally",
                                    "new_text": "reopened by a new relevant conflict"})
    assert "reopened by a new relevant conflict" in (
        monitor.workspace.private_root / "working.md").read_text(encoding="utf-8")
    events = (monitor.workspace.private_root / "audit/progress.jsonl").read_text(encoding="utf-8")
    assert events.count('"event": "dcec_state_mutation"') == 4
    assert monitor.dispatch("file_patch", {"path": "monitor/working.md", "old_text": "absent",
                                           "new_text": "unused"}).data["status"] == "error"
    events = (monitor.workspace.private_root / "audit/progress.jsonl").read_text(encoding="utf-8")
    assert '"event": "dcec_state_mutation_failed"' in events


def test_evidence_receipt_preserves_range_hash_and_truncation_without_truth_label(tmp_path):
    client = SequenceClient([])
    client.config = {"monitor_dcec": True}
    monitor = MonitorAgent(client, workspace(tmp_path))
    (monitor.workspace.evidence_root / "source.txt").write_text("abcdef\nsecond\n", encoding="utf-8")
    receipt = monitor.dispatch("file_read", {
        "path": "task/source.txt", "start": 1, "count": 2, "max_chars": 3}).data
    assert receipt["truncated"] and receipt["next_read"]
    assert receipt["sha256"] and receipt["path"] == "task/source.txt"
    assert not ({"satisfied", "correct", "sufficient", "semantically_stale"} & set(receipt))


def test_dcec_continuation_contract_and_rejected_note_never_overwrite(tmp_path, monkeypatch):
    ws = workspace(tmp_path)
    ws.write_text("monitor/working.md", "Active concern\n- recovering: direct evidence pending")
    client = provider({"monitor_dcec": True})
    monitor = MonitorAgent(client, ws)
    original = (ws.private_root / "working.md").read_text(encoding="utf-8")
    calls = []

    def truncated(_tools):
        calls.append(client.history[-1]["content"][0]["text"])
        assert DCEC_CONTINUATION_PROMPT in calls[-1]
        assert "do not reactivate" in calls[-1].lower()
        client.last_response_metadata = {"stop_reason": "max_tokens"}
        return [{"type": "text", "text": "partial"}], {}

    monkeypatch.setattr(client, "_request", truncated)
    with pytest.raises(ValueError, match="output limit"):
        monitor._prepare_continuation()
    assert len(calls) == 2
    assert (ws.private_root / "working.md").read_text(encoding="utf-8") == original


def test_valid_continuation_replaces_old_state_and_next_view_uses_only_current_note(tmp_path, monkeypatch):
    ws = workspace(tmp_path)
    ws.write_text("monitor/working.md", "Active concern\n- resolved item incorrectly remains active")
    client = provider({"monitor_dcec": True})
    monitor = MonitorAgent(client, ws)
    revised = ("Current decision\n- decide whether recovery evidence is sufficient\n"
               "Active concern\n- recovering: wait for direct result\n"
               "Current grounds and limits\n- Task Agent reports a fix; not direct evidence")

    def request(_tools):
        assert DCEC_CONTINUATION_PROMPT in client.history[-1]["content"][0]["text"]
        client.last_response_metadata = {"stop_reason": "end_turn", "stream_complete": True}
        return [{"type": "text", "text": revised}], {}

    monkeypatch.setattr(client, "_request", request)
    assert monitor._prepare_continuation() == revised
    visible, _ = dcec_working_context(ws)
    assert revised in visible
    assert "resolved item incorrectly remains active" not in visible
    assert "Task Agent reports a fix; not direct evidence" in visible


@pytest.mark.parametrize("value", ["0", "1", "bad"])
def test_adapter_exposes_dcec_without_mutating_input(tmp_path, monkeypatch, value):
    import ga_monitor_adapter as adapter
    monkeypatch.setenv("GA_PMA_ENABLED", "0")
    monkeypatch.setenv("GA_MONITOR_DCEC", value)
    monkeypatch.setenv("GA_MONITOR_DCEC_WORKING_CHARS", "4000")
    captured = {}
    monkeypatch.setattr(adapter, "MonitorRuntime", lambda **kw: captured.update(kw))
    original = {"model": "fixture"}
    if value == "bad":
        with pytest.raises(ValueError, match="must be 0 or 1"):
            adapter.GenericAgentMonitorAdapter(
                task_workspace=tmp_path, public_task="Task", model_config=original)
    else:
        adapter.GenericAgentMonitorAdapter(task_workspace=tmp_path, public_task="Task", model_config=original)
        assert captured["model_config"]["monitor_dcec"] == (value == "1")
        assert captured["model_config"]["monitor_dcec_working_chars"] == 4000
    assert original == {"model": "fixture"}


def test_adapter_rejects_external_pma_stacking(tmp_path, monkeypatch):
    import ga_monitor_adapter as adapter
    monkeypatch.setenv("GA_MONITOR_DCEC", "1")
    monkeypatch.setenv("GA_PMA_ENABLED", "1")
    monkeypatch.setattr(adapter, "MonitorRuntime", lambda **_kw: pytest.fail("must reject before runtime"))
    with pytest.raises(ValueError, match="GA_PMA_ENABLED"):
        adapter.GenericAgentMonitorAdapter(
            task_workspace=tmp_path, public_task="Task", model_config={"model": "fixture"})


def test_discriminating_manifest_is_frozen_unexecuted_and_isolates_candidates():
    path = (Path(__file__).resolve().parents[2] / "method_discovery/artifacts/dcec_v0_20260921"
            / "discriminating_manifest.json")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    assert manifest["status"] == "prepared_not_executed"
    assert manifest["execution_authorized"] is False
    assert manifest["model_api_calls_made_during_preparation"] == 0
    assert manifest["conditions"]["ordinary"]["GA_MONITOR_DCEC"] == "0"
    assert manifest["conditions"]["dcec_v0"]["GA_MONITOR_DCEC"] == "1"
    assert set(manifest["historical_candidate_switches"].values()) == {"0"}
    assert manifest["shared_contract"]["dcec_additional_model_calls"] == 0
    fixture = Path(__file__).resolve().parents[2] / manifest["fixture_spec"]
    assert hashlib.sha256(fixture.read_bytes()).hexdigest() == manifest["fixture_spec_sha256"]
    assert json.loads(fixture.read_text(encoding="utf-8"))["status"] == "frozen_not_materialized"
