import json

import pytest

from monitor_agent_core.agent import MonitorAgent, MONITOR_TOOLS
from monitor_agent_core.advice_basis import advice_tools
from monitor_agent_core.workspace import MonitorWorkspace
from test_monitor_agent import SequenceClient, response


def make_monitor(tmp_path, enabled=True, responses=()):
    evidence = tmp_path / 'evidence'
    evidence.mkdir(exist_ok=True)
    (evidence / 'original_task.txt').write_text('Keep the public contract.', encoding='utf-8')
    client = SequenceClient(responses)
    client.config = {'monitor_advice_revision': enabled}
    return MonitorAgent(client, MonitorWorkspace(evidence, tmp_path / 'private'))


def test_optional_basis_does_not_change_original_tools():
    changed = advice_tools(MONITOR_TOOLS)
    original = next(t['function'] for t in MONITOR_TOOLS if t['function']['name'] == 'intervene')
    revised = next(t['function'] for t in changed if t['function']['name'] == 'intervene')
    assert revised['parameters']['required'] == ['message']
    assert 'basis' in revised['parameters']['properties']
    assert 'basis' not in original['parameters']['properties']
    assert len(changed) == len(MONITOR_TOOLS)


def test_send_first_private_basis_never_leaks_and_next_wake_restores(tmp_path):
    m = make_monitor(tmp_path, responses=[response('wait', {'after_turns': 1})])
    sent = []

    def send(message):
        assert not (m.workspace.private_root / 'advice.md').exists()
        sent.append(message)
        return {'submitted': True}

    m.intervention_callback = send
    result = m.dispatch('intervene', {'message': 'Check the mismatch.', 'basis': 'My explanation may be wrong.'})
    assert sent == ['Check the mismatch.']
    assert result.data['status'] == 'submitted'
    assert m._refresh_review_context() is None  # no redundant echo in current exchange
    m.review('New task progress.')
    assert 'My explanation may be wrong.' in json.dumps(m.client.history)
    assert m._refresh_review_context() is None


def test_revise_clear_archive_and_wait_do_not_erase_root_or_approve(tmp_path):
    m = make_monitor(tmp_path)
    m.dispatch('intervene', {'message': 'Investigate.', 'basis': 'Initial hypothesis.'})
    m.dispatch('file_write', {'path': 'monitor/advice.md', 'content': 'Retract hypothesis; evidence disagrees.'})
    assert 'Retract hypothesis' in m._refresh_review_context()
    assert m.dispatch('wait', {'after_turns': 2}).action.kind == 'wait'
    assert 'Retract hypothesis' in (m.workspace.private_root / 'advice.md').read_text()
    m.dispatch('file_write', {'path': 'monitor/advice.md', 'content': ''})
    assert 'does not approve root completion' in m._refresh_review_context()
    assert m.dispatch('allow_complete', {}).action is None
    archives = list((m.workspace.private_root / 'audit/advice').glob('*.md'))
    assert any('Initial hypothesis' in p.read_text() for p in archives)
    assert any('Retract hypothesis' in p.read_text() for p in archives)


def test_missing_basis_is_not_a_gate_and_duplicate_does_not_rewrite(tmp_path):
    m = make_monitor(tmp_path)
    m.intervention_callback = lambda message: {}
    assert m.dispatch('intervene', {'message': 'Correct this.'}).data['status'] == 'submitted'
    path = m.workspace.private_root / 'advice.md'
    old = path.read_text()
    assert 'No separate grounds' in old
    assert m.dispatch('intervene', {'message': 'Correct this.', 'basis': 'New'}).data['status'] == 'already_submitted'
    assert path.read_text() == old


def test_failed_submission_never_stores_as_success(tmp_path):
    m = make_monitor(tmp_path)

    def fail(message):
        raise RuntimeError('delivery unavailable')

    m.intervention_callback = fail
    assert m.dispatch('intervene', {'message': 'Correct this.'}).data['status'] == 'error'
    assert not (m.workspace.private_root / 'advice.md').exists()


