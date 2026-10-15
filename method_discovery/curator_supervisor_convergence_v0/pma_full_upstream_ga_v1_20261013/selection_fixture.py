"""Offline ordered-selection exercise with per-slot fake-only authorizations."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess

from .run_selection import execute, _slots
from .single_run_certification import source_identity, vendor_identity


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True)
    parser.add_argument('--output', required=True)
    for name in ('official-source-git', 'task-profile-file', 'pma-profile-file',
                 'ga-source', 'runtime-root', 'worker-python', 'harbor-python',
                 'bench-root', 'harbor-source-root'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--python-home', default='cpython-3.12.12-linux-x86_64-gnu')
    args = parser.parse_args()
    slots = _slots(json.loads(Path(args.plan).read_text(encoding='utf-8')))
    checkout = Path(__file__).resolve().parents[3]
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=checkout,
                          capture_output=True, text=True, check=True).stdout.strip()
    identity = {'code_commit': head, 'source_files': source_identity(checkout),
                'vendor_files': vendor_identity(checkout)}
    root = Path(args.output).resolve(strict=False)
    args.mode, args.fake_only, args.certification_dir = 'prepare', True, None
    prepared = execute(args)
    if len(prepared) != len(slots) or any(
            row['status'] != 'prepared_not_authorized' for row in prepared):
        raise RuntimeError('ordered fixture preparation incomplete')
    (root / 'selection_fixture_execution_identity.json').write_text(
        json.dumps(identity, indent=2), encoding='utf-8')
    authorizations = []
    try:
        for order, row in enumerate(slots, 1):
            directory = root / f'{order:02d}-{row["task"]}-{row["condition"]}-r{row["occurrence"]}'
            manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
            selected = json.loads((directory / 'run_identity.json').read_text(encoding='utf-8'))
            binding = dict(manifest['planned_order'][0], run_id=selected['run_id'],
                           run_root=selected['run_root'], batch_id=selected['run_id'],
                           config_sha256=manifest['config_sha256'])
            auth = {'execution_authorized': True, 'zero_model_fixture_only': True,
                    'manifest_sha256': selected['manifest_sha256'],
                    'audited_code_commit': head,
                    'approved_arms': manifest['planned_order'], 'run_bindings': [binding],
                    'run_id': selected['run_id'], 'batch_id': selected['run_id'],
                    'config_sha256': manifest['config_sha256'],
                    'output_root': selected['output_root']}
            path = directory / 'authorization.json'
            with path.open('x', encoding='utf-8') as stream:
                json.dump(auth, stream)
            authorizations.append(path)
        os.environ['PMA_SERVICE_FIXTURE'] = '1'
        args.mode = 'run'
        results = execute(args)
    finally:
        for path in authorizations:
            path.unlink(missing_ok=True)
        (root / 'fake_authorization_removed.json').write_text(json.dumps({
            'authorization_removed': all(not path.exists() for path in authorizations),
            'zero_model_fixture_only': True}), encoding='utf-8')
    print(json.dumps({'planned': len(slots), 'attempted': len(results),
                      'order': [(row['task'], row['condition'], row['occurrence'])
                                for row in results],
                      'all_completed': len(results) == len(slots) and all(
                          (row.get('result', {}).get('arm') or {}).get('disposition') ==
                          'completed' for row in results)}))
    if len(results) != len(slots) or any(
            (row.get('result', {}).get('arm') or {}).get('disposition') != 'completed'
            for row in results):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
