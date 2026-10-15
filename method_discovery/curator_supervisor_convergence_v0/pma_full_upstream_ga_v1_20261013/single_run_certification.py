"""Verify portable, redacted A/B Harbor fixture evidence for generic V4 runs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .prepare_six_task_manifest import V3_SOURCE_FILES, _committed_source_sha


HARBOR_COMMIT = '459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc'
SOURCE_FILES = tuple(dict.fromkeys(V3_SOURCE_FILES + (
    'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/'
    'archive_live_six_task.py',
    'method_discovery/curator_supervisor_convergence_v0/'
    'real_task_effect_pilot_preflight_20261010/pilot_fake_gateway.py',
    'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/'
    'control_processes.py',
    'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/'
    'single_run.py',
    'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/'
    'run_selection.py',
    'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/'
    'single_run_fixture.py',
    'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/'
    'single_run_certification.py',
    'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/'
    'collect_single_run_fixture.py',
    'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/'
    'harbor_adapter.py',
)))
EVIDENCE_FILES = (
    'live_result.json', 'agent_start_identity.json', 'agent_end_native.json',
    'writer_termination_check.json', 'control_process_registry.json',
    'native_reports_checked.json', 'native_test_execution.json',
    'synthetic_test.sh', 'research_events.jsonl',
    'memory_payload.jsonl', 'fake_authorization_removed.json',
)


def verify_evidence(evidence: Path) -> dict:
    outcomes = {}
    hashes = {}
    for condition in ('A', 'B'):
        base = evidence / condition
        required = [name for name in EVIDENCE_FILES
                    if condition == 'B' or name != 'memory_payload.jsonl']
        for name in required:
            path = base / name
            if not path.is_file():
                raise RuntimeError(f'generic {condition} evidence missing: {name}')
            hashes[f'{condition}/{name}'] = hashlib.sha256(path.read_bytes()).hexdigest()
        load = lambda name: json.loads((base / name).read_text(encoding='utf-8'))
        result, started, ended = (load(name) for name in
            ('live_result.json', 'agent_start_identity.json', 'agent_end_native.json'))
        writers, registry, reports = (load(name) for name in
            ('writer_termination_check.json', 'control_process_registry.json',
             'native_reports_checked.json'))
        removed = load('fake_authorization_removed.json')
        execution = load('native_test_execution.json')
        synthetic_script = (base / 'synthetic_test.sh').read_bytes()
        if (result.get('condition') != condition or
                result.get('zero_model_fixture_only') is not True or
                result.get('harbor_return_code') != 0 or
                result.get('cleanup_confirmed') is not True or
                result.get('fake_provider_captures', 0) < 2 or
                result.get('native_result', {}).get('status') != 'native_recorded' or
                result.get('native_reports_checked') is not True or
                ended.get('control_processes_stopped') is not True or
                ended.get('gateway_stopped') is not True or
                writers.get('control_remaining') != [] or
                not any(row.get('kind') == 'transport' for row in
                        writers.get('registered_control_processes', [])) or
                registry.get('container_id') != started.get('container_id') or
                started.get('provider_key_env_absent') is not True or
                started.get('hidden_tests_absent') is not True or
                reports.get('all_reports_executed') is not True or
                execution.get('observed') is not True or
                b'http://127.0.0.1:19173' not in synthetic_script or
                removed.get('authorization_removed') is not True):
            raise RuntimeError(f'generic {condition} fixture incomplete')
        events = [json.loads(line) for line in (base / 'research_events.jsonl').read_text(
            encoding='utf-8').splitlines()]
        ready = [row for row in events if row.get('event_type') == 'provider_request_ready']
        attempts = [row for row in events if row.get('event_type') == 'provider_request_attempt']
        if (len(ready) < 2 or len(attempts) < 2 or
                not all(row.get('payload', {}).get('content_availability') == 'complete'
                        for row in ready)):
            raise RuntimeError(f'generic {condition} Task requests not captured')
        if condition == 'B':
            if (result.get('worker_return_code') != 0 or
                    not any(row.get('event_type') == 'pma_reminder_appended'
                            for row in events) or
                    not any(row.get('payload', {}).get('pma_reminder_event_id')
                            for row in ready)):
                raise RuntimeError('generic PMA reminder did not enter Task request')
            phases = [json.loads(line).get('phase') for line in
                      (base / 'memory_payload.jsonl').read_text(encoding='utf-8').splitlines()]
            if not {'bank_management', 'context_decision'} <= set(phases):
                raise RuntimeError('generic PMA two-stage transport absent')
        else:
            if any(row.get('event_type') == 'pma_reminder_appended' for row in events):
                raise RuntimeError('generic Task-only fixture used PMA')
        outcomes[condition] = {'run_id': result['run_id'],
                               'task': result['task'],
                               'requests': len(ready), 'attempts': len(attempts),
                               'control_stopped': True, 'native_recorded': True}
    return {'outcomes': outcomes, 'file_sha256': hashes}


def source_identity(checkout: Path) -> dict:
    return {name: _committed_source_sha(checkout, name) for name in SOURCE_FILES}
