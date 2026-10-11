"""Mechanical post-run summary and integrity checks; no model or evaluator path."""

import collections
import hashlib
import json
from pathlib import Path
import tarfile
import zipfile

from pack import private_markers


HERE = Path(__file__).resolve().parent
CONTROL = Path(r'E:\pilot_live_batch2_20261011_8cfc4ef2')
NAMES = ('fyne_t', 'fyne_s', 'kitex_s', 'kitex_t')
SOURCE = Path(r'E:\LongContext\long_context_bench\.cache\m12_roadmap_tasks')


def sha(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(data)
    return value.hexdigest()


def lines(path):
    if not path.is_file():
        return []
    with path.open(encoding='utf-8') as stream:
        return [json.loads(line) for line in stream if line.strip()]


def usage_sum(rows):
    keys = ('input_tokens', 'output_tokens', 'cache_creation_input_tokens',
            'cache_read_input_tokens', 'cached_input_tokens')
    return {key: sum(int(row.get(key) or 0) for row in rows) for key in keys}


def task_summary(root):
    event_file = next((root / 'jobs').glob('*/public_agent_task__*/agent/research_events.jsonl'))
    rows = lines(event_file)
    events = collections.Counter(row['event_type'] for row in rows)
    calls = collections.Counter()
    for row in rows:
        if row['event_type'] == 'action_selected':
            calls.update(row['payload'].get('tool_names') or [])
    usage = [row['payload'] for row in rows if row['event_type'] == 'provider_usage']
    return {'event_counts': dict(events), 'tool_calls_by_name': dict(calls),
            'tool_calls_proposed': sum(calls.values()),
            'outer_requests': events['provider_request_ready'],
            'provider_attempts': events['provider_request_attempt'],
            'provider_responses': events['provider_response'],
            'usage_records': len(usage), 'usage_sum': usage_sum(usage),
            'task_wire_payload_limit': 'research_events contain request hashes/metadata, not all raw Task wire bodies'}


def monitor_summary(root):
    audit = root / 'monitor/monitor_private/audit'
    if not audit.is_dir():
        return None
    dialogue = lines(audit / 'dialogue.jsonl')
    progress = lines(audit / 'progress.jsonl')
    attempts = lines(audit / 'request_attempts.jsonl')
    usage = lines(audit / 'provider_usage.jsonl')
    calls = collections.Counter(row['name'] for row in dialogue if row.get('event') == 'tool_call')
    events = collections.Counter(row.get('event') for row in dialogue)
    progress_events = collections.Counter(row.get('event') for row in progress)
    outcomes = collections.Counter(row.get('outcome', 'unknown') for row in attempts)
    return {'dialogue_events': dict(events), 'progress_events': dict(progress_events),
            'tool_calls_by_name': dict(calls), 'tool_calls': sum(calls.values()),
            'model_outputs': events['model_output'], 'request_attempts': len(attempts),
            'request_attempt_outcomes': dict(outcomes),
            'retry_attempts': sum(int(row.get('attempt', 1)) > 1 for row in attempts),
            'usage_records': len(usage), 'usage_sum': usage_sum(usage),
            'reviews': len(lines(audit / 'reviews.jsonl'))}


def workspace_manifest(root, short, markers):
    archive = root / 'archive/pre_evaluation_app.tar'
    output = []
    forbidden = []
    with tarfile.open(archive, 'r:') as tar:
        for member in tar:
            name = member.name.removeprefix('./')
            if name.startswith('../') or name.startswith('/'):
                raise RuntimeError('Unsafe frozen workspace tar path')
            if member.isfile():
                stream = tar.extractfile(member)
                value = hashlib.sha256()
                chunks = []
                while data := stream.read(1024 * 1024):
                    value.update(data)
                    chunks.append(data)
                raw = b''.join(chunks)
                if any(marker in raw for marker in markers):
                    forbidden.append(name)
                output.append({'path': name, 'bytes': member.size,
                               'sha256': value.hexdigest(), 'type': 'file'})
            elif member.issym() or member.islnk():
                output.append({'path': name, 'type': 'link', 'target': member.linkname})
    if forbidden:
        raise RuntimeError(f'Private profile marker in frozen product: {len(forbidden)} files')
    expected_source = SOURCE / short / 'environment/repo'
    final = {row['path']: row for row in output if row['type'] == 'file' and
             '.git' not in Path(row['path']).parts}
    initial = {path.relative_to(expected_source).as_posix(): sha(path)
               for path in expected_source.rglob('*') if path.is_file() and
               not path.is_symlink() and '.git' not in path.relative_to(expected_source).parts}
    changed = [name for name, row in final.items() if name in initial and row['sha256'] != initial[name]]
    added = [name for name in final if name not in initial]
    missing = [name for name in initial if name not in final]
    return {'frozen_tar_sha256': sha(archive), 'members': output,
            'comparison_basis': str(expected_source),
            'comparison_is_raw_path_and_content_hash_not_semantic_diff': True,
            'changed': sorted(changed), 'added': sorted(added), 'missing': sorted(missing)}


def main():
    markers = private_markers()
    status = json.loads((HERE / 'control/BATCH_STATUS.json').read_text(encoding='utf-8'))
    arms = []
    for name, slot in zip(NAMES, status['slots']):
        root = Path(slot['run_root'])
        trial_path = next((root / 'jobs').glob('*/public_agent_task__*/result.json'))
        trial = json.loads(trial_path.read_text(encoding='utf-8'))
        frozen = json.loads((root / 'archive/agent_end_frozen.json').read_text(encoding='utf-8'))
        result = json.loads((root / 'archive/pilot_result.json').read_text(encoding='utf-8'))
        short = 'fyn-2.2.0-roadmap' if name.startswith('fyne') else 'ktx-0.13.0-roadmap'
        workspace = workspace_manifest(root, short, markers)
        workspace_path = HERE / 'arms' / name / 'FINAL_WORKSPACE_MANIFEST.json'
        workspace_path.write_text(json.dumps(workspace, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        arms.append({'slot': slot, 'run_id': frozen['run_id'],
                     'archive_status': (trial.get('agent_result') or {}).get('metadata', {}).get('archive_status'),
                     'legal_agent_end': frozen['legal_agent_end'],
                     'writers_stopped': frozen['writers_stopped'],
                     'sidecar_clean': frozen['sidecar_clean'],
                     'evaluator_released': result['harbor_verifier_released'],
                     'native_result': (trial.get('verifier_result') or {}).get('rewards'),
                     'native_score_unavailable_reason': (None if trial.get('verifier_result') else
                         'legal_agent_end_false_or_verifier_not_released'),
                     'task': task_summary(root), 'supervisor': monitor_summary(root),
                     'workspace_manifest_path': workspace_path.relative_to(HERE).as_posix(),
                     'workspace_tar_sha256': workspace['frozen_tar_sha256'],
                     'workspace_changed_path_count': len(workspace['changed']),
                     'workspace_added_path_count': len(workspace['added']),
                     'workspace_missing_path_count': len(workspace['missing'])})
    summary = {'schema': 'pilot-batch2-mechanical-summary-v1',
               'run_code_commit': status['code_commit'], 'manifest_sha256': status['manifest_sha256'],
               'authorization_sha256': status['authorization_sha256'],
               'planned_arms': 4, 'started_arms': sum(s['status'] != 'not_started' for s in status['slots']),
               'arms': arms, 'semantic_result_classification': 'not_performed'}
    (HERE / 'MECHANICAL_SUMMARY.json').write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    manifest = json.loads((HERE / 'RAW_FILE_MANIFEST.json').read_text(encoding='utf-8'))
    for row in manifest['copied']:
        path = HERE / row['path']
        if not path.is_file() or path.stat().st_size != row['bytes'] or sha(path) != row['sha256']:
            raise RuntimeError(f'Archived file identity mismatch: {row["path"]}')
    for row in manifest.get('reassembly', []):
        value = hashlib.sha256()
        count = 0
        for part in row['parts']:
            with (HERE / part).open('rb') as stream:
                for data in iter(lambda: stream.read(1024 * 1024), b''):
                    value.update(data)
                    count += len(data)
        if value.hexdigest() != row['sha256'] or count != row['bytes']:
            raise RuntimeError('Split checkpoint reassembly mismatch')
    index = {'schema': 'pilot-batch2-raw-trace-index-v1',
             'manifest_sha256': sha(HERE / 'RAW_FILE_MANIFEST.json'),
             'copied_files_verified': len(manifest['copied']),
             'copied_bytes_verified': sum(row['bytes'] for row in manifest['copied']),
             'local_checkpoint_source_files_hashed': len(manifest['local_only']),
             'reassembly': manifest.get('reassembly', []),
             'trace_files': [row for row in manifest['copied'] if row['path'].endswith(
                 ('.jsonl', '.log', '.txt', '.json'))]}
    (HERE / 'RAW_TRACE_INDEX.json').write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    text = ('Fyne/Kitex pilot batch 2 — mechanical audit package\n'
            'No semantic comparison or method-effect classification was performed.\n'
            'Archived files are listed with SHA-256 in RAW_FILE_MANIFEST.json.\n'
            'The oversized Fyne S checkpoint archive is reassembled from ordered parts.\n'
            'Raw Task wire bodies are not universally captured; research_events contain hashes/metadata.\n'
            'Kitex S legal_agent_end=false; native evaluator not released, native score unavailable.\n'
            'Running Task/Supervisor/provider calls in this post-run archival phase: 0.\n\n'
            'FROZEN MANIFEST\n' + (HERE / 'FYNE_KITEX_FOUR_ARM_MANIFEST_BATCH2.json').read_text(encoding='utf-8') +
            '\nAUTHORIZATION\n' + (HERE / 'AUTHORIZATION.json').read_text(encoding='utf-8') +
            '\nBATCH STATUS\n' + (HERE / 'control/BATCH_STATUS.json').read_text(encoding='utf-8') +
            '\nMECHANICAL SUMMARY\n' + json.dumps(summary, ensure_ascii=False, indent=2) + '\n'
            '\nRAW TRACE INDEX\n' + json.dumps(index, ensure_ascii=False, indent=2) + '\n')
    (HERE / 'AUDIT_PACKAGE.txt').write_text(text, encoding='utf-8')
    zip_path = HERE / 'RAW_TRAJECTORIES.zip'
    with zipfile.ZipFile(zip_path, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for row in index['trace_files']:
            archive.write(HERE / row['path'], row['path'])
    with zipfile.ZipFile(zip_path, 'r') as archive:
        if archive.testzip() is not None:
            raise RuntimeError('Raw trajectory ZIP CRC failure')
    print(json.dumps({'arms': len(arms), 'verified_files': len(manifest['copied']),
                      'raw_trace_zip_sha256': sha(zip_path),
                      'raw_trace_zip_bytes': zip_path.stat().st_size,
                      'audit_package_sha256': sha(HERE / 'AUDIT_PACKAGE.txt')}, indent=2))


if __name__ == '__main__':
    main()
