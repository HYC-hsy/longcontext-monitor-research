"""Stream a stopped formal run into bounded public files without resuming it."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.archive_live_six_task import UnsafePublicProjection
from .archive_formal_v6_stop import public
from .collect_native_shared import secrets_from_profile

LIMIT = 16 * 1024 * 1024


def digest(path: Path) -> tuple[int, str]:
    hashed = hashlib.sha256()
    size = 0
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            size += len(block)
            hashed.update(block)
    return size, hashed.hexdigest()


def selected(source: Path) -> dict[str, Path]:
    task = source / '02_adaptive-rejection-sampler'
    identity = json.loads((task / 'run_identity.json').read_text(encoding='utf-8'))
    run = Path(identity['run_root']).resolve(strict=True)
    if not run.is_relative_to(task.resolve(strict=True)):
        raise RuntimeError('run root outside task directory')
    trials = [p for p in (run / 'jobs').glob('*/*') if
              (p / 'agent/research_events.jsonl').is_file()]
    if len(trials) != 1:
        raise RuntimeError('Task trial not unique')
    trial = trials[0]
    mapping = {}
    for name in ('scope.json', 'prepare_02.json'):
        mapping['scope/' + name] = source / name
    for name in ('manifest.json', 'plan.json', 'run_identity.json',
                 'serial_start.json', 'serial_result.json',
                 'authorization_removed.json', 'serial_stdout.txt',
                 'serial_stderr.txt', 'batch_result.json'):
        path = task / name
        if path.is_file():
            mapping['02/' + name] = path
    for name in ('agent_start_identity.json', 'agent_end_native.json',
                 'control_process_registry.json', 'harbor.stderr.log',
                 'harbor.stdout.log', 'live_command_public.json',
                 'live_result.json', 'native_evaluator_uploaded.json',
                 'native_reports_checked.json', 'native_test_execution.json',
                 'pos_archive_status.json', 'prepared.json',
                 'verification_released.json', 'writer_termination_check.json'):
        path = run / 'archive' / name
        if path.is_file():
            mapping['02/archive/' + name] = path
    for name in ('events.jsonl', 'events.provider.jsonl', 'events.host.jsonl',
                 'events.result.json', 'events.close.json', 'events.stderr.log'):
        path = run / 'control/pos_archive' / name
        if path.is_file():
            mapping['02/pos/' + name] = path
    for name in ('research_events.jsonl', 'task_terminal.json',
                 'agent_stdout.log', 'agent_stderr.log',
                 'agent_process_return_code.txt'):
        path = trial / 'agent' / name
        if path.is_file():
            mapping['02/task/' + name] = path
    for name in ('result.json', 'verifier/ctrf.json',
                 'verifier/reward.txt', 'verifier/test-stdout.txt'):
        path = trial / name
        if path.is_file():
            mapping['02/task/' + name] = path
    for order, name in ((3, 'sqlite-with-gcov'), (4, 'write-compressor')):
        directory = source / f'{order:02d}_{name}'
        for item in ('manifest.json', 'plan.json', 'run_identity.json'):
            mapping[f'{order:02d}/{item}'] = directory / item
    return mapping


def archive_line_file(name: str, path: Path, target: Path,
                      secrets: list[str]) -> dict:
    source_bytes, source_sha = digest(path)
    parts, omissions = [], []
    stream = None
    part_size = 0
    part_number = 0
    redactions = 0
    line_count = 0
    with path.open('rb') as original:
        try:
            for number, raw in enumerate(original, 1):
                line_count += 1
                try:
                    data, count = public(raw, secrets)
                except (UnsafePublicProjection, UnicodeError):
                    omissions.append({'line': number,
                                      'source_sha256': hashlib.sha256(raw).hexdigest(),
                                      'source_bytes': len(raw),
                                      'reason': 'unsafe_public_projection'})
                    continue
                if stream is None or (part_size + len(data) > LIMIT and part_size):
                    if stream is not None:
                        stream.close()
                    part_number += 1
                    relative = f'{name}.part{part_number:03d}.jsonl'
                    output = target / relative
                    output.parent.mkdir(parents=True, exist_ok=True)
                    stream = output.open('xb')
                    parts.append(relative)
                    part_size = 0
                stream.write(data)
                part_size += len(data)
                redactions += count
        finally:
            if stream is not None:
                stream.close()
    return {'path': name, 'source_bytes': source_bytes,
            'source_sha256': source_sha, 'source_lines': line_count,
            'public_parts': [dict(path=part, bytes=digest(target / part)[0],
                                  sha256=digest(target / part)[1])
                             for part in parts],
            'redactions': redactions, 'omissions': omissions}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--target', type=Path, required=True)
    parser.add_argument('--task-profile', type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    if list(source.glob('*/authorization.json')):
        raise RuntimeError('activity authorization remains')
    secrets = secrets_from_profile(args.task_profile)
    files = selected(source)
    args.target.mkdir(parents=True, exist_ok=False)
    rows = []
    for name, path in sorted(files.items()):
        if path.suffix == '.jsonl':
            rows.append(archive_line_file(name, path, args.target, secrets))
            continue
        raw = path.read_bytes()
        try:
            data, count = public(raw, secrets)
        except UnsafePublicProjection:
            rows.append({'path': name, 'source_bytes': len(raw),
                         'source_sha256': hashlib.sha256(raw).hexdigest(),
                         'public_parts': [], 'redactions': 0,
                         'omissions': [{'reason': 'unsafe_public_projection'}]})
            continue
        output = args.target / name
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('xb') as stream:
            stream.write(data)
        rows.append({'path': name, 'source_bytes': len(raw),
                     'source_sha256': hashlib.sha256(raw).hexdigest(),
                     'public_parts': [dict(path=name, bytes=len(data),
                                           sha256=hashlib.sha256(data).hexdigest())],
                     'redactions': count, 'omissions': []})
    index = dict(schema='pos-ga-remaining-stop-public-v1',
                 source=str(source), files=rows,
                 public_copy_is_byte_identical_to_source=False)
    output = args.target / 'FILE_HASHES.json'
    with output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(index, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    for row in rows:
        for part in row['public_parts']:
            if digest(args.target / part['path']) != (part['bytes'], part['sha256']):
                raise RuntimeError('public readback mismatch: ' + part['path'])
    print(json.dumps({'files': len(rows),
        'omissions': sum(len(x['omissions']) for x in rows),
        'redactions': sum(x['redactions'] for x in rows),
        'index_sha256': digest(output)[1]}))


if __name__ == '__main__':
    main()
