"""Zero-model focal-identity and root epistemic branch regressions."""

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from monitor_agent_core.agent import MonitorAgent
from monitor_agent_core.loop import MonitorLoopError
from monitor_agent_core.provider import MonitorProviderClient
from monitor_agent_core.runtime import _remaining_root_turns
from monitor_agent_core.actions import MonitorAction
from test_crs_v0 import contrast, events, fixture, visible


def _script(monkeypatch, client, answers):
    snapshots = []
    iterator = iter(answers)

    def respond(tools):
        snapshots.append(client.assembled_request_snapshot(tools))
        name, arguments = next(iterator)
        return ([{'type': 'tool_use', 'id': f'call-{len(snapshots)}',
                  'name': name, 'input': arguments}], {})

    monkeypatch.setattr(client, '_request_once', respond)
    return snapshots


def _root_step(monitor, client, workspace, handoff, monkeypatch, x=None):
    x = x or contrast()
    snapshots = _script(monkeypatch, client,
                        [('allow_complete', x), ('allow_complete', x),
                         ('allow_complete', x)])
    client.history = [{'role': 'user', 'content': [
        {'type': 'text', 'text': 'Target 7 verified earlier — SENTINEL_OLD_PROGRESS'}]}]
    first = monitor.review('root', completion_pending=True, root_handoff=handoff)
    assert first.kind == 'root_reestimate'
    assert first.payload['model_turns_used_in_this_subreview'] == 2
    assert len(snapshots) == 2
    assert monitor.crs.root_reorientation is not None
    # The accepted tool call and its result are closed before resetting history.
    assert client._review_boundaries()
    monitor.enter_root_reestimate(handoff, first)
    assert client.export_history() == []
    second = monitor.review('root', completion_pending=True, root_handoff=handoff)
    assert second.kind == 'allow_complete'
    assert len(snapshots) == 3
    return snapshots


def test_config_requires_ase_crs_and_rhr(tmp_path):
    _, client, workspace, _ = fixture(tmp_path, rhr=True, rer=True)
    for field in ('monitor_adaptive_supervisory_environment',
                  'monitor_contrastive_release_state', 'monitor_receding_horizon_release'):
        config = dict(client.config, **{field: False})
        with pytest.raises(ValueError, match='requires ASE'):
            MonitorAgent(MonitorProviderClient('anthropic', config), workspace)


def test_same_focal_revised_evidence_and_new_focal_are_distinct(tmp_path):
    monitor, _, workspace, _ = fixture(tmp_path, rhr=True)
    x = contrast()
    monitor.dcm.model_turn = 1
    monitor.dispatch('allow_complete', x)
    monitor.crs.surface_visible('request-x')
    monitor.dcm.model_turn = 2
    monitor.dispatch('allow_complete', x)
    prior = monitor.crs.root_reorientation['prior_focal']
    source = workspace.resolve_read('task/public_events.jsonl')
    second = json.loads(source.read_text(encoding='utf-8').splitlines()[0])
    second['archive_sequence'] = 2
    source.write_text(source.read_text(encoding='utf-8') + json.dumps(second) + '\n', encoding='utf-8')
    revised = contrast(observation_refs=['task/public_events.jsonl#2'])
    monitor.dcm.model_turn = 3
    monitor.dispatch('allow_complete', revised)
    current = monitor.crs.root_contrast
    assert current['focal_digest'] == prior['focal_digest']
    assert current['state_digest'] != prior['state_digest']
    assert current['focal_digest'] == hashlib.sha256(
        x['release_blocking_state'].encode('utf-8')).hexdigest()
    assert sum(e['event'] == 'rhr_focal_state_revised' for e in events(workspace)) == 1
    assert not any(e['event'] == 'rhr_new_focal_selected' for e in events(workspace))
    monitor.crs.surface_visible('request-revised')
    monitor.dcm.model_turn = 4
    monitor.dispatch('allow_complete', revised)
    monitor.dcm.model_turn = 5
    monitor.dispatch('allow_complete', contrast(release_blocking_state='Another world state.'))
    assert sum(e['event'] == 'rhr_new_focal_selected' for e in events(workspace)) == 1


def test_same_focal_provenance_revision_is_not_new_focal(tmp_path):
    monitor, _, workspace, _ = fixture(tmp_path, rhr=True)
    x = contrast(ground_refs=['monitor/reference.md'])
    monitor.dcm.model_turn = 1
    monitor.dispatch('allow_complete', x)
    monitor.crs.surface_visible('request-x')
    monitor.dcm.model_turn = 2
    monitor.dispatch('allow_complete', x)
    prior = monitor.crs.root_reorientation['prior_focal']
    workspace.write_text('monitor/reference.md', 'Changed durable cognition.')
    monitor.dcm.model_turn = 3
    monitor.dispatch('allow_complete', x)
    current = monitor.crs.root_contrast
    assert current['focal_digest'] == prior['focal_digest']
    assert current['state_digest'] != prior['state_digest']
    assert current['provenance_sha256'] != prior['provenance_sha256']
    assert any(e['event'] == 'rhr_focal_state_revised' for e in events(workspace))
    assert not any(e['event'] == 'rhr_new_focal_selected' for e in events(workspace))


