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
        stream.write(json.dumps(dict(archive_sequence=number, response_content=content,
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
