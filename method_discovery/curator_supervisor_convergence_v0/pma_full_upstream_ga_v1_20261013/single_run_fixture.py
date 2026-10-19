"""One-slot actual Harbor/Docker zero-model fixture, never a live approval."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from .single_run import prepare
from .single_run_certification import HARBOR_COMMIT, source_identity, vendor_identity


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task', required=True)
    parser.add_argument('--condition', choices=('A', 'B', 'P'), required=True)
    parser.add_argument('--research-candidate', choices=(
        'U', 'V1', 'D1', 'PoS', 'PoS-citation-fixed',
        'pos_pma_complement_v1'), default='U')
    parser.add_argument('--output', type=Path, required=True)
    for name in ('official-source-git', 'task-profile-file',
                 'ga-source', 'runtime-root', 'worker-python', 'harbor-python',
                 'bench-root', 'harbor-source-root'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--pma-profile-file')
    parser.add_argument('--python-home', default='cpython-3.12.12-linux-x86_64-gnu')
    parser.add_argument('--service-fixture', action='store_true')
    args = parser.parse_args()
    root = args.output.resolve(strict=False)
    if args.condition == 'P' and (args.task != 'pos-synthetic-file-http' or
                                   args.research_candidate not in {'PoS',
                                       'PoS-citation-fixed', 'pos_pma_complement_v1'}):
        raise RuntimeError('PoS zero-model fixture must use the synthetic P identity')
    identity = prepare(argparse.Namespace(output=str(root), task=args.task,
        condition=args.condition, occurrence=1, fake_only=True,
        synthetic_pos_fixture=args.condition == 'P',
        research_candidate=args.research_candidate,
        official_source_git=args.official_source_git,
        task_profile_file=args.task_profile_file,
        pma_profile_file=args.pma_profile_file))
    manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    checkout = Path(__file__).resolve().parents[3]
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=checkout,
                          capture_output=True, text=True, check=True).stdout.strip()
    harbor_head = subprocess.run(['git', 'rev-parse', 'HEAD'],
        cwd=args.harbor_source_root, capture_output=True, text=True, check=True).stdout.strip()
    if harbor_head != HARBOR_COMMIT:
        raise RuntimeError('fixture Harbor source commit differs')
    if subprocess.run(['git', 'diff', '--quiet', 'HEAD'],
                      cwd=args.harbor_source_root).returncode:
        raise RuntimeError('fixture Harbor tracked source differs from commit')
    execution = {'code_commit': head,
                 'source_files': (manifest['source_files_sha256'] if args.condition == 'P'
                                  else source_identity(checkout,
                                      candidate=args.research_candidate != 'U')),
                 'vendor_files': (manifest['vendor_files_sha256'] if args.condition == 'P'
                                  else vendor_identity(checkout)),
                 'harbor_commit': harbor_head,
                 **({'upstream_commit': manifest['upstream_commit']} if args.condition == 'P'
                    else {'pma_vendor_commit': manifest['pma_vendor_commit']})}
    if args.condition == 'P':
        from method_discovery.pos_upstream_ga_v1_20261017.single_manifest import SOURCE_FILES
        execution['git_blob_source_files'] = {
            name: hashlib.sha256(subprocess.run(
                ['git', 'cat-file', 'blob', f'{head}:{name}'], cwd=checkout,
                capture_output=True, check=True).stdout).hexdigest()
            for name in SOURCE_FILES}
    (root / 'execution_identity.json').write_text(
        json.dumps(execution, sort_keys=True, indent=2), encoding='utf-8')
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
        'pma_full_upstream_ga_v1_20261013.single_run', 'run',
        '--zero-model-fixture', '--output', str(root),
        '--authorization', str(authorization),
        '--ga-source', args.ga_source, '--runtime-root', args.runtime_root,
        '--task-profile-file', args.task_profile_file,
        '--worker-python', args.worker_python, '--harbor-python', args.harbor_python,
        '--bench-root', args.bench_root,
        '--official-source-git', args.official_source_git,
        '--harbor-source-root', args.harbor_source_root,
        '--python-home', args.python_home]
    if args.pma_profile_file:
        command += ['--pma-profile-file', args.pma_profile_file]
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
