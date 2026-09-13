import json
from pathlib import Path

import pytest

from monitor_agent_core.decision_context import DecisionContext
from monitor_agent_core.workspace import MonitorWorkspace
from monitor_agent_core.vendor.pma_bm25 import BM25Index


@pytest.fixture
def view(tmp_path):
    evidence = tmp_path / 'evidence'
    evidence.mkdir()
    (evidence / 'original_task.txt').write_text('Keep the literal contract.', encoding='utf-8')
    workspace = MonitorWorkspace(evidence, tmp_path / 'private')
    workspace.write_text('monitor/working.md', 'Current uncertainty, not a verdict.')
    return DecisionContext(workspace)


def append(view, number, content='public reasoning'):
    path = view.workspace.evidence_root / 'public_events.jsonl'
    with path.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(dict(archive_sequence=number, text=content,
                     tool_calls=[{'name': 'any_tool'}], tool_results=['observed']), ensure_ascii=False) + '\n')


def test_original_task_note_and_actual_events_together(view):
    append(view, 1, 'Intent before editing')
    result = view.read()
    assert 'literal contract' in result['context']
    assert 'Current uncertainty' in result['context']
    assert 'Intent before editing' in result['context']
    assert 'any_tool' in result['context']
    assert result['sources'] == ['task/public_events.jsonl#L1']


def test_input_followup_excludes_earlier_but_preserves_latest_advice(view):
    append(view, 1, 'old intent')
    view.record_input('Check whether the test assumes the wrong oracle.')
    append(view, 2, 'I will compare the original requirement first.')
    result = DecisionContext(view.workspace).read(after_correction=True)
    assert 'old intent' not in result['context']
    assert 'wrong oracle' in result['context']
    assert 'compare the original' in result['context']
    assert result['after_submission_cursor'] == 1


def test_no_new_evidence_is_explicit_not_recovery(view):
    append(view, 1)
    view.record_input('One correction')
    result = view.read(after_correction=True)
    assert result['sources'] == []
    assert 'Submission does not prove uptake' in result['limits']


def test_default_followup_can_be_overridden(view):
    append(view, 1, 'earlier evidence')
    view.record_input('Reconsider')
    assert view.read()['sources'] == []
    assert view.read(after_correction=False)['sources'] == ['task/public_events.jsonl#L1']


def test_large_actions_are_previews_and_originals_survive(view):
    for n in range(1, 33):
        path = view.workspace.evidence_root / 'public_events.jsonl'
        with path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'archive_sequence': n, 'tool_calls': ['x' * 50000],
                                     'tool_results': ['y' * 50000]}) + '\n')
    result = view.read(steps=32)
    assert len(result['context']) < 20000
    assert 'Preview clipped' in result['context']
    assert path.stat().st_size > 3000000


def test_query_retrieves_late_task_clause_without_duplicate_working(view):
    task = ('Irrelevant preamble.\n' * 200) + '\nUnique quasar contract requires reflection.\n'
    (view.workspace.evidence_root / 'original_task.txt').write_text(task)
    result = view.read(query='quasar reflection')
    assert 'Unique quasar contract' in result['context']
    assert 'task/original_task.txt#L' in result['context']
    assert result['context'].count('Current uncertainty') == 1


def test_attention_is_current_first_layer_not_original_packets(view):
    path = view.workspace.evidence_root / 'synopsis.jsonl'
    path.write_text('\n'.join(json.dumps({'cursor': n, 'intent': f'intent{n}'}) for n in range(1, 7)) + '\n{partial')
    text = view.attention()
    assert 'intent6' in text and 'intent1' not in text
    assert len(text) < 6500
    assert 'not proof' in text
    path.write_text(json.dumps({'cursor': 7, 'intent': 'changed course'}) + '\n')
    assert 'changed course' in view.attention()


def test_attention_does_not_accumulate_in_session(view):
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
    assert len(seen) == 3 and all('Current first-layer synopsis' in text for text in seen)
    assert client.history == before


def test_query_retrieval_preserves_source_and_excludes_audit(view):
    view.workspace.write_text('monitor/notes/alpha.md', 'listener notification contradicts earlier assumption')
    view.workspace.write_text('monitor/notes/beta.md', 'unrelated build setting')
    view.workspace.write_text('monitor/audit/leaked.md', 'listener SECRET')
    result = view.read(query='listener notification')
    assert 'alpha.md#L1' in result['context']
    assert 'SECRET' not in result['context']
    assert 'unrelated build setting' not in result['context']


