"""Resolve only the authorized live S flags and transport values; never log secrets."""

from __future__ import annotations


PILOT_OVERRIDES = {
    'monitor_adaptive_supervisory_environment': True,
    'monitor_contrastive_release_state': True,
    'monitor_receding_horizon_release': True,
    'monitor_root_epistemic_reestimation': True,
    'monitor_history_projection': 'root_records_v1',
    'monitor_pilot_zero_ambiguous_retry': True,
    'timeout': 120,
    'read_timeout': 300,
    'max_retries': 0,
    'verify': True,
    'proxy': None,
}


def resolved_supervisor_profile(base: dict) -> dict:
    if base.get('model') != 'claude-opus-4-8':
        raise ValueError('Pilot Supervisor model identity mismatch')
    if base.get('max_tokens') != 8192 or base.get('thinking_type') != 'adaptive':
        raise ValueError('Pilot Supervisor model generation identity mismatch')
    if base.get('reasoning_effort') != 'high':
        raise ValueError('Pilot Supervisor reasoning setting mismatch')
    if not base.get('apikey') or not base.get('apibase'):
        raise ValueError('Pilot Supervisor transport profile incomplete')
    configured = dict(base)
    configured.update(PILOT_OVERRIDES)
    return configured


def public_profile_identity(config: dict) -> dict:
    """Return a credential-free manifest subset."""
    keys = ('model', 'max_tokens', 'thinking_type', 'reasoning_effort', 'temperature',
            'timeout', 'read_timeout', 'max_retries', 'verify',
            *tuple(key for key in PILOT_OVERRIDES if key.startswith('monitor_')))
    return {key: config.get(key) for key in keys}
