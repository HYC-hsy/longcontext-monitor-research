"""Mechanically preserve a finished static batch without reading diagnostic quality."""

from __future__ import annotations

import collections
import hashlib
import json
from pathlib import Path
import shutil
from urllib.parse import urlparse
import zipfile

from .static_live_batch import SLOTS


SOURCE = Path(r'E:\fyne_evidence_static_batch_20261012_run1')
TARGET = Path(__file__).resolve().parent / 'archive' / 'static_batch_run1_redacted_20261013'
DIRECTORIES = ('host_requests', 'host_audit', 'host_spool', 'monitor_private',
               'task_evidence', 'trusted_control', 'scratch')
ROOT_FILES = ('BATCH_STARTED.json', 'BATCH_RESULT.json', 'MANIFEST_USED.json',
              'AUTHORIZATION_USED.json', 'RAW_FILE_INDEX.json', 'STATIC_BATCH_AUDIT.txt')
SLOT_FILES = ('RESEARCH_ONLY_MANIFEST.json', 'SLOT_RESULT.json',
              'STATIC_CONTROL_PROPOSAL.json', 'child_stdout.txt', 'child_stderr.txt')


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':')).encode('utf-8')


def event_rows(path: Path):
    if not path.is_file():
        return
    with path.open(encoding='utf-8') as stream:
        for number, line in enumerate(stream, 1):
            try:
                yield number, json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f'Damaged event JSONL: {path}:{number}') from exc


REDACTED = []


def redaction_terms():
    profile = json.loads(Path(r'E:\LongContext\monitor_config\models.local.json')
                         .read_text(encoding='utf-8'))['claude_monitor_opus48']
    values = [str(profile.get(key) or '') for key in ('apikey', 'apibase', 'proxy')]
    values += [urlparse(value).hostname or '' for value in values if '://' in value]
    return [value.encode('utf-8') for value in sorted(set(values), key=len, reverse=True)
            if len(value) >= 7]


def copy_verified(source: Path, target: Path, terms):
    if source.is_dir():
        target.mkdir()
        for original in source.rglob('*'):
            if original.is_file():
                duplicate = target / original.relative_to(source)
                copy_verified(original, duplicate, terms)
    elif source.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        if digest(source) != digest(target):
            raise RuntimeError(f'Archive copy mismatch: {source}')
        data = target.read_bytes()
        original = data
        for term in terms:
            data = data.replace(term, b'[REDACTED_PRIVATE_ENDPOINT_OR_CREDENTIAL]')
        if data != original:
            target.write_bytes(data)
            REDACTED.append({'path': str(target.relative_to(TARGET)).replace('\\', '/'),
                'raw_sha256': digest(source), 'redacted_sha256': digest(target)})


