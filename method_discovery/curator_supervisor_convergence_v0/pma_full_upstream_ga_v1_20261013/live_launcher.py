"""Explicitly authorized PMA/GA four-arm entry; no offline flag enables it."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

from long_context_bench.scripts.isolated_run_bundle import digest_tree

from .offline_launcher import (STAGE, TASKS, _prepare_common,
                               capture_mounts, clean_owned_containers)
from .pma_harbor_hooks import verify_live_spec


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _stage_verifier(root: Path, task: str, manifest: dict) -> dict:
    source = STAGE / 'assets' / 'evaluator' / task / 'tests'
    target = root / 'public_task' / 'tests'
    if not source.is_dir() or not target.is_dir() or any(source.rglob('*.lnk')):
        raise RuntimeError('PMA fixed native evaluator is unavailable')
    if any(path.is_symlink() for path in source.rglob('*')) or list(target.iterdir()):
        raise RuntimeError('PMA evaluator contains redirected files or target is not empty')
    expected = manifest['assets'][task]
    identity = {'native_tests_tree_sha256': digest_tree(source),
                'native_test_sh_sha256': _sha(source / 'test.sh')}
    if any(identity[key] != expected[key] for key in identity):
        raise RuntimeError('PMA native evaluator differs from frozen source')
    shutil.copytree(source, target, dirs_exist_ok=True)
    if digest_tree(target) != identity['native_tests_tree_sha256']:
        raise RuntimeError('PMA staged evaluator bytes changed')
    return identity


def _worker_clearance(root: Path, worker: subprocess.Popen | None, run_id: str) -> dict | None:
    target = root / 'control' / 'sidecar_stopped.json'
    if target.exists():
        return json.loads(target.read_text(encoding='utf-8'))
    if worker is None:
        clearance = {'run_id': run_id, 'clean': True}
    elif worker.poll() is None:
        return None
    else:
        receipt = root / 'host_private' / 'worker_exit.json'
        try:
            exit_value = json.loads(receipt.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            exit_value = None
        clearance = {'run_id': run_id, 'clean': bool(
            worker.returncode == 0 and isinstance(exit_value, dict) and
            exit_value.get('task_end_saved') is True and
            exit_value.get('reason') == 'task_end')}
    target.write_text(json.dumps(clearance, sort_keys=True), encoding='utf-8')
    return clearance


def run_live(args) -> dict:
    manifest_path = Path(args.manifest).resolve(strict=True)
    authorization_path = Path(args.authorization).resolve(strict=True)
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    authorized = json.loads(authorization_path.read_text(encoding='utf-8'))
    if (manifest.get('schema') != 'pma-ga-live-manifest-v1' or
            manifest.get('execution_authorized') is not False or
            authorized.get('execution_authorized') is not True or
            authorized.get('manifest_sha256') != _sha(manifest_path)):
        raise RuntimeError('PMA authorization absent or changed')
    if args.condition == 'B' and not os.environ.get('PMA_MEMORY_API_KEY'):
        raise RuntimeError('PMA memory credential is not configured')
    if Path(args.run_root).exists():
        raise FileExistsError(args.run_root)
    args.execution_authorized = False
    prepared = _prepare_common(args, fake_gateway=False)
    root = Path(args.run_root).resolve(strict=True)
    if prepared['public_task_tree_sha256'] != manifest['assets'][args.task]['public_task_tree_sha256']:
        raise RuntimeError('PMA public task package differs from frozen identity')
    order = args.order
    spec = {
        'schema': 'pma-ga-live-run-v1', 'mode': 'authorized_live',
        'execution_authorized': True, 'order': order, 'task': args.task,
        'task_id': args.task, 'condition': args.condition, 'run_id': args.run_id,
        'run_root': str(root), 'image_id': prepared['image_id'],
        'control_root': str(root / 'control'), 'archive_root': str(root / 'archive'),
        'manifest_path': str(manifest_path), 'manifest_sha256': _sha(manifest_path),
        'authorization_path': str(authorization_path),
        'authorization_sha256': _sha(authorization_path),
        'audited_code_commit': authorized['audited_code_commit'],
    }
    verify_live_spec(spec)
    if _sha(Path(args.task_profile_file)) != manifest['task_profile_sha256']:
        raise RuntimeError('PMA Task profile differs from frozen identity')
    staged = _stage_verifier(root, args.task, manifest)
    spec.update(staged)
    spec_path = root / 'control' / 'harbor_spec.json'
    spec_path.write_text(json.dumps(spec, indent=2), encoding='utf-8')
    deadline = time.time() + 14400
    worker = harbor = None
    worker_logs = []
    first_error = None
    cleanup_errors = []
    result = None
    stop_requested_at = None
    try:
        if args.condition == 'B':
            for name in ('worker.stdout.log', 'worker.stderr.log'):
                worker_logs.append((root / 'archive' / name).open('wb'))
            worker_env = dict(os.environ)
            worker_env['PYTHONPATH'] = os.pathsep.join((str(STAGE),
                str(STAGE / 'vendor' / 'pma_89e5c0d' / 'src'),
                str(STAGE / 'vendor' / 'pma_89e5c0d' / 'external' / 'harbor')))
            worker = subprocess.Popen([
                str(Path(args.worker_python).resolve(strict=True)), str(STAGE / 'worker_main.py'),
                '--run-id', args.run_id, '--task-id', args.task,
                '--private-root', str(root / 'host_private'),
                '--requests', str(root / 'control' / 'spool' / 'requests'),
                '--responses', str(root / 'control' / 'spool' / 'responses'),
                '--deadline-epoch', str(deadline)], cwd=STAGE, env=worker_env,
                stdout=worker_logs[0], stderr=worker_logs[1])
            ready = root / 'host_private' / 'worker_ready.json'
            ready_limit = min(deadline, time.time() + 20)
            while not ready.is_file():
                if worker.poll() is not None or time.time() >= ready_limit:
                    raise RuntimeError('PMA host worker not ready')
                time.sleep(.05)
            ready_data = json.loads(ready.read_text(encoding='utf-8'))
            if (ready_data.get('run_id'), ready_data.get('task_id'),
                    ready_data.get('fake_memory')) != (args.run_id, args.task, False):
                raise RuntimeError('PMA worker identity or transport mode mismatch')
        else:
            _worker_clearance(root, None, args.run_id)
        repo = STAGE.parents[2]
        mounts = [
            {'type': 'bind', 'source': str(Path(args.runtime_root).resolve(strict=True)),
             'target': '/opt/m4-runtime', 'read_only': True},
            {'type': 'bind', 'source': str((root / 'bundle/source').resolve(strict=True)),
             'target': '/opt/genericagent-source', 'read_only': True},
        ]
        command = [str(Path(args.harbor_python).resolve(strict=True)), '-m',
            'method_discovery.curator_supervisor_convergence_v0.'
            'pma_full_upstream_ga_v1_20261013.pma_harbor_cli',
            'jobs', 'start', '--job-name', args.run_id, '--jobs-dir', str(root / 'jobs'),
            '--path', str(root / 'public_task'),
            '--agent', ('method_discovery.curator_supervisor_convergence_v0.'
                        'pma_full_upstream_ga_v1_20261013.harbor_adapter:HarborGenericAgent'),
            '--model', 'claude-opus-4-8', '--mounts', json.dumps(mounts),
            '--extra-docker-compose', str(root / 'bundle/isolation.compose.json'),
            '--n-concurrent', '1', '--max-retries', '0', '--yes', '--enable-verification',
            '--agent-timeout-multiplier', '16', '--verifier-timeout-multiplier', '1']
        kwargs = {'llm_no': 0, 'run_id': args.run_id, 'task_id': args.task,
                  'expected_model': 'claude-opus-4-8', 'python_home': args.python_home,
                  'ga_source_sha256': prepared['ga_bundle_tree_sha256'],
                  'timeout_sec': 14400, 'max_turns': 300,
                  'llm_config_name': args.task_profile, 'condition_id': 'pma-neutral'}
        for key, value in kwargs.items():
            command += ['--ak', f'{key}={value}']
        env = dict(os.environ)
        for name in ('PMA_MEMORY_API_KEY', 'OPENROUTER_API_KEY', 'ANTHROPIC_API_KEY'):
            env.pop(name, None)
        env['PYTHONPATH'] = os.pathsep.join((str(repo), str(repo / 'GenericAgent-main'),
                                            str(Path(args.bench_root).resolve(strict=True))))
        env.update(PMA_HARBOR_SPEC=str(spec_path), PYTHONUTF8='1', PYTHONIOENCODING='utf-8',
                   GA_RUN_ISOLATION='no-network-unix-inference-v1',
                   GA_PMA_UPSTREAM_ENABLED='1' if args.condition == 'B' else '0',
                   GA_PMA_ENABLED='0', GA_MONITOR_ENABLED='0', GA_M0_MONITOR_ENABLED='0')
        if args.condition == 'B':
            env.update(GA_PMA_UPSTREAM_REQUESTS='/run/pma-bridge/requests',
                       GA_PMA_UPSTREAM_RESPONSES='/run/pma-bridge/responses',
                       GA_PMA_UPSTREAM_DEADLINE_EPOCH=str(deadline))
        (root / 'archive' / 'live_command_public.json').write_text(json.dumps({
            'argv': command, 'public_env': {name: env[name] for name in (
                'GA_RUN_ISOLATION', 'GA_PMA_UPSTREAM_ENABLED', 'GA_MONITOR_ENABLED')},
            'agent_deadline_epoch': deadline, 'evaluator_timeout_sec': 900,
            'outer_timeout_sec': 14400 + 900 + 600}, indent=2), encoding='utf-8')
        with (root / 'archive/harbor.stdout.log').open('wb') as out, (
                root / 'archive/harbor.stderr.log').open('wb') as err:
            harbor = subprocess.Popen(command, cwd=repo, env=env, stdout=out, stderr=err)
            outer_deadline = deadline + 900 + 600
            while harbor.poll() is None:
                if worker is not None and worker.poll() is None and time.time() >= deadline:
                    if stop_requested_at is None:
                        (root / 'host_private/stop.request').touch()
                        stop_requested_at = time.monotonic()
                    elif time.monotonic() - stop_requested_at >= 10:
                        worker.kill()
                _worker_clearance(root, worker, args.run_id)
                if time.time() >= outer_deadline:
                    raise subprocess.TimeoutExpired(command, 14400 + 900 + 600)
                time.sleep(.25)
            result = harbor.returncode
    except BaseException as exc:
        first_error = {'type': type(exc).__name__, 'message': str(exc)}
    finally:
        if worker is not None and worker.poll() is None:
            try:
                (root / 'host_private/stop.request').touch()
                worker.wait(timeout=10)
            except subprocess.TimeoutExpired:
                try:
                    worker.kill()
                    worker.wait(timeout=5)
                except BaseException as exc:
                    cleanup_errors.append(f'worker_force_stop_unknown:{type(exc).__name__}:{exc}')
            except BaseException as exc:
                cleanup_errors.append(f'worker_stop_unknown:{type(exc).__name__}:{exc}')
        if worker is not None and worker.poll() is None:
            cleanup_errors.append('worker_still_running')
        if harbor is not None and harbor.poll() is None:
            try:
                harbor.kill()
                harbor.wait(timeout=10)
            except BaseException as exc:
                cleanup_errors.append(f'harbor_stop_unknown:{type(exc).__name__}:{exc}')
        for stream in worker_logs:
            stream.close()
        try:
            cleanup_errors.extend(clean_owned_containers(root))
            remaining = capture_mounts(root, include_stopped=True)
        except BaseException as exc:
            cleanup_errors.append(f'container_cleanup_unknown:{type(exc).__name__}:{exc}')
            remaining = None
        frozen = root / 'archive/agent_end_frozen.json'
        release = root / 'archive/verification_released.json'
        status = {'run_id': args.run_id, 'task': args.task, 'condition': args.condition,
                  'harbor_return_code': result, 'primary_failure': first_error,
                  'worker_return_code': None if worker is None else worker.poll(),
                  'remaining_containers': None if remaining is None else [m['id'] for m in remaining],
                  'cleanup_errors': cleanup_errors,
                  'cleanup_confirmed': remaining == [] and not cleanup_errors and
                  (worker is None or worker.poll() is not None) and
                  (harbor is None or harbor.poll() is not None),
                  'frozen_product': frozen.is_file(), 'evaluation_released': release.is_file()}
        (root / 'archive/live_result.json').write_text(json.dumps(status, indent=2), encoding='utf-8')
    return status


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ('manifest', 'authorization', 'run-id', 'run-root', 'ga-source',
                 'runtime-root', 'task-profile-file', 'worker-python', 'harbor-python',
                 'bench-root'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--order', type=int, required=True)
    parser.add_argument('--task', choices=TASKS, required=True)
    parser.add_argument('--condition', choices=('A', 'B'), required=True)
    parser.add_argument('--task-profile', default='native_claude_cc_vibe_opus48')
    parser.add_argument('--python-home', default='cpython-3.12.12-linux-x86_64-gnu')
    args = parser.parse_args()
    print(json.dumps(run_live(args), indent=2))


if __name__ == '__main__':
    main()
