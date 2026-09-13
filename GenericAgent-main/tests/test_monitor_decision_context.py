import json
from pathlib import Path

import pytest

from monitor_agent_core.decision_context import DecisionContext
from monitor_agent_core.workspace import MonitorWorkspace


@pytest.fixture
def view(tmp_path):
    evidence = tmp_path / 'evidence'
    evidence.mkdir()
    (evidence / 'original_task.txt').write_text('Keep the literal contract.', encoding='utf-8')
    workspace = MonitorWorkspace(evidence, tmp_path / 'private')
    workspace.write_text('monitor/working.md', 'Current uncertainty, not a verdict.')
    return DecisionContext(workspace)


def append(view, number, content='public reasoning'):
    for name, record in [
        ('public_events.jsonl', dict(archive_sequence=number, text=content)),
        ('synopsis.jsonl', dict(cursor=number, intent=content, raw_event=f'public_events.jsonl#{number}')),
    ]:
        with (view.workspace.evidence_root / name).open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(record) + '\n')


def overview(view):
    return view.workspace.resolve_read('monitor/overview.md').read_text(encoding='utf-8')


def test_entry_not_packet_and_model_note_remains_owned(view):
    append(view, 1, 'Inspect actual behavior')
    text = view.attention()
    assert 'monitor/overview.md' in text
    assert 'Inspect actual behavior' not in text
    entry = overview(view)
    assert 'Inspect actual behavior' in entry
    assert 'task/original_task.txt' in entry and 'task/public_events.jsonl' in entry
    assert 'Current uncertainty' not in entry  # link, not another summary copy
    assert view.workspace.resolve_read('monitor/working.md').read_text() == 'Current uncertainty, not a verdict.'
    assert not hasattr(view, 'read')  # no retired composite retrieval API


def test_latest_records_not_field_fragments_and_earlier_sources_survive(view):
    for n in range(1, 7):
        append(view, n, f'Unique{n} ' + 'x' * 2000 + ' END')
    with (view.workspace.evidence_root / 'synopsis.jsonl').open('a') as stream:
        stream.write('{partial')
    view.attention()
    text = overview(view)
    assert 'Unique6 ' in text and 'Unique1 ' not in text
    assert text.count(' END') == 4
    assert 'not all changes since you last looked' in text
    assert 'Unique1 ' in view.workspace.resolve_read('task/synopsis.jsonl').read_text()


def test_correction_receipt_and_new_progress_survive_new_view(view):
    append(view, 1, 'Before correction')
    view.record_input('Check the oracle')
    append(view, 2, 'Now checking')
    DecisionContext(view.workspace).attention()
    assert 'Now checking' in overview(view) and 'Check the oracle' in overview(view)
    receipt = view._receipt()
    assert receipt['cursor_at_submission'] == 1


def test_missing_sources_and_isolation(view, tmp_path):
    view.attention()
    assert 'No complete synopsis' in overview(view)
    other = tmp_path / 'other'
    other.mkdir()
    new = DecisionContext(MonitorWorkspace(other, tmp_path / 'other-private'))
    new.attention()
    assert 'Current uncertainty' not in overview(new)


def test_refresh_failure_does_not_claim_freshness(view, monkeypatch):
    monkeypatch.setattr(view.workspace, 'write_text', lambda *a: (_ for _ in ()).throw(OSError('fixture')))
    assert 'refresh failed' in view.attention()


def test_same_monitor_uses_files_corrects_and_observes_without_new_tools(view, monkeypatch):
    from monitor_agent_core.agent import MonitorAgent
    from monitor_agent_core.provider import MonitorProviderClient
    append(view, 1, 'Initial mistaken interpretation')
    client = MonitorProviderClient('openai', {'apikey': 'fixture', 'apibase': 'https://example.test',
        'monitor_decision_context': True, 'monitor_active_working_context': True})
    monitor = MonitorAgent(client, view.workspace)
    messages = []
    monitor.intervention_callback = lambda text: messages.append(text) or {'status': 'queued'}
    actions = iter([
        ('file_read', {'path': 'monitor/overview.md'}),
        ('file_write', {'path': 'monitor/working.md', 'content': 'Check the original oracle.'}),
        ('intervene', {'message': 'Compare the test with the original requirement.'}),
        ('file_read', {'path': 'task/public_events.jsonl', 'tail': True}),
        ('wait', {'after_turns': 1}),
    ])
    calls = []
    def request(tools):
        names = {t['function']['name'] for t in tools}
        assert 'review_context' not in names and 'task_control' not in names
        assert {'file_read', 'file_write', 'file_patch', 'code_run', 'wait', 'intervene', 'allow_complete'} <= names
        name, args = next(actions)
        if len(calls) == 3:
            append(view, 2, 'I will correct the mistaken test, not the production contract.')
        calls.append(name)
        return [{'type': 'tool_use', 'id': str(len(calls)), 'name': name, 'input': args}], {}
    monkeypatch.setattr(client, '_request_once', request)
    result = monitor.review('Inspect public progress')
    assert result.kind == 'wait' and len(messages) == 1 and len(calls) == 5
    history = json.dumps(client.export_history())
    assert 'correct the mistaken test' in history and 'Check the original oracle' in history
    active = monitor._active_working_context()
    assert 'Check the original oracle' not in active  # read on demand, not repeated automatic injection
    wire = client._responses_history()
    assert {r['call_id'] for r in wire if r.get('type') == 'function_call'} == {
        r['call_id'] for r in wire if r.get('type') == 'function_call_output'}


def test_file_entry_context_is_request_local(view):
    from monitor_agent_core.agent import MonitorAgent
    from monitor_agent_core.provider import MonitorProviderClient
    client = MonitorProviderClient('openai', {'apikey': 'fixture', 'apibase': 'https://example.test',
                                            'monitor_decision_context': True})
    MonitorAgent(client, view.workspace)
    before = list(client.history)
    seen = []
    client._request_with_recovery = lambda tools: seen.append(client.history[-1]['content'][0]['text'])
    for _ in range(3):
        client._request([{}])
    assert all('monitor/overview.md' in text for text in seen)
    assert client.history == before


def test_upstream_text_identity_and_behavior():
    from monitor_agent_core.vendor.pma_bm25 import BM25Index
    root = Path(__file__).resolve().parents[2]
    vendor = root / 'GenericAgent-main/monitor_agent_core/vendor'
    pma = root / 'some_research/research_library/02_direct_methods/repositories/yifannnwu__proactive-memory-agent/src/memory_agent/memory'
    liveplan = root / 'some_research/research_library/05_safety_and_monitoring/repositories/Intelligent-CAT-Lab__Agent-Planner/plan_refiner'
    if not pma.exists() or not liveplan.exists():
        pytest.skip('upstream library is not required at deployment')
    for local, source in [('pma_bm25.py', pma / 'bm25_search.py'),
                          ('liveplan_types.py', liveplan / 'types.py'),
                          ('liveplan_formatters.py', liveplan / 'formatters.py')]:
        expected = source.read_text(encoding='utf-8').replace(
            'from plan_refiner.types import', 'from .liveplan_types import').strip()
        assert (vendor / local).read_text(encoding='utf-8').strip() == expected
    assert BM25Index(['alpha beta', 'gamma', 'alpha']).search('gamma') == [1]
