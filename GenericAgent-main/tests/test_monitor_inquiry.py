import json

import pytest

from monitor_agent_core.agent import MonitorAgent
from monitor_agent_core.workspace import MonitorWorkspace
from test_monitor_agent import SequenceClient, response


def make(tmp_path, enabled=True):
    evidence = tmp_path / 'evidence'
    evidence.mkdir(exist_ok=True)
    (evidence / 'original_task.txt').write_text('Original requirement\n', encoding='utf-8')
    client = SequenceClient([])
    client.config = {'monitor_inquiry': enabled}
    return MonitorAgent(client, MonitorWorkspace(evidence, tmp_path / 'private'))


def select(m):
    return m.dispatch('inquiry', {'action': 'open', 'question': 'Does this support the decision?',
                                'sources': [{'path': 'task/original_task.txt'}]})


def test_optional_no_forced_inquiry_and_no_control_gate(tmp_path):
    for enabled in [False, True]:
        m = make(tmp_path, enabled)
        m.client.responses = iter([response('intervene', {'message': 'Material discrepancy.'})])
        assert m.review('Inspect').kind == 'intervene'
        assert not (m.workspace.private_root / 'inquiry.json').exists()
        visible = json.dumps(m.client.history)
        assert ('"name": "inquiry"' in visible) is False  # tool schemas are in the audit
        audit = (m.workspace.private_root / 'audit/dialogue.jsonl').read_text(encoding='utf-8')
        context = [json.loads(x) for x in audit.splitlines() if json.loads(x)['event'] == 'review_context'][-1]
        assert ('inquiry' in [t['function']['name'] for t in context['tools']]) == enabled


def test_selected_sources_refresh_once_at_wake_without_new_call_or_session(tmp_path):
    m = make(tmp_path)
    assert select(m).data['sources'][0]['content'] == 'Original requirement\n'
    source = m.workspace.evidence_root / 'original_task.txt'
    source.write_text('Revised original material\n', encoding='utf-8')
    m.client.history.append({'role': 'user', 'content': 'Earlier investigation'})
    m.client.responses = iter([response('file_read', {'path': 'task/original_task.txt'}),
                               response('wait', {'after_turns': 3})])
    assert m.review('Continue').kind == 'wait'
    history = json.dumps(m.client.history)
    assert 'Earlier investigation' in history and 'Revised original material' in history
    assert history.count('Your selected investigation:') == 1
    assert len(list((m.workspace.private_root / 'audit/inquiry').glob('*.json'))) == 2
    assert m.inquiry.state()['active']  # wait does not close the investigation
    assert m._refresh_review_context() is None  # no per-call passive repetition


def test_close_keeps_history_and_never_approves_root(tmp_path):
    m = make(tmp_path)
    select(m)
    result = m.dispatch('inquiry', {'action': 'close'})
    assert result.action is None and result.data['status'] == 'closed'
    assert m.inquiry.restore() is None
    assert m.dispatch('allow_complete', {}).data['status'] == 'error'
    assert list((m.workspace.private_root / 'audit/inquiry').glob('*.json'))


def test_missing_truncated_and_shifted_sources_not_hidden(tmp_path):
    m = make(tmp_path)
    path = m.workspace.evidence_root / 'large.txt'
    path.write_text('x' * 12000, encoding='utf-8')
    result = m.inquiry.call('open', question='Inspect', sources=[{'path': 'task/large.txt'}])
    assert result['sources'][0]['truncated']
    assert len(result['sources'][0]['content']) == 3000
    assert m.workspace.read_text('task/large.txt')['content'] == 'x' * 12000
    path.unlink()
    assert 'error' in m.inquiry.restore()['sources'][0]
    assert m.inquiry.state()['active']


def test_invalid_selection_preserves_previous_and_tasks_do_not_share_state(tmp_path):
    m = make(tmp_path)
    select(m)
    before = m.inquiry.state()
    bad = m.dispatch('inquiry', {'action': 'open', 'question': 'replace',
                               'sources': [{'path': 'task/../secret'}]})
    assert bad.data['status'] == 'error' and m.inquiry.state() == before
    other = tmp_path / 'other'
    other.mkdir()
    assert make(other).inquiry.restore() is None


@pytest.mark.parametrize('value', ['0', '1', 'invalid'])
def test_adapter_switch(monkeypatch, value):
    import ga_monitor_adapter as adapter
    monkeypatch.setenv('GA_MONITOR_INQUIRY', value)
    captured = {}
    monkeypatch.setattr(adapter, 'MonitorRuntime', lambda **kw: captured.update(kw))
    config = {'model': 'fixture'}
    if value == 'invalid':
        with pytest.raises(ValueError):
            adapter.GenericAgentMonitorAdapter(model_config=config)
    else:
        adapter.GenericAgentMonitorAdapter(model_config=config)
        assert captured['model_config']['monitor_inquiry'] == (value == '1')
    assert config == {'model': 'fixture'}


@pytest.mark.parametrize('enabled', [True, False])
def test_prepare_a_isolated_from_other_candidates(tmp_path, monkeypatch, enabled):
    from pathlib import Path
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / 'method_discovery'))
    import prepare_inquiry_a_run as prepare
    tasks = []
    def build(task, suffix, output):
        tasks.append(task)
        return {'status': 'prepared_not_executed', 'runs': [{'environment': {}}]}
    monkeypatch.setattr(prepare, 'build_manifest', build)
    data = prepare.prepare(tmp_path / 'manifest.json', 'fixture', enabled)
    env = data['runs'][0]['environment']
    assert env['GA_MONITOR_INQUIRY'] == ('1' if enabled else '0')
    assert all(env['GA_MONITOR_' + key] == '0' for key in [
        'GROUNDED_CONTEXT', 'HANDOFF_VALIDATION', 'ADVICE_REVISION', 'FEEDBACK_FOCUS'])
    assert tasks == ['roadmapbench:fyn-2.2.0-roadmap']
    assert data['status'] == 'prepared_not_executed'
    with pytest.raises(FileExistsError):
        prepare.prepare(tmp_path / 'manifest.json', 'duplicate')


def test_live_input_can_precede_any_inquiry_and_review_continues(tmp_path):
    m = make(tmp_path)
    sent = []
    m.intervention_callback = lambda message: sent.append(message) or {'submitted': True}
    m.client.responses = iter([
        response('intervene', {'message': 'Restore the original requirement.'}),
        response('inquiry', {'action': 'open', 'question': 'What happened next?',
                            'sources': [{'path': 'task/original_task.txt'}]}),
        response('file_read', {'path': 'task/original_task.txt'}),
        response('wait', {'after_turns': 1}),
    ])
    assert m.review('Observe').kind == 'wait'
    assert sent == ['Restore the original requirement.']
    assert m.inquiry.state()['active']
