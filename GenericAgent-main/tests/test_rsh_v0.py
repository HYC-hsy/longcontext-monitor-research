"""RSH-v0 provenance and DCM handoff checks; all provider sends are local stubs."""

import json

import pytest

from monitor_agent_core.agent import MonitorAgent
from monitor_agent_core.provider import MonitorProviderClient
from monitor_agent_core.workspace import MonitorWorkspace


def monitor_at(tmp_path, *, rsh=True):
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
              'monitor_coarse_to_fine_surface': True, 'monitor_decision_conditioned_measurement': True,
              'monitor_release_support_horizon': rsh}
    client = MonitorProviderClient('anthropic', config)
    monitor = MonitorAgent(client, workspace)
    monitor.task_budget_state = lambda: (42, 300)
    return monitor, client, workspace


def root(monitor, generation=1):
    handoff = {'generation': generation, 'request_id': f'handoff-{generation}', 'cursor': generation}
    (monitor.workspace.evidence_root / 'public_events.jsonl').write_text(
        json.dumps({'archive_sequence': generation, 'task_turn': 42, 'boundary': 'completion',
                    'text': 'Ready for review.', 'tool_calls': [], 'tool_results': []}) + '\n',
        encoding='utf-8')
    monitor.completion_state = lambda: handoff
    return handoff


def run_script(monitor, client, monkeypatch, calls, *, handoff=None):
    snapshots = []

    def offline_once(tools):
        snapshots.append(client.assembled_request_snapshot(tools))
        item = calls[len(snapshots) - 1]
        if isinstance(item, list):
            values = item
        else:
            values = [item]
        return ([{'type': 'tool_use', 'id': f'call-{len(snapshots)}-{index}',
                  'name': name, 'input': args}
                 for index, (name, args) in enumerate(values)], {})

    monkeypatch.setattr(client, '_request_once', offline_once)
    action = monitor.review('Ordinary wake', completion_pending=handoff is not None,
                            root_handoff=handoff)
    return action, snapshots


def rows(workspace, event):
    path = workspace.private_root / 'audit/dialogue.jsonl'
    return [row for line in path.read_text(encoding='utf-8').splitlines()
            if (row := json.loads(line))['event'] == event]


def horizon(workspace):
    emitted = rows(workspace, 'rsh_horizon_emitted')
    assert len(emitted) == 1
    return emitted[0]


def test_contract_off_and_local_patrol_unchanged(tmp_path, monkeypatch):
    off, off_client, off_ws = monitor_at(tmp_path / 'off', rsh=False)
    on, on_client, on_ws = monitor_at(tmp_path / 'on')
    script = [('wait', {'mode': 'patrol', 'after_turns': 2}),
              ('wait', {'mode': 'patrol', 'after_turns': 2})]
    off_action, off_requests = run_script(off, off_client, monkeypatch, script)
    on_action, on_requests = run_script(on, on_client, monkeypatch, script)
    assert off_action == on_action
    assert off_requests[0]['system'] == on_requests[0]['system']
    assert off_requests[0]['tools'] == on_requests[0]['tools']
    assert len(off_requests[0]['tools']) == 7
    off_results = [row['data'] for row in rows(off_ws, 'tool_result')]
    on_results = [row['data'] for row in rows(on_ws, 'tool_result')]
    for result in off_results + on_results:
        if result:
            result.pop('challenge_id', None)
    assert off_results == on_results
    assert not rows(on_ws, 'rsh_horizon_emitted')

    root_off, root_off_client, root_off_ws = monitor_at(tmp_path / 'root-off', rsh=False)
    root_on, root_on_client, _ = monitor_at(tmp_path / 'root-on')
    off_handoff = root(root_off)
    on_handoff = root(root_on)
    release = [('allow_complete', {'result': 'resolve', 'reason': 'Current evidence'}),
               ('allow_complete', {'result': 'resolve', 'reason': 'Current evidence'})]
    _, off_root_requests = run_script(root_off, root_off_client, monkeypatch, release,
                                      handoff=off_handoff)
    _, on_root_requests = run_script(root_on, root_on_client, monkeypatch, release,
                                     handoff=on_handoff)
    assert off_root_requests[0]['system'] == on_root_requests[0]['system']
    assert off_root_requests[0]['tools'] == on_root_requests[0]['tools']
    assert 'Release Support Horizon' not in json.dumps(off_root_requests)
    assert 'Release Support Horizon' not in json.dumps(on_root_requests[0])
    assert not rows(root_off_ws, 'rsh_horizon_emitted')


