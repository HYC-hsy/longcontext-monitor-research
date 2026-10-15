"""One-slot actual Harbor/Docker zero-model fixture, never a live approval."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from .single_run import prepare


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task', required=True)
    parser.add_argument('--condition', choices=('A', 'B'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    for name in ('official-source-git', 'task-profile-file', 'pma-profile-file',
                 'ga-source', 'runtime-root', 'worker-python', 'harbor-python',
                 'bench-root', 'harbor-source-root'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--python-home', default='cpython-3.12.12-linux-x86_64-gnu')
    parser.add_argument('--service-fixture', action='store_true')
    args = parser.parse_args()
    root = args.output.resolve(strict=False)
    identity = prepare(argparse.Namespace(output=str(root), task=args.task,
        condition=args.condition, occurrence=1, fake_only=True,
        official_source_git=args.official_source_git,
        task_profile_file=args.task_profile_file,
        pma_profile_file=args.pma_profile_file))
    manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True,
                          text=True, check=True).stdout.strip()
    binding = dict(manifest['planned_order'][0], run_id=identity['run_id'],
                   run_root=identity['run_root'], batch_id=identity['run_id'],
                   config_sha256=manifest['config_sha256'])
    auth = {'execution_authorized': True, 'zero_model_fixture_only': True,
            'manifest_sha256': identity['manifest_sha256'],
            'audited_code_commit': head, 'approved_arms': manifest['planned_order'],
            'run_bindings': [binding], 'run_id': identity['run_id'],
            'batch_id': identity['run_id'],
            'config_sha256': manifest['config_sha256'],
            'output_root': identity['output_root']}
    authorization = root / 'authorization.json'
    authorization.write_text(json.dumps(auth, indent=2), encoding='utf-8')
    command = [sys.executable, '-m',
        'method_discovery.curator_supervisor_convergence_v0.'
        'pma_full_upstream_ga_v1_20261013.batch_controller',
        '--zero-model-fixture', '--manifest', str(root / 'manifest.json'),
        '--authorization', str(authorization),
        '--batch-result', str(root / 'batch_result.json'),
        '--ga-source', args.ga_source, '--runtime-root', args.runtime_root,
        '--task-profile-file', args.task_profile_file,
        '--pma-profile-file', args.pma_profile_file,
        '--worker-python', args.worker_python, '--harbor-python', args.harbor_python,
        '--bench-root', args.bench_root,
        '--official-source-git', args.official_source_git,
        '--harbor-source-root', args.harbor_source_root,
        '--python-home', args.python_home]
    try:
        environment = dict(os.environ)
        if args.service_fixture:
            environment['PMA_SERVICE_FIXTURE'] = '1'
        with (root / 'controller.stdout.txt').open('wb') as out, (
                root / 'controller.stderr.txt').open('wb') as err:
            completed = subprocess.run(command, stdout=out, stderr=err, env=environment,
                                       check=False,
                                       timeout=1200)
    finally:
        authorization.unlink(missing_ok=True)
        (root / 'fake_authorization_removed.json').write_text(json.dumps({
            'authorization_removed': not authorization.exists(),
            'zero_model_fixture_only': True}), encoding='utf-8')
    print(json.dumps({'task': args.task, 'condition': args.condition,
                      'controller_exit': completed.returncode,
                      'run_root': identity['run_root'],
                      'authorization_removed': not authorization.exists()}))
    if completed.returncode:
        raise SystemExit(completed.returncode)


if __name__ == '__main__':
    main()
