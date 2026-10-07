"""Zero-model receding-horizon release boundary tests."""

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from monitor_agent_core.agent import MONITOR_TOOLS, MonitorAgent, crs_tools
from monitor_agent_core.provider import MonitorProviderClient
from test_crs_v0 import contrast, events, expose, fixture, visible


def _step(monitor, client, value, turn, *, surface=True):
    monitor.dcm.model_turn = turn
    result = monitor.dispatch('allow_complete', value)
    shown = expose(monitor, client) if surface and result.action is None else None
    return result, shown


def test_configuration_and_frozen_interfaces(tmp_path):
    monitor, client, workspace, _ = fixture(tmp_path, rhr=True)
    assert monitor.crs.receding_horizon is True
    assert [t['function']['name'] for t in crs_tools()] == [t['function']['name'] for t in MONITOR_TOOLS]
    assert set(crs_tools()[-1]['function']['parameters']['required']) == set(contrast())
    monitor.frame_kind = 'local'
    assert MONITOR_TOOLS[-1]['function']['parameters']['properties'] == {}
    for config in ({'monitor_adaptive_supervisory_environment': True,
                    'monitor_contrastive_release_state': False},
                   {'monitor_adaptive_supervisory_environment': False,
                    'monitor_contrastive_release_state': True}):
        bad = dict(client.config, **config)
        bad['monitor_receding_horizon_release'] = True
        with pytest.raises(ValueError, match=r'requires ASE \+ CRS'):
            MonitorAgent(MonitorProviderClient('anthropic', bad), workspace)


def test_exact_x_requires_focal_and_root_surface_before_release(tmp_path):
    monitor, client, workspace, _ = fixture(tmp_path, rhr=True)
    x = contrast()
    proposed, shown = _step(monitor, client, x, 1)
    assert proposed.action is None and 'Contrastive Release State' in shown
    reaffirmed, reset_surface = _step(monitor, client, x, 2)
    assert reaffirmed.action is None and reaffirmed.data['status'] == 'release_not_executed'
    assert monitor.crs.root_contrast is None
    assert 'Root Horizon Reset' in reset_surface
    assert 'Whole-task release has not executed' in reset_surface
    assert 'prior_focal_state_digest=' in reset_surface
    assert 'verified' in reset_surface and 'runtime has not judged' in reset_surface
    active = monitor.crs.root_reorientation
    material = (json.dumps(active['handoff'], sort_keys=True, ensure_ascii=False,
                           separators=(',', ':')) + '\n' + active['task_book_sha256'] +
                '\n' + active['prior_focal']['state_digest'])
    assert active['root_horizon_digest'] == hashlib.sha256(material.encode('utf-8')).hexdigest()
    final, _ = _step(monitor, client, x, 3)
    assert final.action.kind == 'allow_complete'
    assert monitor.crs.root_reorientation is None
    names = [row['event'] for row in events(workspace)]
    for name in ('rhr_entered', 'rhr_surface_prepared', 'rhr_surface_injected',
                 'rhr_final_release_confirmed'):
        assert names.count(name) == 1


def test_same_response_cannot_bypass_either_surface(tmp_path):
    monitor, client, _, _ = fixture(tmp_path, rhr=True)
    x = contrast()
    monitor.dcm.model_turn = 1
    assert monitor.dispatch('allow_complete', x).action is None
    assert monitor.dispatch('allow_complete', x).action is None
    expose(monitor, client)
    monitor.dcm.model_turn = 2
    assert monitor.dispatch('allow_complete', x).action is None
    assert monitor.dispatch('allow_complete', x).action is None
    expose(monitor, client)
    assert monitor.dispatch('allow_complete', x).action is None
    monitor.dcm.model_turn = 3
    assert monitor.dispatch('allow_complete', x).action.kind == 'allow_complete'


def test_three_provider_ready_requests_expose_focal_then_reset(tmp_path, monkeypatch):
    monitor, client, workspace, handoff = fixture(tmp_path, rhr=True)
    snapshots = []

    def offline_response(tools):
        snapshots.append(client.assembled_request_snapshot(tools))
        return ([{'type': 'tool_use', 'id': f'allow-{len(snapshots)}',
                  'name': 'allow_complete', 'input': contrast()}], {})

    monkeypatch.setattr(client, '_request_once', offline_response)
    action = monitor.review('Root', completion_pending=True, root_handoff=handoff)
    assert action.kind == 'allow_complete'
    assert len(snapshots) == 3
    first, second, third = map(visible, snapshots)
    assert 'Contrastive Release State' not in first
    assert 'Contrastive Release State' in second
    assert 'Root Horizon Reset' not in second
    assert 'Root Horizon Reset' in third
    assert 'Whole-task release has not executed' in third
    assert [row['event'] for row in events(workspace)].count('rhr_surface_injected') == 1


