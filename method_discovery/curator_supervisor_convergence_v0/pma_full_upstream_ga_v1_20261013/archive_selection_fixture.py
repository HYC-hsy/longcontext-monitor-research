"""Export the stopped ordered fake fixture as individually readable projections."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .archive_live_six_task import (UnsafePublicProjection, private_values,
                                    redact)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--task-profile-file', type=Path, required=True)
    parser.add_argument('--pma-profile-file', type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    target = args.output.resolve(strict=False)
    target.mkdir(parents=True, exist_ok=False)
    secrets = private_values(args.task_profile_file, args.pma_profile_file)
    selected = {}
    for name in ('selection_preparation.json', 'selection_result.json',
                 'selection_fixture_execution_identity.json',
                 'fake_authorization_removed.json'):
        selected[name] = source / name
    for mode in ('prepare', 'run'):
        for stream in ('stdout', 'stderr'):
            name = f'{mode}.{stream}.txt'
            selected[name] = source.parent / f'{source.name}.{name}'
    result = json.loads((source / 'selection_result.json').read_text(encoding='utf-8'))
    for slot in result['slots']:
        stem = (f'{slot["order"]:02d}-{slot["task"]}-'
                f'{slot["condition"]}-r{slot["occurrence"]}')
        base = source / stem
        for name in ('plan.json', 'manifest.json', 'run_identity.json',
                     'batch_result.json'):
            path = base / name
            if path.is_file():
                selected[f'{stem}/{name}'] = path
        identity = json.loads((base / 'run_identity.json').read_text(encoding='utf-8'))
        run = Path(identity['run_root']).resolve(strict=False)
        if not run.is_relative_to(source):
            raise RuntimeError('ordered run root escaped source')
        for path in (run / 'archive').glob('*.json'):
            selected[f'{stem}/archive/{path.name}'] = path
        for path in (run / 'jobs').rglob('research_events.jsonl'):
            selected[f'{stem}/task/{path.name}'] = path
        for path in (run / 'host_private/archive').glob('*.jsonl'):
            selected[f'{stem}/pma/{path.name}'] = path
        for path in (run / 'archive/fake_provider_requests').glob('*'):
            if path.suffix in {'.json', '.sse'}:
                selected[f'{stem}/fake_requests/{path.name}'] = path
    files = []
    for name, path in sorted(selected.items()):
        if not path.is_file():
            files.append({'path': name, 'missing': True,
                          'reason': 'source file not produced by this fixture version'})
            continue
        raw = path.read_bytes()
        entry = {'path': name, 'private_source_sha256': hashlib.sha256(raw).hexdigest()}
        try:
            public, changes = redact(raw, secrets)
        except UnsafePublicProjection as exc:
            entry.update(excluded=True, reason=str(exc))
        else:
            destination = target / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open('xb') as stream:
                stream.write(public)
            entry.update(bytes=len(public), sha256=hashlib.sha256(public).hexdigest(),
                         redactions=changes)
        files.append(entry)
    (target / 'FILE_HASHES.json').write_text(json.dumps({
        'schema': 'pma-ga-ordered-fake-archive-v1', 'files': files},
        ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'files': len(files), 'excluded': sum(
        bool(row.get('excluded')) for row in files), 'secrets_exported': False}))


if __name__ == '__main__':
    main()
