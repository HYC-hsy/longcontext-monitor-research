"""Zero-network tests of ASE-v0 representation and unchanged seven-tool control loop."""

import hashlib
import json

import pytest

from monitor_agent_core.agent import MONITOR_TOOLS, MonitorAgent
from monitor_agent_core.ase_v0 import REFERENCE_LIMIT, reference_surface
from monitor_agent_core.provider import MonitorProviderClient
from monitor_agent_core.root_scope_v1 import ROOT_SYSTEM_PROMPT
from monitor_agent_core.workspace import MonitorWorkspace


def make_monitor(tmp_path, *, ase=True, cqs=False):
    evidence = tmp_path / 'evidence'
    evidence.mkdir(parents=True)
    (evidence / 'original_task.txt').write_text('Maintain the public route.', encoding='utf-8')
    (evidence / 'public_events.jsonl').write_text('', encoding='utf-8')
    task = tmp_path / 'task'
    task.mkdir()
    (task / 'router.py').write_text('ROUTE = True\n', encoding='utf-8')
    workspace = MonitorWorkspace(evidence, tmp_path / 'private', task_mounts={'workspace': task})
    workspace.write_text('monitor/working.md', 'LOCAL_WORKING_SENTINEL')
    config = {'apikey': 'offline', 'apibase': 'https://offline.invalid', 'model': 'offline',
              'max_retries': 0, 'monitor_adaptive_supervisory_environment': ase}
    if not ase:
        config.update({'monitor_dcec': True, 'monitor_path_control_v0': True,
                       'monitor_verification_loop_v0': True,
                       'monitor_verification_runtime_managed': False,
                       'monitor_coarse_to_fine_surface': True,
                       'monitor_decision_conditioned_measurement': True,
                       'monitor_control_question_state': cqs})
    elif cqs:
        config['monitor_control_question_state'] = True
    client = MonitorProviderClient('anthropic', config)
    monitor = MonitorAgent(client, workspace)
    monitor.task_budget_state = lambda: (12, 300)
    return monitor, client, workspace


def scripted(client, monkeypatch, calls):
    snapshots = []

    def offline_once(tools):
        snapshots.append(client.assembled_request_snapshot(tools))
        rationale, name, args = calls[len(snapshots) - 1]
        blocks = ([{'type': 'text', 'text': rationale}] if rationale else [])
        blocks.append({'type': 'tool_use', 'id': f'call-{len(snapshots)}',
                       'name': name, 'input': args})
        return blocks, {}

    monkeypatch.setattr(client, '_request_once', offline_once)
    return snapshots


def visible(snapshot):
    return json.dumps(snapshot['messages'], ensure_ascii=False)


def rows(workspace):
    path = workspace.private_root / 'audit/dialogue.jsonl'
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()] if path.exists() else []


def root(monitor):
    handoff = {'generation': 1, 'request_id': 'completion-1', 'cursor': 1}
    (monitor.workspace.evidence_root / 'public_events.jsonl').write_text(
        json.dumps({'archive_sequence': 1, 'task_turn': 12, 'boundary': 'completion',
                    'text': 'Ready for review.', 'tool_calls': [], 'tool_results': []}) + '\n',
        encoding='utf-8')
    monitor.completion_state = lambda: handoff
    return handoff


def test_reference_absent_head_tail_and_model_owned_revision(tmp_path):
    monitor, _, ws = make_monitor(tmp_path)
    absent, meta = reference_surface(ws)
    assert meta['status'] == 'absent' and meta['source_characters'] == 0
    assert 'no task interpretation was generated' in absent
    source = 'START_' + 'm' * 8000 + '_END'
    written = monitor.dispatch('file_write', {'path': 'monitor/reference.md', 'content': source})
    assert written.data['sha256'] == hashlib.sha256(source.encode()).hexdigest()
    surface, meta = reference_surface(ws)
    assert len(surface) <= REFERENCE_LIMIT and meta['truncated']
    assert 'START_' in surface and '_END' in surface and 'Middle omitted' in surface
    assert meta['source_characters'] == len(source)
    assert meta['visible_characters'] < len(source)
    assert meta['source_sha256'] == hashlib.sha256(source.encode()).hexdigest()
    monitor.dispatch('file_patch', {'path': 'monitor/reference.md',
                                    'old_text': 'START_', 'new_text': 'REVISED_'})
    revised, _ = reference_surface(ws)
    assert 'REVISED_' in revised
    assert len([r for r in rows(ws) if r['event'] == 'ase_reference_mutated']) == 2