def test_storage_failure_does_not_relabel_submitted_input(tmp_path, monkeypatch):
    m = make_monitor(tmp_path)
    sent = []
    m.intervention_callback = lambda message: sent.append(message)

    def fail(*args):
        raise OSError('disk unavailable')

    monkeypatch.setattr(m.advice_basis, 'atomic_write', fail)
    result = m.dispatch('intervene', {'message': 'Correct this.'})
    assert result.data['status'] == 'submitted'
    assert 'private_advice_error' in result.data
    assert sent == ['Correct this.']


def test_disabled_candidate_and_separate_task_have_no_note(tmp_path):
    m = make_monitor(tmp_path, enabled=False)
    assert m.dispatch('intervene', {'message': 'Correct this.'}).action.kind == 'intervene'
    assert not (m.workspace.private_root / 'advice.md').exists()
    other = tmp_path / 'other'
    other.mkdir()
    fresh = make_monitor(other)
    assert fresh._refresh_review_context() is None


def test_long_note_is_explicit_preview_and_full_text_remains_accessible(tmp_path):
    m = make_monitor(tmp_path)
    text = 'x' * 7000 + ' crucial tail'
    m.dispatch('file_write', {'path': 'monitor/advice.md', 'content': text})
    preview = m._refresh_review_context()
    assert 'Preview ends' in preview and 'crucial tail' not in preview
    assert m.workspace.read_text('monitor/advice.md')['content'] == text


def test_persistent_file_survives_fresh_monitor_history(tmp_path):
    first = make_monitor(tmp_path)
    first.dispatch('intervene', {'message': 'Check.', 'basis': 'Uncertain cause.'})
    resumed = make_monitor(tmp_path)
    assert resumed.client.history == []
    assert 'Uncertain cause.' in resumed._refresh_review_context()


@pytest.mark.parametrize('value', ['0', '1', 'bad', None])
def test_adapter_validates_r_switch_without_mutating_provider_config(tmp_path, monkeypatch, value):
    import ga_monitor_adapter as adapter
    for name in ['GA_MONITOR_ADVICE_REVISION', 'GA_MONITOR_HANDOFF_VALIDATION', 'GA_MONITOR_GROUNDED_CONTEXT']:
        monkeypatch.delenv(name, raising=False)
    if value is not None:
        monkeypatch.setenv('GA_MONITOR_ADVICE_REVISION', value)
    captured = {}
    monkeypatch.setattr(adapter, 'MonitorRuntime', lambda **kw: captured.update(kw))
    original = {'model': 'fixture'}
    if value == 'bad':
        with pytest.raises(ValueError):
            adapter.GenericAgentMonitorAdapter(task_workspace=tmp_path, public_task='Task', model_config=original)
    else:
        adapter.GenericAgentMonitorAdapter(task_workspace=tmp_path, public_task='Task', model_config=original)
        assert captured['model_config'].get('monitor_advice_revision') == (None if value is None else value == '1')
    assert original == {'model': 'fixture'}


def test_prepare_r_only_keeps_common_task_and_never_executes(tmp_path, monkeypatch):
    from pathlib import Path
    method = Path(__file__).resolve().parents[2] / 'method_discovery'
    monkeypatch.syspath_prepend(str(method))
    import prepare_advice_r_run as prepare
    observed = []

    def build(task, suffix, output):
        observed.append((task, suffix))
        return {'status': 'prepared_not_executed', 'runs': [{'environment': {}}]}

    monkeypatch.setattr(prepare, 'build_manifest', build)
    out = tmp_path / 'manifest.json'
    data = prepare.prepare(out, 'r-test')
    env = data['runs'][0]['environment']
    assert observed == [('roadmapbench:fyn-2.2.0-roadmap', 'r-test')]
    assert env['GA_MONITOR_ADVICE_REVISION'] == '1'
    assert env['GA_MONITOR_GROUNDED_CONTEXT'] == env['GA_MONITOR_HANDOFF_VALIDATION'] == '0'
    assert data['status'] == 'prepared_not_executed'
    with pytest.raises(FileExistsError):
        prepare.prepare(out, 'overwrite')
