"""Link recorded PMA reminder text to later complete Task requests, if exact."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.archive_live_six_task import private_values
from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.export_gap_visible_audit import (
    BEARER, KEY, THINKING_TAG, URL, Sanitizer, canonical, file_sha,
)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def strings(value: object):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from strings(child)


def augment(run_root: Path, public_root: Path, secrets: list[str], *, refresh: bool = False) -> dict:
    root = run_root.resolve(strict=True)
    public = public_root.resolve(strict=True)
    index_path = public / 'INDEX.json'
    index = json.loads(index_path.read_bytes())
    if index['schema'] != 'historical-visible-sources-v1' or index['run_id'] != root.name:
        raise ValueError('package/run identity mismatch')
    prior = index.get('derived_reminder_links')
    if prior and not refresh:
        raise ValueError('reminder links already derived')
    if prior:
        prior_file = public / prior['public']
        if prior_file.name != 'reminders.jsonl.gz' or file_sha(prior_file) != prior['public_sha256']:
            raise ValueError('existing derived file identity changed')
    trajectory_path = root / 'host_private/archive/trajectory_memory.json'
    event_paths = list((root / 'jobs').glob('*/*/agent/research_events.jsonl'))
    if not trajectory_path.is_file() or len(event_paths) != 1:
        return {'run_id': root.name, 'status': 'source_unavailable'}
    trajectory = json.loads(trajectory_path.read_bytes())
    events = []
    with event_paths[0].open('rb') as stream:
        for number, raw in enumerate(stream, 1):
            value = json.loads(raw)
            events.append({'value': value, 'line': number, 'sha256': sha(raw)})
    ready = [row for row in events if row['value'].get('event_type') == 'provider_request_ready']
    ready_views = []
    for turn, row in enumerate(ready, 1):
        payload = row['value'].get('payload') or {}
        ready_views.append((turn, row, payload.get('content_availability'),
                            tuple(strings((payload.get('content') or {}).get('messages', [])))))
    response = {row['value'].get('llm_call_id'): row for row in events
                if row['value'].get('event_type') == 'provider_response_content'}
    actions = {row['value'].get('llm_call_id'): row for row in events
               if row['value'].get('event_type') == 'action_selected'}
    links = []
    for step in trajectory.get('steps', []):
        if step.get('should_inject') is not True:
            continue
        reminder = step.get('context_for_action')
        if not isinstance(reminder, str) or not reminder:
            links.append({'step_id': step.get('step_id'), 'status': 'invalid_recorded_reminder'})
            continue
        matches = []
        prior_matches = 0
        for turn, row, availability, visible_strings in ready_views:
            event = row['value']
            if availability != 'complete':
                continue
            if any(reminder in text for text in visible_strings):
                if event.get('timestamp', '') < step.get('timestamp', ''):
                    prior_matches += 1
                else:
                    matches.append((turn, row))
        if not matches:
            links.append({'step_id': step.get('step_id'),
                          'reminder_sha256': sha(reminder.encode('utf-8')),
                          'reminder_text': reminder,
                          'status': 'no_exact_later_complete_task_request_found'})
            continue
        turn, row = matches[0]
        call_id = row['value'].get('llm_call_id')
        reply = response.get(call_id)
        action = actions.get(call_id)
        links.append({
            'step_id': step.get('step_id'), 'step_timestamp': step.get('timestamp'),
            'reminder_sha256': sha(reminder.encode('utf-8')),
            'reminder_text': reminder,
            'status': ('text_preexisted_in_task_history_new_delivery_unproven'
                       if prior_matches else
                       'exact_text_in_complete_task_request_with_visible_response'
                       if reply else 'exact_text_in_complete_task_request_response_unavailable'),
            'first_matching_task_turn': turn,
            'request_event_id': row['value'].get('event_id'),
            'request_source_line': row['line'],
            'request_source_line_sha256': row['sha256'],
            'response_event_id': reply['value'].get('event_id') if reply else None,
            'response_source_line': reply['line'] if reply else None,
            'action_event_id': action['value'].get('event_id') if action else None,
            'action_source_line': action['line'] if action else None,
            'tool_call_ids': (action['value'].get('payload') or {}).get('tool_call_ids', [])
                if action else [],
            'later_history_matches_not_new_insertions': len(matches) - 1,
            'prior_task_requests_containing_same_text': prior_matches,
        })
    sanitizer = Sanitizer(secrets)
    output = public / 'reminders.jsonl.gz'
    line_map = []
    with output.open('wb' if refresh else 'xb') as target:
        with gzip.GzipFile(fileobj=target, mode='wb', filename='', mtime=0) as stream:
            for number, link in enumerate(links, 1):
                raw = canonical(sanitizer.clean(link, f'$.reminders[{number}]')) + b'\n'
                stream.write(raw)
                line_map.append({'line': number, 'public_sha256': sha(raw)})
    with gzip.open(output, 'rt', encoding='utf-8') as stream:
        shown = stream.read()
    if (BEARER.search(shown) or KEY.search(shown) or URL.search(shown) or
            THINKING_TAG.search(shown) or any(secret in shown for secret in secrets)):
        raise ValueError('sensitive marker remains in reminder links')
    index['derived_reminder_links'] = {
        'kind': 'exact_text_and_timestamp_matching_not_independent_delivery_ack',
        'trajectory_original_sha256': file_sha(trajectory_path),
        'task_events_original_sha256': file_sha(event_paths[0]),
        'public': output.name, 'public_sha256': file_sha(output),
        'rows': len(links), 'line_map': line_map,
        'redactions': sanitizer.removals,
        'statuses': {status: sum(row['status'] == status for row in links)
                     for status in sorted({row['status'] for row in links})},
    }
    index_path.write_bytes(canonical(index) + b'\n')
    return {'run_id': root.name, 'reminders': len(links),
            'linked_with_response': sum(row['status'].endswith('visible_response') for row in links)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-root', type=Path, required=True)
    parser.add_argument('--public-root', type=Path, required=True)
    parser.add_argument('--task-profile', type=Path, required=True)
    parser.add_argument('--pma-profile', type=Path, required=True)
    parser.add_argument('--refresh', action='store_true',
                        help='rederive only after verifying the existing generated file hash')
    args = parser.parse_args()
    print(json.dumps(augment(args.run_root, args.public_root,
                            private_values(args.task_profile, args.pma_profile),
                            refresh=args.refresh), sort_keys=True))


if __name__ == '__main__':
    main()
