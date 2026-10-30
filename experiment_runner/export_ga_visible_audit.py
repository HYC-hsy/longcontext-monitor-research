"""Read-only, source-mapped visible GA transcript export for stopped real runs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.archive_live_six_task import private_values
from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.export_gap_visible_audit import (
    BEARER, KEY, THINKING_TAG, URL, Sanitizer, canonical, file_sha, sha,
)


HIDDEN_BLOCKS = {'thinking', 'redacted_thinking', 'reasoning'}


def _read_jsonl(path: Path, root: Path) -> tuple[list[dict], dict]:
    if not path.resolve(strict=True).is_relative_to(root.resolve(strict=True)):
        raise ValueError('source outside run root')
    records = []
    with path.open('rb') as stream:
        for number, raw in enumerate(stream, 1):
            if not raw.strip():
                raise ValueError(f'blank source line {number}')
            value = json.loads(raw)
            records.append({'value': value, 'source_line': number,
                            'source_sha256': sha(raw), 'source_bytes': len(raw)})
    return records, {'relative_path': path.relative_to(root).as_posix(),
                     'sha256': file_sha(path), 'bytes': path.stat().st_size,
                     'lines': len(records)}


def _strip_hidden_blocks(value: object, removals: list[dict], where: str) -> object:
    if isinstance(value, dict):
        if isinstance(value.get('type'), str) and value['type'] in HIDDEN_BLOCKS:
            removals.append({'path': where, 'reason': 'hidden_block',
                             'original_value_sha256': sha(canonical(value))})
            return {'type': value['type'], 'excluded': 'hidden_block',
                    'original_value_sha256': sha(canonical(value))}
        return {key: _strip_hidden_blocks(item, removals, f'{where}.{key}')
                for key, item in value.items()}
    if isinstance(value, list):
        return [_strip_hidden_blocks(item, removals, f'{where}[{n}]')
                for n, item in enumerate(value)]
    return value


def _write_jsonl(path: Path, values: list[dict], sanitizer: Sanitizer) -> dict:
    rows = []
    with path.open('xb') as stream:
        for number, value in enumerate(values, 1):
            raw = canonical(sanitizer.clean(value, f'$.{path.name}[{number}]')) + b'\n'
            stream.write(raw)
            rows.append({'public_line': number, 'sha256': sha(raw), 'bytes': len(raw),
                         'source_line': value.get('source_line'),
                         'source_sha256': value.get('source_sha256')})
    return {'file': path.name, 'sha256': file_sha(path), 'bytes': path.stat().st_size,
            'lines': len(values), 'line_map': rows}


def export(run_root: Path, output: Path, run_id: str, secrets: list[str]) -> dict:
    root = run_root.resolve(strict=True)
    live_path = root / 'archive/live_result.json'
    live = json.loads(live_path.read_bytes())
    if (live.get('run_id') != run_id or live.get('condition') != 'A' or
            live.get('research_candidate') not in (None, 'U') or
            live.get('zero_model_fixture_only') is not False or
            live.get('native_result', {}).get('status') != 'native_recorded'):
        raise ValueError('not a completed real GA-only run')
    event_paths = list((root / 'jobs').glob('*/*/agent/research_events.jsonl'))
    terminal_paths = list((root / 'jobs').glob('*/*/agent/task_terminal.json'))
    report_paths = list((root / 'jobs').glob('*/*/verifier/ctrf.json'))
    if any(len(paths) != 1 for paths in (event_paths, terminal_paths, report_paths)):
        raise ValueError('Task event, terminal, or report source missing/ambiguous')
    original, source = _read_jsonl(event_paths[0], root)
    if any(row['value'].get('run_id') != run_id for row in original):
        raise ValueError('cross-run event in source')
    terminal = json.loads(terminal_paths[0].read_bytes())
    ctrf = json.loads(report_paths[0].read_bytes())
    by_kind: dict[str, list[dict]] = {}
    for row in original:
        by_kind.setdefault(row['value']['event_type'], []).append(row)
    ready = by_kind.get('provider_request_ready', [])
    visible = by_kind.get('provider_response_content', [])
    response = by_kind.get('provider_response', [])
    actions = by_kind.get('action_selected', [])
    if not ready or len(ready) != len(actions):
        raise ValueError('Task request/action cardinality differs')
    keyed = lambda rows: {row['value']['llm_call_id']: row for row in rows}
    if any(len(keyed(rows)) != len(rows) for rows in (ready, visible, actions)):
        raise ValueError('duplicate Task call identity')
    responses_by_call = {}
    for row in response:
        responses_by_call.setdefault(row['value']['llm_call_id'], []).append(row)
    if not set(responses_by_call) == set(keyed(ready)) or \
            set(keyed(actions)) != set(keyed(ready)) or \
            not set(keyed(visible)) <= set(keyed(ready)):
        raise ValueError('Task call identity mismatch')
    if any(row['value']['payload'].get('content_availability') != 'complete'
           for row in ready):
        raise ValueError('Task-visible request capture incomplete')

    omitted = []
    projected = []
    for row in original:
        value = _strip_hidden_blocks(row['value'], omitted,
                                     f'events[{row["source_line"]}]')
        projected.append({**{k: row[k] for k in ('source_line', 'source_sha256',
                                                  'source_bytes')}, 'event': value})
    receipts = {}
    for turn, row in enumerate(ready, 1):
        content = row['value']['payload']['content']
        for message in content.get('messages', []):
            for block in message.get('content', []):
                if isinstance(block, dict) and block.get('type') == 'tool_result':
                    receipts.setdefault(block['tool_use_id'], []).append({
                        'visible_in_task_turn': turn, 'source_line': row['source_line'],
                        'block': block})
    turns = []
    for turn, row in enumerate(ready, 1):
        call_id = row['value']['llm_call_id']
        shown = keyed(visible).get(call_id)
        response_attempts = responses_by_call[call_id]
        response_row = response_attempts[-1]
        blocks = shown['value']['payload']['parsed_visible_blocks'] if shown else []
        if not shown and response_row['value']['payload'].get('outcome') not in {
                'http_error', 'transport_error', 'incomplete', 'error'}:
            raise ValueError(f'missing visible response without recorded failure at turn {turn}')
        tools = []
        for block in blocks:
            if block.get('type') != 'tool_use':
                continue
            future = [item for item in receipts.get(block['id'], [])
                      if item['visible_in_task_turn'] > turn]
            if not future:
                raise ValueError(f'Task tool receipt not captured for turn {turn}')
            tools.append({'tool_call': block, 'receipt': future[0]})
        turns.append({'task_turn': turn, 'llm_call_id': call_id,
                      'source_line': row['source_line'],
                      'source_sha256': row['source_sha256'],
                      'request_event_id': row['value']['event_id'],
                      'request_payload_sha256': row['value']['payload']['sha256'],
                      'task_visible_request': row['value']['payload']['content'],
                      'visible_response_source_line': shown['source_line'] if shown else None,
                      'visible_response_blocks': blocks,
                      'response_event_id': response_row['value']['event_id'],
                      'response_outcome': response_row['value']['payload'].get('outcome'),
                      'response_attempts': [{
                          'source_line': attempt['source_line'],
                          'event_id': attempt['value']['event_id'],
                          'outcome': attempt['value']['payload'].get('outcome')}
                          for attempt in response_attempts],
                      'action_event_id': keyed(actions)[call_id]['value']['event_id'],
                      'tools_and_later_visible_receipts': tools})

    output.mkdir(parents=True, exist_ok=False)
    sanitizer = Sanitizer(secrets)
    public = [_write_jsonl(output / 'events.jsonl', projected, sanitizer),
              _write_jsonl(output / 'task_turns.jsonl', turns, sanitizer)]
    summary = ctrf['results']['summary']
    evaluation = {'run_id': run_id, 'terminal': terminal,
                  'native_status': live['native_result']['status'],
                  'reward': live['native_result']['rewards']['reward'],
                  'ctrf_summary': {key: summary.get(key) for key in
                                   ('tests', 'passed', 'failed', 'skipped',
                                    'pending', 'other')},
                  'cleanup_confirmed': live.get('cleanup_confirmed')}
    public.append(_write_jsonl(output / 'evaluation.jsonl', [evaluation], sanitizer))
    blob = b''.join((output / item['file']).read_bytes() for item in public)
    text = blob.decode('utf-8')
    if (any(secret.encode('utf-8') in blob for secret in secrets) or
            BEARER.search(text) or KEY.search(text) or URL.search(text) or
            THINKING_TAG.search(text)):
        raise ValueError('sensitive marker remains in public projection')
    index = {'schema': 'ga-visible-readonly-audit-v1', 'run_id': run_id,
             'private_originals': {'research_events': source,
                 'task_terminal': {'relative_path': terminal_paths[0].relative_to(root).as_posix(),
                                   'sha256': file_sha(terminal_paths[0])},
                 'live_result': {'relative_path': live_path.relative_to(root).as_posix(),
                                 'sha256': file_sha(live_path)},
                 'native_ctrf': {'relative_path': report_paths[0].relative_to(root).as_posix(),
                                 'sha256': file_sha(report_paths[0])}},
             'public_kind': 'redacted_reencoded_jsonl_not_original_http_bytes',
             'public_files': public, 'excluded_or_replaced': omitted + sanitizer.removals,
             'counts': {'events': len(original), 'task_turns': len(turns),
                        'provider_response_attempts': len(response),
                        'complete_visible_responses': len(visible),
                        'tool_calls_with_later_visible_receipts': sum(
                            len(turn['tools_and_later_visible_receipts']) for turn in turns)}}
    (output / 'INDEX.json').write_bytes(canonical(index) + b'\n')
    return index['counts']


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--task-profile', type=Path, required=True)
    parser.add_argument('--pma-profile', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export(args.run_root, args.output, args.run_id,
        private_values(args.task_profile, args.pma_profile)), sort_keys=True))


if __name__ == '__main__':
    main()
