"""Candidate W: verify a draft, not a second active Monitor or a task gate."""
import json

import pytest

from monitor_agent_core.agent import MonitorAgent
from test_monitor_continuation_mode import setup_monitor, review


def configured(tmp_path, enabled=True):
    client, monitor = setup_monitor(tmp_path)
    client.config["monitor_handoff_validation"] = enabled
    monitor = MonitorAgent(client, monitor.workspace)
    (monitor.workspace.evidence_root / "original_task.txt").write_text(
        "Public contract: preserve the requested behavior.", encoding="utf-8")
    monitor._atomic_private_text("working.md", "Old uncertain understanding")
    client.history = sum((review(i) for i in range(6)), [])
    return client, monitor


@pytest.mark.parametrize("enabled", [False, True])
def test_only_validated_note_is_consumed_and_feature_off_is_unchanged(tmp_path, monkeypatch, enabled):
    client, monitor = configured(tmp_path, enabled)
    original = client.export_history()
    calls = []

    def request(tools):
        calls.append(client.export_history())
        assert tools == []
        assert client.history[:len(original)] == original
        assert "not an active review" in client.system
        if len(calls) == 1:
            assert (monitor.workspace.private_root / "working.md").read_text() == "Old uncertain understanding"
            return [{"type": "text", "text": "Unverified draft"}], {"input_tokens": 10}
        context = json.dumps(client.history[-3:])
        assert "Public contract" in context and "Old uncertain understanding" in context
        assert "Unverified draft" in context and "Planned retirement" in context
        assert (monitor.workspace.private_root / "working.md").read_text() == "Old uncertain understanding"
        return [{"type": "text", "text": "Revised with uncertainty intact"}], {"input_tokens": 20}

    monkeypatch.setattr(client, "_request", request)
    client._compact_history()
    assert len(calls) == 1 + int(enabled)
    expected = "Revised with uncertainty intact" if enabled else "Unverified draft"
    assert expected in json.dumps(client.history)
    if enabled:
        assert "Unverified draft" not in json.dumps(client.history)
        assert len(list((monitor.workspace.private_root / "audit/handoff_validation").glob("*/draft.md"))) == 1
        assert client.usage_records[-1]["purpose"] == "handoff_validation"
    assert client.history[-10:] == original[-10:]
    assert (monitor.workspace.private_root / "working.md").read_text() == expected
    assert client.continuation_context is None
    wire = client._responses_history()
    assert {r['call_id'] for r in wire if r.get('type') == 'function_call'} == {
        r['call_id'] for r in wire if r.get('type') == 'function_call_output'}


@pytest.mark.parametrize("failure", ["empty", "tool", "transport", "missing_task", "reasoning_echo", "draft_echo"])
def test_validation_failure_preserves_prior_note_and_dialogue(tmp_path, monkeypatch, failure):
    client, monitor = configured(tmp_path)
    original = client.export_history()
    original_system = client.system
    calls = []
    if failure == "missing_task":
        (monitor.workspace.evidence_root / "original_task.txt").unlink()

    def request(tools):
        calls.append(1)
        if failure == "draft_echo" or (failure == "reasoning_echo" and len(calls) > 1):
            summary = "**Planning comprehensive note revision****Checking evidence**"
            return [
                {"type": "openai_item", "item": {"type": "reasoning", "summary": [
                    {"type": "summary_text", "text": summary}]}},
                {"type": "text", "text": summary},
            ], {}
        if len(calls) == 1:
            return [{"type": "text", "text": "draft"}], {}
        if failure == "transport":
            raise RuntimeError("fixture transport failure")
        if failure == "tool":
            return [{"type": "tool_use", "name": "intervene"}], {}
        return [], {}

    monkeypatch.setattr(client, "_request", request)
    with pytest.raises((ValueError, RuntimeError, FileNotFoundError)):
        client._compact_history()
    assert client.history == original
    assert client.system == original_system
    assert client.continuation_context is None
    assert (monitor.workspace.private_root / "working.md").read_text() == "Old uncertain understanding"
    assert not client.history_transforms
    assert not (monitor.workspace.private_root / "audit/continuations.jsonl").exists()


def test_w_does_not_add_a_call_when_no_handoff_is_needed(tmp_path, monkeypatch):
    client, _ = configured(tmp_path)
    client.history = review(1, size=1)
    monkeypatch.setattr(client, "_request", lambda _: pytest.fail("no paid handoff needed"))
    client._compact_history()
    assert not client.usage_records


def test_invalid_combination_fails_explicitly(tmp_path):
    client, monitor = configured(tmp_path)
    client.config["monitor_semantic_continuity"] = False
    with pytest.raises(ValueError, match="requires semantic continuity"):
        MonitorAgent(client, monitor.workspace)


@pytest.mark.parametrize("value", ["0", "1", "bad", None])
def test_adapter_copies_config_and_validates_switch(monkeypatch, value):
    import ga_monitor_adapter as adapter
    monkeypatch.delenv("GA_MONITOR_HANDOFF_VALIDATION", raising=False)
    monkeypatch.delenv("GA_MONITOR_GROUNDED_CONTEXT", raising=False)
    if value is not None:
        monkeypatch.setenv("GA_MONITOR_HANDOFF_VALIDATION", value)
    captured = {}
    monkeypatch.setattr(adapter, "MonitorRuntime", lambda **kw: captured.update(kw))
    original = {"model": "fixture"}
    if value == "bad":
        with pytest.raises(ValueError):
            adapter.GenericAgentMonitorAdapter(model_config=original)
    else:
        adapter.GenericAgentMonitorAdapter(model_config=original)
        assert captured['model_config'].get('monitor_handoff_validation') == (
            None if value is None else value == "1")
    assert original == {"model": "fixture"}
