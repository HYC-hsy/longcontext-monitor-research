"""Export every recorded public-visible row of a finished PMA-gap batch.

This is a read-only projection. It never opens a verifier script or hidden test
body. Gzip members are complete redacted streams, not developer summaries.
"""

from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import re

from .archive_live_six_task import private_values
from .export_gap_visible_audit import Sanitizer, canonical, file_sha, sha


HOST_STREAMS = ('accepted', 'events', 'gap_cycle', 'gap_visible_transport',
                'memory_payload', 'memory_transport')
HOST_OBJECTS = ('memory', 'trajectory_memory')
ARCHIVE_OBJECTS = ('agent_start_identity', 'agent_end_native',
                   'native_evaluator_uploaded', 'live_result', 'download_retry_v1')


def _stream(source: Path, target: Path, root: Path, sanitizer: Sanitizer) -> dict:
    if not source.resolve(strict=True).is_relative_to(root.resolve(strict=True)):
        raise ValueError('source outside selected run')
    input_hash = hashlib.sha256()
    output_hash = hashlib.sha256()
    line_map = []
    redactions = Counter()
    with source.open('rb') as inp, target.open('xb') as compressed:
        with gzip.GzipFile(fileobj=compressed, mode='wb', filename='', mtime=0) as out:
            for number, raw in enumerate(inp, 1):
                if not raw.strip():
                    raise ValueError(f'blank source row: {source.name}:{number}')
                input_hash.update(raw)
                before = len(sanitizer.removals)
                clean = sanitizer.clean(json.loads(raw))
                for removal in sanitizer.removals[before:]:
                    redactions[removal['reason']] += 1
                del sanitizer.removals[before:]
                shown = canonical({'source_line': number,
                                   'source_line_sha256': sha(raw),
                                   'value': clean}) + b'\n'
                out.write(shown)
                output_hash.update(shown)
                line_map.append({'line': number, 'original_sha256': sha(raw),
                                 'public_sha256': sha(shown)})
    return {'source': source.relative_to(root).as_posix(),
            'source_sha256': input_hash.hexdigest(), 'source_bytes': source.stat().st_size,
            'public': target.name, 'public_gzip_sha256': file_sha(target),
            'public_gzip_bytes': target.stat().st_size,
            'public_uncompressed_sha256': output_hash.hexdigest(),
            'rows': len(line_map), 'row_map': line_map,
            'redactions': dict(sorted(redactions.items()))}


def _one_json(source: Path, target: Path, root: Path, sanitizer: Sanitizer) -> dict:
    # JSON objects are one source row; no unbounded text splitting or inference.
    if not source.resolve(strict=True).is_relative_to(root.resolve(strict=True)):
        raise ValueError('source outside selected run')
    raw = source.read_bytes()
    before = len(sanitizer.removals)
    clean = sanitizer.clean(json.loads(raw))
    removals = Counter(x['reason'] for x in sanitizer.removals[before:])
    del sanitizer.removals[before:]
    shown = canonical({'source_sha256': sha(raw), 'value': clean}) + b'\n'
    with target.open('xb') as compressed:
        with gzip.GzipFile(fileobj=compressed, mode='wb', filename='', mtime=0) as out:
            out.write(shown)
    return {'source': source.relative_to(root).as_posix(),
            'source_sha256': sha(raw), 'source_bytes': len(raw),
            'public': target.name, 'public_gzip_sha256': file_sha(target),
            'public_gzip_bytes': target.stat().st_size,
            'public_uncompressed_sha256': sha(shown), 'rows': 1,
            'row_map': [{'line': 1, 'original_sha256': sha(raw),
                         'public_sha256': sha(shown)}],
            'redactions': dict(sorted(removals.items()))}


def _unique(paths: list[Path], kind: str) -> Path:
    if len(paths) != 1:
        raise ValueError(f'{kind} source not unique: {len(paths)}')
    return paths[0]