def test_turn_zero_and_provider_ready_composition_no_working_ledger(tmp_path, monkeypatch):
    monitor, client, ws = make_monitor(tmp_path)
    sends = scripted(client, monkeypatch, [
        ('', 'file_read', {'path': 'task/original_task.txt'}),
        ('', 'file_read', {'path': 'task/workspace/router.py'}),
        ('', 'file_write', {'path': 'monitor/reference.md',
                            'content': 'REFERENCE_SENTINEL: route behavior matters.'}),
        ('Watch route use.', 'wait', {'mode': 'follow', 'after_turns': 2}),
    ])
    assert monitor.review('Initialization').kind == 'wait'
    assert len(sends) == 4
    assert [tool['function']['name'] for tool in sends[0]['tools']] == [
        'file_read', 'file_write', 'file_patch', 'code_run', 'wait', 'intervene', 'allow_complete']
    assert sends[0]['tools'] == MONITOR_TOOLS
    assert 'verification' not in json.dumps(sends[0]['tools'])
    assert 'result' not in sends[0]['tools'][-1]['function']['parameters']['properties']
    assert 'monitor/reference.md' in sends[0]['system']
    assert 'task/original_task.txt' in sends[0]['system']
    assert 'Reference absent' in visible(sends[0])
    assert 'LOCAL_WORKING_SENTINEL' not in visible(sends[0])
    assert 'REFERENCE_SENTINEL' in visible(sends[3])
    assert 'Supervisory Situation' in visible(sends[0])
    assert 'Situation unchanged through cursor 0' in visible(sends[3])
    assert visible(sends[3]).index('REFERENCE_SENTINEL') < visible(sends[3]).index('Situation unchanged')
    injections = [r for r in rows(ws) if r['event'] == 'ase_context_injected']
    assert len(injections) == 4
    assert injections[-1]['reference_source_characters'] > 0
    assert injections[-1]['composition_order'] == ['reference', 'cfs']
    assert monitor.dispatch('file_read', {'path': 'monitor/working.md'}).data['content'] == 'LOCAL_WORKING_SENTINEL'


def test_initialization_requires_model_authored_reference_before_wait(tmp_path, monkeypatch):
    monitor, client, ws = make_monitor(tmp_path)
    sends = scripted(client, monkeypatch, [
        ('', 'wait', {'after_turns': 3, 'mode': 'patrol'}),
        ('', 'file_write', {'path': 'monitor/reference.md', 'content': '   '}),
        ('', 'wait', {'after_turns': 3, 'mode': 'follow'}),
        ('', 'file_write', {'path': 'monitor/reference.md',
                            'content': 'Public route response matters.'}),
        ('', 'wait', {'after_turns': 3, 'mode': 'patrol'}),
    ])
    action = monitor.review('Initialization')
    assert action.kind == 'wait' and action.payload['mode'] == 'patrol'
    assert len(sends) == 5
    feedback = [r['data'] for r in rows(ws) if r['event'] == 'tool_result'
                and isinstance(r.get('data'), dict)
                and r['data'].get('status') == 'reference_initialization_pending']
    assert len(feedback) == 2
    assert all('route' not in str(item).lower() for item in feedback)
    assert [r['event'] for r in rows(ws) if r['event'].startswith('ase_reference_initialization_')] == [
        'ase_reference_initialization_pending', 'ase_reference_initialization_pending',
        'ase_reference_initialization_ready']
    assert ws.resolve_read('monitor/reference.md').read_text(encoding='utf-8') == 'Public route response matters.'
    assert not [r for r in rows(ws) if r['event'] == 'ase_reconsideration_boundary']


