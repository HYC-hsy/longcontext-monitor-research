"""Thin ordered selection of independent single_run invocations.

Preparation is the default. Real execution requires one distinct authorization
file per run; this module never creates one or changes the method itself.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

from .single_run import prepare, run
from .export_official_evaluator import COMMIT


def _slots(plan: dict) -> list[dict]:
    slots = plan.get('slots')
    if (plan.get('schema') != 'pma-ga-ordered-selection-v1' or
            plan.get('execution_authorized') is not False or
            plan.get('official_source_git_commit') != COMMIT or
            set(plan) != {'schema', 'execution_authorized',
                          'official_source_git_commit', 'slots'} or
            not isinstance(slots, list) or not slots):
        raise ValueError('ordered selection is empty or not a draft')
    seen = set()
    for row in slots:
        if (not isinstance(row, dict) or set(row) != {'task', 'condition', 'occurrence'} or
                not isinstance(row['task'], str) or
                re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', row['task']) is None or
                row['condition'] not in {'A', 'B'} or
                type(row['occurrence']) is not int or row['occurrence'] < 1):
            raise ValueError('ordered selection slot invalid')
        key = (row['task'], row['condition'], row['occurrence'])
        if key in seen:
            raise ValueError('ordered selection repeats one occurrence identity')
        seen.add(key)
    return slots


def execute(args: argparse.Namespace) -> list[dict]:
    plan = json.loads(Path(args.plan).read_text(encoding='utf-8'))
    slots = _slots(plan)
    root = Path(args.output).resolve(strict=False)
    if args.mode == 'prepare':
        root.mkdir(parents=True, exist_ok=False)
    else:
        root = root.resolve(strict=True)
    result_path = root / ('selection_preparation.json' if args.mode == 'prepare'
                          else 'selection_result.json')
    if result_path.exists():
        raise FileExistsError(result_path)
    results = []
    for order, row in enumerate(slots, 1):
        directory = root / f'{order:02d}-{row["task"]}-{row["condition"]}-r{row["occurrence"]}'
        if args.mode == 'prepare':
            try:
                outcome = prepare(argparse.Namespace(output=str(directory), **row,
                    official_source_git=args.official_source_git,
                    task_profile_file=args.task_profile_file,
                    pma_profile_file=args.pma_profile_file, fake_only=args.fake_only,
                    certification_dir=args.certification_dir))
                results.append({'order': order, **row, 'status': 'prepared_not_authorized',
                                'identity': outcome})
            except BaseException as exc:
                results.append({'order': order, **row, 'status': 'preparation_failed',
                                'error_type': type(exc).__name__, 'error': str(exc)})
                break
        else:
            authorization = directory / 'authorization.json'
            if not authorization.is_file():
                results.append({'order': order, **row, 'status': 'not_started_missing_approval'})
                break
            try:
                outcome = run(argparse.Namespace(output=str(directory),
                    authorization=str(authorization), ga_source=args.ga_source,
                    runtime_root=args.runtime_root, task_profile_file=args.task_profile_file,
                    pma_profile_file=args.pma_profile_file,
                    worker_python=args.worker_python, harbor_python=args.harbor_python,
                    bench_root=args.bench_root, official_source_git=args.official_source_git,
                    harbor_source_root=args.harbor_source_root, python_home=args.python_home,
                    zero_model_fixture=args.fake_only))
                results.append({'order': order, **row, 'status': 'attempted',
                                'result': outcome})
                if (outcome['stop_reason'] or outcome['arm'] is None or
                        outcome['arm']['disposition'] != 'completed'):
                    break
            except BaseException as exc:
                started = any(directory.rglob('research_events.jsonl')) or any(
                    directory.rglob('live_result.json'))
                results.append({'order': order, **row,
                                'status': 'started_incomplete' if started else
                                          'not_started_validation_failure',
                                'error_type': type(exc).__name__, 'error': str(exc)})
                break
    with result_path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump({'schema': 'pma-ga-selection-result-v1', 'mode': args.mode,
                   'slots': results, 'remaining_not_started': [
                       {'order': index, **row, 'status': 'not_started'} for index, row in
                       enumerate(slots[len(results):], len(results) + 1)]},
                  stream, indent=2, ensure_ascii=False)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--official-source-git', required=True)
    parser.add_argument('--task-profile-file', required=True)
    parser.add_argument('--pma-profile-file', required=True)
    parser.add_argument('--mode', choices=('prepare', 'run'), default='prepare')
    parser.add_argument('--fake-only', action='store_true')
    parser.add_argument('--certification-dir')
    for name in ('ga-source', 'runtime-root', 'worker-python', 'harbor-python',
                 'bench-root', 'harbor-source-root'):
        parser.add_argument('--' + name)
    parser.add_argument('--python-home', default='cpython-3.12.12-linux-x86_64-gnu')
    args = parser.parse_args()
    if args.mode == 'run' and any(getattr(args, name) is None for name in (
            'ga_source', 'runtime_root', 'worker_python', 'harbor_python',
            'bench_root', 'harbor_source_root')):
        parser.error('run requires all GA, Harbor and worker paths')
    results = execute(args)
    print(json.dumps({'mode': args.mode, 'attempted_or_prepared': len(results)}))
    if (len(results) != len(_slots(json.loads(Path(args.plan).read_text(encoding='utf-8')))) or
            any(row['status'] in {'preparation_failed', 'started_incomplete',
                                  'not_started_missing_approval',
                                  'not_started_validation_failure'} or
                (args.mode == 'run' and
                 (row.get('result', {}).get('arm') or {}).get('disposition') !=
                 'completed') for row in results)):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
