"""One-batch continuation guard; invokes only the existing single_run entry.

This file is outside the execution repository. It does not alter a running
Task, mint a sampler authorization before the SQLite terminal gate, or retry
either task. The two prepared manifests and audited code are fixed below.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

REPO = Path(r'E:\longcontext-cqs-v0-20261005')
SQLITE = Path(r'E:\LongContext\candidate_live_20261020_sqlite_v1')
SAMPLER = Path(r'E:\LongContext\candidate_live_20261020_sampler_v1')
HEAD = 'b522837613f361b4c52bd67577bca72c394ef59b'
SQLITE_MANIFEST = '17ae7fc1beb372081ab9000fa667508f8c6bff48bede956a23a68d21f62828f0'
SAMPLER_MANIFEST = '3ab103c22ef723e71338efb159ae05c16589c892586239ed332ecac299991acf'
TASK_PROFILE = Path(r'E:\LongContext\GenericAgent-main\mykey.py')
PMA_PROFILE = Path(r'E:\LongContext\monitor_config\models.local.json')
OFFICIAL = Path(r'E:\pma-posthoc-official-source-20261014')
HARBOR = Path(r'E:\LongContext\bench_runtime\m4\harbor-src-pos-clean')
STARTED = time.time()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def checkpoint(message: str) -> None:
    print(message, flush=True)


def recorded(root: Path, name: str, value: dict) -> None:
    with (root / name).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def current_head() -> str:
    return subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO,
                          capture_output=True, text=True, check=True).stdout.strip()


def fixed_files() -> None:
    if current_head() != HEAD:
        raise RuntimeError('execution repository HEAD changed')
    if subprocess.run(['git', 'diff', '--quiet', 'HEAD'], cwd=REPO).returncode:
        raise RuntimeError('tracked execution worktree changed')
    for base, expected, task in ((SQLITE, SQLITE_MANIFEST, 'sqlite-with-gcov'),
                                 (SAMPLER, SAMPLER_MANIFEST,
                                  'adaptive-rejection-sampler')):
        identity, manifest = read(base / 'run_identity.json'), read(base / 'manifest.json')
        if (sha(base / 'manifest.json') != expected or
                identity.get('manifest_sha256') != expected or
                manifest.get('planned_order', [{}])[0].get('task') != task or
                manifest.get('config', {}).get('name') != 'pos_pma_complement_v1' or
                manifest.get('config', {}).get('task_complete_response_policy') !=
                    'complete-response-v1' or
                manifest.get('config', {}).get('task_turns_max') != 300 or
                manifest.get('config', {}).get('agent_wall_seconds') != 14400 or
                manifest.get('task_profile_sha256') != sha(TASK_PROFILE) or
                manifest.get('pma_profile_sha256') != sha(PMA_PROFILE) or
                manifest.get('native_shared_certification', {}).get('result', {}).get(
                    'status') != 'pass'):
            raise RuntimeError('frozen manifest/profile/certification differs: ' + task)


def sqlite_gate() -> dict | None:
    batch = SQLITE / 'batch_result.json'
    if not batch.is_file():
        return None
    try:
        result = read(batch)
    except (OSError, ValueError):
        return None  # Controller may still be writing its single result file.
    identity = read(SQLITE / 'run_identity.json')
    run = Path(identity['run_root'])
    if (len(result.get('arms', [])) != 1 or result.get('stop_reason') is not None or
            result['arms'][0].get('run_id') != identity['run_id'] or
            result['arms'][0].get('launcher_exit') != 0 or
            result['arms'][0].get('disposition') != 'completed'):
        raise RuntimeError('SQLite controller did not complete cleanly')
    live = read(run / 'archive/live_result.json')
    archive = live.get('pos_archive_status') or {}
    native = live.get('native_result') or {}
    provider = archive.get('provider_capture') or {}
    if (live.get('run_id') != identity['run_id'] or
            live.get('task') != 'sqlite-with-gcov' or
            live.get('research_candidate') != 'pos_pma_complement_v1' or
            live.get('primary_failure') is not None or
            live.get('harbor_return_code') != 0 or
            live.get('cleanup_confirmed') is not True or
            live.get('remaining_containers') != [] or live.get('cleanup_errors') or
            live.get('frozen_product') is not True or
            live.get('evaluation_released') is not True or
            live.get('native_upload_checked') is not True or
            live.get('native_script_observed') is not True or
            live.get('native_reports_checked') is not True or
            native.get('status') != 'native_recorded' or
            'reward' not in (native.get('rewards') or {}) or
            archive.get('run_id') != identity['run_id'] or
            archive.get('task_id') != 'sqlite-with-gcov' or
            archive.get('result_bound') is not True or
            archive.get('close_bound') is not True or
            archive.get('result_status') != 'completed' or
            archive.get('close_status') != 'graceful_exit' or
            archive.get('archive_incomplete') is not False or
            archive.get('task_archive_incomplete') is not False or
            archive.get('task_terminal_status') != 'available' or
            archive.get('task_result') not in {'CURRENT_TASK_DONE',
                                               'MAX_TURNS_EXCEEDED'} or
            provider.get('mode') != 'profile' or
            provider.get('capture_complete') is not True or
            provider.get('status') != 'complete'):
        raise RuntimeError('SQLite Task/candidate/evaluation/cleanup gate incomplete')
    return {'sqlite_run_id': identity['run_id'],
            'task_result': archive['task_result'],
            'reward': native['rewards']['reward'],
            'provider_calls': provider.get('role_calls'),
            'elapsed_since_guard_start_seconds': round(time.time() - STARTED, 3)}


def sampler_authorization() -> Path:
    fixed_files()
    identity, manifest = read(SAMPLER / 'run_identity.json'), read(SAMPLER / 'manifest.json')
    if (SAMPLER / 'batch_result.json').exists() or Path(identity['run_root']).exists():
        raise RuntimeError('sampler output already exists')
    row = manifest['planned_order'][0]
    binding = dict(row, run_id=identity['run_id'], run_root=identity['run_root'],
                   batch_id=identity['run_id'], config_sha256=manifest['config_sha256'])
    auth = {'execution_authorized': True, 'zero_model_fixture_only': False,
            'candidate_profile_fixture_only': False,
            'task_complete_response_policy': 'complete-response-v1',
            'manifest_sha256': identity['manifest_sha256'],
            'audited_code_commit': HEAD, 'approved_arms': [row],
            'run_bindings': [binding], 'run_id': identity['run_id'],
            'batch_id': identity['run_id'], 'config_sha256': manifest['config_sha256'],
            'output_root': identity['output_root']}
    path = SAMPLER / 'authorization.json'
    recorded(SAMPLER, 'authorization.json', auth)
    return path


def main() -> int:
    fixed_files()
    checkpoint('guard_ready: SQLite running; sampler authorization absent')
    while True:
        gate = sqlite_gate()
        if gate is not None:
            break
        if time.time() - STARTED > 18000:
            raise TimeoutError('SQLite terminal evidence unavailable after finite guard wait')
        time.sleep(30)
    recorded(SQLITE, 'followup_gate.json', gate)
    sqlite_auth = SQLITE / 'authorization.json'
    sqlite_auth.unlink(missing_ok=True)
    recorded(SQLITE, 'authorization_removed.json',
             {'authorization_removed': not sqlite_auth.exists(),
              'run_id': gate['sqlite_run_id']})
    checkpoint('sqlite_gate_pass: clean Task/candidate/native evaluation/cleanup; '
               'starting sampler once')
    auth = sampler_authorization()
    command = [sys.executable, '-B', '-u', '-m',
        'method_discovery.curator_supervisor_convergence_v0.'
        'pma_full_upstream_ga_v1_20261013.single_run', 'run',
        '--output', str(SAMPLER), '--authorization', str(auth),
        '--ga-source', str(REPO / 'GenericAgent-main'),
        '--runtime-root', r'E:\LongContext\bench_runtime\m2\linux',
        '--task-profile-file', str(TASK_PROFILE),
        '--pma-profile-file', str(PMA_PROFILE),
        '--worker-python', r'E:\LongContext\bench_runtime\pma_native_venv\Scripts\python.exe',
        '--harbor-python', sys.executable,
        '--bench-root', str(REPO / 'long_context_bench'),
        '--official-source-git', str(OFFICIAL),
        '--harbor-source-root', str(HARBOR)]
    environment = dict(os.environ, GA_TASK_COMPLETE_RESPONSE='1')
    try:
        with (SAMPLER / 'serial_stdout.txt').open('xb') as stdout, (
                SAMPLER / 'serial_stderr.txt').open('xb') as stderr:
            completed = subprocess.run(command, cwd=REPO, env=environment,
                                       stdout=stdout, stderr=stderr, check=False)
    finally:
        auth.unlink(missing_ok=True)
        recorded(SAMPLER, 'authorization_removed.json',
                 {'authorization_removed': not auth.exists(),
                  'run_id': read(SAMPLER / 'run_identity.json')['run_id']})
    recorded(SAMPLER, 'serial_result.json',
             {'run_id': read(SAMPLER / 'run_identity.json')['run_id'],
              'process_exit_code': completed.returncode,
              'single_run_attempts': 1,
              'authorization_removed': not auth.exists()})
    checkpoint(f'sampler_single_run_exit={completed.returncode}; no further task starts')
    return completed.returncode


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        checkpoint(f'guard_stop={type(exc).__name__}: {exc}')
        raise
