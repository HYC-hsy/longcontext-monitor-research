"""One GA/U-PMA trial over one fixed upstream Task, defaulting to preparation.

This is a thin CLI over the existing materializer, controller and Harbor
launcher. It never mints a real authorization. An independently approved,
one-use binding is required for ``run``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import uuid

from .batch_controller import run_batch
from .export_official_evaluator import COMMIT
from .prepare_six_task_manifest import prepare as prepare_manifest
from .six_task_plan import validate_plan


def _write_new(path: Path, value: dict) -> None:
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def prepare(args: argparse.Namespace) -> dict:
    root = Path(args.output).resolve(strict=False)
    root.mkdir(parents=True, exist_ok=False)
    plan = {'schema': 'pma-ga-single-plan-v1', 'execution_authorized': False,
            'official_source_git_commit': COMMIT, 'task': args.task,
            'condition': args.condition, 'occurrence': args.occurrence}
    candidate = getattr(args, 'research_candidate', 'U')
    if candidate != 'U':
        plan['schema'] = 'pma-ga-single-plan-v2'
        plan['research_candidate'] = candidate
    _write_new(root / 'plan.json', plan)
    manifest = prepare_manifest(Path(args.official_source_git).resolve(strict=True),
        Path(args.task_profile_file).resolve(strict=True),
        Path(args.pma_profile_file).resolve(strict=True),
        evidence=(Path(args.certification_dir).resolve(strict=True)
                  if getattr(args, 'certification_dir', None) else None), plan=plan)
    if args.fake_only:
        manifest['zero_model_fixture_only'] = True
    _write_new(root / 'manifest.json', manifest)
    # Keep Windows Harbor paths below MAX_PATH while retaining a fresh random ID.
    run_id = 'pma-' + uuid.uuid4().hex[:16]
    identity = {'run_id': run_id, 'run_root': str(root / 'runs' / run_id),
                'output_root': str(root / 'runs'), 'plan_sha256': hashlib.sha256(
                    (root / 'plan.json').read_bytes()).hexdigest(),
                'manifest_sha256': hashlib.sha256(
                    (root / 'manifest.json').read_bytes()).hexdigest(),
                'execution_authorized': False}
    _write_new(root / 'run_identity.json', identity)
    return identity


def run(args: argparse.Namespace) -> dict:
    root = Path(args.output).resolve(strict=True)
    manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    identity = json.loads((root / 'run_identity.json').read_text(encoding='utf-8'))
    granted = json.loads(Path(args.authorization).read_text(encoding='utf-8'))
    bindings = validate_plan(manifest, granted)
    if (len(bindings) != 1 or bindings[0]['run_id'] != identity['run_id'] or
            bindings[0]['run_root'] != identity['run_root'] or
            granted.get('manifest_sha256') != identity['manifest_sha256'] or
            bool(args.zero_model_fixture) != (manifest.get('zero_model_fixture_only') is True)):
        raise RuntimeError('single-run identity or fixture mode differs from approval')
    if (root / 'batch_result.json').exists() or Path(identity['run_root']).exists():
        raise FileExistsError('single-run result or run root already exists')
    options = argparse.Namespace(
        manifest=str(root / 'manifest.json'), authorization=str(args.authorization),
        batch_result=str(root / 'batch_result.json'),
        ga_source=args.ga_source, runtime_root=args.runtime_root,
        task_profile_file=args.task_profile_file,
        pma_profile_file=args.pma_profile_file,
        worker_python=args.worker_python, harbor_python=args.harbor_python,
        bench_root=args.bench_root, official_source_git=args.official_source_git,
        harbor_source_root=args.harbor_source_root, python_home=args.python_home,
        zero_model_fixture=args.zero_model_fixture)
    result = run_batch(options)
    return {'run_id': identity['run_id'], 'arm': result['arms'][0] if result['arms'] else None,
            'stop_reason': result['stop_reason']}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prepared = commands.add_parser('prepare', help='fixed-Git asset and image check; no calls')
    prepared.add_argument('--task', required=True)
    prepared.add_argument('--condition', choices=('A', 'B'), required=True)
    prepared.add_argument('--research-candidate', choices=('U', 'V1', 'D1'), default='U')
    prepared.add_argument('--occurrence', type=int, default=1)
    prepared.add_argument('--output', required=True)
    prepared.add_argument('--official-source-git', required=True)
    prepared.add_argument('--task-profile-file', required=True)
    prepared.add_argument('--pma-profile-file', required=True)
    prepared.add_argument('--fake-only', action='store_true')
    prepared.add_argument('--certification-dir',
                          help='committed A/B Harbor evidence for future authorized use')
    launched = commands.add_parser('run', help='requires an independent one-use approval')
    launched.add_argument('--output', required=True)
    launched.add_argument('--authorization', required=True)
    for name in ('ga-source', 'runtime-root', 'task-profile-file',
                 'worker-python', 'harbor-python', 'bench-root',
                 'official-source-git', 'harbor-source-root'):
        launched.add_argument('--' + name, required=True)
    launched.add_argument('--pma-profile-file')
    launched.add_argument('--python-home', default='cpython-3.12.12-linux-x86_64-gnu')
    launched.add_argument('--zero-model-fixture', action='store_true')
    args = parser.parse_args()
    outcome = prepare(args) if args.command == 'prepare' else run(args)
    print(json.dumps(outcome, ensure_ascii=False, indent=2))
    if (args.command == 'run' and
            (outcome['stop_reason'] or not outcome['arm'] or
             outcome['arm'].get('disposition') != 'completed')):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
