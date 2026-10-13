"""Run the real PMA Harbor hook with a local fake model and fake verifier only.

This executable fixture never reads live PMA credentials, and is not a pilot
arm or a native-evaluator result. It uses the existing fixed-image bundle.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

from .live_launcher import _worker_clearance
from .offline_launcher import _prepare_common, capture_mounts, clean_owned_containers
from .offline_launcher import STAGE
from long_context_bench.scripts.isolated_run_bundle import digest_tree


def _write(path: Path, value: dict) -> str:
    path.write_text(json.dumps(value, sort_keys=True), encoding='utf-8')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args):
    root = Path(args.run_root).resolve()
    args.task = 'db-wal-recovery'
    args.condition = 'B'
    args.task_profile = 'native_claude_cc_vibe_opus48'
    args.multiturn_fixture = True
    record = _prepare_common(args, fake_gateway=True)
    test_script = root / 'public_task/tests/test.sh'
    test_script.write_text('#!/bin/sh\nmkdir -p /logs/verifier\n'
                           'printf "fake-only\\n" > /logs/verifier/reward.txt\n',
                           encoding='utf-8', newline='\n')
    arms = [dict(order=i, task=t, condition=c) for i, t, c in (
        (1, 'db-wal-recovery', 'A'), (2, 'db-wal-recovery', 'B'),
        (3, 'fix-code-vulnerability', 'B'), (4, 'fix-code-vulnerability', 'A'))]
    bindings = [dict(arm, run_id=(args.run_id if arm['order'] == 2 else
                                   f'unused-fixture-{arm["order"]}'),
                     run_root=str(root if arm['order'] == 2 else
                                  root.parent / f'unused-fixture-{arm["order"]}'))
                for arm in arms]
    manifest = root / 'control/fixture_manifest.json'
    authorization = root / 'control/fixture_authorization.json'
    manifest_sha = _write(manifest, {'schema': 'pma-ga-live-manifest-v1',
                                    'execution_authorized': False, 'arms': arms})
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=STAGE.parents[2],
                          capture_output=True, text=True, check=True).stdout.strip()
    authorization_sha = _write(authorization, {'execution_authorized': True,
        'manifest_sha256': manifest_sha, 'audited_code_commit': head,
        'approved_arms': arms, 'run_bindings': bindings,
        'fixture_fake_transport_only': True})
    spec = {'schema': 'pma-ga-live-run-v1', 'mode': 'authorized_live',
        'execution_authorized': True, 'order': 2, 'task': args.task,
        'task_id': args.task, 'condition': 'B', 'run_id': args.run_id,
        'run_root': str(root), 'image_id': record['image_id'],
        'control_root': str(root / 'control'), 'archive_root': str(root / 'archive'),
        'manifest_path': str(manifest), 'manifest_sha256': manifest_sha,
        'authorization_path': str(authorization),
        'authorization_sha256': authorization_sha,
        'audited_code_commit': head,
        'native_test_sh_sha256': hashlib.sha256(test_script.read_bytes()).hexdigest(),
        'native_tests_tree_sha256': digest_tree(test_script.parent)}
    spec_path = root / 'control/harbor_spec.json'
    _write(spec_path, spec)
    deadline = time.time() + 240
    worker_env = dict(os.environ)
    worker_env['LITELLM_LOCAL_MODEL_COST_MAP'] = 'True'
    worker_env['PYTHONPATH'] = os.pathsep.join((str(STAGE),
        str(STAGE / 'vendor/pma_89e5c0d/src'),
        str(STAGE / 'vendor/pma_89e5c0d/external/harbor')))
    worker_out = (root / 'archive/worker.stdout.log').open('wb')
    worker_err = (root / 'archive/worker.stderr.log').open('wb')
    worker = harbor = None
    failure = None
    cleanup_errors = []
    try:
        worker = subprocess.Popen([str(Path(args.worker_python).resolve(strict=True)),
            str(STAGE / 'worker_main.py'), '--run-id', args.run_id,
            '--task-id', args.task, '--private-root', str(root / 'host_private'),
            '--requests', str(root / 'control/spool/requests'),
            '--responses', str(root / 'control/spool/responses'),
            '--deadline-epoch', str(deadline), '--fake-memory',
            '--fake-memory-update'], cwd=STAGE, env=worker_env,
            stdout=worker_out, stderr=worker_err)
        ready = root / 'host_private/worker_ready.json'
        while not ready.is_file() and worker.poll() is None and time.time() < deadline:
            time.sleep(.05)
        if not ready.is_file():
            raise RuntimeError('fake worker did not become ready')
        mounts = [{'type': 'bind', 'source': str(Path(args.runtime_root).resolve()),
                   'target': '/opt/m4-runtime', 'read_only': True},
                  {'type': 'bind', 'source': str((root / 'bundle/source').resolve()),
                   'target': '/opt/genericagent-source', 'read_only': True}]
        command = [str(Path(args.harbor_python).resolve(strict=True)), '-m',
            'method_discovery.curator_supervisor_convergence_v0.'
            'pma_full_upstream_ga_v1_20261013.pma_harbor_cli',
            'jobs', 'start', '--job-name', args.run_id, '--jobs-dir', str(root / 'jobs'),
            '--path', str(root / 'public_task'), '--agent',
            'method_discovery.curator_supervisor_convergence_v0.'
            'pma_full_upstream_ga_v1_20261013.harbor_adapter:HarborGenericAgent',
            '--model', 'claude-opus-4-8', '--mounts', json.dumps(mounts),
            '--extra-docker-compose', str(root / 'bundle/isolation.compose.json'),
            '--n-concurrent', '1', '--max-retries', '0', '--yes',
            '--enable-verification', '--agent-timeout-multiplier', '0.25']
        kwargs = dict(llm_no=0, run_id=args.run_id, task_id=args.task,
                      expected_model='claude-opus-4-8',
                      python_home=args.python_home,
                      ga_source_sha256=record['ga_bundle_tree_sha256'],
                      timeout_sec=225, max_turns=2,
                      llm_config_name=args.task_profile,
                      condition_id='pma-neutral')
        for key, value in kwargs.items():
            command += ['--ak', f'{key}={value}']
        env = dict(os.environ)
        for name in ('PMA_MEMORY_API_KEY', 'OPENROUTER_API_KEY', 'ANTHROPIC_API_KEY'):
            env.pop(name, None)
        repo = STAGE.parents[2]
        env['PYTHONPATH'] = os.pathsep.join((str(repo), str(repo / 'GenericAgent-main'),
                                            str(Path(args.bench_root).resolve())))
        env.update(PMA_HARBOR_SPEC=str(spec_path), PYTHONUTF8='1',
                   GA_RUN_ISOLATION='no-network-unix-inference-v1',
                   GA_PMA_UPSTREAM_ENABLED='1', GA_PMA_ENABLED='0',
                   GA_MONITOR_ENABLED='0', GA_M0_MONITOR_ENABLED='0',
                   GA_PMA_UPSTREAM_REQUESTS='/run/pma-bridge/requests',
                   GA_PMA_UPSTREAM_RESPONSES='/run/pma-bridge/responses',
                   GA_PMA_UPSTREAM_DEADLINE_EPOCH=str(deadline))
        _write(root / 'archive/fixture_command.json', {'argv': command,
            'fake_gateway': True, 'fake_memory': True, 'fake_evaluator': True})
        with (root / 'archive/harbor.stdout.log').open('wb') as out, (
                root / 'archive/harbor.stderr.log').open('wb') as err:
            harbor = subprocess.Popen(command, cwd=repo, env=env,
                                      stdout=out, stderr=err)
            while harbor.poll() is None:
                _worker_clearance(root, worker, args.run_id)
                if time.time() >= deadline:
                    raise RuntimeError('fake fixture deadline')
                time.sleep(.1)
    except BaseException as exc:
        failure = {'type': type(exc).__name__, 'message': str(exc)}
    finally:
        if worker is not None and worker.poll() is None:
            try:
                (root / 'host_private/stop.request').touch()
                worker.wait(timeout=10)
            except subprocess.TimeoutExpired:
                worker.kill()
                worker.wait(timeout=5)
        if harbor is not None and harbor.poll() is None:
            harbor.kill()
            harbor.wait(timeout=10)
        worker_out.close()
        worker_err.close()
        try:
            cleanup_errors += clean_owned_containers(root)
            remaining = capture_mounts(root, include_stopped=True)
        except BaseException as exc:
            cleanup_errors.append(f'cleanup_unknown:{type(exc).__name__}:{exc}')
            remaining = None
    status = {'failure': failure, 'harbor_return_code': None if harbor is None else harbor.poll(),
              'worker_return_code': None if worker is None else worker.poll(),
              'agent_start_identity': (root / 'archive/agent_start_identity.json').exists(),
              'frozen_product': (root / 'archive/agent_end_frozen.json').exists(),
              'verification_released': (root / 'archive/verification_released.json').exists(),
              'remaining_containers': None if remaining is None else len(remaining),
              'cleanup_errors': cleanup_errors}
    try:
        authorization.unlink()
        status['fixture_authorization_removed'] = not authorization.exists()
    except BaseException as exc:
        status['fixture_authorization_removed'] = False
        status['cleanup_errors'].append(f'fixture_auth_remove_unknown:{type(exc).__name__}:{exc}')
    _write(root / 'archive/fixture_result.json', status)
    return status


def main():
    parser = argparse.ArgumentParser()
    for name in ('run-id', 'run-root', 'ga-source', 'runtime-root',
                 'task-profile-file', 'worker-python', 'harbor-python', 'bench-root'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--python-home', default='cpython-3.12.12-linux-x86_64-gnu')
    result = run(parser.parse_args())
    print(json.dumps(result, indent=2))
    if (result['failure'] or result['harbor_return_code'] != 0 or
            not result['frozen_product'] or not result['verification_released'] or
            result['remaining_containers'] != 0 or result['cleanup_errors']):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
