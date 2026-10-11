"""Research-only, no-provider configuration checks."""

import pytest

from method_discovery.curator_supervisor_convergence_v0.real_task_effect_pilot_preflight_20261010.pilot_profile import (
    public_profile_identity, resolved_supervisor_profile)


BASE = {'model': 'claude-opus-4-8', 'max_tokens': 8192,
        'thinking_type': 'adaptive', 'reasoning_effort': 'high',
        'apikey': 'offline-test', 'apibase': 'https://offline.invalid'}


def test_explicit_candidate_resolution_and_old_paths():
    candidate = resolved_supervisor_profile(BASE, variant='evidence_package_v1')
    assert candidate['monitor_evidence_package_v1'] is True
    assert candidate['monitor_narrow_supervisor_v1'] is True
    assert candidate['monitor_adaptive_supervisory_environment'] is True
    assert candidate['monitor_history_projection'] == 'off'
    assert all(candidate[key] is False for key in (
        'monitor_contrastive_release_state', 'monitor_receding_horizon_release',
        'monitor_root_epistemic_reestimation'))
    assert public_profile_identity(candidate)['monitor_evidence_package_v1'] is True
    assert 'monitor_evidence_package_v1' not in public_profile_identity(
        resolved_supervisor_profile(BASE, variant='narrow_v1'))
    assert 'monitor_evidence_package_v1' not in public_profile_identity(
        resolved_supervisor_profile(BASE, variant='legacy'))
    for variant in ('legacy', 'narrow_v1'):
        with pytest.raises(ValueError):
            resolved_supervisor_profile({**BASE, 'monitor_evidence_package_v1': True},
                                        variant=variant)
    with pytest.raises(ValueError):
        resolved_supervisor_profile({**BASE, 'monitor_root_epistemic_reestimation': True},
                                    variant='evidence_package_v1')