def test_grounding_revision_is_same_focal(tmp_path):
    monitor, _, workspace, _ = fixture(tmp_path, rhr=True)
    x = contrast()
    monitor.dcm.model_turn = 1
    monitor.dispatch('allow_complete', x)
    monitor.crs.surface_visible('request-x')
    monitor.dcm.model_turn = 2
    monitor.dispatch('allow_complete', x)
    monitor.dcm.model_turn = 3
    monitor.dispatch('allow_complete', contrast(grounding='Reworded public-task grounding.'))
    assert any(e['event'] == 'rhr_focal_state_revised' for e in events(workspace))
    assert not any(e['event'] == 'rhr_new_focal_selected' for e in events(workspace))


def test_fresh_root_frame_is_protocol_closed_and_no_extra_model_response(tmp_path, monkeypatch):
    monitor, client, workspace, handoff = fixture(tmp_path, rhr=True, rer=True)
    snapshots = _root_step(monitor, client, workspace, handoff, monkeypatch)
    fresh = visible(snapshots[2])
    assert 'SENTINEL_OLD_PROGRESS' not in fresh
    assert 'Root Epistemic Re-estimation Frame' in fresh
    assert 'Root Horizon Reset' in fresh
    assert monitor.crs.root_reorientation is None
    assert contrast()['release_blocking_state'] in fresh
    assert 'Resolved mechanical provenance' in fresh
    assert 'The route must remain public.' in fresh
    assert 'Durable public-route requirement.' in fresh
    assert len(snapshots) == 3
    names = [e['event'] for e in events(workspace)]
    assert names.count('rer_frame_entered') == 1
    assert names.count('rhr_final_release_confirmed') == 1
    assert names.count('rer_parent_history_restored') == 1
    assert any(e['event'] == 'control_result' and e['results'][0]['content'].find(
        'root_reestimate') >= 0 for e in events(workspace))


def test_new_focal_restarts_fresh_branch_and_restores_parent_after_intervention(tmp_path, monkeypatch):
    monitor, client, workspace, handoff = fixture(tmp_path, rhr=True, rer=True)
    x = contrast()
    y = contrast(release_blocking_state='Independent capability B may still be incomplete.')
    replies = [('allow_complete', x), ('allow_complete', x),
               ('allow_complete', y), ('allow_complete', y),
               ('intervene', {'message': 'Revisit the independent capability.'})]
    snapshots = _script(monkeypatch, client, replies)
    client.history = [{'role': 'user', 'content': [
        {'type': 'text', 'text': 'SENTINEL_OLD_PROGRESS'}]}]
    monitor.intervention_callback = lambda message: {
        'submission_id': 'submission-1', 'delivery': 'queued',
        'submitted_task_turn': 8, 'submitted_cursor': 1}
    first = monitor.review('root', completion_pending=True, root_handoff=handoff)
    monitor.enter_root_reestimate(handoff, first)
    second = monitor.review('root', completion_pending=True, root_handoff=handoff)
    assert second.kind == 'root_reestimate'
    client.history.append({'role': 'user', 'content': [
        {'type': 'text', 'text': 'SENTINEL_FRAME1_PROGRESS'}]})
    monitor.enter_root_reestimate(handoff, second)
    third = monitor.review('root', completion_pending=True, root_handoff=handoff)
    assert third.kind == 'root_intervened'
    fresh = visible(snapshots[4])
    assert 'SENTINEL_OLD_PROGRESS' not in fresh
    assert 'SENTINEL_FRAME1_PROGRESS' not in fresh
    assert y['release_blocking_state'] in fresh
    assert 'SENTINEL_OLD_PROGRESS' in json.dumps(client.export_history())
    assert 'SENTINEL_FRAME1_PROGRESS' not in json.dumps(client.export_history())
    assert monitor.control_echo.pending_submission is not None
    names = [e['event'] for e in events(workspace)]
    assert names.count('rer_frame_restarted') == 1
    assert names.count('rhr_new_focal_selected') == 1


