"""Disposable, non-solving Docker identity and visibility check for six images."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess


SCRIPT = ('printf "pwd="; pwd; '
          'for x in sh bash python3 go gcc g++ cobc vim; do command -v "$x" || true; done; '
          'if test -e /tests; then find /tests -mindepth 1 -print -quit; '
          'else echo tests_absent; fi; '
          'if test -e /solution; then echo solution_visible; '
          'else echo solution_absent; fi')


def inspect(manifest: dict) -> list[dict]:
    rows = []
    for task, asset in manifest['assets'].items():
        tag = asset['image_tag']
        identity = subprocess.run(['docker', 'image', 'inspect', tag],
                                  capture_output=True, text=True, timeout=30)
        if identity.returncode:
            raise RuntimeError(f'{task}: image inspect failed: {identity.stderr}')
        image = json.loads(identity.stdout)[0]
        if (image['Id'] != asset['image_id'] or
                asset['repo_digest'] not in image.get('RepoDigests', []) or
                f"{image['Os']}/{image['Architecture']}" != asset['platform']):
            raise RuntimeError(f'{task}: image differs from frozen asset identity')
        command = ['docker', 'run', '--rm', '--network', 'bridge',
                   '--entrypoint', '/bin/sh', tag, '-lc', SCRIPT]
        result = subprocess.run(command, capture_output=True, text=True, timeout=90)
        rows.append({'task': task, 'image_tag': tag, 'image_id': image['Id'],
                     'repo_digests': image.get('RepoDigests', []),
                     'platform': f"{image['Os']}/{image['Architecture']}",
                     'argv': command, 'exit_code': result.returncode,
                     'stdout': result.stdout, 'stderr': result.stderr,
                     'hidden_material_absent': result.returncode == 0 and
                         'tests_absent' in result.stdout and
                         'solution_absent' in result.stdout})
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    rows = inspect(manifest)
    args.output.write_text(json.dumps(rows, indent=2), encoding='utf-8')
    print(json.dumps({'images': len(rows), 'exit_codes': [r['exit_code'] for r in rows],
                      'hidden_absent': all(r['hidden_material_absent'] for r in rows)}))
    if any(r['exit_code'] or not r['hidden_material_absent'] for r in rows):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
