"""DCM-v0 release transitions, using only a zero-network scripted provider."""

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
    config = {'apikey': 'offline', 'apibase': 'https://offline.invalid', 'model': 'offline',
              'max_retries': 0, 'monitor_dcec': True, 'monitor_path_control_v0': True,
              'monitor_verification_loop_v0': True, 'monitor_verification_runtime_managed': False,
              'monitor_coarse_to_fine_surface': True,
              'monitor_decision_conditioned_measurement': enabled}
    client = MonitorProviderClient('anthropic', config)
    monitor = MonitorAgent(client, workspace)
    monitor.task_budget_state = lambda: (42, 300)
    return monitor, client, workspace


def events(workspace):
    path = workspace.private_root / 'audit/dialogue.jsonl'
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


def scripted(client, monkeypatch, calls):
    snapshots = []

    def offline_once(tools):
        snapshots.append(client.assembled_request_snapshot(tools))
        name, args = calls[len(snapshots) - 1]
        return ([{'type': 'tool_use', 'id': f'call-{len(snapshots)}',
                  'name': name, 'input': args}], {})

    monkeypatch.setattr(client, '_request_once', offline_once)
    return snapshots


def root(monitor):
    handoff = {'generation': 1, 'request_id': 'handoff-1', 'cursor': 1}
    (monitor.workspace.evidence_root / 'public_events.jsonl').write_text(
        json.dumps({'archive_sequence': 1, 'task_turn': 1, 'boundary': 'completion',
                    'text': 'Implementation is ready for review.', 'tool_calls': [],
                    'tool_results': []}) + '\n', encoding='utf-8')
    monitor.completion_state = lambda: handoff
    return handoff


def test_off_on_contract_equal_and_off_control_unchanged(tmp_path, monkeypatch):
    off, off_client, _ = make_monitor(tmp_path / 'off', enabled=False)
    on, on_client, _ = make_monitor(tmp_path / 'on')
    off_requests = scripted(off_client, monkeypatch, [('wait', {'mode': 'patrol', 'after_turns': 3})])
    on_requests = scripted(on_client, monkeypatch, [
        ('wait', {'mode': 'patrol', 'after_turns': 3}),
        ('wait', {'mode': 'patrol', 'after_turns': 3})])
    assert off.review('Ordinary wake').kind == 'wait'
    assert on.review('Ordinary wake').kind == 'wait'
    assert len(off_requests) == 1 and len(on_requests) == 2
    assert off_requests[0]['system'] == on_requests[0]['system']
    assert off_requests[0]['tools'] == on_requests[0]['tools']
    assert len(on_requests[0]['tools']) == 7
    for request in (off_requests[0], on_requests[0]):
        visible = json.dumps(request['messages'])
        assert 'Ordinary wake' in visible and 'Task turns used: 42; limit: 300' in visible
        assert 'Supervisory Situation' in visible
        assert 'This release has not executed' not in visible


def test_patrol_boundary_then_repeat_and_budget_exhaustion(tmp_path, monkeypatch):
    monitor, client, ws = make_monitor(tmp_path / 'repeat')
    snapshots = scripted(client, monkeypatch, [
        ('wait', {'mode': 'patrol', 'after_turns': 2, 'reason': 'Evidence holds'}),
        ('wait', {'mode': 'patrol', 'after_turns': 2, 'reason': 'Same decision'})])
    action = monitor.review('Wake')
    assert action.kind == 'wait' and action.payload['mode'] == 'patrol'
    assert len(snapshots) == 2
    record = events(ws)
    assert len([row for row in record if row['event'] == 'dcm_boundary_issued']) == 1
    assert len([row for row in record if row['event'] == 'dcm_release_confirmed']) == 1
    first = next(row for row in record if row['event'] == 'tool_result')
    assert first['data']['status'] == 'release_not_executed'
    assert first['action'] is None
    assert 'Task control has not entered patrol' in json.dumps(snapshots[1])

    monitor, client, ws = make_monitor(tmp_path / 'exhaust')
    scripted(client, monkeypatch, [('wait', {'mode': 'patrol', 'after_turns': 2})])
    with pytest.raises(Exception, match='exceeded 1 turns'):
        monitor.review('Wake', max_turns_override=1)
    assert not any(row['event'] == 'control_result' for row in events(ws))
    assert any(row['event'] == 'dcm_review_ended_with_boundary_pending' and
               row['disposition'] == 'review_exhausted' for row in events(ws))