def test_inactive_patrol_is_one_turn_but_active_patrol_reconsiders(tmp_path, monkeypatch):
    monitor, client, ws = make_monitor(tmp_path)
    ws.write_text('monitor/reference.md', 'Public route response matters.')
    sends = scripted(client, monkeypatch, [('', 'wait', {'after_turns': 1, 'mode': 'patrol'})])
    assert monitor.review('Initial').payload['mode'] == 'patrol'
    assert len(sends) == 1
    assert not [r for r in rows(ws) if r['event'] == 'ase_reconsideration_boundary']
    monitor.intervention_callback = lambda message: {'delivery': 'queued'}
    scripted(client, monkeypatch, [
        ('Route discrepancy.', 'intervene', {'message': 'Check route response.'}),
        ('Await update.', 'wait', {'after_turns': 1, 'mode': 'follow'}),
    ])
    assert monitor.review('Later').payload['mode'] == 'follow'
    sends = scripted(client, monkeypatch, [
        ('', 'wait', {'after_turns': 1, 'mode': 'patrol'}),
        ('', 'wait', {'after_turns': 1, 'mode': 'patrol'}),
    ])
    assert monitor.review('Release').payload['mode'] == 'patrol'
    assert len(sends) == 2
    assert len([r for r in rows(ws) if r['event'] == 'ase_reconsideration_boundary']) == 1


def test_intervention_before_reference_does_not_waive_initialization(tmp_path, monkeypatch):
    monitor, client, ws = make_monitor(tmp_path)
    monitor.intervention_callback = lambda message: {'delivery': 'queued'}
    sends = scripted(client, monkeypatch, [
        ('Observed route discrepancy.', 'intervene', {'message': 'Inspect route behavior.'}),
        ('', 'wait', {'after_turns': 1, 'mode': 'follow'}),
        ('', 'file_write', {'path': 'monitor/reference.md', 'content': 'Public route behavior matters.'}),
        ('', 'wait', {'after_turns': 1, 'mode': 'follow'}),
    ])
    assert monitor.review('Initialization').payload['mode'] == 'follow'
    assert len(sends) == 4
    assert monitor.cqs.anchor['message'] == 'Inspect route behavior.'
    assert len([r for r in rows(ws) if r['event'] == 'ase_reference_initialization_pending']) == 1


def test_intervention_anchor_survives_follows_then_patrol_clears(tmp_path, monkeypatch):
    monitor, client, ws = make_monitor(tmp_path)
    ws.write_text('monitor/reference.md', 'Route response is the public requirement.')
    monitor.intervention_callback = lambda message: {'delivery': 'queued'}
    sends = scripted(client, monkeypatch, [
        ('Route may be wrong.', 'intervene', {'message': 'Check actual route response.'}),
        ('Await first edit.', 'wait', {'mode': 'follow', 'after_turns': 2}),
    ])
    assert monitor.review('Wake').kind == 'wait'
    assert 'Check actual route response.' in visible(sends[1])
    assert visible(sends[1]).index('Supervisor Reference') < visible(sends[1]).index('Local Control Continuity')
    assert visible(sends[1]).index('Local Control Continuity') < visible(sends[1]).index('Situation unchanged')
    assert monitor.cqs.anchor['message'] == 'Check actual route response.'
    for reason in ('Await test', 'Await result'):
        sends = scripted(client, monkeypatch, [
            (reason, 'wait', {'mode': 'follow', 'after_turns': 2}),
        ])
        assert monitor.review('Next feedback').kind == 'wait'
        assert 'Check actual route response.' in visible(sends[0])
        assert monitor.cqs.anchor['message'] == 'Check actual route response.'
    assert monitor.cqs.follow['reason'] == 'Await result'
    assert monitor.cqs.follow_count == 3
    follow_events = [r for r in rows(ws) if r['event'] == 'ase_continuity_updated'
                     and r['source'] == 'wait_follow']
    assert [r['follow_count'] for r in follow_events] == [1, 2, 3]
    assert all(r['requested_after_turns'] == 2 for r in follow_events)
    sends = scripted(client, monkeypatch, [
        ('', 'wait', {'mode': 'patrol', 'after_turns': 2}),
        ('', 'wait', {'mode': 'patrol', 'after_turns': 2}),
    ])
    assert monitor.review('Release').payload['mode'] == 'patrol'
    assert 'Check actual route response.' in visible(sends[0])
    assert monitor.cqs.anchor is None and monitor.cqs.follow is None
    assert len([r for r in rows(ws) if r['event'] == 'ase_continuity_cleared']) == 1
    assert [r for r in rows(ws) if r['event'] == 'ase_reconsideration_boundary']


