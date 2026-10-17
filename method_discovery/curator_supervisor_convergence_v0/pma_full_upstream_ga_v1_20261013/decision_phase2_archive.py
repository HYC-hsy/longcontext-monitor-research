"""Allowlisted public projection of a private D1/V1 Phase-2 screen run."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from zipfile import ZipFile, ZIP_DEFLATED


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def rows(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


def safe_content(value: str | None) -> tuple[str | None, dict]:
    if value is None:
        return None, {'status': 'absent'}
    if '<think>' in value and '</think>' not in value:
        return None, {'status': 'excluded_unclosed_thinking',
                      'original_sha256': digest(value.encode())}
    projected = re.sub(r'<think>.*?</think>', '[thinking omitted]', value,
                       flags=re.DOTALL)
    if re.search(r'(?i)sk-[a-z0-9]{12}|bearer\s+[a-z0-9._-]{12}', projected):
        return None, {'status': 'excluded_sensitive_pattern',
                      'original_sha256': digest(value.encode())}
    return projected, {'status': 'unchanged' if projected == value else 'thinking_removed',
                       'original_sha256': digest(value.encode())}


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n',
                    encoding='utf-8')


def archive(run_root: Path, manifest_path: Path, public_root: Path) -> dict:
    if public_root.exists():
        raise FileExistsError('public archive root must be new')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if (manifest.get('schema') != 'pma-decision-phase2-once-v1' or
            manifest.get('output_root') != str(run_root.resolve())):
        raise PermissionError('private run and frozen Phase-2 manifest differ')
    public_root.mkdir(parents=True, exist_ok=False)
    write(public_root / 'manifest_public.json', manifest)
    status_path = run_root / 'status_table.json'
    statuses = (json.loads(status_path.read_text(encoding='utf-8'))['rows']
                if status_path.is_file() else [])
    if not statuses:
        for number, row in enumerate(manifest['planned_order'], 1):
            slot = run_root / f'{number:02d}-{row["variant"].lower()}'
            statuses.append({'order': number, 'arm': row['arm'],
                             'pma_step': row['pma_step'], 'variant': row['variant'],
                             'status': ('started_incomplete' if slot.exists() else
                                        'confirmed_not_started')})
    write(public_root / 'status_table.json', {'rows': statuses})
    sample_parts = []
    exclusions = []
    for status in statuses:
        number = status['order']
        private = run_root / f'{number:02d}-{status["variant"].lower()}'
        public = public_root / f'{number:02d}-{status["variant"].lower()}'
        if not private.exists():
            continue
        request = rows(private / 'requests.jsonl')
        response = rows(private / 'responses.jsonl')
        attempts = rows(private / 'provider_attempts_private.jsonl')
        result_path = private / 'result.json'
        result = (json.loads(result_path.read_text(encoding='utf-8'))
                  if result_path.is_file() else None)
        if request:
            selected = {key: request[0].get(key) for key in
                        ('logical_call', 'phase', 'epoch', 'system', 'prompt',
                         'tools', 'prompt_sha256', 'system_sha256')}
            write(public / 'request.json', selected)
            sample_parts.append(f'=== {number:02d} {status["variant"]} REQUEST ===\n'
                                + json.dumps(selected, ensure_ascii=False, indent=2))
        if response:
            projected = []
            for entry in response:
                content, note = safe_content(entry.get('content'))
                item = {key: entry.get(key) for key in
                        ('logical_call', 'event', 'epoch', 'error_type',
                         'server_execution', 'usage', 'tool_calls')}
                item['content'] = content
                item['content_projection'] = note
                projected.append(item)
                if note['status'].startswith('excluded') or note['status'] == 'thinking_removed':
                    exclusions.append({'order': number, **note})
            write(public / 'response.json', projected)
            sample_parts.append(f'=== {number:02d} {status["variant"]} RESPONSE ===\n'
                                + json.dumps(projected, ensure_ascii=False, indent=2))
        if result is not None:
            content, note = safe_content(result.get('raw_content'))
            projected = {key: result.get(key) for key in
                         ('order', 'arm', 'pma_step', 'variant', 'status',
                          'started_epoch', 'ended_epoch', 'logical_requests',
                          'observable_litellm_calls', 'deeper_network_attempts',
                          'output_class', 'returned_usage', 'error_type',
                          'server_execution', 'accepted_response_observed',
                          'model_prompt_sha256', 'model_system_sha256')}
            projected['raw_content'] = content
            projected['content_projection'] = note
            projected['parsed_reminder'], parsed_note = safe_content(
                result.get('parsed_reminder'))
            projected['parsed_projection'] = parsed_note
            write(public / 'result.json', projected)
        if attempts:
            projected = [{key: attempt.get(key) for key in
                          ('attempt', 'event', 'epoch', 'model', 'temperature',
                           'max_tokens', 'thinking', 'reasoning_effort', 'timeout',
                           'drop_params', 'private_endpoint_present',
                           'private_key_present', 'returned_model', 'usage',
                           'error_type', 'server_execution')}
                         for attempt in attempts]
            write(public / 'provider_attempts_public.json', projected)
    write(public_root / 'projection_exclusions.json', exclusions)
    (public_root / 'REQUEST_RESPONSE_SAMPLES.txt').write_text(
        '\n\n'.join(sample_parts) + '\n', encoding='utf-8')
    summary = {'batch_id': manifest['batch_id'],
               'run_code_commit': manifest['code_identity']['commit'],
               'manifest_sha256': digest(manifest_path.read_bytes()),
               'completed': sum(row['status'] == 'completed' for row in statuses),
               'started_incomplete_or_failed': sum(row['status'] not in
                   ('completed', 'confirmed_not_started') for row in statuses),
               'confirmed_not_started': sum(row['status'] == 'confirmed_not_started'
                                            for row in statuses),
               'private_root': str(run_root), 'private_root_uploaded': False,
               'provider_internal_attempts': 'unknown',
               'phase1_task_evaluator_training_scoring_calls': 0,
               'redactions_or_exclusions': exclusions}
    write(public_root / 'SUMMARY.json', summary)
    (public_root / 'AUDIT.txt').write_text(
        'PMA U/V1/D1 Phase-2-only archived-input comparison.\n'
        'The private root retains original request/response/provider records; '
        'only allowlisted projections below are public.\n'
        'No Task delivery, Phase 1, native evaluation, training or scorer calls.\n'
        + json.dumps(summary, ensure_ascii=False, indent=2)
        + '\n\n=== VISIBLE REQUESTS AND RESPONSES ===\n'
        + '\n\n'.join(sample_parts) + '\n', encoding='utf-8')
    hashes = []
    for file in sorted(public_root.rglob('*')):
        if file.is_file() and file.name not in ('FILE_HASHES.json', 'raw_trajectories_public.zip'):
            hashes.append({'path': file.relative_to(public_root).as_posix(),
                           'bytes': file.stat().st_size, 'sha256': digest(file.read_bytes())})
    write(public_root / 'FILE_HASHES.json', hashes)
    with ZipFile(public_root / 'raw_trajectories_public.zip', 'x', ZIP_DEFLATED) as packed:
        for file in sorted(public_root.rglob('*')):
            if file.is_file() and file.name != 'raw_trajectories_public.zip':
                packed.write(file, file.relative_to(public_root).as_posix())
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-root', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--public-root', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(archive(args.run_root, args.manifest, args.public_root),
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
