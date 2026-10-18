"""One-use, source-bound serial continuation for sampler then compressor."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from . import resume_remaining as previous
from .certification import verify_evidence
from .serial_live import ENTRY, common, write_new
from .single_manifest import CHECKOUT, source_hashes, vendor_hashes


ROOT = Path(__file__).resolve().parent
TASKS = ('adaptive-rejection-sampler', 'write-compressor')
ORDERS = (1, 2)
OLD_TWO = ROOT / 'raw_final_two_v2'
OLD_RETRY = ROOT / 'raw_retry_stop_v1/01/serial_result.json'
PREFLIGHT = ROOT / 'raw_retry_preflight_v2'
REVIEW = ROOT / 'raw_review_v3/compatibility_review.json'


def sha(path: Path) -> str:
    return previous.sha(path)


def head() -> str:
    return previous.head()


def prior_identity() -> dict:
    # The old review describes the *old* deployed bytes. Do not compare its
    # source map with the current Task transport after complete-response-v1.
    review = json.loads(REVIEW.read_text(encoding='utf-8'))
    if (review.get('decision') !=
            'fixed_native_unscored_fallback_accepted_for_discovery' or
            review.get('historical_status') != 'failed' or
            review.get('accepted_failure') !=
            'progress_affected_record_ids_unchanged_e1_only' or
            review.get('initial_audit') != 'completed_once' or
            review.get('update_audit') != 'completed_twice_repaired' or
            review.get('progress') != 'invalid_unscored_not_zero'):
        raise RuntimeError('historical PoS review identity changed')
    reviewed = {'review_sha256': sha(REVIEW),
                'reviewed_code_commit': review['current_code_commit'],
                'reviewed_source_files_sha256': review['current_source_files_sha256']}
    sqlite = json.loads((OLD_TWO / '03/serial_result.json').read_text(encoding='utf-8'))
    compressor = json.loads((OLD_TWO / '04/serial_result.json').read_text(encoding='utf-8'))
    sampler_retry = json.loads(OLD_RETRY.read_text(encoding='utf-8'))
    if (sqlite.get('task') != 'sqlite-with-gcov' or
            sqlite.get('task_terminal_result') != 'CURRENT_TASK_DONE' or
            sqlite.get('native_reward', {}).get('reward') != 1.0 or
            sqlite.get('continue_safe') is not True or
            compressor.get('task') != 'write-compressor' or
            compressor.get('run_id') != 'pos-390e3b64fc144eba' or
            compressor.get('task_terminal_result') != 'PROVIDER_FAILURE' or
            compressor.get('native_reward', {}).get('reward') != 0.0 or
            compressor.get('continue_safe') is not False or
            compressor.get('cleanup_confirmed') is not True or
            compressor.get('provider_capture', {}).get('capture_complete') is not True):
        raise RuntimeError('historical completed/failed tasks differ')
    if (sampler_retry.get('task') != 'adaptive-rejection-sampler' or
            sampler_retry.get('run_id') != 'pos-7c969aa45b944db5' or
            sampler_retry.get('task_terminal_result') != 'PROVIDER_FAILURE' or
            sampler_retry.get('native_reward', {}).get('reward') != 0.0 or
            sampler_retry.get('continue_safe') is not False or
            sampler_retry.get('cleanup_confirmed') is not True):
        raise RuntimeError('historical retry failure differs')
    index_path = PREFLIGHT / 'SOURCE_AND_PUBLIC_HASHES.json'
    index = json.loads(index_path.read_text(encoding='utf-8'))
    for row in index['files']:
        public = PREFLIGHT / row['path']
        if public.stat().st_size != row['public_bytes'] or sha(public) != row['public_sha256']:
            raise RuntimeError('preflight public readback mismatch')
        if row['source_path'] != 'generated_from_recorded_source_lines':
            source = Path(row['source_path'])
            if (source.stat().st_size != row['source_bytes'] or
                    sha(source) != row['source_sha256']):
                raise RuntimeError('preflight source identity changed')
    for identity in index['v4_actual_bundle'].values():
        source = Path(identity['source_path'])
        if (source.stat().st_size != identity['source_bytes'] or
                sha(source) != identity['source_sha256']):
            raise RuntimeError('retained v4 packed source identity changed')
    last_call = json.loads((PREFLIGHT / 'old_compressor/final_task_call.json').read_text(
        encoding='utf-8'))
    for key in ('task_source', 'host_source', 'stdout_source'):
        identity = last_call[key]
        source = Path(identity['source_path'])
        if (source.stat().st_size != identity['source_bytes'] or
                sha(source) != identity['source_sha256']):
            raise RuntimeError('retained compressor source identity changed')
    result = json.loads((PREFLIGHT / 'v4/profile_integration_result.json').read_text(
        encoding='utf-8'))
    classification = json.loads((PREFLIGHT /
        'old_compressor/return_classification.json').read_text(encoding='utf-8'))
    if (result.get('status') != 'pass' or result.get('model_calls') != 0 or
            result.get('fake_http_requests') != 9 or
            result.get('provider_timeout_seconds') != 3 or
            result.get('update_elapsed_seconds', 0) <= 3 or
            any(value != 1 for value in result.get(
                'timeout_case_attempts_by_call', {}).values()) or
            len(result.get('timeout_case_attempts_by_call', {})) != 2 or
            classification.get('logical_requests') != 125 or
            classification.get('observable_http_attempts') != 125 or
            classification.get('return_records') != 125 or
            classification.get('categories') != {
                'terminal_unproven_or_unknown': 124,
                'incomplete_stream_marker': 1} or
            classification.get('final_call', {}).get('category') !=
                'incomplete_stream_marker' or
            result.get('source_sha256') != {
                name: index['v4_actual_bundle'][name]['source_sha256']
                for name in ('llmcore.py', 'research_runtime.py',
                             'pos_runtime/worker.py', 'pos_runtime/episode.py')}):
        raise RuntimeError('old final call or retained packed-worker v4 differs')
    tests = (PREFLIGHT / 'offline_tests/stderr.txt').read_text(encoding='utf-8')
    if 'Ran 5 tests' not in tests or '\nOK\n' not in tests:
        raise RuntimeError('offline classification tests did not pass')
    if subprocess.run(['git', 'cat-file', '-e',
        'HEAD:method_discovery/pos_upstream_ga_v1_20261017/'
        'raw_retry_preflight_v2/SOURCE_AND_PUBLIC_HASHES.json'],
        cwd=CHECKOUT, check=False).returncode != 0:
        raise RuntimeError('preflight evidence not committed')
    return {'historical_review': reviewed,
            'sqlite_serial_sha256': sha(OLD_TWO / '03/serial_result.json'),
            'compressor_serial_sha256': sha(OLD_TWO / '04/serial_result.json'),
            'sampler_retry_serial_sha256': sha(OLD_RETRY),
            'preflight_index_sha256': sha(index_path)}


def validate(args) -> tuple[Path, dict]:
    root = Path(args.output).resolve(strict=True)
    scope = json.loads((root / 'scope.json').read_text(encoding='utf-8'))
    if (scope.get('schema') != 'pos-ga-sampler-compressor-retry-scope-v1' or
            scope.get('task_complete_response_policy') != 'complete-response-v1' or
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
            scope.get('historical_not_repeated') !=
                ['nginx-request-logging', 'sqlite-with-gcov'] or
            tuple(row['task'] for row in scope['prepared']) != TASKS or
            tuple(row['order'] for row in scope['prepared']) != ORDERS):
        raise RuntimeError('retry scope differs from frozen identity')
    if verify_evidence(Path(args.certification), require_committed=True).get('status') != 'pass':
        raise RuntimeError('source-bound synthetic certification failed')
    for row in scope['prepared']:
        directory = Path(row['directory']).resolve(strict=True)
        manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
        identity = json.loads((directory / 'run_identity.json').read_text(encoding='utf-8'))
        if (directory.parent != root or
                sha(directory / 'manifest.json') != row['manifest_sha256'] or
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
                manifest['config'].get('task_complete_response_policy') !=
                    'complete-response-v1' or
                manifest.get('zero_model_fixture_only') is not False or
                manifest.get('execution_authorized') is not False or
                manifest['assets'][row['task']]['image_id'] != row['image_id'] or
                manifest['assets'][row['task']]['native_tests_tree_sha256'] !=
                    row['native_tests_tree_sha256']):
            raise RuntimeError('retry task asset/config binding differs')
    return root, scope


def prepare(args) -> None:
    plan = json.loads(Path(args.plan).read_text(encoding='utf-8'))
    if (plan.get('schema') != 'pos-ga-sampler-compressor-retry-plan-v1' or
            plan.get('task_complete_response_policy') != 'complete-response-v1' or
            plan.get('execution_authorized') is not False or
            plan.get('historical_not_repeated') !=
                ['nginx-request-logging', 'sqlite-with-gcov'] or
            plan.get('method') != 'PoS' or
            plan.get('official_source_git_commit') !=
                '2fd12b88aafdd04a52c298e3940bcb189f9766d6' or
            tuple(row.get('task') for row in plan['planned_order']) != TASKS or
            tuple(row.get('order') for row in plan['planned_order']) != ORDERS or
            any(row.get('condition') != 'P' for row in plan['planned_order'])):
        raise RuntimeError('not the authorized fixed two-task retry')
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
        command.append('--task-complete-response')
        completed = subprocess.run(command, cwd=CHECKOUT, capture_output=True,
                                   text=True, check=False)
        write_new(root / f'prepare_{order:02d}.json', dict(task=task,
            command_public=command, return_code=completed.returncode,
            stdout=completed.stdout, stderr=completed.stderr))
        if completed.returncode:
            raise RuntimeError('retry task preparation failed: ' + task)
        manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
        identity = json.loads((directory / 'run_identity.json').read_text(encoding='utf-8'))
        prepared.append(dict(order=order, task=task, directory=str(directory),
            run_id=identity['run_id'], run_root=identity['run_root'],
            manifest_sha256=sha(directory / 'manifest.json'),
            config_sha256=manifest['config_sha256'],
            image_id=manifest['assets'][task]['image_id'],
            native_tests_tree_sha256=manifest['assets'][task][
                'native_tests_tree_sha256']))
    write_new(root / 'scope.json', dict(schema='pos-ga-sampler-compressor-retry-scope-v1',
        authorization_basis='user requested sampler then compressor once each',
        historical_not_repeated=['nginx-request-logging', 'sqlite-with-gcov'],
        code_commit=head(), launcher_sha256=sha(Path(__file__)),
        plan_sha256=sha(Path(args.plan)),
        source_files_sha256=source_hashes(), vendor_files_sha256=vendor_hashes(),
        profile_sha256=sha(Path(args.task_profile_file)),
        certification_sha256=sha(Path(args.certification) / 'FILE_HASHES.json'),
        prior=prior, prepared=prepared, task_turns_max=300,
        agent_wall_seconds=14400,
        task_complete_response_policy='complete-response-v1'))
    validate(args)
    print(json.dumps({'prepared':len(prepared), 'code_commit':head(),
                      'scope':str(root / 'scope.json')}), flush=True)


def run(args) -> None:
    root, scope = validate(args)
    for row in scope['prepared']:
        root, scope = validate(args)
        directory = Path(row['directory'])
        if (Path(row['run_root']).exists() or
                (directory / 'batch_result.json').exists() or
                (directory / 'authorization.json').exists()):
            raise RuntimeError('retry task already started or grant exists')
        manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
        arm = manifest['planned_order'][0]
        binding = dict(arm, run_id=row['run_id'], run_root=row['run_root'],
                       batch_id=row['run_id'], config_sha256=row['config_sha256'])
        identity = json.loads((directory / 'run_identity.json').read_text(encoding='utf-8'))
        authorization = dict(execution_authorized=True,
            task_complete_response_policy='complete-response-v1',
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
                task_env = dict(os.environ)
                task_env['GA_TASK_COMPLETE_RESPONSE'] = '1'
                completed = subprocess.run(command, cwd=CHECKOUT, env=task_env,
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
        print(json.dumps({'order':row['order'], 'task':row['task'],
            'continue_safe':safe, 'reward':summary['native_reward']},
            ensure_ascii=False), flush=True)
        if not safe:
            raise RuntimeError('formal run/evaluation/cleanup uncertain; later task stopped')


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
        validate(args)
        print('retry scope verified; no model, Task or Harbor call')
    else:
        run(args)


if __name__ == '__main__':
    main()
