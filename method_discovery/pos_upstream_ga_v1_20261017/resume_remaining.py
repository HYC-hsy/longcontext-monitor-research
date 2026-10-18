"""Thin one-use serial launcher for the three v6 tasks not yet started.

It calls the existing single_run prepare/run entry. It does not alter PoS,
Task, Harbor, provider, evaluator, or cleanup behavior. No repository commits
are permitted between prepare and the last run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from .certification import verify_evidence
from .single_manifest import CHECKOUT, source_hashes, vendor_hashes
from .serial_live import ENTRY, common, write_new

ROOT = Path(__file__).resolve().parent
TASKS = ('adaptive-rejection-sampler', 'sqlite-with-gcov', 'write-compressor')
ORDERS = (2, 3, 4)
PRIOR = ROOT / 'raw_formal_stop_v3'
REVIEW = ROOT / 'raw_review_v3/compatibility_review.json'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def head() -> str:
    return subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=CHECKOUT,
                          capture_output=True, text=True, check=True).stdout.strip()


def prior_identity() -> dict:
    one = json.loads((PRIOR / '01/serial_result.json').read_text(encoding='utf-8'))
    two = json.loads((PRIOR / '02/serial_result.json').read_text(encoding='utf-8'))
    failure = (PRIOR / '02/serial_stderr.txt').read_text(encoding='utf-8')
    review = json.loads(REVIEW.read_text(encoding='utf-8'))
    if (one.get('task') != 'nginx-request-logging' or
            one.get('continue_safe') is not True or
            one.get('native_reward', {}).get('reward') != 1.0 or
            one.get('cleanup_confirmed') is not True or
            one.get('provider_capture', {}).get('capture_complete') is not True or
            two.get('task') != TASKS[0] or two.get('status_available') is not False or
            two.get('provider_capture', {}).get('status') != 'role_ledger_unavailable' or
            two.get('native_reward') is not None or
            'PoS running code differs from authorized commit' not in failure or
            review.get('decision') !=
                'fixed_native_unscored_fallback_accepted_for_discovery' or
            review.get('historical_status') != 'failed' or
            review.get('accepted_failure') !=
                'progress_affected_record_ids_unchanged_e1_only' or
            review.get('initial_audit') != 'completed_once' or
            review.get('update_audit') != 'completed_twice_repaired' or
            review.get('progress') != 'invalid_unscored_not_zero' or
            review.get('current_source_files_sha256') != source_hashes() or
            review.get('current_vendor_files_sha256') != vendor_hashes()):
        raise RuntimeError('prior completion/stop/review is outside this scope')
    names = ('01/serial_result.json', '01/task/task_terminal.json',
             '01/archive/live_result.json', '02/serial_result.json',
             '02/serial_stderr.txt')
    return {'prior_files_sha256': {name: sha(PRIOR / name) for name in names},
            'review_sha256': sha(REVIEW),
            'first_run_id': one['run_id'], 'blocked_second_run_id': two['run_id']}


def validate_scope(args) -> tuple[Path, dict]:
    root = Path(args.output).resolve(strict=True)
    scope = json.loads((root / 'scope.json').read_text(encoding='utf-8'))
    if (scope.get('schema') != 'pos-ga-remaining-scope-v1' or
            scope.get('code_commit') != head() or
            scope.get('launcher_sha256') != sha(Path(__file__)) or
            scope.get('plan_sha256') != sha(Path(args.plan)) or
            scope.get('source_files_sha256') != source_hashes() or
            scope.get('vendor_files_sha256') != vendor_hashes() or
            scope.get('profile_sha256') != sha(Path(args.task_profile_file)) or
            scope.get('profile_sha256') != json.loads(REVIEW.read_text(
                encoding='utf-8')).get('profile_sha256') or
            scope.get('certification_sha256') !=
                sha(Path(args.certification) / 'FILE_HASHES.json') or
            scope.get('prior') != prior_identity() or
            tuple(row['task'] for row in scope['prepared']) != TASKS or
            tuple(row['order'] for row in scope['prepared']) != ORDERS):
        raise RuntimeError('remaining serial scope differs from frozen identity')
    if verify_evidence(Path(args.certification), require_committed=True).get('status') != 'pass':
        raise RuntimeError('source-bound synthetic certification failed')
    for row in scope['prepared']:
        directory = Path(row['directory']).resolve(strict=True)
        manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
        identity = json.loads((directory / 'run_identity.json').read_text(encoding='utf-8'))
        if (directory.parent != root or sha(directory / 'manifest.json') !=
                row['manifest_sha256'] or
                identity['run_id'] != row['run_id'] or
                identity['run_root'] != row['run_root'] or
                manifest['planned_order'][0]['task'] != row['task'] or
                manifest['planned_order'][0]['condition'] != 'P' or
                manifest['planned_order'][0]['research_candidate'] != 'PoS' or
                manifest['config_sha256'] != row['config_sha256'] or
                manifest['source_files_sha256'] != scope['source_files_sha256'] or
                manifest['vendor_files_sha256'] != scope['vendor_files_sha256'] or
                manifest['task_profile_sha256'] != scope['profile_sha256'] or
                manifest['config']['task_turns_max'] != 300 or
                manifest['config']['agent_wall_seconds'] != 14400 or
                manifest.get('zero_model_fixture_only') is not False or
                manifest.get('execution_authorized') is not False or
                manifest['assets'][row['task']]['image_id'] != row['image_id'] or
                manifest['assets'][row['task']]['native_tests_tree_sha256'] !=
                    row['native_tests_tree_sha256']):
            raise RuntimeError('remaining task asset/config binding differs')
    return root, scope


def prepare(args) -> None:
    plan = json.loads(Path(args.plan).read_text(encoding='utf-8'))
    if (plan.get('schema') != 'pos-ga-remaining-plan-v1' or
            plan.get('execution_authorized') is not False or
            plan.get('prior_completed_task') != 'nginx-request-logging' or
            plan.get('method') != 'PoS' or
            plan.get('official_source_git_commit') !=
                '2fd12b88aafdd04a52c298e3940bcb189f9766d6' or
            tuple(row.get('task') for row in plan['planned_order']) != TASKS or
            tuple(row.get('order') for row in plan['planned_order']) != ORDERS or
            any(row.get('condition') != 'P' for row in plan['planned_order'])):
        raise RuntimeError('remaining tasks are not the fixed unstarted suffix')
    if verify_evidence(Path(args.certification), require_committed=True).get('status') != 'pass':
        raise RuntimeError('source-bound synthetic certification failed')
    prior = prior_identity()
    root = Path(args.output).resolve(strict=False)
    root.mkdir(parents=True, exist_ok=False)
    prepared = []
    for order, task in zip(ORDERS, TASKS):
        directory = root / f'{order:02d}_{task}'
        command = [sys.executable, '-B', '-m', ENTRY, 'prepare',
                   '--condition', 'P', '--research-candidate', 'PoS',
                   '--task', task, '--output', str(directory),
                   '--certification-dir', str(Path(args.certification).resolve()),
                   '--official-source-git', args.official_source_git,
                   '--task-profile-file', args.task_profile_file]
        completed = subprocess.run(command, cwd=CHECKOUT, capture_output=True,
                                   text=True, check=False)
        write_new(root / f'prepare_{order:02d}.json', dict(task=task,
            command_public=command, return_code=completed.returncode,
            stdout=completed.stdout, stderr=completed.stderr))
        if completed.returncode:
            raise RuntimeError('remaining task preparation failed: ' + task)
        manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
        identity = json.loads((directory / 'run_identity.json').read_text(encoding='utf-8'))
        prepared.append(dict(order=order, task=task, directory=str(directory),
            run_id=identity['run_id'], run_root=identity['run_root'],
            manifest_sha256=sha(directory / 'manifest.json'),
            config_sha256=manifest['config_sha256'],
            image_id=manifest['assets'][task]['image_id'],
            native_tests_tree_sha256=manifest['assets'][task][
                'native_tests_tree_sha256']))
    write_new(root / 'scope.json', dict(schema='pos-ga-remaining-scope-v1',
        authorization_basis='user requested only the three not-started tasks',
        code_commit=head(), launcher_sha256=sha(Path(__file__)),
        plan_sha256=sha(Path(args.plan)),
        source_files_sha256=source_hashes(), vendor_files_sha256=vendor_hashes(),
        profile_sha256=sha(Path(args.task_profile_file)),
        certification_sha256=sha(Path(args.certification) / 'FILE_HASHES.json'),
        prior=prior, prepared=prepared, task_turns_max=300,
        agent_wall_seconds=14400))
    validate_scope(args)
    print(json.dumps(dict(prepared=len(prepared), code_commit=head(),
                          scope=str(root / 'scope.json'))), flush=True)


def run(args) -> None:
    root, scope = validate_scope(args)
    for row in scope['prepared']:
        # An intervening commit is a hard stop before creating the next grant.
        root, scope = validate_scope(args)
        directory = Path(row['directory'])
        if (Path(row['run_root']).exists() or
                (directory / 'batch_result.json').exists() or
                (directory / 'authorization.json').exists()):
            raise RuntimeError('remaining task already started or grant exists')
        manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
        arm = manifest['planned_order'][0]
        binding = dict(arm, run_id=row['run_id'], run_root=row['run_root'],
                       batch_id=row['run_id'], config_sha256=row['config_sha256'])
        identity = json.loads((directory / 'run_identity.json').read_text(encoding='utf-8'))
        authorization = dict(execution_authorized=True,
            zero_model_fixture_only=False, manifest_sha256=row['manifest_sha256'],
            audited_code_commit=scope['code_commit'], approved_arms=[arm],
            run_bindings=[binding], run_id=row['run_id'], batch_id=row['run_id'],
            config_sha256=row['config_sha256'], output_root=identity['output_root'])
        auth_path = directory / 'authorization.json'
        write_new(auth_path, authorization)
        command = [sys.executable, '-B', '-m', ENTRY, 'run',
                   '--output', str(directory), '--authorization', str(auth_path),
                   *common(args)]
        record = dict(order=row['order'], task=row['task'], run_id=row['run_id'],
                      authorization_sha256=sha(auth_path),
                      command_public=command, status='started')
        write_new(directory / 'serial_start.json', record)
        try:
            with (directory / 'serial_stdout.txt').open('xb') as out, (
                    directory / 'serial_stderr.txt').open('xb') as err:
                completed = subprocess.run(command, cwd=CHECKOUT,
                                           stdout=out, stderr=err, check=False)
        finally:
            auth_path.unlink(missing_ok=True)
            write_new(directory / 'authorization_removed.json', dict(
                authorization_removed=not auth_path.exists(),
                authorization_sha256=record['authorization_sha256']))
        status_path = Path(row['run_root']) / 'archive/live_result.json'
        try:
            status = json.loads(status_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            status = None
        terminal_paths = list(Path(row['run_root']).glob('jobs/*/*/agent/task_terminal.json'))
        try:
            terminal = json.loads(terminal_paths[0].read_text(encoding='utf-8')) if len(
                terminal_paths) == 1 else None
        except (OSError, ValueError):
            terminal = None
        from .collect_native_shared import collect_provider_capture, secrets_from_profile
        provider_public = None
        provider_collection_error = None
        try:
            provider_public = collect_provider_capture(
                Path(row['run_root']) / 'control/pos_archive',
                directory / 'provider_public',
                secrets_from_profile(Path(args.task_profile_file)),
                row['run_id'], row['task'], profile_mode=True)
        except (OSError, ValueError, RuntimeError) as error:
            provider_collection_error = type(error).__name__
        archive = status.get('pos_archive_status') or {} if status else {}
        summary = dict(order=row['order'], task=row['task'], run_id=row['run_id'],
            run_exit=completed.returncode, status_available=status is not None,
            primary_failure=status.get('primary_failure') if status else None,
            cleanup_confirmed=status.get('cleanup_confirmed') if status else None,
            harbor_return_code=status.get('harbor_return_code') if status else None,
            native_result_status=(status.get('native_result') or {}).get('status') if status else None,
            native_reward=((status.get('native_result') or {}).get('rewards') or {}) if status else None,
            task_terminal_result=terminal.get('result') if terminal else None,
            pos_archive_status=archive if status else None,
            provider_collection_error_type=provider_collection_error,
            provider_capture=provider_public.get('capture') if provider_public else None)
        safe = bool(status and not status.get('primary_failure') and
            status.get('cleanup_confirmed') is True and
            status.get('remaining_containers') == [] and
            status.get('harbor_return_code') == 0 and
            status.get('frozen_product') is True and
            status.get('evaluation_released') is True and
            (status.get('native_result') or {}).get('status') == 'native_recorded' and
            status.get('native_script_observed') is True and
            len(status.get('native_script_executions') or []) == 1 and
            status.get('native_upload_checked') is True and
            status.get('native_reports_checked') is True and
            archive.get('result_bound') is True and
            archive.get('close_bound') is True and
            archive.get('archive_incomplete') is False and
            provider_collection_error is None and provider_public is not None and
            provider_public['capture']['capture_complete'] is True and
            archive.get('close_status') == 'graceful_exit' and
            terminal and terminal.get('run_id') == row['run_id'] and
            terminal.get('task_id') == row['task'] and
            terminal.get('result') in {'CURRENT_TASK_DONE', 'MAX_TURNS_EXCEEDED', 'EXITED'})
        summary['continue_safe'] = safe
        write_new(directory / 'serial_result.json', summary)
        print(json.dumps(dict(order=row['order'], task=row['task'],
                              continue_safe=safe, reward=summary['native_reward']),
                         ensure_ascii=False), flush=True)
        if not safe:
            raise RuntimeError('formal run/evaluation/cleanup uncertain; later tasks stopped')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('prepare', 'check', 'run'):
        command = commands.add_parser(name)
        command.add_argument('--output', required=True)
        command.add_argument('--plan', required=True)
        command.add_argument('--certification', required=True)
        command.add_argument('--task-profile-file', required=True)
        if name in ('prepare', 'run'):
            command.add_argument('--official-source-git', required=True)
        if name == 'run':
            for item in ('ga-source', 'runtime-root', 'worker-python',
                         'harbor-python', 'bench-root', 'harbor-source-root'):
                command.add_argument('--' + item, required=True)
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare(args)
    elif args.command == 'check':
        validate_scope(args)
        print('remaining scope verified; no model, Task or Harbor call')
    else:
        run(args)


if __name__ == '__main__':
    main()