def test_task_book_mutation_survives_parent_restore_and_echo_is_pending(tmp_path, monkeypatch):
    monitor, client, workspace, handoff = fixture(tmp_path, rhr=True, rer=True)
    x = contrast()
    snapshots = _script(monkeypatch, client, [
        ('allow_complete', x), ('allow_complete', x),
        ('file_write', {'path': 'monitor/reference.md', 'content': 'NEW_DURABLE_BOOK'}),
        ('intervene', {'message': 'Reconsider the public contract.'})])
    client.history = [{'role': 'user', 'content': [
        {'type': 'text', 'text': 'SENTINEL_OLD_PROGRESS'}]}]
    monitor.intervention_callback = lambda message: {
        'submission_id': 'submission-1', 'delivery': 'queued',
        'submitted_task_turn': 8, 'submitted_cursor': 1}
    first = monitor.review('root', completion_pending=True, root_handoff=handoff)
    monitor.enter_root_reestimate(handoff, first)
    second = monitor.review('root', completion_pending=True, root_handoff=handoff)
    assert second.kind == 'root_intervened'
    assert workspace.resolve_read('monitor/reference.md').read_text(encoding='utf-8') == 'NEW_DURABLE_BOOK'
    assert 'SENTINEL_OLD_PROGRESS' in json.dumps(client.export_history())
    assert 'Root Epistemic Re-estimation Frame' in visible(snapshots[2])
    assert monitor.control_echo.pending_submission['submission_id'] == 'submission-1'
    assert monitor.control_echo.active_echo is None
    monitor.frame_kind = 'local'
    monitor.root_frame_handoff = None
    assert 'NEW_DURABLE_BOOK' in monitor._active_working_context()


def test_budget_exhaustion_cannot_release_or_leak_branch(tmp_path, monkeypatch):
    monitor, client, workspace, handoff = fixture(tmp_path, rhr=True, rer=True)
    x = contrast()
    snapshots = _script(monkeypatch, client, [
        ('allow_complete', x), ('allow_complete', x),
        ('allow_complete', contrast(release_blocking_state='Another state.'))])
    first = monitor.review('root', completion_pending=True, root_handoff=handoff)
    assert first.payload['model_turns_used_in_this_subreview'] == 2
    monitor.enter_root_reestimate(handoff, first)
    with pytest.raises(MonitorLoopError):
        monitor.review('root', completion_pending=True, root_handoff=handoff,
                       max_turns_override=1)
    assert len(snapshots) == 3
    assert monitor.crs.root_reorientation is None
    assert monitor._rer_parent_history is None
    assert not any(e['event'] == 'rhr_final_release_confirmed' for e in events(workspace))


def test_root_turn_budget_is_cumulative_across_reestimation_frames():
    remaining = 20
    remaining = _remaining_root_turns(remaining, MonitorAction('root_route', {'prior_model_turns': 5}))
    remaining = _remaining_root_turns(remaining, MonitorAction('root_reestimate', {
        'model_turns_used_in_this_subreview': 4}))
    assert remaining == 11
    remaining = _remaining_root_turns(remaining, MonitorAction('root_reestimate', {
        'model_turns_used_in_this_subreview': 11}))
    assert remaining == 0
    with pytest.raises(ValueError):
        _remaining_root_turns(20, MonitorAction('root_reestimate', {
            'model_turns_used_in_this_subreview': -1}))


def test_provider_failure_clears_horizon_and_restores_parent(tmp_path, monkeypatch):
    monitor, client, workspace, handoff = fixture(tmp_path, rhr=True, rer=True)
    x = contrast()
    snapshots = _script(monkeypatch, client, [('allow_complete', x), ('allow_complete', x)])
    client.history = [{'role': 'user', 'content': [
        {'type': 'text', 'text': 'SENTINEL_OLD_PROGRESS'}]}]
    first = monitor.review('root', completion_pending=True, root_handoff=handoff)
    monitor.enter_root_reestimate(handoff, first)

    def fail(_tools):
        raise RuntimeError('offline provider failure')

    monkeypatch.setattr(client, '_request_once', fail)
    with pytest.raises(Exception, match='offline provider failure'):
        monitor.review('root', completion_pending=True, root_handoff=handoff)
    assert len(snapshots) == 2
    assert monitor.crs.root_reorientation is None
    assert monitor._rer_parent_history is None
    assert 'SENTINEL_OLD_PROGRESS' in json.dumps(client.export_history())
    assert not any(e['event'] == 'rhr_final_release_confirmed' for e in events(workspace))


def test_frozen_prompt_and_provider(tmp_path):
    root = Path(__file__).resolve().parents[2]
    for source in ('ase_v0.py', 'provider.py'):
        path = 'GenericAgent-main/monitor_agent_core/' + source
        frozen = subprocess.check_output(['git', 'show',
            '29bdcb1694835aa8a6007cfa95e595e714604fca:' + path], cwd=root)
        assert frozen == (root / path).read_bytes()
