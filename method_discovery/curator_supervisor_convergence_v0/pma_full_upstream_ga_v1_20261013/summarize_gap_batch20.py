"""Summarize a verified, full visible PMA-gap batch projection."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import gzip
import json
from pathlib import Path
import re

from .export_gap_visible_audit import canonical, file_sha
from .verify_gap_batch20_visible import verify


def _values(path: Path):
    with gzip.open(path, 'rb') as stream:
        for raw in stream:
            yield json.loads(raw)['value']


def _seconds(section: dict | None) -> float | None:
    if not section or not section.get('started_at') or not section.get('finished_at'):
        return None
    start = datetime.fromisoformat(section['started_at'].replace('Z', '+00:00'))
    end = datetime.fromisoformat(section['finished_at'].replace('Z', '+00:00'))
    return round((end - start).total_seconds(), 3)


def summarize(batch_root: Path, public_root: Path, authorization_index: Path,
              expected_slots: int = 20) -> dict:
    verified = verify(batch_root, public_root, expected_slots)
    index = json.loads((public_root / 'INDEX.json').read_bytes())
    auth = json.loads(authorization_index.read_bytes())
    if (auth.get('authorizations_removed') is not True or
            len(auth.get('files', [])) != expected_slots or
            any((batch_root / row['slot'] / 'authorization.json').exists()
                for row in auth['files'])):
        raise ValueError('one-use authorizations not fully revoked')
    result = {'schema': f'pma-gap-batch{expected_slots}-result-v1',
              'executed_code_commit': index['executed_code_commit'],
              'method': 'pma-gap', 'research_candidate': 'pma_gap_memory_v0',
              'evaluation_preparation': 'download_retry_v1',
              'persistent_evaluation_cache': False,
              'agent_time_protocol': 'diagnostic_uncapped_not_official_agent_limit',
              'source_selection_sha256': index['selection_source_sha256'],
              'public_index_sha256': file_sha(public_root / 'INDEX.json'),
              'authorization_index_sha256': file_sha(authorization_index),
              'all_authorizations_removed': True,
              'verified_public_members': verified['members'], 'slots': []}
    for row in index['slots']:
        directory = public_root / f"{row['order']:02d}-{row['task']}-r1"
        run = batch_root / directory.name / 'runs' / row['run_id']
        identity = json.loads((directory / 'IDENTITY.json').read_bytes())
        gap = list(_values(directory / 'gap_cycle.jsonl.gz'))
        requests = list(_values(directory / 'memory_payload.jsonl.gz'))
        responses = list(_values(directory / 'gap_visible_transport.jsonl.gz'))
        events = list(_values(directory / 'events.jsonl.gz'))
        task_events = list(_values(directory / 'task_events.jsonl.gz'))
        role_counts = Counter(item['phase'] for item in requests)
        response_counts = Counter(item['phase'] for item in responses)
        request_keys = {(item['cycle_step'], item['call_sequence'], item['phase'])
                        for item in requests}
        response_keys = {(item['cycle_step'], item['call_sequence'], item['phase'])
                         for item in responses}
        missing = sorted(request_keys - response_keys)
        if missing:
            trajectory = json.loads((run / 'host_private/archive/trajectory_memory.json').read_bytes())
            steps = {step['step_count']: step for step in trajectory['steps']}
            missing = [{'cycle_step': step, 'call_sequence': sequence, 'phase': phase,
                        'trajectory_response_present': isinstance(steps[step].get(
                            'raw_response_phase1' if phase == 'maintenance' else
                            'raw_response_phase2'), str)} for step, sequence, phase in missing]
        task_counts = Counter(item['event_type'] for item in task_events)
        reminders_selected = sum(bool(item.get('result', {}).get('reminder'))
                                 for item in events)
        explicit_silent = sum(bool(re.fullmatch(r'<no_intervention\s*/>',
            item.get('content', '').strip())) for item in responses
            if item['phase'] == 'selection')
        delivered = sum(bool(item.get('payload', {}).get('pma_reminder_event_id'))
                        for item in task_events if item['event_type'] == 'provider_request_ready')
        commands = sum(len(item['event'].get('commands') or []) for item in events
                       if item['event'].get('kind') == 'actor_step')
        usage = Counter()
        for item in task_events:
            if item['event_type'] == 'provider_usage':
                for key in ('input_tokens', 'output_tokens',
                            'cache_creation_input_tokens', 'cache_read_input_tokens'):
                    if type(item.get('payload', {}).get(key)) is int:
                        usage[key] += item['payload'][key]
        trial_paths = list((run / 'jobs').glob('*/*/result.json'))
        if len(trial_paths) != 1:
            raise ValueError('Harbor trial result not unique')
        trial = json.loads(trial_paths[0].read_bytes())
        detail = {'order': row['order'], 'task': row['task'], 'run_id': row['run_id'],
                  'disposition': identity['disposition'],
                  'reward': identity['reward'],
                  'evaluation_status': identity['evaluation_status'],
                  'bootstrap_status': identity['bootstrap_status'],
                  'bootstrap_failed_stage': identity['bootstrap_failed_stage'],
                  'test_entry_starts': identity['test_entry_starts'],
                  'download_coverage': identity['download_coverage'],
                  'max_download_attempts': identity['max_download_attempts'],
                  'maintenance_requests': role_counts['maintenance'],
                  'selection_requests': role_counts['selection'],
                  'maintenance_visible_responses': response_counts['maintenance'],
                  'selection_visible_responses': response_counts['selection'],
                  'missing_role_response_captures': missing,
                  'cycles': len(gap), 'reminders_selected': reminders_selected,
                  'reminders_in_Task_requests': delivered,
                  'explicit_silent_responses': explicit_silent,
                  'other_nonreminding_cycles': len(gap) - reminders_selected - explicit_silent,
                  'Task_request_attempt_events': task_counts['provider_request_attempt'],
                  'Task_valid_visible_responses': task_counts['provider_response_content'],
                  'Task_recorded_tool_commands': commands,
                  'Task_usage_reported': dict(usage),
                  'auxiliary_physical_HTTP_attempts': 'unavailable',
                  'pre_agent_setup_seconds': _seconds(trial.get('environment_setup')),
                  'agent_setup_seconds': _seconds(trial.get('agent_setup')),
                  'Task_execution_seconds': _seconds(trial.get('agent_execution')),
                  'verifier_phase_seconds': _seconds(trial.get('verifier')),
                  'trial_result_source_sha256': file_sha(trial_paths[0]),
                  'public_identity_sha256': row['identity_sha256'],
                  'public_index_sha256': row['index_sha256'],
                  'cleanup_confirmed': identity['cleanup_confirmed']}
        if (role_counts['maintenance'] != role_counts['selection'] or
                role_counts['maintenance'] != len(gap) or
                delivered != reminders_selected or
                detail['other_nonreminding_cycles'] < 0):
            detail['capture_or_delivery_discrepancy'] = True
        result['slots'].append(detail)
    result['totals'] = {
        'planned': expected_slots, 'started': len(result['slots']),
        'native_scored': sum(x['reward'] != 'unavailable' for x in result['slots']),
        'reward_one': sum(x['reward'] == 1.0 for x in result['slots']),
        'reward_zero': sum(x['reward'] == 0.0 for x in result['slots']),
        'evaluation_unavailable': sum(x['reward'] == 'unavailable' for x in result['slots']),
        'Task_request_attempt_events': sum(x['Task_request_attempt_events'] for x in result['slots']),
        'Task_recorded_tool_commands': sum(x['Task_recorded_tool_commands'] for x in result['slots']),
        'maintenance_requests': sum(x['maintenance_requests'] for x in result['slots']),
        'selection_requests': sum(x['selection_requests'] for x in result['slots']),
        'reminders_selected': sum(x['reminders_selected'] for x in result['slots']),
        'reminders_in_Task_requests': sum(x['reminders_in_Task_requests'] for x in result['slots']),
        'explicit_silent_responses': sum(x['explicit_silent_responses'] for x in result['slots']),
        'other_nonreminding_cycles': sum(x['other_nonreminding_cycles'] for x in result['slots']),
        'test_entry_starts': sum(x['test_entry_starts'] for x in result['slots']),
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch-root', type=Path, required=True)
    parser.add_argument('--public-root', type=Path, required=True)
    parser.add_argument('--authorization-index', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--expected-slots', type=int, default=20)
    args = parser.parse_args()
    result = summarize(args.batch_root, args.public_root, args.authorization_index,
                       args.expected_slots)
    with args.output.open('xb') as stream:
        stream.write(canonical(result) + b'\n')
    print(json.dumps(result['totals']))


if __name__ == '__main__':
    main()
