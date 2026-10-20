"""Redact one stopped shared-view episode; never resume Task or evaluator."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.archive_live_six_task import (
    UnsafePublicProjection, private_values,
)
from method_discovery.pos_upstream_ga_v1_20261017.archive_formal_v6_stop import public
from method_discovery.pos_upstream_ga_v1_20261017.archive_remaining_stop import (
    archive_line_file, digest,
)
from method_discovery.pos_upstream_ga_v1_20261017.collect_native_shared import secrets_from_profile


def selected(source: Path) -> dict[str, Path]:
    if (source / 'authorization.json').exists():
        raise RuntimeError('one-use authorization remains active')
    identity = json.loads((source / 'run_identity.json').read_text(encoding='utf-8'))
    run = Path(identity['run_root']).resolve(strict=True)
    if not run.is_relative_to(source.resolve(strict=True)) or run.name != identity['run_id']:
        raise RuntimeError('run root identity differs')
    if not (source / 'batch_result.json').is_file() or not (
            run / 'archive/live_result.json').is_file():
        raise RuntimeError('stopped result or native lifecycle receipt missing')
    files: dict[str, Path] = {}
    for name in ('plan.json', 'manifest.json', 'run_identity.json',
                 'batch_result.json', 'authorization_removed.json'):
        path = source / name
        if path.is_file():
            files['scope/' + name] = path
    for path in sorted((run / 'archive').glob('*')):
        if path.is_file():
            files['archive/' + path.name] = path
    for path in sorted((run / 'control/pos_archive').glob('*')):
        if path.is_file() and path.name != 'binding.json':
            files['pos/' + path.name] = path
    for kind in ('requests', 'responses'):
        for path in sorted((run / 'control/spool' / kind).glob('*.json')):
            files[f'spool/{kind}/{path.name}'] = path
    for path in sorted((run / 'host_private').glob('*')):
        if path.is_file() and path.suffix in {'.json', '.log'}:
            files['host/' + path.name] = path
    trials = [path for path in (run / 'jobs').glob('*/*')
              if (path / 'agent/task_terminal.json').is_file()]
    if len(trials) != 1:
        raise RuntimeError('Task trial terminal not unique')
    trial = trials[0]
    for name in ('agent/research_events.jsonl', 'agent/task_terminal.json',
                 'agent/agent_stdout.log', 'agent/agent_stderr.log',
                 'agent/isolated_transport.log',
                 'agent/agent_process_return_code.txt', 'result.json',
                 'verifier/ctrf.json', 'verifier/reward.txt',
                 'verifier/test-stdout.txt'):
        path = trial / name
        if path.is_file():
            files['task/' + name] = path
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--task-profile', type=Path, required=True)
    parser.add_argument('--pma-profile', type=Path, required=True)
    args = parser.parse_args()
    files = selected(args.source)
    secrets = sorted(set(secrets_from_profile(args.task_profile) +
                         private_values(args.task_profile, args.pma_profile)),
                     key=len, reverse=True)
    args.output.mkdir(parents=True, exist_ok=False)
    rows = []
    for name, path in sorted(files.items()):
        if path.suffix == '.jsonl':
            rows.append(archive_line_file(name, path, args.output, secrets))
            continue
        size, source_hash = digest(path)
        try:
            data, redactions = public(path.read_bytes(), secrets)
        except (UnsafePublicProjection, UnicodeError):
            rows.append({'path': name, 'source_bytes': size,
                         'source_sha256': source_hash, 'public_parts': [],
                         'redactions': 0,
                         'omissions': [{'reason': 'unsafe_public_projection'}]})
            continue
        target = args.output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(data)
        rows.append({'path': name, 'source_bytes': size,
                     'source_sha256': source_hash,
                     'public_parts': [{'path': name, 'bytes': len(data),
                                      'sha256': hashlib.sha256(data).hexdigest()}],
                     'redactions': redactions, 'omissions': []})
    index = args.output / 'FILE_HASHES.json'
    with index.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump({'schema': 'pos-pma-shared-view-single-live-public-v1',
                   'run_id': 'pos-235d5ee3ccf64fa7', 'files': rows,
                   'public_copy_is_source_byte_identical': False},
                  stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    for row in rows:
        for part in row['public_parts']:
            if digest(args.output / part['path']) != (part['bytes'], part['sha256']):
                raise RuntimeError('public readback differs: ' + part['path'])
    print(json.dumps({'source_files': len(rows),
                      'public_files': sum(len(row['public_parts']) for row in rows),
                      'redactions': sum(row['redactions'] for row in rows),
                      'omissions': sum(len(row['omissions']) for row in rows),
                      'index_sha256': digest(index)[1]}))


if __name__ == '__main__':
    main()
