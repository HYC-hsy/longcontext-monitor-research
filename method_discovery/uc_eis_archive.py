"""Copy raw EIS trials and build mechanical locators; never calls a model or verifier."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import shutil

from method_discovery import uc_path_control_archive as raw
from method_discovery.uc_eis_freeze import ROOT, PLAN, CAMPAIGN


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


def copy_eis_sources(slot, destination):
    trials = [path for path in (CAMPAIGN / 'jobs' / slot['run_id']).iterdir() if path.is_dir()]
    if len(trials) != 1:
        raise RuntimeError('Expected exactly one original trial')
    source = trials[0] / 'agent/monitor/task_evidence'
    manifest_path = destination / 'RAW_FILE_MANIFEST.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    for name in ('candidate_validation_index.jsonl', 'candidate_validation_latest.json'):
        original = source / name
        target = destination / 'monitor/task_evidence' / name
        if original.is_file():
            shutil.copy2(original, target)
            manifest['copied'].append({'source': str(original), 'archive': f'monitor/task_evidence/{name}',
                                       'bytes': target.stat().st_size, 'sha256': raw.digest(target),
                                       'status': 'copied'})
        else:
            manifest['copied'].append({'source': str(original), 'archive': f'monitor/task_evidence/{name}',
                                       'status': 'missing'})
    raw.write(manifest_path, manifest)


def augment(slot, summary):
    destination = RECORDS / f"{slot['position']:02d}_{slot['run_id']}"
    copy_eis_sources(slot, destination)
    rows = raw.rows(destination / 'monitor/task_evidence/candidate_validation_index.jsonl')
    dialogue = raw.rows(destination / 'monitor/audit/dialogue.jsonl')
    reviews = raw.rows(destination / 'monitor/audit/reviews.jsonl')
    task = raw.rows(destination / 'agent/research_events.jsonl')
    monitor_usage = raw.rows(destination / 'monitor/audit/provider_usage.jsonl')
    task_usage = [row['payload'] for row in task if row.get('event_type') == 'provider_usage'
                  and isinstance(row.get('payload'), dict)]
    attempts = raw.rows(destination / 'monitor/audit/request_attempts.jsonl')
    tools = [(line, row) for line, row in enumerate(dialogue, 1) if row.get('event') == 'tool_call']
    surfaces = [(line, row) for line, row in enumerate(dialogue, 1)
                if row.get('event') == 'executable_interpretation_surface']
    counts = Counter(row.get('kind') for row in rows)
    task_counts = Counter(row.get('event_type') for row in task)
    tool_counts = Counter(row.get('name') for _, row in tools)
    def tool_path(row):
        arguments = row.get('arguments') or {}
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                return ''
        return str(arguments.get('path', '')) if isinstance(arguments, dict) else ''
    def tokens(entries):
        if not entries:
            return None
        return {key: sum(item.get(key) or 0 for item in entries) for key in
                ('input_tokens', 'output_tokens', 'cache_creation_input_tokens',
                 'cache_read_input_tokens', 'cached_input_tokens')}
    summary.update({
        'candidate_validation_artifact_change_rows': counts['task_validation_artifact_change'],
        'candidate_validation_execution_rows': counts['task_validation_execution'],
        'eis_surface_injections': len(surfaces),
        'monitor_test_file_reads': sum(row.get('name') == 'file_read' and
                                       any(token in tool_path(row).lower()
                                           for token in ('_test.', 'test_', '.spec.', '.test.', '/test/', '/tests/'))
                                       for _, row in tools),
        'monitor_code_run_calls': tool_counts['code_run'],
        'monitor_interventions': tool_counts['intervene'],
        'monitor_review_count': len(reviews),
        'task_provider_requests': task_counts['provider_request_ready'],
        'task_provider_attempts': task_counts['provider_request_attempt'],
        'monitor_requests': len(monitor_usage),
        'monitor_provider_attempts': len(attempts),
        'task_tokens_observed': tokens(task_usage),
        'monitor_tokens_observed': tokens(monitor_usage),
    })
    raw.write(destination / 'EIS_MECHANICAL_INDEX.json', {
        'surface_events': [{'dialogue_line': line, 'review_id': row.get('review_id'),
                            'event_locators': row.get('event_locators'),
                            'source_boundary': row.get('source_boundary')}
                           for line, row in surfaces],
        'validation_rows': [{'index_line': line, 'kind': row.get('kind'),
                             'event_locator': row.get('event_locator'),
                             'tool_use_id': row.get('tool_use_id')}
                            for line, row in enumerate(rows, 1)],
        'tool_calls': [{'dialogue_line': line, 'review_id': row.get('review_id'),
                        'name': row.get('name'), 'tool_id': row.get('tool_id')}
                       for line, row in tools],
        'raw_dialogue': 'monitor/audit/dialogue.jsonl',
        'raw_public_events': 'monitor/task_evidence/public_events.jsonl',
    })
    raw.write(destination / 'MECHANICAL_SUMMARY.json', summary)
    return summary


def main():
    plan = json.loads(PLAN.read_text(encoding='utf-8'))
    if [row['run_id'] for row in plan['slots']] != plan['run_order'] or len(plan['slots']) != 4:
        raise RuntimeError('Frozen plan mismatch')
    if RECORDS.exists():
        raise RuntimeError('Archive records already exist; no overwrite')
    raw.PLAN = PLAN
    raw.PLAN_ROOT = ROOT
    raw.CAMPAIGN = CAMPAIGN
    raw.RECORDS = RECORDS
    summaries = [augment(slot, raw.record_one(slot)) for slot in plan['slots']]
    copy_host()
    raw.write(ROOT / 'BLOCK_MECHANICAL_SUMMARY.json', {'records': summaries})
    print(json.dumps({'archived_runs': [row['run_id'] for row in summaries]}, indent=2))


if __name__ == '__main__':
    main()
