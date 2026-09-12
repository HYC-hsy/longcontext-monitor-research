import json

import pytest

from monitor_agent_core.agent import MonitorAgent
from monitor_agent_core.workspace import MonitorWorkspace
from test_monitor_agent import SequenceClient, response


def make(tmp_path, enabled=True):
    evidence = tmp_path / 'evidence'
    evidence.mkdir(exist_ok=True)
    client = SequenceClient([response('wait', {'after_turns': 1})])
    client.config = {'monitor_feedback_focus': enabled}
    return MonitorAgent(client, MonitorWorkspace(evidence, tmp_path / 'private'))


def test_incremental_feedback_not_repeated_basis_and_same_task_restart(tmp_path):
    m = make(tmp_path)
    source = m.workspace.evidence_root / 'public_events.jsonl'
    source.write_text('{"intent":"old"}\n', encoding='utf-8')
    f = m.feedback_focus
    f.call('begin', note='Restore original behavior, not just report accuracy.')
    with source.open('a', encoding='utf-8') as s:
        s.write('{"intent":"I will only update the report"}\n')
    m.workspace.write_text('monitor/delivery_feedback.jsonl', '{"delivery":"sent"}\n')
    first = f.call('read')
    assert 'only update the report' in first['public']['text']
    assert 'old' not in first['public']['text']
    assert 'sent' in first['delivery']['text']
    assert f.call('read')['public']['text'] == ''
    m.dispatch('file_write', {'path': 'monitor/focus.md', 'content': 'Cleanup done; behavior still missing.'})
    resumed = make(tmp_path)
    result = resumed.feedback_focus.call('read')
    assert result['note'] == 'Cleanup done; behavior still missing.'
    assert result['public']['text'] == ''
    assert m._refresh_review_context() is None  # no automatic passive injection


def test_paged_unicode_and_rewind_no_lost_evidence(tmp_path):
    m = make(tmp_path)
    data = json.dumps({'text': '证据' * 2000}, ensure_ascii=False) + '\n'
    source = m.workspace.evidence_root / 'public_events.jsonl'
    source.write_text(data, encoding='utf-8')
    m.feedback_focus.call('begin', note='Inspect.', after_event=0)
    parts = []
    while True:
        page = m.feedback_focus.call('read', limit=257)['public']
        parts.append(page['text'])
        if not page['more']:
            break
    assert ''.join(parts).encode('utf-8') == source.read_bytes()
    m.feedback_focus.call('begin', note='Revisit.', after_event=0)
    assert m.feedback_focus.call('read')['public']['text']


def test_close_is_not_completion_or_message_and_disabled_is_inert(tmp_path):
    m = make(tmp_path)
    m.feedback_focus.call('begin', note='Concern.')
    result = m.dispatch('feedback_focus', {'action': 'close'})
    assert result.action is None and result.data['status'] == 'closed'
    assert m.dispatch('allow_complete', {}).data['status'] == 'error'
    assert m.dispatch('wait', {'after_turns': 2}).action.kind == 'wait'
    assert m.feedback_focus.call('read')['status'] == 'inactive'
    off = make(tmp_path, False)
    assert off.feedback_focus is None
    assert off.dispatch('feedback_focus', {'action': 'read'}).data['status'] == 'error'


def test_failed_read_does_not_consume_and_no_cross_task_state(tmp_path):
    m = make(tmp_path)
    source = m.workspace.evidence_root / 'public_events.jsonl'
    source.write_text('first\n', encoding='utf-8')
    m.feedback_focus.call('begin', note='Follow.', after_event=0)
    m.feedback_focus.call('read')
    source.write_text('', encoding='utf-8')
    with pytest.raises(ValueError, match='truncated'):
        m.feedback_focus.call('read')
    other = tmp_path / 'other'
    other.mkdir()
    assert make(other).feedback_focus.call('read')['status'] == 'inactive'