def test_two_releases_in_one_model_response_do_not_bypass_boundary(tmp_path, monkeypatch):
    monitor, client, ws = make_monitor(tmp_path)
    sends = []

    def offline_once(tools):
        sends.append(client.assembled_request_snapshot(tools))
        if len(sends) == 1:
            return ([{'type': 'tool_use', 'id': f'wait-{i}', 'name': 'wait',
                      'input': {'mode': 'patrol', 'after_turns': 1}} for i in (1, 2)], {})
        return ([{'type': 'tool_use', 'id': 'wait-3', 'name': 'wait',
                  'input': {'mode': 'patrol', 'after_turns': 1}}], {})

    monkeypatch.setattr(client, '_request_once', offline_once)
    assert monitor.review('Wake').kind == 'wait'
    first_results = [row for row in events(ws) if row['event'] == 'tool_result' and row['turn'] == 1]
    assert len(first_results) == 2 and all(row['action'] is None for row in first_results)
    assert len([row for row in events(ws) if row['event'] == 'dcm_release_confirmed']) == 1
    assert len(sends) == 2


def test_follow_and_intervene_abandon_then_new_patrol_boundary(tmp_path, monkeypatch):
    monitor, client, ws = make_monitor(tmp_path / 'follow')
    scripted(client, monkeypatch, [
        ('wait', {'mode': 'patrol', 'after_turns': 1}),
        ('wait', {'mode': 'follow', 'after_turns': 1})])
    assert monitor.review('Wake').payload['mode'] == 'follow'
    assert any(row['event'] == 'dcm_release_abandoned' and
               row['disposition'] == 'changed_to_follow' for row in events(ws))
    scripted(client, monkeypatch, [
        ('wait', {'mode': 'patrol', 'after_turns': 1}),
        ('wait', {'mode': 'patrol', 'after_turns': 1})])
    assert monitor.review('Next wake').payload['mode'] == 'patrol'
    assert len([row for row in events(ws) if row['event'] == 'dcm_boundary_issued']) == 2

    monitor, _, ws = make_monitor(tmp_path / 'plain-follow')
    assert monitor.dispatch('wait', {'mode': 'follow', 'after_turns': 1}).action.kind == 'wait'
    assert not any(row['event'] == 'dcm_boundary_issued' for row in events(ws))

    monitor, client, ws = make_monitor(tmp_path / 'intervene')
    monitor.intervention_callback = lambda message: {'delivery': 'queued'}
    scripted(client, monkeypatch, [
        ('wait', {'mode': 'patrol', 'after_turns': 1}),
        ('intervene', {'message': 'Please inspect the route.'}),
        ('wait', {'mode': 'patrol', 'after_turns': 1}),
        ('wait', {'mode': 'patrol', 'after_turns': 1})])
    assert monitor.review('Wake').payload['mode'] == 'patrol'
    assert len([row for row in events(ws) if row['event'] == 'dcm_boundary_issued']) == 2
    assert any(row['event'] == 'dcm_release_abandoned' and
               row['disposition'] == 'intervened' for row in events(ws))


def test_observation_tools_and_invalid_wait(tmp_path):
    monitor, _, ws = make_monitor(tmp_path)
    monitor.review_id = 'review-local'
    monitor.dcm.begin_review(monitor.review_id)
    invalid = monitor.dispatch('wait', {'mode': 'bad', 'after_turns': 1})
    assert invalid.data['status'] == 'error' and monitor.dcm.challenge is None
    first = monitor.dispatch('wait', {'mode': 'patrol', 'after_turns': 1})
    assert first.action is None
    assert monitor.dispatch('file_read', {'path': 'task/workspace/router.py'}).data
    assert monitor.dispatch('code_run', {'code': 'print(1)', 'type': 'python'}).data
    confirmed = monitor.dispatch('wait', {'mode': 'patrol', 'after_turns': 1})
    assert confirmed.action.kind == 'wait'
    tools = [row for row in events(ws) if row['event'] == 'dcm_post_boundary_tool']
    assert [row['tool_name'] for row in tools] == ['file_read', 'code_run']
    assert tools[0]['task_path'] == 'task/workspace/router.py'


