"""Archive the stopped SQLite candidate attempt; never resume either Task.

Records private-source and derived-public hashes separately. Unsafe files are
listed as omissions, never copied raw. JSONL is split on complete records.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.archive_live_six_task import UnsafePublicProjection
from method_discovery.pos_upstream_ga_v1_20261017 import archive_remaining_stop
from method_discovery.pos_upstream_ga_v1_20261017.archive_formal_v6_stop import public
from method_discovery.pos_upstream_ga_v1_20261017.collect_native_shared import secrets_from_profile


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mapping(sqlite: Path, sampler: Path, guard: Path) -> dict[str, Path]:
    if (sqlite / 'authorization.json').exists() or (sampler / 'authorization.json').exists():
        raise RuntimeError('activity authorization remains')
    identity = json.loads((sqlite / 'run_identity.json').read_text(encoding='utf-8'))
    run = Path(identity['run_root']).resolve(strict=True)
    if not run.is_relative_to(sqlite.resolve(strict=True)) or run.name != identity['run_id']:
        raise RuntimeError('SQLite run root identity differs')
    other = json.loads((sampler / 'run_identity.json').read_text(encoding='utf-8'))
    if Path(other['run_root']).exists() or (sampler / 'batch_result.json').exists():
        raise RuntimeError('sampler was not unstarted')
    selected = {'scope/followup_guard.py': guard}
    for prefix, base in (('sqlite', sqlite), ('sampler_unstarted', sampler)):
        for name in ('plan.json', 'manifest.json', 'run_identity.json',
                     'batch_result.json', 'authorization_removed.json'):
            path = base / name
            if path.is_file():
                selected[f'{prefix}/{name}'] = path
    for path in sorted((run / 'archive').iterdir()):
        if path.is_file() and path.name != 'fake_host_calls.jsonl':
            selected[f'sqlite/archive/{path.name}'] = path
    for path in sorted((run / 'control/pos_archive').iterdir()):
        if path.is_file():
            selected[f'sqlite/pos/{path.name}'] = path
    for path in sorted((run / 'host_private').iterdir()):
        if path.is_file() and path.suffix in {'.json', '.log'}:
            selected[f'sqlite/host/{path.name}'] = path
    for kind in ('requests', 'responses'):
        for path in sorted((run / 'control/spool' / kind).glob('*.json')):
            selected[f'sqlite/spool/{kind}/{path.name}'] = path
    trials = [path for path in (run / 'jobs').glob('*/*')
              if (path / 'agent/research_events.jsonl').is_file()]
    if len(trials) != 1:
        raise RuntimeError('SQLite Task trial not unique')
    trial = trials[0]
    for name in ('agent/research_events.jsonl', 'agent/task_terminal.json',
                 'agent/agent_stdout.log', 'agent/agent_stderr.log',
                 'agent/isolated_transport.log',
                 'agent/agent_process_return_code.txt', 'result.json',
                 'verifier/ctrf.json', 'verifier/reward.txt',
                 'verifier/test-stdout.txt'):
        path = trial / name
        if path.is_file():
            selected[f'sqlite/task/{name}'] = path
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sqlite', type=Path, required=True)
    parser.add_argument('--sampler', type=Path, required=True)
    parser.add_argument('--guard', type=Path, required=True)
    parser.add_argument('--task-profile', type=Path, required=True)
    parser.add_argument('--pma-profile', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    selected = mapping(args.sqlite, args.sampler, args.guard)
    secrets = secrets_from_profile(args.task_profile)
    pma = json.loads(args.pma_profile.read_text(encoding='utf-8'))['claude_monitor_opus48']
    secrets.extend(value for key, value in pma.items() if isinstance(value, str)
                   and len(value) >= 6 and any(part in key.lower() for part in
                   ('key', 'token', 'secret', 'password', 'base', 'url')))
    secrets = sorted(set(secrets), key=len, reverse=True)
    args.output.mkdir(parents=True, exist_ok=False)
    archive_remaining_stop.LIMIT = 1024 * 1024
    rows = []
    for name, path in sorted(selected.items()):
        if path.suffix == '.jsonl':
            rows.append(archive_remaining_stop.archive_line_file(
                name, path, args.output, secrets))
            continue
        size, source_hash = archive_remaining_stop.digest(path)
        try:
            data, count = public(path.read_bytes(), secrets)
        except (UnsafePublicProjection, UnicodeError):
            rows.append({'path': name, 'source_bytes': size,
                         'source_sha256': source_hash, 'public_parts': [],
                         'redactions': 0,
                         'omissions': [{'reason': 'unsafe_public_projection'}]})
            continue
        output = args.output / name
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('xb') as stream:
            stream.write(data)
        rows.append({'path': name, 'source_bytes': size,
                     'source_sha256': source_hash,
                     'public_parts': [{'path': name, 'bytes': len(data),
                                      'sha256': hashlib.sha256(data).hexdigest()}],
                     'redactions': count, 'omissions': []})
    index = args.output / 'FILE_HASHES.json'
    with index.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump({'schema': 'pos-pma-complement-sqlite-stop-public-v1',
                   'files': rows, 'public_copy_is_source_byte_identical': False,
                   'real_task_attempts': 1, 'sampler_started': False},
                  stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    for row in rows:
        for part in row['public_parts']:
            if archive_remaining_stop.digest(args.output / part['path']) != (
                    part['bytes'], part['sha256']):
                raise RuntimeError('public readback differs: ' + part['path'])
    print(json.dumps({'source_files': len(rows),
                      'public_files': sum(len(row['public_parts']) for row in rows),
                      'omissions': sum(len(row['omissions']) for row in rows),
                      'redactions': sum(row['redactions'] for row in rows),
                      'index_sha256': sha(index)}))


if __name__ == '__main__':
    main()