def test_unfinished_event_at_begin_is_not_skipped(tmp_path):
    m = make(tmp_path)
    p = m.workspace.evidence_root / 'public_events.jsonl'
    p.write_bytes(b'{"intent":')
    m.feedback_focus.call('begin', note='Follow.')
    with p.open('ab') as s:
        s.write(b'"new"}\n')
    assert m.feedback_focus.call('read')['public']['text'] == '{"intent":"new"}\n'


def test_real_tool_loop_follows_intervention_then_public_response(tmp_path):
    m = make(tmp_path)
    m.client.responses = iter([
        response('feedback_focus', {'action': 'begin', 'note': 'Restore behavior.'}),
        response('intervene', {'message': 'Check the missing behavior, not only the report.'}),
        response('feedback_focus', {'action': 'read'}),
        response('wait', {'after_turns': 1}),
    ])
    sent = []

    def deliver(message):
        sent.append(message)
        (m.workspace.evidence_root / 'public_events.jsonl').write_text(
            '{"intent":"I will investigate the behavior"}\n', encoding='utf-8')
        m.workspace.write_text('monitor/delivery_feedback.jsonl', '{"delivery":"handed_over"}\n')
        return {'submitted': True}

    m.intervention_callback = deliver
    action = m.review('Observe current task.')
    assert action.kind == 'wait' and len(sent) == 1
    history = json.dumps(m.client.history)
    assert 'I will investigate the behavior' in history and 'handed_over' in history
    assert 'A read is not understanding or resolution' in history
    assert m.feedback_focus._state()['active']  # wait is not a local close


@pytest.mark.parametrize('enabled', [True, False])
def test_tool_surface_optional_and_live_intervention_unchanged(tmp_path, enabled):
    m = make(tmp_path, enabled)
    m.intervention_callback = lambda message: {'sent': message}
    result = m.dispatch('intervene', {'message': 'Inspect the original requirement.'})
    assert result.data['status'] == 'submitted'
    assert not (m.workspace.private_root / 'focus.md').exists()
    m.review('Observe.')
    assert m.client.history
    assert ('feedback_focus' in json.dumps(m.client.history)) == enabled


@pytest.mark.parametrize('value', ['0', '1', 'bad'])
def test_adapter_b_switch_is_validated(monkeypatch, value):
    import ga_monitor_adapter as adapter
    monkeypatch.setenv('GA_MONITOR_FEEDBACK_FOCUS', value)
    captured = {}
    monkeypatch.setattr(adapter, 'MonitorRuntime', lambda **kw: captured.update(kw))
    original = {'model': 'fixture'}
    if value == 'bad':
        with pytest.raises(ValueError):
            adapter.GenericAgentMonitorAdapter(model_config=original)
    else:
        adapter.GenericAgentMonitorAdapter(model_config=original)
        assert captured['model_config']['monitor_feedback_focus'] == (value == '1')
    assert original == {'model': 'fixture'}


@pytest.mark.parametrize('enabled', [True, False])
def test_prepare_common_task_no_execution_and_no_uwr(tmp_path, monkeypatch, enabled):
    from pathlib import Path
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / 'method_discovery'))
    import prepare_feedback_b_run as prepare
    calls = []

    def build(task, suffix, output):
        calls.append((task, suffix))
        return {'status': 'prepared_not_executed', 'runs': [{'environment': {}}]}

    monkeypatch.setattr(prepare, 'build_manifest', build)
    path = tmp_path / 'manifest.json'
    data = prepare.prepare(path, 'b-fixture', enabled)
    env = data['runs'][0]['environment']
    assert env['GA_MONITOR_FEEDBACK_FOCUS'] == ('1' if enabled else '0')
    assert all(env['GA_MONITOR_' + name] == '0' for name in [
        'GROUNDED_CONTEXT', 'HANDOFF_VALIDATION', 'ADVICE_REVISION'])
    assert calls == [('roadmapbench:fyn-2.2.0-roadmap', 'b-fixture')]
    assert data['status'] == 'prepared_not_executed'
    with pytest.raises(FileExistsError):
        prepare.prepare(path, 'new')
