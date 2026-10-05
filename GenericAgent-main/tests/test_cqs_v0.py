"""CQS-v0 control continuity, exercised through the ordinary zero-network review loop."""

import json

import pytest

from monitor_agent_core.agent import MonitorAgent
from monitor_agent_core.provider import MonitorProviderClient
from monitor_agent_core.workspace import MonitorWorkspace


def make_monitor(tmp_path, *, enabled=True):
    evidence = tmp_path / 'evidence'
    evidence.mkdir(parents=True)
    (evidence / 'original_task.txt').write_text('Maintain the public route.', encoding='utf-8')
    task = tmp_path / 'task'
    task.mkdir()
    (task / 'router.py').write_text('ROUTE = True\n', encoding='utf-8')
    workspace = MonitorWorkspace(evidence, tmp_path / 'private', task_mounts={'workspace': task})
    workspace.write_text('monitor/working.md', 'PRIVATE_WORKING_SENTINEL')
    config = {'apikey': 'offline', 'apibase': 'https://offline.invalid', 'model': 'offline',
              'max_retries': 0, 'monitor_dcec': True, 'monitor_path_control_v0': True,
              'monitor_verification_loop_v0': True, 'monitor_verification_runtime_managed': False,
              'monitor_coarse_to_fine_surface': True,
              'monitor_decision_conditioned_measurement': True,
              'monitor_control_question_state': enabled}
    client = MonitorProviderClient('anthropic', config)
    monitor = MonitorAgent(client, workspace)
    monitor.task_budget_state = lambda: (42, 300)
    return monitor, client, workspace


def rows(workspace):
    path = workspace.private_root / 'audit/dialogue.jsonl'
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()] if path.exists() else []


def scripted(client, monkeypatch, calls):
    snapshots = []

    def offline_once(tools):
        snapshots.append(client.assembled_request_snapshot(tools))
        index = len(snapshots) - 1
        rationale, name, args = calls[index]
        blocks = ([{'type': 'text', 'text': rationale}] if rationale else [])
        blocks.append({'type': 'tool_use', 'id': f'call-{index}', 'name': name, 'input': args})
        return blocks, {}

    monkeypatch.setattr(client, '_request_once', offline_once)
    return snapshots


def visible(snapshot):
    return json.dumps(snapshot['messages'], ensure_ascii=False)


def root(monitor):
    handoff = {'generation': 1, 'request_id': 'handoff-1', 'cursor': 1}
    (monitor.workspace.evidence_root / 'public_events.jsonl').write_text(
        json.dumps({'archive_sequence': 1, 'task_turn': 1, 'boundary': 'completion',
                    'text': 'Ready for review.', 'tool_calls': [], 'tool_results': []}) + '\n',
        encoding='utf-8')
    monitor.completion_state = lambda: handoff
    return handoff


def test_off_on_contract_working_view_and_turn_zero(tmp_path, monkeypatch):
    off, off_client, off_ws = make_monitor(tmp_path / 'off', enabled=False)
    on, on_client, on_ws = make_monitor(tmp_path / 'on')
    off_sends = scripted(off_client, monkeypatch, [('', 'wait', {'mode': 'follow', 'after_turns': 1})])
    on_sends = scripted(on_client, monkeypatch, [('', 'wait', {'mode': 'follow', 'after_turns': 1})])
    assert off.review('Wake').kind == on.review('Wake').kind == 'wait'
    assert off_sends[0]['system'] == on_sends[0]['system']
    assert off_sends[0]['tools'] == on_sends[0]['tools']
    assert len(on_sends[0]['tools']) == 7
    assert 'PRIVATE_WORKING_SENTINEL' in visible(off_sends[0])
    assert 'PRIVATE_WORKING_SENTINEL' not in visible(on_sends[0])
    assert 'Supervisory Control Continuity' in visible(on_sends[0])
    assert 'No active concern is carried' in visible(on_sends[0])
    assert 'Supervisory Situation' in visible(on_sends[0])
    assert on.dispatch('file_read', {'path': 'monitor/working.md'}).data['content'] == 'PRIVATE_WORKING_SENTINEL'
    assert not any(row['event'] == 'cqs_surface_emitted' for row in rows(off_ws))
    assert any(row['event'] == 'cqs_surface_emitted' for row in rows(on_ws))


def test_intervene_same_review_follow_next_review_and_patrol_clear(tmp_path, monkeypatch):
    monitor, client, ws = make_monitor(tmp_path)
    monitor.intervention_callback = lambda message: {'delivery': 'queued'}
    sends = scripted(client, monkeypatch, [
        ('The route may diverge.', 'intervene', {'message': 'Inspect the route behavior.'}),
        ('Wait for its repair.', 'wait', {'mode': 'follow', 'after_turns': 1, 'reason': 'Await route repair'}),
    ])
    assert monitor.review('Wake').payload['mode'] == 'follow'
    assert 'Inspect the route behavior.' in visible(sends[1])
    assert 'The route may diverge.' in visible(sends[1])
    assert monitor.cqs.state['source'] == 'wait_follow'
    sends = scripted(client, monkeypatch, [
        ('', 'wait', {'mode': 'patrol', 'after_turns': 1}),
        ('', 'wait', {'mode': 'patrol', 'after_turns': 1}),
    ])
    assert monitor.review('Next wake').payload['mode'] == 'patrol'
    assert 'Await route repair' in visible(sends[0])
    assert monitor.cqs.state is None
    sends = scripted(client, monkeypatch, [('', 'wait', {'mode': 'follow', 'after_turns': 1})])
    monitor.review('Later wake')
    current_surface = visible(sends[0]).split('Supervisory Control Continuity')[-1]
    assert 'Inspect the route behavior.' not in current_surface
    assert 'No active concern is carried' in current_surface
    assert any(row['event'] == 'cqs_state_cleared' for row in rows(ws))


