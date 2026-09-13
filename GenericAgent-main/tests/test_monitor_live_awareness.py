import json

import pytest

from monitor_agent_core.agent import MonitorAgent
from monitor_agent_core.live_awareness import LiveAwareness
from monitor_agent_core.provider import MonitorProviderClient
from monitor_agent_core.workspace import MonitorWorkspace


@pytest.fixture
def workspace(tmp_path):
    evidence = tmp_path / 'evidence'
    evidence.mkdir()
    return MonitorWorkspace(evidence, tmp_path / 'private')


def make_client(**flags):
    return MonitorProviderClient('openai', {
        'apikey': 'fixture', 'apibase': 'https://example.test', **flags,
    })


def test_activity_only_no_semantic_payload_or_file_rewrite(workspace):
    path = workspace.evidence_root / 'public_events.jsonl'
    path.write_text('UNTRUSTED PUBLIC CONTENT', encoding='utf-8')
    view = LiveAwareness(workspace)
    first, _ = view.context()
    assert 'present' in first and 'UNTRUSTED' not in first
    second, _ = view.context()
    assert 'public_events.jsonl: unchanged' in second
    path.write_text('NEW CONTENT', encoding='utf-8')
    third, _ = view.context()
    assert 'public_events.jsonl: changed' in third and 'NEW CONTENT' not in third
    assert path.read_text() == 'NEW CONTENT'


def test_missing_recreated_deleted_and_cross_task_state(workspace):
    view = LiveAwareness(workspace)
    assert 'not present' in view.context()[0]
    path = workspace.evidence_root / 'synopsis.jsonl'
    path.write_text('row\n', encoding='utf-8')
    assert 'synopsis.jsonl: changed' in view.context()[0]
    assert 'first sample' in LiveAwareness(workspace).context()[0]
    path.unlink()
    assert 'synopsis.jsonl: not present' in view.context()[0]


def test_tail_keeps_line_numbers_unicode_and_full_digest(workspace):
    path = workspace.evidence_root / 'events.txt'
    path.write_text('first\n第二行\nthird\nlast', encoding='utf-8')
    whole = workspace.read_text('task/events.txt')
    tail = workspace.read_text('task/events.txt', count=2, tail=True)
    assert tail['content'] == 'third\nlast'
    assert tail['start'] == 3 and tail['total_lines'] == 4
    assert tail['sha256'] == whole['sha256']
    assert workspace.read_text('task/events.txt', count=20, tail=True) == whole
    with pytest.raises(ValueError):
        workspace.read_text('task/events.txt', start=2, tail=True)


def test_candidate_independent_from_note_and_not_added_to_history(workspace):
    client = make_client(monitor_live_awareness=True)
    MonitorAgent(client, workspace)
    client.history = [{'role': 'user', 'content': [{'type': 'text', 'text': 'original'}]}]
    original = client.export_history()
    seen = []
    client._request_with_recovery = lambda tools: seen.append(client.export_history())
    client._request([{}])
    assert 'Live file activity' in json.dumps(seen[-1])
    assert client.history == original
    client._request([])
    assert seen[-1] == original  # no metadata poll during memory maintenance


def test_two_request_contexts_compose_without_losing_note(workspace):
    client = make_client(monitor_live_awareness=True, monitor_active_working_context=True)
    monitor = MonitorAgent(client, workspace)
    workspace.write_text('monitor/working.md', 'Unresolved grounds')
    content = monitor._active_working_context()
    assert 'Unresolved grounds' in content and 'Live file activity' in content


def test_permission_failure_is_not_silently_missing(workspace, monkeypatch):
    monkeypatch.setattr(workspace, 'resolve_read', lambda _: (_ for _ in ()).throw(PermissionError()))
    assert 'unavailable (PermissionError)' in LiveAwareness(workspace).context()[0]


def test_tail_tool_available_independently_of_awareness(workspace, monkeypatch):
    import monitor_agent_core.agent as module
    from monitor_agent_core.actions import MonitorAction
    captured = []
    def review(*args, **kwargs):
        captured.append(args[3])
        return MonitorAction('wait', {'after_turns': 1})
    monkeypatch.setattr(module, 'run_review', review)
    for enabled in [True, False]:
        monitor = MonitorAgent(make_client(monitor_live_awareness=enabled), workspace)
        monitor.review('fixture')
    assert 'tail' in captured[0][0]['function']['parameters']['properties']
    assert 'tail' in captured[1][0]['function']['parameters']['properties']
    assert [t['function']['name'] for t in captured[0]] == [t['function']['name'] for t in captured[1]]


def test_invalid_flag_rejected(workspace):
    with pytest.raises(ValueError, match='monitor_live_awareness'):
        MonitorAgent(make_client(monitor_live_awareness='false'), workspace)