def test_root_boundary_repeat_defer_stale_and_generation_change(tmp_path, monkeypatch):
    monitor, client, ws = make_monitor(tmp_path / 'repeat')
    handoff = root(monitor)
    scripted(client, monkeypatch, [
        ('allow_complete', {'result': 'resolve', 'reason': 'Current evidence'}),
        ('allow_complete', {'result': 'resolve', 'reason': 'Still supported'})])
    action = monitor.review('Root wake', completion_pending=True, root_handoff=handoff)
    assert action.kind == 'allow_complete'
    assert len([row for row in events(ws) if row['event'] == 'dcm_boundary_issued']) == 1
    assert next(row for row in events(ws) if row['event'] == 'tool_result')['action'] is None
    assert monitor.completion_state() == handoff

    monitor, _, ws = make_monitor(tmp_path / 'defer')
    handoff = root(monitor)
    monitor._enter_root_frame(handoff)
    monitor._refresh_completion()
    try:
        assert monitor.dispatch('allow_complete', {'result': 'defer', 'reason': 'Limited'}).action.kind == 'incomplete_delivery'
        assert monitor.dcm.challenge is None
        assert not any(row['event'] == 'dcm_boundary_issued' for row in events(ws))
        monitor.dcm.begin_review('root')
        assert monitor.dispatch('allow_complete', {'result': 'resolve', 'reason': 'Ready'}).action is None
        monitor.completion_state = lambda: {**handoff, 'generation': 2}
        stale = monitor.dispatch('allow_complete', {'result': 'resolve', 'reason': 'Ready'})
        assert stale.data['status'] == 'error' and stale.action is None
        assert not any(row['event'] == 'dcm_release_confirmed' for row in events(ws))
    finally:
        monitor._leave_root_frame()

    monitor, _, ws = make_monitor(tmp_path / 'challenge-defer')
    handoff = root(monitor)
    monitor._enter_root_frame(handoff)
    monitor._refresh_completion()
    try:
        assert monitor.dispatch('allow_complete', {'result': 'resolve', 'reason': 'Maybe'}).action is None
        assert monitor.dispatch('allow_complete', {'result': 'defer', 'reason': 'Limited'}).action.kind == 'incomplete_delivery'
        assert any(row['event'] == 'dcm_release_abandoned' and row['disposition'] == 'deferred'
                   for row in events(ws))
    finally:
        monitor._leave_root_frame()


def test_root_stale_and_local_allow_do_not_issue_boundary(tmp_path):
    monitor, _, ws = make_monitor(tmp_path)
    handoff = root(monitor)
    monitor._refresh_completion()
    assert monitor.dispatch('allow_complete', {'result': 'resolve', 'reason': 'No root frame'}).data['status'] == 'error'
    monitor._enter_root_frame(handoff)
    monitor._refresh_completion()
    pending_wait = monitor.dispatch('wait', {'mode': 'patrol', 'after_turns': 1})
    assert pending_wait.data['status'] == 'handoff_pending'
    monitor.completion_state = lambda: {**handoff, 'generation': 2}
    assert monitor.dispatch('allow_complete', {'result': 'resolve', 'reason': 'Stale'}).data['status'] == 'error'
    assert not any(row['event'] == 'dcm_boundary_issued' for row in events(ws))
    monitor._leave_root_frame()


def test_invalid_switch_combinations(tmp_path):
    monitor, client, ws = make_monitor(tmp_path / 'valid')
    assert monitor.dcm is not None
    for key, value in [('monitor_coarse_to_fine_surface', False),
                       ('monitor_verification_runtime_managed', True),
                       ('monitor_executable_interpretation_surface', True)]:
        config = dict(client.config, **{key: value})
        with pytest.raises(ValueError):
            MonitorAgent(MonitorProviderClient('anthropic', config), ws)
