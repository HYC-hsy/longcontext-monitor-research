"""Maintenance is the same identity, but not an active control-action turn."""
import pytest
import json

from monitor_agent_core.agent import MonitorAgent, MONITOR_SYSTEM_PROMPT, REVIEW_MODE_PROMPT
from monitor_agent_core.provider import MonitorProviderClient
from monitor_agent_core.workspace import MonitorWorkspace


@pytest.mark.parametrize("failure", [False, True])
def test_handoff_role_is_scoped_and_restored(tmp_path, monkeypatch, failure):
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    client = MonitorProviderClient("openai", {
        "apikey": "test", "apibase": "https://example.test", "model": "test",
    })
    monitor = MonitorAgent(client, MonitorWorkspace(evidence, tmp_path / "private"))
    client.system = MONITOR_SYSTEM_PROMPT + "\n\n" + REVIEW_MODE_PROMPT
    before_system = client.system
    client.history = [{"role": "user", "content": [{"type": "text", "text": "Public evidence"}]}]
    before_history = client.export_history()

    def request(tools):
        assert tools == []
        assert MONITOR_SYSTEM_PROMPT in client.system
        assert REVIEW_MODE_PROMPT not in client.system
        assert "not an active review" in client.system
        assert client.history[0] == before_history[0]
        if failure:
            raise RuntimeError("transport failure")
        return [{"type": "text", "text": "Cause uncertain; inspect accepted experiment."}], {}

    monkeypatch.setattr(client, "_request", request)
    if failure:
        with pytest.raises(RuntimeError, match="transport failure"):
            monitor._prepare_continuation()
    else:
        assert "Cause uncertain" in monitor._prepare_continuation()
    assert client.system == before_system
    assert client.history == before_history


def review(index, size=1200):
    return [
        {"role": "user", "content": [{"type": "text", "text": f"wake {index}"}]},
        {"role": "assistant", "content": [{"type": "tool_use", "id": f"r{index}",
                                               "name": "file_read", "input": {}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": f"r{index}",
                                         "content": "evidence" * size}]},
        {"role": "assistant", "content": [{"type": "tool_use", "id": f"w{index}",
                                               "name": "wait", "input": {"after_turns": 1}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": f"w{index}",
                                         "content": "accepted"}]},
    ]


def setup_monitor(tmp_path):
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    client = MonitorProviderClient("openai", {
        "apikey": "test", "apibase": "https://example.test", "model": "test",
        "monitor_history_char_limit": 30000,
    })
    monitor = MonitorAgent(client, MonitorWorkspace(evidence, tmp_path / "private"))
    return client, monitor


def test_planned_compaction_archives_full_evidence_and_keeps_recent_dialogue(tmp_path, monkeypatch):
    client, monitor = setup_monitor(tmp_path)
    client.history = sum((review(i) for i in range(6)), [])
    before = client.export_history()
    recent = before[-10:]
    calls = []
    def request(tools):
        calls.append(1)
        assert client.history[:-1] == before
        return [{"type": "text", "text": "Uncertain cause; compare original semantics."}], {}
    monkeypatch.setattr(client, "_request", request)
    client._compact_history()
    assert client.history[-10:] == recent
    transform = client.history_transforms[-1]
    archived = monitor.workspace.private_root / transform["archive"].removeprefix("monitor/")
    assert json.loads(archived.read_text(encoding="utf-8")) == before
    assert transform["target_reached"]
    client._compact_history()
    assert len(calls) == 1
    wire = client._responses_history()
    assert {x['call_id'] for x in wire if x.get('type') == 'function_call'} == {
        x['call_id'] for x in wire if x.get('type') == 'function_call_output'}


def test_large_current_result_is_retrievable_without_paid_note(tmp_path, monkeypatch):
    client, monitor = setup_monitor(tmp_path)
    client.history = review(1, 6000)
    before = client.export_history()
    def unexpected(_):
        pytest.fail("no useful prefix retirement, so no maintenance request")
    monkeypatch.setattr(client, "_request", unexpected)
    client._compact_history()
    client._compact_history()
    assert client.history != before
    transform = client.history_transforms[-1]
    assert transform['kind'] == 'monitor_tool_payload_archival'
    path = monitor.workspace.private_root / transform['archive'].removeprefix('monitor/')
    assert json.loads(path.read_text(encoding='utf-8')) == before
    assert "Middle archived" in client.history[2]['content'][0]['content']
    assert client.history_measure()['characters'] <= client.history_target_chars


def test_failed_planned_handoff_keeps_history_and_previous_note(tmp_path, monkeypatch):
    client, monitor = setup_monitor(tmp_path)
    monitor._atomic_private_text("working.md", "Previous understanding")
    client.history = sum((review(i) for i in range(6)), [])
    before = client.export_history()
    monkeypatch.setattr(client, "_request", lambda _: ([], {}))
    with pytest.raises(ValueError, match="Empty continuation"):
        client._compact_history()
    assert client.history == before
    assert (monitor.workspace.private_root / "working.md").read_text() == "Previous understanding"
    assert not client.history_transforms


def test_second_compaction_replaces_old_carried_note(tmp_path, monkeypatch):
    client, _ = setup_monitor(tmp_path)
    client.history = sum((review(i) for i in range(6)), [])
    notes = iter(["old judgment", "revised judgment"])
    monkeypatch.setattr(client, "_request", lambda _: ([{"type": "text", "text": next(notes)}], {}))
    client._compact_history()
    client.history.extend(sum((review(i) for i in range(6, 10)), []))
    client._compact_history()
    assert "revised judgment" in json.dumps(client.history)
    assert "old judgment" not in json.dumps(client.history)


def test_archive_failure_prevents_model_call_and_history_loss(tmp_path, monkeypatch):
    client, _ = setup_monitor(tmp_path)
    client.history = sum((review(i) for i in range(6)), [])
    before = client.export_history()
    def archive_failure(_):
        raise OSError("archive unavailable")
    monkeypatch.setattr(client, "archive_continuation_history", archive_failure)
    monkeypatch.setattr(client, "_request", lambda _: pytest.fail("must archive before paying"))
    with pytest.raises(OSError, match="archive unavailable"):
        client._compact_history()
    assert client.history == before


def test_oversized_non_payload_dialogue_fails_before_request(tmp_path, monkeypatch):
    from monitor_agent_core.provider import ProviderError
    client, _ = setup_monitor(tmp_path)
    client.history = [{'role': 'user', 'content': [{'type': 'text', 'text': 'x' * 40000}]}]
    before = client.export_history()
    monkeypatch.setattr(client, '_request', lambda _: pytest.fail('must not send oversized history'))
    with pytest.raises(ProviderError, match='over capacity'):
        client._compact_history()
    assert client.history == before