def test_release_boundary_root_and_changed_control(tmp_path, monkeypatch):
    monitor, client, ws = make_monitor(tmp_path)
    handoff = root(monitor)
    sends = scripted(client, monkeypatch, [
        ('', 'allow_complete', {}),
        ('', 'file_read', {'path': 'task/workspace/router.py'}),
        ('', 'allow_complete', {}),
    ])
    action = monitor.review('Root', completion_pending=True, root_handoff=handoff)
    assert action.kind == 'allow_complete' and len(sends) == 3
    assert ROOT_SYSTEM_PROMPT not in sends[0]['system']
    assert 'monitor/root_working/' not in visible(sends[0])
    assert 'monitor/audit/root_frames/' not in visible(sends[0])
    assert monitor.root_routed and not monitor.verification_loop_v0
    events = rows(ws)
    assert len([r for r in events if r['event'] == 'ase_reconsideration_boundary']) == 1
    assert len([r for r in events if r['event'] == 'ase_release_confirmed']) == 1
    assert len([r for r in events if r['event'] == 'ase_post_boundary_tool' and r['tool_name'] == 'file_read']) == 1
    first_result = next(r for r in events if r['event'] == 'tool_result' and
                        r['data'] and r['data'].get('status') == 'release_not_executed')
    assert 'material state' not in first_result['data']['message']
    assert 'has not executed' in first_result['data']['message']
    assert 'scope' not in first_result['data']
    assert first_result['action'] is None
    assert [r for r in events if r['event'] == 'ase_reconsideration_boundary'][0]['visible_context']['reference_surface_sha256']


def test_boundary_can_change_to_follow_or_intervene(tmp_path, monkeypatch):
    monitor, client, ws = make_monitor(tmp_path)
    ws.write_text('monitor/reference.md', 'Route response is the public requirement.')
    monitor.intervention_callback = lambda message: {'delivery': 'queued'}
    scripted(client, monkeypatch, [
        ('Route concern.', 'intervene', {'message': 'Check route behavior.'}),
        ('Await feedback.', 'wait', {'mode': 'follow', 'after_turns': 1}),
    ])
    assert monitor.review('Initial').kind == 'wait'
    sends = scripted(client, monkeypatch, [
        ('', 'wait', {'mode': 'patrol', 'after_turns': 1}),
        ('Need response.', 'wait', {'mode': 'follow', 'after_turns': 1}),
    ])
    assert monitor.review('Wake').payload['mode'] == 'follow'
    assert len(sends) == 2
    assert any(r['event'] == 'ase_release_abandoned' and r['disposition'] == 'changed_to_follow'
               for r in rows(ws))
    scripted(client, monkeypatch, [
        ('', 'wait', {'mode': 'patrol', 'after_turns': 1}),
        ('Now correct it.', 'intervene', {'message': 'Fix route handling.'}),
        ('', 'wait', {'mode': 'follow', 'after_turns': 1}),
    ])
    assert monitor.review('Next wake').payload['mode'] == 'follow'
    assert any(r['event'] == 'ase_release_abandoned' and r['disposition'] == 'intervened'
               for r in rows(ws))
    assert monitor.cqs.anchor['message'] == 'Fix route handling.'