def main():
    if TARGET.exists():
        raise RuntimeError('Research archive target already exists')
    if (Path(r'E:\fyne_evidence_static_batch_control_20261012') /
            'AUTHORIZATION.json').exists():
        raise RuntimeError('Active authorization was not removed')
    batch = json.loads((SOURCE / 'BATCH_RESULT.json').read_text(encoding='utf-8'))
    if batch.get('started_count') != 12 or batch.get('planned') != SLOTS or len(batch['slots']) != 12:
        raise RuntimeError('Batch did not contain the exact twelve planned slots')
    raw_index = json.loads((SOURCE / 'RAW_FILE_INDEX.json').read_text(encoding='utf-8'))
    post_run_mutations = []
    for row in raw_index:
        path = SOURCE / row['path']
        if not path.is_file():
            raise RuntimeError(f'Raw batch index file missing: {row["path"]}')
        actual_sha = digest(path)
        if path.stat().st_size != row['bytes'] or actual_sha != row['sha256']:
            if row['path'] != '01-C01-R1-N/app/.git/index':
                raise RuntimeError(f'Raw batch index mismatch: {row["path"]}')
            post_run_mutations.append({'path': row['path'],
                'batch_close_bytes': row['bytes'], 'batch_close_sha256': row['sha256'],
                'after_git_status_bytes': path.stat().st_size,
                'after_git_status_sha256': actual_sha,
                'cause': 'post-batch read-only-intended git status refreshed Git index; '
                         'no model call occurred afterward'})
    if len(post_run_mutations) != 1:
        raise RuntimeError('Expected one explicitly audited Git-index mutation')
    TARGET.mkdir(parents=True)
    terms = redaction_terms()
    for name in ROOT_FILES:
        copy_verified(SOURCE / name, TARGET / name, terms)
    batch = json.loads((TARGET / 'BATCH_RESULT.json').read_text(encoding='utf-8'))
    summaries = []
    for slot, result in zip(SLOTS, batch['slots']):
        if result['slot'] != slot:
            raise RuntimeError('Slot order or condition changed')
        name = f"{slot['order']:02d}-{slot['scene']}-{slot['repeat']}-{slot['condition']}"
        source = SOURCE / name
        target = TARGET / name
        target.mkdir()
        for item in DIRECTORIES + SLOT_FILES:
            copy_verified(source / item, target / item, terms)
        provider = list(event_rows(target / 'host_requests' / 'provider_events.jsonl'))
        dialogue_path = (target / 'host_audit' / 'dialogue.jsonl'
                         if slot['condition'] == 'E' else
                         target / 'monitor_private' / 'audit' / 'dialogue.jsonl')
        dialogue = [(number, row) for number, row in event_rows(dialogue_path)
                    if row.get('timestamp', 0) >= result['started_unix']]
        attempts = [row for _, row in provider if row.get('event') == 'request_started']
        finished = [row for _, row in provider if row.get('event') == 'request_finished']
        usage = collections.Counter()
        for _, row in provider:
            if row.get('event') == 'request_usage':
                for key, value in row.get('usage', {}).items():
                    if isinstance(value, int):
                        usage[key] += value
        events = collections.Counter(row.get('event') for _, row in dialogue)
        tools = collections.Counter(row.get('name') or row.get('data', {}).get('name')
                                    or 'unknown' for _, row in dialogue
                                    if row.get('event') == 'tool_call')
        summaries.append({'slot': slot, 'run_id': result['run_id'],
            'outcome_kind': (result.get('outcome') or {}).get('kind'),
            'error_type': result.get('error_type'), 'error_chain': result.get('error_chain'),
            'integrity_failure': result.get('integrity_failure'),
            'cleanup_certified': result.get('cleanup_certified'),
            'outer_cycles': result['complete_calls'],
            'pre_send_attempts': result['pre_send_attempts'],
            'provider_request_started': len(attempts),
            'provider_request_finished': len(finished),
            'provider_successes': sum(row.get('outcome') == 'success' for row in finished),
            'provider_retries': sum(row.get('attempt', 1) > 1 for row in attempts),
            'maintenance_attempts': sum(row.get('purpose') != 'review' for row in attempts),
            'provider_usage_known': dict(usage),
            'current_dialogue_events': dict(events),
            'current_tool_calls_by_name': dict(tools),
            'current_tool_calls': events.get('tool_call', 0),
            'current_tool_results': events.get('tool_result', 0),
            'current_control_results': events.get('control_result', 0),
            'elapsed_seconds': result['ended_unix'] - result['started_unix'],
            'workspace_git_status': 'not_run_to_preserve_batch_git_index',
            'raw_dialogue_locator': str(dialogue_path.relative_to(TARGET)).replace('\\', '/'),
            'raw_provider_locator': f'{name}/host_requests/provider_events.jsonl'})
    (TARGET / 'MECHANICAL_SLOT_SUMMARY.json').write_bytes(canonical(summaries))
    scope = {'original_run_root': str(SOURCE),
        'original_raw_index_sha256': digest(SOURCE / 'RAW_FILE_INDEX.json'),
        'original_raw_file_count': len(raw_index),
        'original_raw_bytes': sum(row['bytes'] for row in raw_index),
        'first_post_batch_index_verification': '32919 checked, 0 mismatches before git status',
        'post_batch_git_index_mutation': post_run_mutations,
        'redacted_archival_copies': REDACTED,
        'excluded_from_remote': 'Twelve immutable app source trees and empty scratch dirs; '
                                'their original local paths, identities and every-file hashes '
                                'remain in RAW_FILE_INDEX.json and each RESEARCH_ONLY_MANIFEST.json.',
        'native_evaluator_calls': 0, 'Task_Agent_calls': 0,
        'quality_interpretation': 'not_performed'}
    (TARGET / 'ARCHIVE_SCOPE.json').write_bytes(canonical(scope))
    audit = ('HOST-STATIC N/E BATCH: MECHANICAL ARCHIVE\n\n'
             'This is not a Task outcome or diagnostic-quality judgment.\n'
             'The source run index was verified file-by-file before copying.\n'
             'Active authorization was absent before archiving.\n\n'
             'ARCHIVE SCOPE\n' + json.dumps(scope, ensure_ascii=False, indent=2) +
             '\n\nFROZEN MANIFEST\n' + (TARGET / 'MANIFEST_USED.json').read_text(encoding='utf-8') +
             '\n\nAUTHORIZATION USED\n' + (TARGET / 'AUTHORIZATION_USED.json').read_text(encoding='utf-8') +
             '\n\nMECHANICAL SLOT SUMMARY\n' + json.dumps(summaries, ensure_ascii=False, indent=2) +
             '\n\nBATCH RESULT\n' + (TARGET / 'BATCH_RESULT.json').read_text(encoding='utf-8') +
             '\n\nIndividual raw request, SSE, dialogue, command, receipt and control files '
             'are directly readable under each slot directory.\n')
    (TARGET / 'COMPLETE_REDACTED_AUDIT.txt').write_text(audit, encoding='utf-8')
    rows = [{'path': str(path.relative_to(TARGET)).replace('\\', '/'),
             'bytes': path.stat().st_size, 'sha256': digest(path)}
            for path in sorted(TARGET.rglob('*')) if path.is_file() and
            path.name not in {'RESEARCH_ARCHIVE_FILE_INDEX.json', 'RAW_TRAJECTORIES.zip'}]
    (TARGET / 'RESEARCH_ARCHIVE_FILE_INDEX.json').write_bytes(canonical(rows))
    archive = TARGET / 'RAW_TRAJECTORIES.zip'
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED,
                         compresslevel=6, allowZip64=True) as zipped:
        for row in rows:
            zipped.write(TARGET / row['path'], row['path'])
    with zipfile.ZipFile(archive) as zipped:
        if zipped.testzip() is not None:
            raise RuntimeError('ZIP CRC validation failed')
        for row in rows:
            if hashlib.sha256(zipped.read(row['path'])).hexdigest() != row['sha256']:
                raise RuntimeError(f'ZIP entry mismatch: {row["path"]}')
    print(json.dumps({'slots': len(summaries), 'archived_files': len(rows),
        'raw_index_sha256': digest(SOURCE / 'RAW_FILE_INDEX.json'),
        'research_index_sha256': digest(TARGET / 'RESEARCH_ARCHIVE_FILE_INDEX.json'),
        'zip_bytes': archive.stat().st_size, 'zip_sha256': digest(archive)}, sort_keys=True))


if __name__ == '__main__':
    main()
