"""Explicitly authorized PMA/GA four-arm entry; no offline flag enables it."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time

from long_context_bench.scripts.isolated_run_bundle import digest_tree

from .offline_launcher import (STAGE, TASKS, _prepare_common,
                               capture_mounts, clean_owned_containers)
from .pma_harbor_hooks import verify_live_spec
from .export_official_evaluator import (COMMIT as OFFICIAL_COMMIT,
                                         export_task, official_members)
from .prepare_six_task_manifest import SOURCE_FILES, EVIDENCE_FILES


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _stage_verifier(root: Path, task: str, manifest: dict,
                    official_source_git: Path) -> dict:
    target = root / 'public_task' / 'tests'
    if manifest.get('official_evaluator_commit') != OFFICIAL_COMMIT:
        raise RuntimeError('PMA manifest does not identify fixed official evaluator blobs')
    expected = manifest['assets'][task]
    source = official_source_git.resolve(strict=True)
    members = [{k: v for k, v in item.items() if k != 'raw'}
               for item in official_members(source, task)]
    if members != expected.get('official_evaluator_members'):
        raise RuntimeError('PMA official evaluator members differ from frozen manifest')
    export_task(source, task, target)
    identity = {'native_tests_tree_sha256': digest_tree(target),
                'native_test_sh_sha256': _sha(target / 'test.sh')}
    if any(identity[key] != expected[key] for key in identity):
        raise RuntimeError('PMA native evaluator differs from frozen source')
    if digest_tree(target) != identity['native_tests_tree_sha256']:
        raise RuntimeError('PMA staged evaluator bytes changed')
    return identity


def _require_evaluation_state_contract(manifest: dict) -> None:
    """Bind the native SHARED protocol to code and zero-model raw evidence."""
    if manifest.get('schema') == 'pma-ga-live-manifest-v2':
        cert = manifest.get('native_shared_certification')
        if (manifest.get('status') != 'prepared_not_executed' or
                not isinstance(cert, dict) or
                cert.get('harbor_commit') !=
                '459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc' or
                set(cert.get('source_files', {})) != set(SOURCE_FILES) or
                set(cert.get('evidence_files', {})) != set(EVIDENCE_FILES)):
            raise RuntimeError('six-task SHARED evidence/identity not frozen')
        checkout = STAGE.parents[2]
        evidence = STAGE / 'six_task_native_base_20261014'
        for name in SOURCE_FILES:
            if _sha(checkout / name) != cert['source_files'][name]:
                raise RuntimeError('six-task SHARED source bytes changed')
        for name in EVIDENCE_FILES:
            if _sha(evidence / name) != cert['evidence_files'][name]:
                raise RuntimeError('six-task SHARED evidence bytes changed')
        index = json.loads((evidence / 'FILE_HASHES.json').read_text(encoding='utf-8'))
        for item in index['files']:
            path = (checkout / item['path']).resolve(strict=True)
            if not path.is_relative_to(evidence) or _sha(path) != item['sha256']:
                raise RuntimeError('six-task SHARED raw evidence changed')
        images = json.loads((evidence / 'image_checks.json').read_text(encoding='utf-8'))
        if (len(images) != 6 or any(row.get('exit_code') != 0 or
                                    not row.get('hidden_material_absent') for row in images)):
            raise RuntimeError('six-task image/hidden-material evidence incomplete')
        compared = json.loads((evidence / 'request_comparison.json').read_text(
            encoding='utf-8'))
        if (compared.get('only_metadata_differs') is not True or
                compared.get('b_second_request_reminder_visible') is not True):
            raise RuntimeError('six-task A/B fake request identity not established')
        test_log = (evidence / 'unittest.stderr.txt').read_text(encoding='utf-16')
        match = re.search(r'Ran (\d+) tests', test_log)
        if (match is None or int(match.group(1)) < 15 or
                not test_log.rstrip().endswith('OK')):
            raise RuntimeError('six-task offline test record incomplete')
        def fixture(number: str) -> dict:
            return json.loads((evidence / 'fixtures' / number / 'archive' /
                               'fixture_result.json').read_text(encoding='utf-8'))
        if (not fixture('02').get('verification_released') or
                not fixture('03').get('verification_released') or
                fixture('04').get('verification_released') or
                fixture('08').get('native_result', {}).get('status') != 'unavailable' or
                fixture('09').get('native_result', {}).get('exception_info', {}).get(
                    'exception_type') != 'AgentTimeoutError' or
                not fixture('10').get('native_reports_checked', {}).get(
                    'all_reports_executed') or
                fixture('11').get('frozen_product')):
            raise RuntimeError('six-task native lifecycle fixture outcomes changed')
        return
    raise RuntimeError('PMA live evaluation state/environment transition is not '
                       'certified; no Task/provider request may start')


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


def _native_trial_result(root: Path) -> dict:
    """Read this fresh Harbor job's result, without interpreting task answers."""
    candidates = []
    for path in (root / 'jobs').glob('*/*/result.json'):
        data = json.loads(path.read_text(encoding='utf-8'))
        if isinstance(data, dict) and 'verifier_result' in data:
            candidates.append((path, data))
    if len(candidates) != 1:
        return {'status': 'unavailable', 'reason': 'one_trial_result_not_found',
                'candidates': len(candidates)}
    path, data = candidates[0]
    verifier = data.get('verifier_result')
    rewards = verifier.get('rewards') if isinstance(verifier, dict) else None
    if not isinstance(rewards, dict) or not rewards:
        return {'status': 'unavailable', 'reason': 'native_reward_missing',
                'result_path': str(path.relative_to(root)),
                'exception_info': data.get('exception_info')}
    return {'status': 'native_recorded', 'rewards': rewards,
            'result_path': str(path.relative_to(root)),
            'exception_info': data.get('exception_info'),
            'agent_execution': data.get('agent_execution'),
            'verifier': data.get('verifier')}


