"""Copy and index the four completed root-scope records without re-running them."""

from __future__ import annotations

from collections import Counter
import argparse
import json
from pathlib import Path
import shutil

from method_discovery import uc_path_control_archive as previous
from method_discovery.uc_root_scope_entry import PLAN, PLAN_ROOT
from method_discovery.uc_r5_execution_bridge import file_sha


CAMPAIGN = Path(r'E:\LongContext\long_context_bench\output\uc_root_scope_v1_20261004')
RECORDS = PLAN_ROOT / 'records'


def rows(path):
    return previous.rows(path)


def copy_one(source, destination, copied):
    if not source.is_file():
        copied.append({'source': str(source), 'destination': str(destination), 'status': 'missing'})
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    copied.append({'source': str(source), 'destination': str(destination),
                   'bytes': destination.stat().st_size, 'sha256': file_sha(destination),
                   'status': 'copied'})


def augment(slot):
    run_id = slot['run_id']
    destination = RECORDS / f"{slot['position']:02d}_{run_id}"
    trial = next((CAMPAIGN / 'jobs' / run_id).iterdir())
    private = trial / 'agent/monitor/monitor_private'
    copied = []
    for source in sorted((private / 'root_working').glob('*.md')):
        copy_one(source, destination / 'monitor/root_working' / source.name, copied)
    for source in sorted((private / 'audit/root_frames').glob('*/*')):
        if source.is_file():
            copy_one(source, destination / 'monitor/root_frames' /
                     source.parent.name / source.name, copied)
    for source in sorted((private / 'audit/live_checkpoints').glob('checkpoint-*.tar')):
        copied.append({'source': str(source), 'status': 'local_only_large_artifact',
                       'bytes': source.stat().st_size, 'sha256': file_sha(source)})
    dialogue = rows(destination / 'monitor/audit/dialogue.jsonl')
    progress = rows(destination / 'monitor/audit/progress.jsonl')
    reviews = rows(destination / 'monitor/audit/reviews.jsonl')
    root_reviews = [
        {'review_row': index, 'frame': row.get('frame'), 'handoff': row.get('handoff'),
         'action': row.get('action')}
        for index, row in enumerate(reviews, 1) if row.get('frame') == 'root']
    root_events = [
        {'dialogue_line': index, 'review_id': row.get('review_id'),
         'event': row.get('event'), 'handoff': row.get('handoff')}
        for index, row in enumerate(dialogue, 1)
        if row.get('event') in {'root_frame_input', 'model_input', 'tool_call', 'tool_result'}
        and (row.get('event') == 'root_frame_input'
             or any(row.get('review_id') == r.get('review_id')
                    for r in progress if r.get('event') == 'root_frame_entered'))]
    root_progress = [
        {'progress_line': index, 'review_id': row.get('review_id'),
         'event': row.get('event'), 'generation': row.get('generation'),
         'request_id': row.get('request_id')}
        for index, row in enumerate(progress, 1)
        if row.get('event') in {'root_frame_entered', 'root_frame_left',
                                'root_checkpoint_created', 'root_checkpoint_invalid'}]
    previous.write(destination / 'ROOT_FRAME_INDEX.json', {
        'root_reviews': root_reviews, 'root_progress': root_progress,
        'root_dialogue_events': root_events,
        'first_root_request_originals': [
            {'path': str(path.relative_to(destination)).replace('\\', '/'),
             'sha256': file_sha(path)}
            for path in sorted((destination / 'monitor/root_checkpoints').glob(
                'checkpoint-*/request.json'))],
        'copied_root_files': copied,
    })
    public = rows(destination / 'monitor/task_evidence/public_events.jsonl')
    transitions = rows(destination / 'monitor/audit/workspace_transitions.jsonl')
    follow_index = []
    for root_row in root_reviews:
        review_id = next((row.get('review_id') for row in progress
                          if row.get('event') == 'root_frame_entered'
                          and row.get('request_id') == (root_row.get('handoff') or {}).get('request_id')), None)
        calls = [(line, row) for line, row in enumerate(dialogue, 1)
                 if row.get('review_id') == review_id and row.get('event') == 'tool_call']
        controls = [(line, row) for line, row in calls
                    if row.get('name') in {'intervene', 'allow_complete', 'wait'}]
        cutoff = controls[-1][1].get('timestamp') if controls else None
        later = [(line, row) for line, row in enumerate(public, 1)
                 if cutoff is not None and isinstance(row.get('archived_at'), (int, float))
                 and row['archived_at'] > cutoff]
        next_handoff = next((row.get('archive_sequence') for _, row in later
                            if row.get('boundary') == 'task_control_handoff'), None)
        until = [(line, row) for line, row in later
                 if next_handoff is None or (row.get('archive_sequence') or 0) <= next_handoff]
        handoff_cursor = (root_row.get('handoff') or {}).get('cursor')
        follow_index.append({
            'review_row': root_row['review_row'], 'review_id': review_id,
            'handoff': root_row.get('handoff'), 'root_action': root_row.get('action'),
            'root_tool_calls': [{'dialogue_line': line, 'name': row.get('name')}
                                for line, row in calls],
            'control_call': ({'dialogue_line': controls[-1][0],
                              'name': controls[-1][1].get('name')}
                             if controls else None),
            'next_task_events': [
                {'public_event_line': line, 'archive_sequence': row.get('archive_sequence'),
                 'task_turn': row.get('task_turn'), 'boundary': row.get('boundary'),
                 'tool_names': [call.get('name') for call in row.get('tool_calls') or []],
                 'tool_result_count': len(row.get('tool_results') or [])}
                for line, row in until[:20]],
            'next_task_events_total_before_next_handoff': len(until),
            'workspace_samples_until_next_handoff': [
                {'sample_line': line, 'from_cursor': row.get('from_cursor'),
                 'to_cursor': row.get('to_cursor'),
                 'added': row.get('added'), 'modified': row.get('modified'),
                 'deleted': row.get('deleted'), 'sample_complete': row.get('sample_complete')}
                for line, row in enumerate(transitions, 1)
                if isinstance(row.get('to_cursor'), int)
                and isinstance(handoff_cursor, int) and row['to_cursor'] > handoff_cursor
                and (next_handoff is None or row['to_cursor'] <= next_handoff)],
            'raw_task_path': 'monitor/task_evidence/public_events.jsonl',
            'raw_dialogue_path': 'monitor/audit/dialogue.jsonl',
        })
    previous.write(destination / 'ROOT_FOLLOW_LOCATORS.json', {'root_handoffs': follow_index})
    summary = json.loads((destination / 'MECHANICAL_SUMMARY.json').read_text(encoding='utf-8'))
    summary['root_review_count'] = len(root_reviews)
    summary['root_frame_entry_count'] = Counter(
        row.get('event') for row in progress).get('root_frame_entered', 0)
    summary['root_checkpoint_count'] = Counter(
        row.get('event') for row in progress).get('root_checkpoint_created', 0)
    summary['root_working_files'] = len(list((destination / 'monitor/root_working').glob('*.md')))
    previous.write(destination / 'MECHANICAL_SUMMARY.json', summary)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--supplement-only', action='store_true')
    args = parser.parse_args()
    plan = json.loads(PLAN.read_text(encoding='utf-8'))
    previous.PLAN = PLAN
    previous.PLAN_ROOT = PLAN_ROOT
    previous.CAMPAIGN = CAMPAIGN
    previous.RECORDS = RECORDS
    summaries = []
    for slot in plan['slots']:
        if not args.supplement_only:
            previous.record_one(slot)
        summaries.append(augment(slot))
    previous.write(PLAN_ROOT / 'BLOCK_MECHANICAL_SUMMARY.json', {'records': summaries})
    copied = []
    host = CAMPAIGN / 'host_execution'
    for source in sorted(host.glob('*')):
        if source.is_file():
            copy_one(source, PLAN_ROOT / 'host_execution' / source.name, copied)
    previous.write(PLAN_ROOT / 'HOST_ARCHIVE_MANIFEST.json', {'copied': copied})
    print(json.dumps({'archived_runs': [row['run_id'] for row in summaries],
                      'root_reviews': [row['root_review_count'] for row in summaries]}, indent=2))


if __name__ == '__main__':
    main()
