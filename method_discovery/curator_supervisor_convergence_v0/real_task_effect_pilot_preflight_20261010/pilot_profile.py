"""Resolve only the authorized live S flags and transport values; never log secrets."""

from __future__ import annotations


PILOT_OVERRIDES = {
    'monitor_adaptive_supervisory_environment': True,
    'monitor_contrastive_release_state': True,
    'monitor_receding_horizon_release': True,
    'monitor_root_epistemic_reestimation': True,
    'monitor_history_projection': 'root_records_v1',
    'monitor_pilot_zero_ambiguous_retry': True,
    'incomplete_stream_recovery_v1': True,
    'timeout': 120,
    'read_timeout': 300,
    'max_retries': 0,
    'verify': True,
    'proxy': None,
}

NARROW_OVERRIDES = {
    **PILOT_OVERRIDES,
    'monitor_narrow_supervisor_v1': True,
    'monitor_contrastive_release_state': False,
    'monitor_receding_horizon_release': False,
    'monitor_root_epistemic_reestimation': False,
    'monitor_history_projection': 'off',
}


def resolved_supervisor_profile(base: dict, *, variant: str = 'legacy') -> dict:
    if variant not in {'legacy', 'narrow_v1'}:
        raise ValueError('Unsupported Supervisor variant')
    if base.get('model') != 'claude-opus-4-8':
        raise ValueError('Pilot Supervisor model identity mismatch')
    if base.get('max_tokens') != 8192 or base.get('thinking_type') != 'adaptive':
        raise ValueError('Pilot Supervisor model generation identity mismatch')
    if base.get('reasoning_effort') != 'high':
        raise ValueError('Pilot Supervisor reasoning setting mismatch')
    if not base.get('apikey') or not base.get('apibase'):
        raise ValueError('Pilot Supervisor transport profile incomplete')
    if variant == 'legacy' and base.get('monitor_narrow_supervisor_v1', False) is not False:
        raise ValueError('Narrow Supervisor requires the explicit narrow_v1 variant')
    configured = dict(base)
    if variant == 'narrow_v1':
        for key, expected in NARROW_OVERRIDES.items():
            if key.startswith('monitor_') and key in base and base[key] != expected:
                raise ValueError('Incompatible narrow Supervisor switch: ' + key)
    configured.update(NARROW_OVERRIDES if variant == 'narrow_v1' else PILOT_OVERRIDES)
    return configured


def public_profile_identity(config: dict) -> dict:
    """Return a credential-free manifest subset."""
    keys = ('model', 'max_tokens', 'thinking_type', 'reasoning_effort', 'temperature',
            'timeout', 'read_timeout', 'max_retries', 'verify',
            'incomplete_stream_recovery_v1',
            'monitor_narrow_supervisor_v1',
            *tuple(key for key in PILOT_OVERRIDES if key.startswith('monitor_')))
    return {key: config.get(key) for key in keys}