def _owned_volume_clearance(root: Path) -> dict:
    try:
        identity = json.loads((root / 'archive/agent_start_identity.json').read_text(
            encoding='utf-8'))
    except (OSError, ValueError):
        return {'status': 'unknown', 'reason': 'mount_identity_unavailable'}
    names = {m.get('Name') for m in identity.get('mounts', [])
             if m.get('Type') == 'volume'}
    if None in names or not names:
        return {'status': 'unknown', 'reason': 'owned_volume_names_unavailable'}
    remaining = []
    for name in sorted(names):
        check = subprocess.run(['docker', 'volume', 'inspect', name],
                               capture_output=True, text=True, timeout=30)
        if check.returncode == 0:
            remaining.append(name)
        elif 'no such volume' not in check.stderr.lower():
            return {'status': 'unknown', 'reason': 'docker_volume_inspect_failed',
                    'name': name}
    return {'status': 'clean' if not remaining else 'remaining',
            'names': sorted(names), 'remaining': remaining}


def run_live(args) -> dict:
    manifest_path = Path(args.manifest).resolve(strict=True)
    authorization_path = Path(args.authorization).resolve(strict=True)
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    authorized = json.loads(authorization_path.read_text(encoding='utf-8'))
    if (manifest.get('schema') not in {'pma-ga-live-manifest-v1',
                                       'pma-ga-live-manifest-v2'} or
            manifest.get('execution_authorized') is not False or
            authorized.get('execution_authorized') is not True or
            authorized.get('manifest_sha256') != _sha(manifest_path)):
        raise RuntimeError('PMA authorization absent or changed')
    memory_profile_path = None
    if args.condition == 'B':
        if not args.pma_profile_file:
            raise RuntimeError('PMA Opus 4.8 profile is required for B')
        memory_profile_path = Path(args.pma_profile_file).resolve(strict=True)
        if _sha(memory_profile_path) != manifest.get('pma_profile_sha256'):
            raise RuntimeError('PMA memory profile differs from frozen identity')
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
    if manifest['schema'] == 'pma-ga-live-manifest-v2':
        spec.update(repeat=args.repeat, batch_id=authorized['batch_id'],
                    config_sha256=manifest['config_sha256'],
                    evaluation_protocol='official_shared_v2',
                    official_source_git_commit=OFFICIAL_COMMIT,
                    expected_native_reports=manifest['assets'][args.task][
                        'expected_native_reports'],
                    official_evaluator_files=[{
                        'relative': '/'.join(item['path'].split('/')[1:]),
                        'sha256': item['sha256']}
                        for item in manifest['assets'][args.task]['official_evaluator_members']])
    verify_live_spec(spec)
    if _sha(Path(args.task_profile_file)) != manifest['task_profile_sha256']:
        raise RuntimeError('PMA Task profile differs from frozen identity')
    staged = _stage_verifier(root, args.task, manifest,
                             Path(args.official_source_git))
    spec.update(staged)
    _require_evaluation_state_contract(manifest)
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
                str(STAGE / 'vendor' / 'pma_89e5c0d' / 'external' / 'harbor' / 'src')))
            worker_env['PMA_MEMORY_PROFILE_FILE'] = str(memory_profile_path)
            worker_env['PMA_MEMORY_PROFILE_SHA256'] = manifest['pma_profile_sha256']
            worker_env['LITELLM_LOCAL_MODEL_COST_MAP'] = 'True'
            worker_env.pop('PMA_MEMORY_API_BASE', None)
            worker_env.pop('PMA_MEMORY_API_KEY', None)
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
            '--agent-timeout-multiplier', str(14400 /
                manifest['assets'][args.task]['native_agent_seconds'])
                if manifest['schema'] == 'pma-ga-live-manifest-v2' else '16',
            '--verifier-timeout-multiplier', '1']
        if manifest['schema'] == 'pma-ga-live-manifest-v2':
            command += ['--verifier-import-path',
                'method_discovery.curator_supervisor_convergence_v0.'
                'pma_full_upstream_ga_v1_20261013.native_shared_verifier:NativeSharedVerifier']
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
        python_roots = [str(repo), str(repo / 'GenericAgent-main'),
                        str(Path(args.bench_root).resolve(strict=True))]
        if manifest['schema'] == 'pma-ga-live-manifest-v2':
            harbor_source = Path(args.harbor_source_root).resolve(strict=True)
            head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=harbor_source,
                                  capture_output=True, text=True, check=True).stdout.strip()
            dirty = subprocess.run(['git', 'status', '--porcelain'], cwd=harbor_source,
                                   capture_output=True, text=True, check=True).stdout.strip()
            if head != '459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc' or dirty:
                raise RuntimeError('fixed clean native Harbor source unavailable')
            python_roots.insert(0, str(harbor_source / 'src'))
        env['PYTHONPATH'] = os.pathsep.join(python_roots)
        env.update(PMA_HARBOR_SPEC=str(spec_path), PYTHONUTF8='1', PYTHONIOENCODING='utf-8',
                   GA_RUN_ISOLATION=('networked-host-keyed-v1' if
                       manifest['schema'] == 'pma-ga-live-manifest-v2' else
                       'no-network-unix-inference-v1'),
                   GA_PMA_UPSTREAM_ENABLED='1' if args.condition == 'B' else '0',
                   GA_PMA_CAPTURE_TASK_REQUESTS='1' if args.condition == 'B' else '0',
                   GA_PMA_ENABLED='0', GA_MONITOR_ENABLED='0', GA_M0_MONITOR_ENABLED='0')
        if args.condition == 'B':
            env.update(GA_PMA_UPSTREAM_REQUESTS='/run/pma-bridge/requests',
                       GA_PMA_UPSTREAM_RESPONSES='/run/pma-bridge/responses',
                       GA_PMA_UPSTREAM_DEADLINE_EPOCH=str(deadline))
        (root / 'archive' / 'live_command_public.json').write_text(json.dumps({
            'argv': command, 'public_env': {name: env[name] for name in (
                'GA_RUN_ISOLATION', 'GA_PMA_UPSTREAM_ENABLED', 'GA_MONITOR_ENABLED')},
            'agent_deadline_epoch': deadline,
            'evaluator_timeout_sec': manifest['assets'][args.task].get(
                'native_verifier_seconds', 900),
            'outer_timeout_sec': 14400 + manifest['assets'][args.task].get(
                'native_verifier_seconds', 900) + 600}, indent=2), encoding='utf-8')
        with (root / 'archive/harbor.stdout.log').open('wb') as out, (
                root / 'archive/harbor.stderr.log').open('wb') as err:
            harbor = subprocess.Popen(command, cwd=repo, env=env, stdout=out, stderr=err)
            outer_deadline = deadline + manifest['assets'][args.task].get(
                'native_verifier_seconds', 900) + 600
            while harbor.poll() is None:
                if worker is not None and worker.poll() is None and time.time() >= deadline:
                    if stop_requested_at is None:
                        (root / 'host_private/stop.request').touch()
                        stop_requested_at = time.monotonic()
                    elif time.monotonic() - stop_requested_at >= 10:
                        worker.kill()
                _worker_clearance(root, worker, args.run_id)
                if time.time() >= outer_deadline:
                    raise subprocess.TimeoutExpired(command, 14400 +
                        manifest['assets'][args.task].get('native_verifier_seconds', 900) + 600)
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
        native_shared = manifest['schema'] == 'pma-ga-live-manifest-v2'
        volumes = _owned_volume_clearance(root) if native_shared else None
        frozen = root / 'archive' / ('agent_end_native.json' if native_shared else
                                     'agent_end_frozen.json')
        release = root / 'archive/verification_released.json'
        native = _native_trial_result(root) if native_shared else None
        execution = None
        reports = None
        if native_shared:
            try:
                execution = json.loads((root / 'archive/native_test_execution.json').read_text(
                    encoding='utf-8'))
            except (OSError, ValueError):
                execution = None
            try:
                reports = json.loads((root / 'archive/native_reports_checked.json').read_text(
                    encoding='utf-8'))
            except (OSError, ValueError):
                reports = None
        status = {'schema': manifest['schema'], 'run_id': args.run_id,
                  'task': args.task, 'condition': args.condition,
                  'harbor_return_code': result, 'primary_failure': first_error,
                  'worker_return_code': None if worker is None else worker.poll(),
                  'remaining_containers': None if remaining is None else [m['id'] for m in remaining],
                  'cleanup_errors': cleanup_errors,
                  'cleanup_confirmed': remaining == [] and not cleanup_errors and
                  (not native_shared or volumes.get('status') == 'clean') and
                  (worker is None or worker.poll() is not None) and
                  (harbor is None or harbor.poll() is not None),
                  'frozen_product': frozen.is_file(), 'evaluation_released': release.is_file(),
                  'native_result': native,
                  'native_upload_checked': (root / 'archive/native_evaluator_uploaded.json').is_file()
                      if native_shared else None,
                  'native_script_observed': (isinstance(execution, dict) and
                      execution.get('run_id') == args.run_id and
                      execution.get('observed') is True) if native_shared else None,
                  'native_script_executions': execution.get('executions')
                      if isinstance(execution, dict) else None,
                  'native_reports_checked': (isinstance(reports, dict) and
                      reports.get('run_id') == args.run_id and
                      reports.get('all_reports_executed') is True)
                      if native_shared else None,
                  'native_report_diagnostics': reports}
        status['owned_volume_clearance'] = volumes
        (root / 'archive/live_result.json').write_text(json.dumps(status, indent=2), encoding='utf-8')
    return status