def test_bounded_window_and_malformed_tail(view):
    for n in range(1, 12):
        append(view, n)
    with (view.workspace.evidence_root / 'public_events.jsonl').open('a') as stream:
        stream.write('{partial')
    result = view.read(steps=2)
    assert result['sources'] == ['task/public_events.jsonl#L10', 'task/public_events.jsonl#L11']
    assert result['malformed_records_skipped'] == 1
    assert 'not necessarily complete Agent turns' in result['limits']


def test_empty_and_different_task(view, tmp_path):
    assert view.read()['sources'] == []
    other = tmp_path / 'other'
    other.mkdir()
    (other / 'original_task.txt').write_text('Independent task')
    result = DecisionContext(MonitorWorkspace(other, tmp_path / 'other-private')).read()
    assert 'Current uncertainty' not in result['context']


def test_forward_followup_covers_first_reactions_and_continues(view):
    append(view, 1)
    view.record_input('Correction')
    for n in range(2, 10):
        append(view, n)
    page = view.read(order='forward', steps=3, include_context=False)
    assert page['sources'] == [f'task/public_events.jsonl#L{n}' for n in range(2, 5)]
    assert page['remaining_later_records'] == 5
    assert 'Current uncertainty' not in page['context']
    seen = list(page['sources'])
    while page['remaining_later_records']:
        page = view.read(**page['next_read'])
        seen.extend(page['sources'])
    assert seen == [f'task/public_events.jsonl#L{n}' for n in range(2, 10)]
    append(view, 10)
    assert view.read(**page['next_read'])['last_cursor'] == 10


def test_latest_reports_skipped_reactions_and_recovery(view):
    for n in range(1, 9):
        append(view, n)
    page = view.read(steps=2)
    assert page['skipped_earlier_records'] == 6
    first = view.read(**page['read_from_start'])
    assert first['sources'] == ['task/public_events.jsonl#L1', 'task/public_events.jsonl#L2']


def test_explicit_cursor_survives_new_correction(view):
    append(view, 1)
    page = view.read(order='forward')
    append(view, 2)
    view.record_input('New correction must not move an explicit read cursor')
    assert view.read(**page['next_read'])['last_cursor'] == 2


def test_upstream_text_identity_and_behavior():
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


@pytest.mark.parametrize('kwargs', [{'steps': 0}, {'steps': True}, {'query': None}, {'after_correction': 'false'}])
def test_invalid_arguments(view, kwargs):
    with pytest.raises(ValueError):
        view.read(**kwargs)


def test_same_monitor_reconstructs_corrects_then_observes_reaction(view, monkeypatch):
    from monitor_agent_core.agent import MonitorAgent
    from monitor_agent_core.provider import MonitorProviderClient
    append(view, 1, 'Initial mistaken interpretation')
    client = MonitorProviderClient('openai', {'apikey': 'fixture', 'apibase': 'https://example.test',
        'monitor_decision_context': True})
    monitor = MonitorAgent(client, view.workspace)
    messages = []
    monitor.intervention_callback = lambda text: messages.append(text) or {'status': 'queued'}
    actions = iter([
        ('review_context', {}),
        ('file_write', {'path': 'monitor/working.md', 'content': 'A test oracle can be wrong; check the original.'}),
        ('intervene', {'message': 'Compare the test with the original requirement.'}),
        ('review_context', {'after_correction': True}),
        ('wait', {'after_turns': 1}),
    ])
    calls = []
    def request(tools):
        assert 'task_control' not in {t['function']['name'] for t in tools}
        name, args = next(actions)
        if name == 'review_context' and args:
            append(view, 2, 'I will correct the mistaken test, not the production contract.')
        calls.append(name)
        return [{'type': 'tool_use', 'id': str(len(calls)), 'name': name, 'input': args}], {}
    monkeypatch.setattr(client, '_request_once', request)
    result = monitor.review('Inspect public progress')
    assert result.kind == 'wait'
    assert len(messages) == 1
    assert len(calls) == 5  # no hidden maintenance or classifier calls
    history = json.dumps(client.export_history())
    assert 'correct the mistaken test' in history and 'A test oracle can be wrong' in history
    wire = client._responses_history()
    assert {r['call_id'] for r in wire if r.get('type') == 'function_call'} == {
        r['call_id'] for r in wire if r.get('type') == 'function_call_output'}