def test_failed_intervention_and_dcm_boundary_do_not_replace_state(tmp_path, monkeypatch):
    monitor, client, ws = make_monitor(tmp_path)
    monitor.intervention_callback = lambda message: {'delivery': 'queued'}
    scripted(client, monkeypatch, [
        ('Initial concern.', 'intervene', {'message': 'Check route.'}),
        ('', 'wait', {'mode': 'follow', 'after_turns': 1, 'reason': 'Await response'}),
    ])
    monitor.review('Wake')
    original = dict(monitor.cqs.state)
    monitor.intervention_callback = lambda message: (_ for _ in ()).throw(RuntimeError('delivery failed'))
    result = monitor.dispatch('intervene', {'message': 'Unsent correction.'})
    assert result.data['status'] == 'error' and monitor.cqs.state == original
    monitor.review_id = 'manual-review'
    monitor.cqs.begin_review('manual-review')
    monitor.dcm.begin_review('manual-review')
    first = monitor.dispatch('wait', {'mode': 'patrol', 'after_turns': 1})
    assert first.action is None and monitor.cqs.state == original
    monitor.intervention_callback = lambda message: {'delivery': 'queued'}
    submitted = monitor.dispatch('intervene', {'message': 'Revised correction.'})
    assert submitted.data['status'] == 'submitted'
    assert monitor.cqs.state['source'] == 'intervene'
    assert monitor.cqs.state['control_excerpt'] == 'Revised correction.'
    assert not any(row['event'] == 'cqs_state_cleared' for row in rows(ws))


def test_compaction_independent_state_and_config_gate(tmp_path, monkeypatch):
    monitor, client, ws = make_monitor(tmp_path / 'valid')
    monitor.intervention_callback = lambda message: {'delivery': 'queued'}
    scripted(client, monkeypatch, [
        ('Natural basis.', 'intervene', {'message': 'Review route.'}),
        ('', 'wait', {'mode': 'follow', 'after_turns': 1}),
    ])
    monitor.review('Wake')
    ws.write_text('monitor/working.md', 'REWRITTEN_AFTER_COMPACTION')
    client.restore_history([])
    sends = scripted(client, monkeypatch, [('', 'wait', {'mode': 'follow', 'after_turns': 1})])
    monitor.review('After continuation')
    assert 'Natural basis.' in visible(sends[0])
    assert 'REWRITTEN_AFTER_COMPACTION' not in visible(sends[0])
    for key, value in [('monitor_coarse_to_fine_surface', False),
                       ('monitor_decision_conditioned_measurement', False),
                       ('monitor_verification_runtime_managed', True),
                       ('monitor_executable_interpretation_surface', True)]:
        config = dict(client.config, **{key: value})
        with pytest.raises(ValueError):
            MonitorAgent(MonitorProviderClient('anthropic', config), ws)


def test_root_intervention_carries_same_state_and_stale_does_not(tmp_path, monkeypatch):
    monitor, client, _ = make_monitor(tmp_path)
    handoff = root(monitor)
    monitor.intervention_callback = lambda message: {'delivery': 'queued'}
    scripted(client, monkeypatch, [
        ('The current handoff needs a correction.', 'intervene',
         {'message': 'Inspect the public behavior before completion.'}),
    ])
    assert monitor.review('Root wake', completion_pending=True,
                          root_handoff=handoff).kind == 'root_intervened'
    assert monitor.cqs.state['source'] == 'intervene'
    assert monitor.cqs.state['control_excerpt'] == 'Inspect the public behavior before completion.'
    monitor.completion_state = lambda: None
    sends = scripted(client, monkeypatch, [('', 'wait', {'mode': 'follow', 'after_turns': 1})])
    monitor.review('Task resumed')
    assert 'Inspect the public behavior before completion.' in visible(sends[0])
    previous = dict(monitor.cqs.state)
    monitor.completion_state = lambda: handoff
    monitor._enter_root_frame(handoff)
    monitor._refresh_completion()
    monitor.completion_state = lambda: {**handoff, 'generation': 2}
    try:
        rejected = monitor.dispatch('intervene', {'message': 'Stale root correction.'})
        assert rejected.data['status'] == 'error'
        assert monitor.cqs.state == previous
    finally:
        monitor._leave_root_frame()


def test_root_dcm_boundary_preserves_state_and_is_not_second_mode(tmp_path, monkeypatch):
    monitor, client, _ = make_monitor(tmp_path)
    monitor.intervention_callback = lambda message: {'delivery': 'queued'}
    scripted(client, monkeypatch, [
        ('A source issue remains.', 'intervene', {'message': 'Review route source.'}),
        ('', 'wait', {'mode': 'follow', 'after_turns': 1, 'reason': 'Await source change'}),
    ])
    monitor.review('Wake')
    handoff = root(monitor)
    monitor._enter_root_frame(handoff)
    monitor._refresh_completion()
    monitor.review_id = 'root-review'
    monitor.cqs.begin_review('root-review')
    monitor.dcm.begin_review('root-review')
    try:
        before = dict(monitor.cqs.state)
        first = monitor.dispatch('allow_complete', {'result': 'resolve', 'reason': 'Ready'})
        assert first.action is None and monitor.cqs.state == before
        assert 'Await source change' in monitor.cqs.render()
        assert 'Root Control Continuity' not in monitor.cqs.render()
    finally:
        monitor._leave_root_frame()