def test_new_focal_after_reset_runs_its_own_full_cycle(tmp_path):
    monitor, client, workspace, _ = fixture(tmp_path, rhr=True)
    x = contrast(release_blocking_state='Focal capability A may still be incomplete.')
    y = contrast(release_blocking_state='Independent capability B may still be incomplete.')
    _step(monitor, client, x, 1)
    _, reset = _step(monitor, client, x, 2)
    old_digest = monitor.crs.root_reorientation['root_horizon_digest']
    assert 'Root Horizon Reset' in reset
    selected, y_surface = _step(monitor, client, y, 3)
    assert selected.action is None and 'Contrastive Release State' in y_surface
    assert monitor.crs.root_reorientation is None
    assert monitor.crs.root_contrast['state_digest'] != old_digest
    _, second_reset = _step(monitor, client, y, 4)
    assert 'Root Horizon Reset' in second_reset
    final, _ = _step(monitor, client, y, 5)
    assert final.action.kind == 'allow_complete'
    assert [row['event'] for row in events(workspace)].count('rhr_new_focal_selected') == 1
    assert [row['event'] for row in events(workspace)].count('rhr_entered') == 2


def test_book_change_reenters_horizon_without_semantic_parsing(tmp_path):
    monitor, client, workspace, _ = fixture(tmp_path, rhr=True)
    x = contrast()
    _step(monitor, client, x, 1)
    _step(monitor, client, x, 2)
    old = monitor.crs.root_reorientation['root_horizon_digest']
    workspace.write_text('monitor/reference.md', 'Different durable cognition.')
    blocked, refreshed = _step(monitor, client, x, 3)
    assert blocked.action is None
    new = monitor.crs.root_reorientation['root_horizon_digest']
    assert new != old and new in refreshed
    assert monitor.crs.root_reorientation['surfaced'] is True
    assert monitor.crs.root_reorientation['task_book_sha256'] == hashlib.sha256(
        workspace.resolve_read('monitor/reference.md').read_bytes()).hexdigest()
    final, _ = _step(monitor, client, x, 4)
    assert final.action.kind == 'allow_complete'
    assert any(row['event'] == 'rhr_reentered' and row['reason'] == 'task_book_changed'
               for row in events(workspace))


def test_provenance_change_returns_to_new_focal(tmp_path):
    monitor, client, workspace, _ = fixture(tmp_path, rhr=True)
    x = contrast(ground_refs=['monitor/reference.md'])
    _step(monitor, client, x, 1)
    _step(monitor, client, x, 2)
    old = monitor.crs.root_reorientation['prior_focal']['state_digest']
    workspace.write_text('monitor/reference.md', 'Revised book source.')
    revised, shown = _step(monitor, client, x, 3)
    assert revised.action is None and 'Contrastive Release State' in shown
    assert monitor.crs.root_reorientation is None
    assert monitor.crs.root_contrast['state_digest'] != old


def test_intervention_stale_handoff_and_review_failure_abandon(tmp_path):
    monitor, client, workspace, handoff = fixture(tmp_path, rhr=True)
    x = contrast()
    _step(monitor, client, x, 1)
    monitor.dcm.abandon('intervened')
    assert monitor.crs.root_contrast is None and monitor.crs.root_reorientation is None
    _step(monitor, client, x, 2)
    _step(monitor, client, x, 3)
    assert monitor.crs.root_reorientation is not None
    monitor.dcm.abandon('intervened')
    assert monitor.crs.root_reorientation is None
    _step(monitor, client, x, 4)
    _step(monitor, client, x, 5)
    assert monitor.crs.render_root(dict(handoff, generation=2), workspace) is None
    assert monitor.crs.root_reorientation is None
    _step(monitor, client, x, 6)
    monitor.dcm.end_review('review_exhausted')
    assert monitor.crs.root_contrast is None and monitor.crs.root_reorientation is None
    _step(monitor, client, x, 7)
    _step(monitor, client, x, 8)
    monitor.dcm.end_review('error')
    assert monitor.crs.root_contrast is None and monitor.crs.root_reorientation is None


def test_local_control_cannot_advance_root_reset(tmp_path):
    monitor, client, _, _ = fixture(tmp_path, rhr=True)
    x = contrast()
    _step(monitor, client, x, 1)
    _step(monitor, client, x, 2)
    reset = monitor.crs.root_reorientation
    monitor.frame_kind = 'local'
    assert monitor.dispatch('allow_complete', x).action is None
    assert monitor.crs.root_reorientation is reset
    # A pending root handoff rejects local waiting before it can touch RHR.
    assert monitor.dispatch('wait', {'after_turns': 1, 'mode': 'follow'}).action is None
    assert monitor.crs.root_reorientation is reset


def test_baseline_without_rhr_retains_two_stage_release(tmp_path):
    monitor, client, _, _ = fixture(tmp_path, rhr=False)
    _step(monitor, client, contrast(), 1)
    confirmed, _ = _step(monitor, client, contrast(), 2)
    assert confirmed.action.kind == 'allow_complete'


def test_frozen_prompt_and_no_new_state_file():
    root = Path(__file__).resolve().parents[2]
    before = subprocess.check_output(['git', 'show',
        'dfec10511bdafe97e8a0041cb95d19f5bed4de9b:GenericAgent-main/monitor_agent_core/ase_v0.py'],
        cwd=root)
    now = (root / 'GenericAgent-main/monitor_agent_core/ase_v0.py').read_bytes()
    assert before == now
    source = (root / 'GenericAgent-main/monitor_agent_core/crs_v0.py').read_text(encoding='utf-8')
    assert 'coverage_complete' not in source and 'root_supported' not in source