def test_continuation_only_rewrites_working_and_legacy_paths_unchanged(tmp_path, monkeypatch):
    monitor, client, ws = make_monitor(tmp_path / 'ase')
    ws.write_text('monitor/reference.md', 'PERMANENT_REFERENCE')
    before = ws.resolve_read('monitor/reference.md').read_bytes()
    monkeypatch.setattr(client, '_request_once', lambda tools: ([{'type': 'text',
        'text': 'Local continuation note only.'}], {}))
    monitor._prepare_continuation()
    assert ws.resolve_read('monitor/reference.md').read_bytes() == before
    assert ws.resolve_read('monitor/working.md').read_text(encoding='utf-8') == 'Local continuation note only.'
    legacy, legacy_client, _ = make_monitor(tmp_path / 'legacy', ase=False, cqs=True)
    disabled, disabled_client, _ = make_monitor(tmp_path / 'disabled', ase=False, cqs=True)
    disabled_client.config.pop('monitor_adaptive_supervisory_environment')
    assert legacy.system_prompt == disabled.system_prompt
    assert legacy.cqs.__class__ == disabled.cqs.__class__
    assert legacy.dcm.__class__ == disabled.dcm.__class__
    with pytest.raises(ValueError):
        make_monitor(tmp_path / 'bad', ase=True, cqs=True)


def test_exact_duplicate_telemetry_is_mechanical_and_not_a_control_trigger(tmp_path, monkeypatch):
    monitor, client, ws = make_monitor(tmp_path)
    ws.write_text('monitor/reference.md', 'Route response is the public requirement.')
    sends = scripted(client, monkeypatch, [
        ('', 'file_read', {'path': 'task/workspace/router.py'}),
        ('', 'file_read', {'path': 'task/workspace/router.py', 'start': 1, 'count': 200}),
        ('', 'code_run', {'code': 'print(1)', 'type': 'python'}),
        ('', 'code_run', {'code': 'print(1)', 'type': 'python'}),
        ('', 'wait', {'mode': 'follow', 'after_turns': 3}),
    ])
    assert monitor.review('Wake').payload['mode'] == 'follow'
    assert len(sends) == 5
    duplicate = [r for r in rows(ws) if r['event'] == 'ase_exact_duplicate_observation_call']
    assert [r['tool_name'] for r in duplicate] == ['file_read', 'code_run']
    assert all(r['count'] == 2 for r in duplicate)
    assert not [r for r in rows(ws) if r['event'] == 'ase_reconsideration_boundary']


def test_failed_provider_request_does_not_claim_reference_exposure(tmp_path, monkeypatch):
    monitor, client, ws = make_monitor(tmp_path)
    ws.write_text('monitor/reference.md', 'Task reference from Supervisor.')
    original = client._request_with_recovery

    def transport_failure(_tools):
        raise RuntimeError('offline transport failure')

    monkeypatch.setattr(client, '_request_with_recovery', transport_failure)
    with pytest.raises(RuntimeError, match='offline transport failure'):
        monitor.review('Wake')
    assert [r for r in rows(ws) if r['event'] == 'ase_reference_surface_prepared']
    assert not [r for r in rows(ws) if r['event'] == 'ase_context_injected']
    monkeypatch.setattr(client, '_request_with_recovery', original)
    sends = scripted(client, monkeypatch, [('', 'wait', {'mode': 'follow', 'after_turns': 1})])
    assert monitor.review('Fresh wake').kind == 'wait'
    assert 'Task reference from Supervisor.' in visible(sends[0])
    assert len([r for r in rows(ws) if r['event'] == 'ase_context_injected']) == 1