def live_status_success(status: dict) -> bool:
    native = status.get('native_result')
    native_required = status.get('schema') == 'pma-ga-live-manifest-v2'
    return (status.get('primary_failure') is None and
            status.get('harbor_return_code') == 0 and
            status.get('cleanup_confirmed') is True and
            status.get('frozen_product') is True and
            status.get('evaluation_released') is True and
            (not native_required or (isinstance(native, dict) and
                                native.get('status') == 'native_recorded' and
                                status.get('native_upload_checked') is True and
                                status.get('native_script_observed') is True and
                                status.get('native_reports_checked') is True)) and
            (status.get('condition') != 'B' or
             status.get('worker_return_code') == 0))


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ('manifest', 'authorization', 'run-id', 'run-root', 'ga-source',
                 'runtime-root', 'task-profile-file', 'worker-python', 'harbor-python',
                 'bench-root', 'official-source-git'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--order', type=int, required=True)
    parser.add_argument('--repeat', type=int, choices=(1, 2))
    parser.add_argument('--task', choices=TASKS, required=True)
    parser.add_argument('--condition', choices=('A', 'B'), required=True)
    parser.add_argument('--task-profile', default='native_claude_cc_vibe_opus48')
    parser.add_argument('--pma-profile-file')
    parser.add_argument('--harbor-source-root')
    parser.add_argument('--python-home', default='cpython-3.12.12-linux-x86_64-gnu')
    args = parser.parse_args()
    status = run_live(args)
    print(json.dumps(status, indent=2))
    if not live_status_success(status):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
