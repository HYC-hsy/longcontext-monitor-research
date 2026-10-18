"""Archive the stopped sampler retry and the prepared-but-unstarted suffix."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .archive_remaining_stop import archive_line_file, digest
from .archive_formal_v6_stop import public
from .collect_native_shared import secrets_from_profile
from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.archive_live_six_task import UnsafePublicProjection


def selected(source: Path) -> dict[str, Path]:
    if list(source.glob('*/authorization.json')):
        raise RuntimeError('active authorization remains')
    files = {'scope/scope.json': source / 'scope.json'}
    first = source / '01_adaptive-rejection-sampler'
    second = source / '02_write-compressor'
    identity = json.loads((first / 'run_identity.json').read_text(encoding='utf-8'))
    run = Path(identity['run_root']).resolve(strict=True)
    if not run.is_relative_to(first.resolve(strict=True)) or identity['run_id'] != run.name:
        raise RuntimeError('sampler run identity mismatch')
    if (second / 'serial_start.json').exists() or (second / 'authorization.json').exists():
        raise RuntimeError('compressor was started or authorized')
    for base, prefix, names in (
        (first, '01', ('manifest.json', 'plan.json', 'run_identity.json',
                       'serial_start.json', 'serial_result.json',
                       'authorization_removed.json', 'serial_stdout.txt',
                       'serial_stderr.txt', 'batch_result.json')),
        (second, '02_prepared_only', ('manifest.json', 'plan.json',
                                     'run_identity.json')),
    ):
        for name in names:
            path = base / name
            if path.is_file():
                files[f'{prefix}/{name}'] = path
    for path in (run / 'archive').glob('*'):
        if path.is_file():
            files[f'01/archive/{path.name}'] = path
    for path in (first / 'provider_public').glob('*'):
        if path.is_file():
            files[f'01/pos/{path.name}'] = path
    for name in ('events.host.jsonl', 'events.stderr.log', 'events.bridge.jsonl'):
        path = run / 'control' / 'pos_archive' / name
        if path.is_file():
            files[f'01/pos_host/{name}'] = path
    trials = [p for p in (run / 'jobs').glob('*/*') if
              (p / 'agent/research_events.jsonl').is_file()]
    if len(trials) != 1:
        raise RuntimeError('Task trial not unique')
    trial = trials[0]
    for name in ('research_events.jsonl', 'task_terminal.json',
                 'agent_stdout.log', 'agent_stderr.log',
                 'agent_process_return_code.txt'):
        path = trial / 'agent' / name
        if path.is_file():
            files[f'01/task/{name}'] = path
    for name in ('result.json', 'verifier/ctrf.json',
                 'verifier/reward.txt', 'verifier/test-stdout.txt'):
        path = trial / name
        if path.is_file():
            files[f'01/task/{name}'] = path
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--target', type=Path, required=True)
    parser.add_argument('--task-profile', type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    files = selected(source)
    secrets = secrets_from_profile(args.task_profile)
    args.target.mkdir(parents=True, exist_ok=False)
    rows = []
    for name, path in sorted(files.items()):
        if path.suffix == '.jsonl':
            rows.append(archive_line_file(name, path, args.target, secrets))
            continue
        size, source_sha = digest(path)
        try:
            data, count = public(path.read_bytes(), secrets)
        except (UnsafePublicProjection, UnicodeError):
            rows.append({'path': name, 'source_bytes': size,
                         'source_sha256': source_sha, 'public_parts': [],
                         'redactions': 0,
                         'omissions': [{'reason': 'unsafe_public_projection'}]})
            continue
        output = args.target / name
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(data)
        rows.append({'path': name, 'source_bytes': size,
                     'source_sha256': source_sha,
                     'public_parts': [{'path': name, 'bytes': len(data),
                                      'sha256': hashlib.sha256(data).hexdigest()}],
                     'redactions': count, 'omissions': []})
    index = {'schema': 'pos-ga-retry-stop-public-v1', 'source': str(source),
             'public_copy_is_byte_identical_to_source': False, 'files': rows}
    output = args.target / 'FILE_HASHES.json'
    output.write_text(json.dumps(index, ensure_ascii=False, indent=2) + '\n',
                      encoding='utf-8', newline='\n')
    for row in rows:
        for part in row['public_parts']:
            if digest(args.target / part['path']) != (part['bytes'], part['sha256']):
                raise RuntimeError('public readback mismatch: ' + part['path'])
    print(json.dumps({'files': len(rows),
                      'omissions': sum(len(row['omissions']) for row in rows),
                      'redactions': sum(row['redactions'] for row in rows),
                      'index_sha256': digest(output)[1]}))


if __name__ == '__main__':
    main()
