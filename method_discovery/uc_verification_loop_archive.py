"""Copy existing raw trial artifacts and index verification events mechanically."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
import argparse
import json
from pathlib import Path
import shutil

from method_discovery import uc_path_control_archive as raw
from method_discovery.uc_verification_loop_freeze import ROOT, PLAN, CAMPAIGN
from method_discovery.uc_r5_execution_bridge import file_sha


RECORDS = ROOT / 'records'


def verify_no_gateway_credentials(slot):
    config = json.loads((CAMPAIGN / 'isolated_bundles' / slot['run_id'] / 'gateway/config.json'
                        ).read_text(encoding='utf-8'))
    secrets = [value.encode() for route in config['models'].values()
               for name, value in route['headers'].items()
               if name.lower() == 'authorization' and value]
    destination = RECORDS / f"{slot['position']:02d}_{slot['run_id']}"
    for path in destination.rglob('*'):
        if path.is_file() and any(secret in path.read_bytes() for secret in secrets):
            raise RuntimeError(f'Gateway credential found in archive file: {path.name}')


def copy_host():
    copied = []
    for source in sorted((CAMPAIGN / 'host_execution').glob('*')):
        if not source.is_file():
            continue
        destination = ROOT / 'host_execution' / source.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            raise RuntimeError('Host record already archived')
        shutil.copy2(source, destination)
        copied.append({'path': str(destination.relative_to(ROOT)).replace('\\', '/'),
                       'bytes': destination.stat().st_size, 'sha256': file_sha(destination)})
    raw.write(ROOT / 'HOST_ARCHIVE_MANIFEST.json', {'copied': copied})


def augment(slot, summary):
    destination = RECORDS / f"{slot['position']:02d}_{slot['run_id']}"
    progress = raw.rows(destination / 'monitor/audit/progress.jsonl')
    dialogue = raw.rows(destination / 'monitor/audit/dialogue.jsonl')
    reviews = raw.rows(destination / 'monitor/audit/reviews.jsonl')
    task = raw.rows(destination / 'agent/research_events.jsonl')
    public = raw.rows(destination / 'monitor/task_evidence/public_events.jsonl')
    usage = [row['payload'] for row in task if row.get('event_type') == 'provider_usage'
             and isinstance(row.get('payload'), dict)]
    monitor_usage = raw.rows(destination / 'monitor/audit/provider_usage.jsonl')
    def totals(entries):
        if not entries:
            return None
        return {key: sum(entry.get(key) or 0 for entry in entries) for key in
                ('input_tokens', 'output_tokens', 'cache_creation_input_tokens',
                 'cache_read_input_tokens', 'cached_input_tokens')}

    selected = [(line, row) for line, row in enumerate(progress, 1)
                if row.get('event') in {'verification_selected', 'verification_result',
                                        'verification_boundary_expired', 'verification_disposition',
                                        'verification_follow_opened', 'verification_follow_armed',
                                        'verification_execution_error'}]
    calls = [(line, row) for line, row in enumerate(dialogue, 1) if row.get('event') == 'tool_call']
    related_calls = [(line, row) for line, row in calls
                     if row.get('name') in {'code_run', 'intervene', 'wait', 'allow_complete'}]
    raw.write(destination / 'VERIFICATION_EVENT_INDEX.json', {
        'progress_events': [{'line': line, 'review_id': row.get('review_id'),
                             'event': row.get('event'), 'verification_id':
                             (row.get('definition') or row.get('receipt') or {}).get('id') or
                             (row.get('receipt') or {}).get('verification_id') or
                             row.get('verification_id')}
                            for line, row in selected],
        'dialogue_calls': [{'line': line, 'review_id': row.get('review_id'),
                            'name': row.get('name'), 'tool_id': row.get('tool_id')}
                           for line, row in related_calls],
        'review_rows': [{'line': line, 'action': row.get('action'), 'frame': row.get('frame'),
                         'handoff': row.get('handoff')}
                        for line, row in enumerate(reviews, 1)],
        'raw_progress': 'monitor/audit/progress.jsonl',
        'raw_dialogue': 'monitor/audit/dialogue.jsonl',
        'raw_task_events': 'agent/research_events.jsonl',
        'raw_verification_output': 'monitor/commands/',
    })
    interventions = []
    for line, call in calls:
        if call.get('name') != 'intervene':
            continue
        later = [(number, event) for number, event in enumerate(public, 1)
                 if isinstance(event.get('archived_at'), (int, float))
                 and event['archived_at'] > call.get('timestamp', 0)]
        interventions.append({
            'dialogue_line': line, 'review_id': call.get('review_id'),
            'next_public_events': [{'line': number, 'archive_sequence': event.get('archive_sequence'),
                                    'task_turn': event.get('task_turn'), 'boundary': event.get('boundary'),
                                    'tool_result_count': len(event.get('tool_results') or [])}
                                   for number, event in later[:5]],
            'next_workspace_observations': [
                {'dialogue_line': number, 'name': event.get('name'),
                 'review_id': event.get('review_id')}
                for number, event in calls if number > line and event.get('name') in {'file_read', 'code_run'}
            ][:5],
        })
    raw.write(destination / 'INTERVENTION_FOLLOW_INDEX.json', {
        'interventions': interventions,
        'raw_dialogue': 'monitor/audit/dialogue.jsonl',
        'raw_public_events': 'monitor/task_evidence/public_events.jsonl',
    })
    event_counts = Counter(row.get('event') for row in progress)
    tool_counts = Counter(row.get('name') for _, row in calls)
    task_counts = Counter(row.get('event_type') for row in task)
    definitions = {row.get('verification_id') for _, row in selected
                   if row.get('event') == 'verification_result' and row.get('verification_id')}
    summary.update({
        'task_provider_requests': task_counts.get('provider_request_ready', 0),
        'task_provider_attempts': task_counts.get('provider_request_attempt', 0),
        'task_usage_observations': len(usage), 'task_tokens_observed': totals(usage),
        'monitor_requests': len(monitor_usage),
        'monitor_provider_attempts': len(raw.rows(destination / 'monitor/audit/request_attempts.jsonl')),
        'monitor_tokens_observed': totals(monitor_usage),
        'task_turns_observed': max((row.get('internal_turn') or 0 for row in task), default=None),
        'completion_proposals': task_counts.get('completion_proposal', 0),
        'monitor_review_count': len(reviews),
        'monitor_tools': dict(tool_counts),
        'monitor_intervention_count': tool_counts.get('intervene', 0),
        'verification_select_events': event_counts.get('verification_selected', 0),
        'verification_execution_events': event_counts.get('verification_result', 0),
        'verification_distinct_result_ids': len(definitions),
        'verification_repeat_executions': max(0, event_counts.get('verification_result', 0) - len(definitions)),
        'verification_disposition_events': event_counts.get('verification_disposition', 0),
        'manual_code_run_calls': tool_counts.get('code_run', 0) if slot['condition'] == 'MANUAL' else None,
        'root_review_count': sum(row.get('frame') == 'root' for row in reviews),
        'final_review_action': ((reviews[-1].get('action') or {}).get('kind')
                                if reviews and isinstance(reviews[-1].get('action'), dict) else None),
        'task_termination_code': next((row.get('payload', {}).get('result') for row in reversed(task)
                                       if row.get('event_type') == 'termination'), None),
        'final_monitor_control_tool': next((row.get('name') for _, row in reversed(related_calls)
                                            if row.get('name') in {'wait', 'intervene', 'allow_complete'}), None),
    })
    trial = json.loads((destination / 'trial/result.json').read_text(encoding='utf-8'))
    summary['runner_valid'] = trial.get('valid')
    summary['validation_errors'] = trial.get('validation_errors')
    summary['exception_info'] = trial.get('exception_info')
    try:
        summary['duration_seconds'] = (datetime.fromisoformat(trial['finished_at'].replace('Z', '+00:00'))
            - datetime.fromisoformat(trial['started_at'].replace('Z', '+00:00'))).total_seconds()
    except (ValueError, TypeError, KeyError):
        summary['duration_seconds'] = None
    run_manifest = json.loads((destination / 'runner/manifest.json').read_text(encoding='utf-8'))
    summary['native_result'] = run_manifest.get('rewards')
    summary['trial_outcome'] = run_manifest.get('trial_outcome')
    summary['observed_models'] = (run_manifest.get('trace') or {}).get('observed_models')
    raw.write(destination / 'MECHANICAL_SUMMARY.json', summary)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--refresh-index-only', action='store_true')
    args = parser.parse_args()
    plan = json.loads(PLAN.read_text(encoding='utf-8'))
    if [slot['run_id'] for slot in plan['slots']] != plan['run_order'] or len(plan['slots']) != 4:
        raise RuntimeError('Frozen four-slot plan mismatch')
    if RECORDS.exists() and not args.refresh_index_only:
        raise RuntimeError('Archive records already exist; no overwrite')
    raw.PLAN = PLAN
    raw.PLAN_ROOT = ROOT
    raw.CAMPAIGN = CAMPAIGN
    raw.RECORDS = RECORDS
    summaries = [augment(slot, json.loads((RECORDS / f"{slot['position']:02d}_{slot['run_id']}"
                         / 'MECHANICAL_SUMMARY.json').read_text(encoding='utf-8'))
                         if args.refresh_index_only else raw.record_one(slot))
                 for slot in plan['slots']]
    for slot in plan['slots']:
        verify_no_gateway_credentials(slot)
    if not args.refresh_index_only:
        copy_host()
    raw.write(ROOT / 'BLOCK_MECHANICAL_SUMMARY.json', {'records': summaries})
    print(json.dumps({'archived_runs': [row['run_id'] for row in summaries],
                      'native_results': [row['native_result'] for row in summaries]}, indent=2))


if __name__ == '__main__':
    main()