def test_root_fresh_read_and_code_result_visible_then_second_allow(tmp_path, monkeypatch):
    monitor, client, ws = monitor_at(tmp_path)
    handoff = root(monitor)
    monitor.analysis.start = lambda *args: {'status': 'success', 'session_id': 'session-1',
                                            'exit_code': 0, 'stdout': 'public observation'}
    action, requests = run_script(monitor, client, monkeypatch, [
        [('file_read', {'path': 'task/workspace/router.py'}),
         ('file_read', {'path': 'monitor/working.md'}),
         ('code_run', {'code': 'printf observed', 'type': 'bash'})],
        ('allow_complete', {'result': 'resolve', 'reason': 'Current evidence'}),
        ('allow_complete', {'result': 'resolve', 'reason': 'Still supported'})], handoff=handoff)
    assert action.kind == 'allow_complete'
    assert len(rows(ws, 'dcm_boundary_issued')) == 1
    assert len(rows(ws, 'rsh_horizon_emitted')) == 1
    result = horizon(ws)
    assert [r['path'] for r in result['fresh_task_file_reads']] == ['task/workspace/router.py']
    assert result['fresh_supervisor_code_runs'][0]['status'] == 'success'
    assert result['fresh_supervisor_code_runs'][0]['exit_code'] == 0
    assert result['full_original_task_in_root_input'] is True
    assert result['fresh_original_task_read'] is False
    assert 'not a coverage or adequacy verdict' in result['rendered_content']
    assert 'Task code_run rows=' in result['rendered_content']
    assert len(result['rendered_content']) <= 1800
    first_allow = [row for row in rows(ws, 'tool_result')
                   if row['data'] and row['data'].get('release_support_horizon')]
    assert len(first_allow) == 1 and first_allow[0]['action'] is None
    assert 'Release Support Horizon' in json.dumps(requests[2]['messages'])
    assert result['fresh_task_file_reads'][0]['visible_model_output_locator'].startswith(
        'monitor/audit/dialogue.jsonl#')


def test_same_response_tool_not_fresh_and_previous_local_not_fresh(tmp_path, monkeypatch):
    monitor, client, ws = monitor_at(tmp_path)
    run_script(monitor, client, monkeypatch, [
        ('file_read', {'path': 'task/workspace/router.py'}),
        ('wait', {'mode': 'follow', 'after_turns': 1})])
    handoff = root(monitor)
    action, _ = run_script(monitor, client, monkeypatch, [
        [('allow_complete', {'result': 'resolve', 'reason': 'Proposed'}),
         ('file_read', {'path': 'task/workspace/router.py'})],
        ('allow_complete', {'result': 'resolve', 'reason': 'Confirmed'})], handoff=handoff)
    assert action.kind == 'allow_complete'
    assert horizon(ws)['fresh_task_file_reads'] == []


