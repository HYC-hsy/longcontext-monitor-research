"""Thin prepare/run loop over the existing single_run entry and one-use bindings."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from .single_manifest import CHECKOUT, FOUR, source_hashes, vendor_hashes
from .worker import (ROLE_JSON_CONTRACT_VERSION, ROLE_INPUT_CONTRACT_VERSION,
                     ROLE_OBJECT_INSTRUCTION, ROLE_UPDATE_FIELDS_INSTRUCTION,
                     ROLE_MAX_TOKENS, ROLE_TEMPERATURE, ROLE_THINKING_TYPE)

ENTRY = ('method_discovery.curator_supervisor_convergence_v0.'
         'pma_full_upstream_ga_v1_20261013.single_run')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def base_arguments(parser):
    for name in ('task-profile-file', 'official-source-git', 'ga-source',
                 'runtime-root', 'worker-python', 'harbor-python', 'bench-root',
                 'harbor-source-root'):
        parser.add_argument('--' + name, required=True)


def common(args):
    return ['--task-profile-file', args.task_profile_file,
            '--official-source-git', args.official_source_git,
            '--ga-source', args.ga_source, '--runtime-root', args.runtime_root,
            '--worker-python', args.worker_python,
            '--harbor-python', args.harbor_python,
            '--bench-root', args.bench_root,
            '--harbor-source-root', args.harbor_source_root]


def prepare(args):
    root = Path(args.output).resolve(strict=False)
    root.mkdir(parents=True, exist_ok=False)
    plan = json.loads(Path(args.plan).read_text(encoding='utf-8'))
    tasks = tuple(row['task'] for row in plan['planned_order'])
    if (plan.get('schema') != 'pos-ga-serial-plan-v1' or
            plan.get('execution_authorized') is not False or tasks != FOUR or
            [row.get('order') for row in plan['planned_order']] != [1, 2, 3, 4]):
        raise RuntimeError('four-task historical order/identity differs')
    from .certification import verify_evidence
    certified = verify_evidence(Path(args.certification))
    if certified.get('status') != 'pass':
        raise RuntimeError('committed PoS synthetic certification failed')
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=CHECKOUT,
        capture_output=True, text=True, check=True).stdout.strip()
    prepared = []
    role_generation = {'role_max_tokens': ROLE_MAX_TOKENS,
        'role_thinking_type': ROLE_THINKING_TYPE,
        'role_temperature': ROLE_TEMPERATURE,
        'role_json_contract': ROLE_JSON_CONTRACT_VERSION,
        'role_input_contract': ROLE_INPUT_CONTRACT_VERSION,
        'role_object_instruction': ROLE_OBJECT_INSTRUCTION,
        'role_update_fields_instruction': ROLE_UPDATE_FIELDS_INSTRUCTION,
        'role_transport_retries': 0}
    for order, task in enumerate(tasks, 1):
        directory = root / f'{order:02d}_{task}'
        command = [sys.executable, '-B', '-m', ENTRY, 'prepare',
                   '--condition', 'P', '--research-candidate', 'PoS',
                   '--task', task, '--output', str(directory),
                   '--certification-dir', str(Path(args.certification).resolve()),
                   '--official-source-git', args.official_source_git,
                   '--task-profile-file', args.task_profile_file]
        completed = subprocess.run(command, cwd=CHECKOUT, capture_output=True,
                                   text=True, check=False)
        write_new(root / f'prepare_{order:02d}.json', {
            'task': task, 'command_public': command, 'return_code': completed.returncode,
            'stdout': completed.stdout, 'stderr': completed.stderr})
        if completed.returncode:
            raise RuntimeError('PoS prepare failed for order ' + str(order))
        manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
        identity = json.loads((directory / 'run_identity.json').read_text(encoding='utf-8'))
        if (manifest['config']['task_turns_max'] != 300 or
                manifest['config']['agent_wall_seconds'] != 14400 or
                any(manifest['config'].get(key) != value
                    for key, value in role_generation.items()) or
                manifest['source_files_sha256'] != source_hashes() or
                manifest['vendor_files_sha256'] != vendor_hashes() or
                manifest.get('zero_model_fixture_only') is not False):
            raise RuntimeError('prepared PoS profile/source/budget differs')
        prepared.append({'order': order, 'task': task, 'directory': str(directory),
            'run_id': identity['run_id'], 'run_root': identity['run_root'],
            'manifest_sha256': sha(directory / 'manifest.json'),
            'profile_sha256': manifest['task_profile_sha256'],
            'config_sha256': manifest['config_sha256'],
            'image_id': manifest['assets'][task]['image_id'],
            'native_tests_tree_sha256': manifest['assets'][task]['native_tests_tree_sha256']})
    write_new(root / 'authorized_serial_scope.json', {
        'schema': 'pos-ga-user-authorized-serial-scope-v1',
        'authorization_basis': 'current user instruction; each run still requires a one-use binding',
        'historical_plan_sha256': sha(args.plan),
        'code_commit': head, 'certification_sha256': sha(
            Path(args.certification) / 'FILE_HASHES.json'),
        'source_files_sha256': source_hashes(), 'vendor_files_sha256': vendor_hashes(),
        'role_generation': role_generation,
        'prepared': prepared, 'task_turns_max': 300,
        'agent_wall_seconds': 14400, 'formal_runs_started': 0})
    print(json.dumps({'prepared': len(prepared), 'code_commit': head,
                      'scope': str(root / 'authorized_serial_scope.json')}))


def run(args):
    from .compatibility_probe import compatibility_checks
    root = Path(args.output).resolve(strict=True)
    scope_path = root / 'authorized_serial_scope.json'
    scope = json.loads(scope_path.read_text(encoding='utf-8'))
    compat_path = Path(args.compatibility_result).resolve(strict=True)
    compat = json.loads(compat_path.read_text(encoding='utf-8'))
    wire = json.loads((compat_path.parent / 'http_attempts.json').read_text(
        encoding='utf-8'))
    role_events = [json.loads(line) for line in
        (compat_path.parent / 'role_events.jsonl').read_text(
            encoding='utf-8').splitlines()]
    identity = compat.get('identity') or {}
    recomputed = compatibility_checks(role_events, compat.get('pos_result') or {},
        compat.get('initial_context') or {}, compat.get('update_context') or {},
        wire, compat.get('pos_roles') or [],
        work_finished=(compat.get('compatibility_checks') or {}).get('checks', {}).get(
            'applicable_work_finished') is True)
    if (compat.get('schema') != 'pos-ga-live-compatibility-result-v3' or
            compat.get('status') != 'passed' or
            recomputed != compat.get('compatibility_checks') or
            recomputed.get('status') != 'passed' or
            identity.get('schema') != 'pos-ga-live-compatibility-v3' or
            identity.get('scope_sha256') != sha(scope_path) or
            identity.get('code_commit') != scope.get('code_commit') or
            identity.get('source_files_sha256') != scope.get('source_files_sha256') or
            identity.get('vendor_files_sha256') != scope.get('vendor_files_sha256') or
            identity.get('certification_sha256') != scope.get('certification_sha256') or
            identity.get('role_generation') != scope.get('role_generation') or
            identity.get('profile_sha256') != sha(args.task_profile_file) or
            identity.get('probe_sha256') != sha(Path(__file__).with_name(
                'compatibility_probe.py')) or
            identity.get('serial_sha256') != sha(__file__) or
            compat.get('role_events_sha256') != sha(
                compat_path.parent / 'role_events.jsonl') or
            compat.get('http_attempts_sha256') != sha(
                compat_path.parent / 'http_attempts.json') or
            not wire or
            compat.get('http_attempts') != len(wire) or
            compat.get('pos_logical_calls') != len([
                row for row in role_events if row.get('event') == 'pos_role_request']) or
            not {'belief', 'consistency', 'progress'} <= set(compat.get('pos_roles', [])) or
            not any(row.get('event') == 'belief_model_input' and
                    row.get('operation') == 'textualize' for row in role_events) or
            not compat.get('update_context', {}).get('belief_text') or
            not all(row.get('http_status') == 200 and
                    row.get('returned_model') == 'claude-opus-4-8' for row in wire) or
            compat.get('task_logical_calls') != 0 or
            compat.get('official_evaluator_calls') != 0 or
            compat.get('task_tools_executed') != 0):
        raise RuntimeError('current bound PoS compatibility did not pass')
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=CHECKOUT,
        capture_output=True, text=True, check=True).stdout.strip()
    if (scope['code_commit'] != head or scope['source_files_sha256'] != source_hashes() or
            scope['vendor_files_sha256'] != vendor_hashes() or
            sha(Path(args.certification) / 'FILE_HASHES.json') !=
            scope['certification_sha256']):
        raise RuntimeError('frozen execution code/certification changed')
    rows = scope['prepared']
    if tuple(row['task'] for row in rows) != FOUR:
        raise RuntimeError('serial order changed')
    for row in rows:
        order, task = row['order'], row['task']
        directory = Path(row['directory'])
        manifest_path = directory / 'manifest.json'
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        identity = json.loads((directory / 'run_identity.json').read_text(encoding='utf-8'))
        if (sha(manifest_path) != row['manifest_sha256'] or
                sha(args.task_profile_file) != row['profile_sha256'] or
                Path(row['run_root']).exists() or (directory / 'batch_result.json').exists()):
            raise RuntimeError('prepared run identity or output root changed')
        arm = manifest['planned_order'][0]
        binding = dict(arm, run_id=row['run_id'], run_root=row['run_root'],
                       batch_id=row['run_id'], config_sha256=row['config_sha256'])
        authorization = {'execution_authorized': True,
            'zero_model_fixture_only': False,
            'manifest_sha256': row['manifest_sha256'],
            'audited_code_commit': head, 'approved_arms': [arm],
            'run_bindings': [binding], 'run_id': row['run_id'],
            'batch_id': row['run_id'], 'config_sha256': row['config_sha256'],
            'output_root': identity['output_root']}
        auth_path = directory / 'authorization.json'
        write_new(auth_path, authorization)
        command = [sys.executable, '-B', '-m', ENTRY, 'run',
            '--output', str(directory), '--authorization', str(auth_path),
            *common(args)]
        record = {'order': order, 'task': task, 'run_id': row['run_id'],
                  'authorization_sha256': sha(auth_path),
                  'command_public': command, 'status': 'started'}
        write_new(directory / 'serial_start.json', record)
        try:
            with (directory / 'serial_stdout.txt').open('xb') as out, (
                    directory / 'serial_stderr.txt').open('xb') as err:
                completed = subprocess.run(command, cwd=CHECKOUT,
                                           stdout=out, stderr=err, check=False)
        finally:
            auth_path.unlink(missing_ok=True)
            write_new(directory / 'authorization_removed.json', {
                'authorization_removed': not auth_path.exists(),
                'authorization_sha256': record['authorization_sha256']})
        status_path = Path(row['run_root']) / 'archive/live_result.json'
        try:
            status = json.loads(status_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            status = None
        terminal_paths = list(Path(row['run_root']).glob('jobs/*/*/agent/task_terminal.json'))
        try:
            terminal = (json.loads(terminal_paths[0].read_text(encoding='utf-8'))
                        if len(terminal_paths) == 1 else None)
        except (OSError, ValueError):
            terminal = None
        summary = {'order': order, 'task': task, 'run_id': row['run_id'],
                   'run_exit': completed.returncode,
                   'status_available': status is not None,
                   'primary_failure': status.get('primary_failure') if status else None,
                   'cleanup_confirmed': status.get('cleanup_confirmed') if status else None,
                   'harbor_return_code': status.get('harbor_return_code') if status else None,
                   'native_result_status': (status.get('native_result') or {}).get('status')
                       if status else None,
                   'native_reward': ((status.get('native_result') or {}).get('rewards') or {})
                       if status else None,
                   'task_terminal_result': terminal.get('result') if terminal else None,
                   'pos_archive_status': status.get('pos_archive_status') if status else None}
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
            (status.get('pos_archive_status') or {}).get('result_bound') is True and
            (status.get('pos_archive_status') or {}).get('close_bound') is True and
            (status.get('pos_archive_status') or {}).get('archive_incomplete') is False and
            (status.get('pos_archive_status') or {}).get('close_status') == 'graceful_exit' and
            terminal and terminal.get('run_id') == row['run_id'] and
            terminal.get('task_id') == task and
            terminal.get('result') in {'CURRENT_TASK_DONE', 'MAX_TURNS_EXCEEDED', 'EXITED'})
        summary['continue_safe'] = safe
        write_new(directory / 'serial_result.json', summary)
        print(json.dumps({'order': order, 'task': task,
                          'continue_safe': safe, 'reward': summary['native_reward']},
                         ensure_ascii=False), flush=True)
        if not safe:
            raise RuntimeError('formal run/evaluation/cleanup uncertain; later tasks stopped')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prepared = commands.add_parser('prepare')
    base_arguments(prepared)
    prepared.add_argument('--plan', required=True)
    prepared.add_argument('--certification', required=True)
    prepared.add_argument('--output', required=True)
    launched = commands.add_parser('run')
    base_arguments(launched)
    launched.add_argument('--certification', required=True)
    launched.add_argument('--compatibility-result', required=True)
    launched.add_argument('--output', required=True)
    args = parser.parse_args()
    prepare(args) if args.command == 'prepare' else run(args)


if __name__ == '__main__':
    main()
