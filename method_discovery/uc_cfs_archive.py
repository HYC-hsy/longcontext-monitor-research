"""Copy CFS raw records and build mechanical indexes; no model or verifier call."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import shutil

from method_discovery import uc_path_control_archive as raw
from method_discovery.uc_cfs_freeze import ROOT, PLAN, CAMPAIGN


RECORDS = ROOT / 'records'


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
                       'bytes': destination.stat().st_size, 'sha256': raw.digest(destination)})
    raw.write(ROOT / 'HOST_ARCHIVE_MANIFEST.json', {'copied': copied})


def copy_cfs_deltas(slot, destination):
    trials = [path for path in (CAMPAIGN / 'jobs' / slot['run_id']).iterdir() if path.is_dir()]
    if len(trials) != 1:
        raise RuntimeError('Expected exactly one original trial')
    source = trials[0] / 'agent/monitor/monitor_private/audit/cfs_deltas'
    manifest_path = destination / 'RAW_FILE_MANIFEST.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if slot['condition'] == 'CFS' and not source.is_dir():
        raise RuntimeError('CFS delta archive missing in treatment trial')
    for original in sorted(source.glob('*.json')) if source.is_dir() else ():
        target = destination / 'monitor/audit/cfs_deltas' / original.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, target)
        manifest['copied'].append({'source': str(original),
                                   'archive': f'monitor/audit/cfs_deltas/{original.name}',
                                   'bytes': target.stat().st_size, 'sha256': raw.digest(target),
                                   'status': 'copied'})
    raw.write(manifest_path, manifest)


def augment(slot, summary):
    destination = RECORDS / f"{slot['position']:02d}_{slot['run_id']}"
    copy_cfs_deltas(slot, destination)
    dialogue = raw.rows(destination / 'monitor/audit/dialogue.jsonl')
    reviews = raw.rows(destination / 'monitor/audit/reviews.jsonl')
    progress = raw.rows(destination / 'monitor/audit/progress.jsonl')
    task = raw.rows(destination / 'agent/research_events.jsonl')
    attempts = raw.rows(destination / 'monitor/audit/request_attempts.jsonl')
    monitor_usage = raw.rows(destination / 'monitor/audit/provider_usage.jsonl')
    public = raw.rows(destination / 'monitor/task_evidence/public_events.jsonl')
    deltas = []
    for path in sorted((destination / 'monitor/audit/cfs_deltas').glob('*.json')):
        deltas.append((path, json.loads(path.read_text(encoding='utf-8'))))
    tools = [(line, row) for line, row in enumerate(dialogue, 1) if row.get('event') == 'tool_call']
    surfaces = [(line, row) for line, row in enumerate(dialogue, 1)
                if row.get('event') == 'supervisory_situation_surface']
    injections = [(line, row) for line, row in enumerate(dialogue, 1)
                  if row.get('event') == 'supervisory_situation_injected']
    tool_counts = Counter(row.get('name') for _, row in tools)
    wait_modes = Counter((row.get('arguments') or {}).get('mode')
                         for _, row in tools if row.get('name') == 'wait'
                         and isinstance(row.get('arguments'), dict))
    intervals = []
    for path, row in deltas:
        changed = row.get('changed_paths') or {}
        outcomes = row.get('code_run_outcomes') or []
        baseline = row.get('from_cursor')
        through = row.get('shown_through_cursor')
        intervals.append({
            'manifest': f'monitor/audit/cfs_deltas/{path.name}',
            'review_id': row.get('review_id'), 'from_cursor': baseline,
            'shown_through_cursor': through,
            'interval_size': through - baseline if isinstance(through, int) and isinstance(baseline, int) else None,
            'changed_path_count': sum(len(changed.get(kind) or []) for kind in ('added', 'modified', 'deleted')),
            'unique_code_run_identities': len(outcomes),
            'split_boundary_pairs': sum(bool(item.get('result_event_locator')) and
                                        int(str(item.get('call_event_locator')).rsplit('#', 1)[-1]) <= baseline
                                        for item in outcomes if isinstance(baseline, int) and
                                        str(item.get('call_event_locator')).rsplit('#', 1)[-1].isdigit()),
            'call_conflicts': sum(len(item.get('call_conflicts') or []) for item in outcomes),
            'event_locators': row.get('event_locators'), 'control': row.get('control'),
        })
    task_counts = Counter(row.get('event_type') for row in task)
    summary.update({
        'task_turns_observed': max((row.get('task_turn') for row in public
                                    if isinstance(row.get('task_turn'), int)), default=None),
        'task_provider_requests': task_counts['provider_request_ready'],
        'task_provider_attempts': task_counts['provider_request_attempt'],
        'monitor_requests': len(monitor_usage), 'monitor_provider_attempts': len(attempts),
        'monitor_review_count': len(reviews), 'monitor_file_reads': tool_counts['file_read'],
        'monitor_code_runs': tool_counts['code_run'], 'monitor_wait_modes': dict(wait_modes),
        'monitor_interventions': tool_counts['intervene'],
        'situation_surface_count': len(surfaces), 'situation_injection_count': len(injections),
        'situation_full_count': sum(not str(row.get('content', '')).startswith('Situation unchanged')
                                    for _, row in surfaces),
        'situation_unchanged_count': sum(str(row.get('content', '')).startswith('Situation unchanged')
                                         for _, row in surfaces),
        'situation_delta_manifest_count': len(deltas),
        'situation_changed_paths_total': sum(item['changed_path_count'] for item in intervals),
        'situation_unique_code_run_rows_total': sum(item['unique_code_run_identities'] for item in intervals),
        'situation_split_boundary_pairs_total': sum(item['split_boundary_pairs'] for item in intervals),
        'situation_call_conflicts_total': sum(item['call_conflicts'] for item in intervals),
    })
    raw.write(destination / 'CFS_MECHANICAL_INDEX.json', {
        'surface_events': [{'dialogue_line': line, 'review_id': row.get('review_id'),
                            'manifest_locator': row.get('manifest_locator'),
                            'shown_through_cursor': row.get('shown_through_cursor')}
                           for line, row in surfaces],
        'injection_events': [{'dialogue_line': line, 'review_id': row.get('review_id'),
                              'manifest_locator': row.get('manifest_locator'),
                              'shown_through_cursor': row.get('shown_through_cursor')}
                             for line, row in injections],
        'intervals': intervals,
        'tool_calls': [{'dialogue_line': line, 'review_id': row.get('review_id'),
                        'name': row.get('name'), 'tool_id': row.get('tool_id')}
                       for line, row in tools],
        'review_rows': len(reviews), 'progress_rows': len(progress),
        'raw_dialogue': 'monitor/audit/dialogue.jsonl',
        'raw_public_events': 'monitor/task_evidence/public_events.jsonl',
    })
    raw.write(destination / 'MECHANICAL_SUMMARY.json', summary)
    return summary


def main():
    plan = json.loads(PLAN.read_text(encoding='utf-8'))
    if len(plan['slots']) != 4 or [row['run_id'] for row in plan['slots']] != plan['run_order']:
        raise RuntimeError('Frozen plan mismatch')
    if RECORDS.exists():
        raise RuntimeError('Archive records already exist; no overwrite')
    host = json.loads((CAMPAIGN / 'host_execution/progress.json').read_text(encoding='utf-8'))
    slots = plan['slots'][:len(host)]
    if [row['run_id'] for row in slots] != [row['run_id'] for row in host]:
        raise RuntimeError('Host progress differs from frozen order')
    raw.PLAN = PLAN
    raw.PLAN_ROOT = ROOT
    raw.CAMPAIGN = CAMPAIGN
    raw.RECORDS = RECORDS
    summaries = []
    for slot in slots:
        jobs = CAMPAIGN / 'jobs' / slot['run_id']
        if jobs.is_dir() and any(path.is_dir() for path in jobs.iterdir()):
            summaries.append(augment(slot, raw.record_one(slot)))
        else:
            summaries.append({'run_id': slot['run_id'], 'status': 'no_trial_artifact',
                              'host_progress': next(row for row in host if row['run_id'] == slot['run_id'])})
    copy_host()
    raw.write(ROOT / 'BLOCK_MECHANICAL_SUMMARY.json', {'records': summaries})
    print(json.dumps({'archived_runs': [row['run_id'] for row in summaries]}, indent=2))


if __name__ == '__main__':
    main()