def test_unseen_result_and_previous_root_generation_excluded(tmp_path, monkeypatch):
    monitor, client, ws = monitor_at(tmp_path)
    first = root(monitor, 1)
    run_script(monitor, client, monkeypatch, [
        ('file_read', {'path': 'task/workspace/router.py'}),
        ('allow_complete', {'result': 'resolve', 'reason': 'One'}),
        ('allow_complete', {'result': 'resolve', 'reason': 'One'})], handoff=first)
    assert len(horizon(ws)['fresh_task_file_reads']) == 1
    second = root(monitor, 2)
    run_script(monitor, client, monkeypatch, [
        ('allow_complete', {'result': 'resolve', 'reason': 'Two'}),
        ('allow_complete', {'result': 'resolve', 'reason': 'Two'})], handoff=second)
    assert rows(ws, 'rsh_horizon_emitted')[-1]['fresh_task_file_reads'] == []

    other, other_client, other_ws = monitor_at(tmp_path / 'unseen')
    handoff = root(other)
    run_script(other, other_client, monkeypatch, [
        [('file_read', {'path': 'task/workspace/router.py'}),
         ('allow_complete', {'result': 'resolve', 'reason': 'Before receipt'})],
        ('allow_complete', {'result': 'resolve', 'reason': 'Again'})], handoff=handoff)
    assert horizon(other_ws)['fresh_task_file_reads'] == []


def test_code_result_unseen_and_explicit_original_task_read(tmp_path, monkeypatch):
    monitor, client, ws = monitor_at(tmp_path / 'unseen-code')
    handoff = root(monitor)
    monitor.analysis.start = lambda *args: {'status': 'success', 'exit_code': 0,
                                            'session_id': 'code-1', 'stdout': ''}
    run_script(monitor, client, monkeypatch, [
        [('code_run', {'code': 'printf one', 'type': 'bash'}),
         ('allow_complete', {'result': 'resolve', 'reason': 'Before result'})],
        ('allow_complete', {'result': 'resolve', 'reason': 'Repeat'})], handoff=handoff)
    assert horizon(ws)['fresh_supervisor_code_runs'] == []

    monitor, client, ws = monitor_at(tmp_path / 'original-read')
    handoff = root(monitor)
    run_script(monitor, client, monkeypatch, [
        ('file_read', {'path': 'task/original_task.txt'}),
        ('allow_complete', {'result': 'resolve', 'reason': 'After read'}),
        ('allow_complete', {'result': 'resolve', 'reason': 'Repeat'})], handoff=handoff)
    assert horizon(ws)['fresh_original_task_read'] is True
    assert [r['path'] for r in horizon(ws)['fresh_task_file_reads']] == ['task/original_task.txt']


def test_stale_handoff_rejected_before_horizon_and_config_gate(tmp_path):
    monitor, _, ws = monitor_at(tmp_path)
    handoff = root(monitor)
    monitor.review_id = 'root-review'
    monitor._enter_root_frame(handoff)
    monitor.rsh.begin('root-review', handoff)
    monitor._refresh_completion()
    monitor.completion_state = lambda: {**handoff, 'generation': 2}
    assert monitor.dispatch('allow_complete', {'result': 'resolve', 'reason': 'Old'}).data['status'] == 'error'
    assert not rows(ws, 'rsh_horizon_emitted')
    monitor.rsh.end()
    monitor._leave_root_frame()

    monitor, client, _ = monitor_at(tmp_path / 'bad')
    client.config['monitor_release_support_horizon'] = True
    client.config['monitor_decision_conditioned_measurement'] = False
    with pytest.raises(ValueError, match='RSH-v0 requires'):
        MonitorAgent(client, monitor.workspace)


def test_result_not_promoted_when_followup_provider_request_fails(tmp_path, monkeypatch):
    monitor, client, ws = monitor_at(tmp_path)
    handoff = root(monitor)
    sends = 0

    def offline_once(tools):
        nonlocal sends
        sends += 1
        if sends == 1:
            return ([{'type': 'tool_use', 'id': 'read-1', 'name': 'file_read',
                      'input': {'path': 'task/workspace/router.py'}}], {})
        raise RuntimeError('scripted transport failure')

    monkeypatch.setattr(client, '_request_once', offline_once)
    with pytest.raises(RuntimeError, match='scripted transport failure'):
        monitor.review('Root wake', completion_pending=True, root_handoff=handoff)
    assert sends == 2
    assert rows(ws, 'rsh_direct_observation_visible') == []
    assert rows(ws, 'rsh_root_started') and rows(ws, 'rsh_root_ended')