def export(batch_root: Path, output: Path, secrets: list[str],
           executed_code_commit: str) -> dict:
    if re.fullmatch(r'[0-9a-f]{40}', executed_code_commit) is None:
        raise ValueError('executed code commit must be an exact SHA')
    batch_root = batch_root.resolve(strict=True)
    selection_path = batch_root / 'selection_result.json'
    selection = json.loads(selection_path.read_bytes())
    slots = selection.get('slots', [])
    if len(slots) != 20 or selection.get('remaining_not_started') != []:
        raise ValueError('batch has not reached 20 distinct terminal slots')
    output.mkdir(parents=True, exist_ok=False)
    index = {'schema': 'pma-gap-batch20-visible-projection-v1',
             'executed_code_commit': executed_code_commit,
             'selection_source_sha256': file_sha(selection_path),
             'selection_source_bytes': selection_path.stat().st_size,
             'slots': [], 'never_exported': ['private_profiles', 'authorization_contents',
                 'hidden_thinking', 'raw_http_headers', 'verifier_scripts',
                 'hidden_test_cases', 'hidden_test_stdout']}
    for row in slots:
        if row.get('status') != 'attempted':
            raise ValueError('slot has no attempted terminal status')
        slot = batch_root / f"{row['order']:02d}-{row['task']}-r{row['occurrence']}"
        run = _unique(list((slot / 'runs').iterdir()), 'run directory')
        if not run.is_dir():
            raise ValueError('run directory missing')
        result = json.loads((run / 'archive/live_result.json').read_bytes())
        run_id = result['run_id']
        manifest = json.loads((slot / 'manifest.json').read_bytes())
        if (manifest['planned_order'][0]['task'] != row['task'] or
                manifest['planned_order'][0]['research_candidate'] != 'pma_gap_memory_v0' or
                manifest['config'].get('evaluation_bootstrap_protocol') !=
                    'download_retry_v1' or
                result.get('research_candidate') != 'pma_gap_memory_v0' or
                result.get('zero_model_fixture_only') is not False or
                result.get('cleanup_confirmed') is not True or
                run.name != run_id):
            raise ValueError('run identity, method, protocol, or cleanup differs')
        directory = output / slot.name
        directory.mkdir(exist_ok=False)
        sanitizer = Sanitizer(secrets)
        files = []
        host = run / 'host_private/archive'
        for name in HOST_STREAMS:
            files.append(_stream(host / f'{name}.jsonl',
                                 directory / f'{name}.jsonl.gz', run, sanitizer))
        for name in HOST_OBJECTS:
            files.append(_one_json(host / f'{name}.json',
                                   directory / f'{name}.json.gz', run, sanitizer))
        task_events = _unique(list((run / 'jobs').glob('*/*/agent/research_events.jsonl')),
                              'Task event')
        files.append(_stream(task_events, directory / 'task_events.jsonl.gz', run, sanitizer))
        for name in ARCHIVE_OBJECTS:
            files.append(_one_json(run / 'archive' / f'{name}.json',
                                   directory / f'{name}.json.gz', run, sanitizer))
        stage_dir = run / 'archive/download_retry_v1_stages'
        for number, stage in enumerate(sorted(stage_dir.glob('*.json')), 1):
            files.append(_one_json(stage, directory / f'evaluation_stage_{number:03d}.json.gz',
                                   run, sanitizer))
        optional = run / 'archive/native_reports_checked.json'
        if optional.is_file():
            files.append(_one_json(optional, directory / 'native_reports_checked.json.gz',
                                   run, sanitizer))
        native = result.get('native_result') or {}
        ctrf_paths = list((run / 'jobs').glob('*/*/verifier/ctrf.json'))
        if native.get('status') == 'native_recorded':
            ctrf = _unique(ctrf_paths, 'native CTRF')
            summary = json.loads(ctrf.read_bytes())['results']['summary']
            reward = native['rewards']['reward']
            ctrf_source = {'file': ctrf.relative_to(run).as_posix(),
                           'sha256': file_sha(ctrf), 'bytes': ctrf.stat().st_size}
            public_summary = {key: summary[key] for key in
                ('tests', 'passed', 'failed', 'skipped', 'pending', 'other')}
        elif native.get('status') == 'unavailable' and not ctrf_paths:
            reward, ctrf_source, public_summary = 'unavailable', None, None
        else:
            raise ValueError('native evaluation state or report differs')
        bootstrap = json.loads((run / 'archive/download_retry_v1.json').read_bytes())
        if (bootstrap.get('run_id') != run_id or
                (reward == 'unavailable' and
                 (bootstrap.get('status') != 'bootstrap_failed' or
                  bootstrap.get('test_starts') != 0)) or
                (reward != 'unavailable' and
                 (bootstrap.get('status') != 'evaluation_completed' or
                  bootstrap.get('test_starts') != 1))):
            raise ValueError('evaluation outcome and bootstrap receipt differ')
        identity = {'run_id': run_id, 'task': row['task'], 'order': row['order'],
            'condition': 'B', 'research_candidate': 'pma_gap_memory_v0',
            'manifest_sha256': file_sha(slot / 'manifest.json'),
            'config_sha256': manifest['config_sha256'],
            'executed_code_commit': executed_code_commit,
            'runtime_policy': manifest['config'].get('runtime_policy'),
            'disposition': row['result']['arm']['disposition'],
            'cleanup_confirmed': result['cleanup_confirmed'],
            'evaluation_status': native['status'], 'reward': reward,
            'bootstrap_status': bootstrap['status'],
            'bootstrap_failed_stage': bootstrap.get('failed_stage'),
            'test_entry_starts': bootstrap['test_starts'],
            'download_coverage': bootstrap.get('coverage'),
            'max_download_attempts': bootstrap.get('max_attempts'),
            'ctrf_source': ctrf_source, 'ctrf_summary': public_summary}
        (directory / 'IDENTITY.json').write_bytes(canonical(identity) + b'\n')
        (directory / 'INDEX.json').write_bytes(canonical({
            'schema': 'pma-gap-run-visible-projection-v1', 'run_id': run_id,
            'files': files, 'identity_sha256': file_sha(directory / 'IDENTITY.json'),
            'redaction_policy': 'export_gap_visible_audit.Sanitizer',
            'private_originals_retained': True}) + b'\n')
        index['slots'].append({'order': row['order'], 'task': row['task'],
            'run_id': run_id, 'identity_sha256': file_sha(directory / 'IDENTITY.json'),
            'index_sha256': file_sha(directory / 'INDEX.json'),
            'reward': reward, 'evaluation_status': native['status'],
            'files': len(files), 'public_bytes': sum(x['public_gzip_bytes'] for x in files)})
    (output / 'INDEX.json').write_bytes(canonical(index) + b'\n')
    return {'slots': len(index['slots']),
            'scored': sum(x['reward'] != 'unavailable' for x in index['slots']),
            'unavailable': sum(x['reward'] == 'unavailable' for x in index['slots']),
            'public_bytes': sum(x['public_bytes'] for x in index['slots'])}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--task-profile', type=Path, required=True)
    parser.add_argument('--pma-profile', type=Path, required=True)
    parser.add_argument('--executed-code-commit', required=True)
    args = parser.parse_args()
    print(json.dumps(export(args.batch_root, args.output,
                            private_values(args.task_profile, args.pma_profile),
                            args.executed_code_commit)))


if __name__ == '__main__':
    main()
