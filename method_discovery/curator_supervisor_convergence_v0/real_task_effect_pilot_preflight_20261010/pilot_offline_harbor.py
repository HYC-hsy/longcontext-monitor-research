"""One-arm, no-network Harbor fixture using the actual pilot entry and hooks.

This module is deliberately unable to use a live inference gateway.  It
replaces the gateway container with a local deterministic Unix-socket server
before Harbor starts and refuses an authorized-live specification.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time

from .pilot_analysis_bridge import PilotDockerToolPort, PilotHostBridge
from .pilot_entry import TASKS, prepare_run, require_live_authorization
from long_context_bench.scripts.isolated_run_bundle import digest_tree


def _offline_gateway(run_root: Path, runtime_root: Path, python_home: str) -> None:
    compose_path = run_root / 'bundle' / 'isolation.compose.json'
    compose = json.loads(compose_path.read_text(encoding='utf-8'))
    source = Path(__file__).with_name('pilot_fake_gateway.py').resolve(strict=True)
    captures = run_root / 'archive' / 'fake_provider_requests'
    captures.mkdir()
    service = compose['services']['model-gateway']
    service['network_mode'] = 'none'
    service['volumes'] = [
        f'{runtime_root.resolve(strict=True).as_posix()}:/opt/m4-runtime:ro',
        f'{source.as_posix()}:/fake_gateway.py:ro',
        f'{captures.resolve().as_posix()}:/fake_capture',
        'model-channel:/run/model-channel',
    ]
    python = f'/opt/m4-runtime/python/{python_home}/bin/python3.12'
    service['entrypoint'] = [python, '/fake_gateway.py']
    service['environment'] = {}
    service['healthcheck']['test'] = ['CMD', python, '-c',
        "import socket; s=socket.socket(socket.AF_UNIX); "
        "s.connect('/run/model-channel/gateway.sock'); s.close()"]
    compose_path.write_text(json.dumps(compose, indent=2), encoding='utf-8')
    # The private live gateway config remains host-side; it is not mounted by
    # this fixture, and no container in this compose can reach the network.
    assert all(value['network_mode'] == 'none' for value in compose['services'].values())


def _serve_spool(root: Path, image: str, volume: str, run_id: str,
                 stopped: threading.Event, errors: list[str]) -> None:
    control = root / 'control'
    bridge = None
    try:
        while not stopped.is_set():
            private = root / 'monitor' / 'monitor_private'
            evidence = root / 'monitor' / 'task_evidence'
            identity = root / 'monitor' / 'task_identity.json'
            if bridge is None and private.is_dir() and evidence.is_dir() and identity.is_file():
                port = PilotDockerToolPort(image=image, task_volume=volume,
                    trusted_root=root / 'trusted', cognition_root=private,
                    scratch_root=root / 'scratch', evidence_root=evidence)
                bridge = PilotHostBridge(root=control / 'spool', run_id=run_id,
                                         port=port, adopt_existing=True)
            if bridge is not None:
                bridge.serve_once()
            if (control / 'agent_end_pending.json').exists():
                if bridge is not None:
                    bridge.close()
                clearance = control / 'sidecar_stopped.json'
                clearance.write_text(json.dumps({'run_id': run_id, 'clean': True}), encoding='utf-8')
                return
            time.sleep(.05)
    except BaseException as exc:
        errors.append(f'{type(exc).__name__}: {exc}')
        stopped.set()
    finally:
        if bridge is not None and not bridge.closed:
            try:
                bridge.close()
            except BaseException as exc:
                errors.append(f'cleanup: {type(exc).__name__}: {exc}')


def _cleanup_offline_containers(run_root: Path) -> list[str]:
    """Remove only containers whose Compose config cites this exact fixture."""
    listed = subprocess.run(['docker', 'ps', '-aq'], capture_output=True,
                            text=True, timeout=30, check=True)
    matches = []
    for container in listed.stdout.splitlines():
        inspected = subprocess.run(['docker', 'inspect', container], capture_output=True,
                                   text=True, timeout=30, check=True)
        record = json.loads(inspected.stdout)[0]
        files = record.get('Config', {}).get('Labels', {}).get(
            'com.docker.compose.project.config_files', '')
        if str((run_root / 'bundle' / 'isolation.compose.json').resolve()) in files:
            matches.append(container)
    for container in matches:
        subprocess.run(['docker', 'rm', '-f', container], capture_output=True,
                       text=True, timeout=30, check=True)
        absent = subprocess.run(['docker', 'inspect', container], capture_output=True,
                                text=True, timeout=30)
        if absent.returncode == 0 or 'no such object' not in absent.stderr.lower():
            raise RuntimeError('Offline fixture container cleanup unconfirmed')
    return matches


def _fake_evaluator_sentinel(root: Path, run_id: str) -> dict:
    """Assert ordering only; never open /tests or compute a task score."""
    archive = root / 'archive'
    freeze = json.loads((archive / 'agent_end_frozen.json').read_text(encoding='utf-8'))
    clearance = json.loads((root / 'control' / 'sidecar_stopped.json').read_text(encoding='utf-8'))
    if (freeze.get('run_id') != run_id or not freeze.get('writers_stopped') or
            not freeze.get('sidecar_clean') or
            freeze.get('legal_agent_end') is not True or
            clearance != {'run_id': run_id, 'clean': True}):
        raise RuntimeError('Fake evaluator barrier lacks clean agent termination')
    remaining = _cleanup_offline_containers(root)
    if remaining:
        raise RuntimeError('Fake evaluator barrier found executable containers')
    tar = archive / 'pre_evaluation_app.tar'
    digest = hashlib.sha256()
    with tar.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    if digest.hexdigest() != freeze['tar_sha256']:
        raise RuntimeError('Fake evaluator barrier product changed')
    sentinel = {'run_id': run_id, 'fake_evaluator_only': True,
                'native_evaluator_calls': 0, 'frozen_product_sha256': digest.hexdigest(),
                'agent_and_sidecar_stopped': True}
    (archive / 'fake_evaluator_sentinel.json').write_text(
        json.dumps(sentinel, indent=2), encoding='utf-8')
    return sentinel


def _stage_native_tests(manifest: Path, task_id: str, source_root: Path,
                        run_root: Path) -> tuple[str, str]:
    short = TASKS[task_id][0]
    original = Path(source_root).resolve(strict=True) / short / 'tests'
    expected = json.loads(Path(manifest).read_text(encoding='utf-8'))['task_assets'][task_id]
    if not original.is_dir() or any(path.is_symlink() for path in original.rglob('*')):
        raise RuntimeError('Native evaluator source is absent or redirected')
    source_tree = digest_tree(original)
    script_sha = hashlib.sha256((original / 'test.sh').read_bytes()).hexdigest()
    if (source_tree != expected['native_tests_tree_sha256'] or
            script_sha != expected['native_test_sh_sha256']):
        raise RuntimeError('Native evaluator identity differs from frozen manifest')
    target = run_root / 'public_agent_task' / 'tests'
    if list(target.iterdir()):
        raise RuntimeError('Agent-phase verifier staging directory is not empty')
    shutil.copytree(original, target, dirs_exist_ok=True)
    if digest_tree(target) != source_tree:
        raise RuntimeError('Staged native evaluator changed')
    return source_tree, script_sha


def run_offline(*, manifest: Path, task_id: str, condition: str, run_id: str,
                run_root: Path, source_root: Path, ga_source: Path,
                runtime_root: Path, task_profile_file: Path,
                monitor_profile_file: Path, python_home: str,
                harbor_python: Path, timeout_seconds: int = 360,
                verify_sentinel: bool = False,
                execution_mode: str = 'offline_fake', authorization: Path | None = None) -> dict:
    if condition not in {'T', 'S'} or task_id not in TASKS:
        raise ValueError('Unsupported offline task or condition')
    if execution_mode not in {'offline_fake', 'authorized_live'}:
        raise ValueError('Unsupported pilot execution mode')
    if execution_mode == 'authorized_live':
        if authorization is None or verify_sentinel:
            raise RuntimeError('Live pilot requires exact authorization and cannot use fake evaluation')
        require_live_authorization(manifest, authorization,
            {'task_id': task_id, 'condition': condition})
    prepared = prepare_run(manifest=manifest, task_id=task_id,
        condition=condition, run_id=run_id, run_root=run_root,
        source_root=source_root, ga_source=ga_source,
        runtime_root=runtime_root, task_profile_file=task_profile_file,
        monitor_profile_file=monitor_profile_file, python_home=python_home)
    if execution_mode == 'offline_fake':
        _offline_gateway(run_root, runtime_root, python_home)
    control = run_root / 'control'
    spec_file = control / 'harbor_spec.json'
    spec = json.loads(spec_file.read_text(encoding='utf-8'))
    if spec['mode'] != 'unarmed' or spec['execution_authorized'] is not False:
        raise RuntimeError('Offline Harbor fixture requires an unarmed preparation')
    spec['mode'] = execution_mode
    if execution_mode == 'authorized_live':
        tests_tree, test_script = _stage_native_tests(manifest, task_id, source_root, run_root)
        spec.update(execution_authorized=True, native_tests_tree_sha256=tests_tree,
                    native_test_sh_sha256=test_script,
                    authorization_path=str(Path(authorization).resolve(strict=True)),
                    authorization_sha256=hashlib.sha256(Path(authorization).read_bytes()).hexdigest(),
                    manifest_sha256=hashlib.sha256(Path(manifest).read_bytes()).hexdigest())
    elif verify_sentinel:
        fake_test = (run_root / 'public_agent_task' / 'tests' / 'test.sh')
        if list(fake_test.parent.iterdir()):
            raise RuntimeError('Public task test directory was not empty before fake staging')
        fake_test.write_bytes(b'#!/bin/sh\nmkdir -p /logs/verifier\n'
                              b'printf 0 > /logs/verifier/reward.txt\n'
                              b'printf "{\\"offline_fake_sentinel\\":1}" > /logs/verifier/reward.json\n')
        spec['fake_evaluator'] = True
        spec['fake_evaluator_sha256'] = hashlib.sha256(fake_test.read_bytes()).hexdigest()
    spec_file.write_text(json.dumps(spec, indent=2), encoding='utf-8')
    runtime = Path(runtime_root).resolve(strict=True)
    source = run_root / 'bundle' / 'source'
    compose = run_root / 'bundle' / 'isolation.compose.json'
    mounts = [
        {'type': 'bind', 'source': str(runtime), 'target': '/opt/m4-runtime', 'read_only': True},
        {'type': 'bind', 'source': str(source.resolve()), 'target': '/opt/genericagent-source', 'read_only': True},
    ]
    command = [str(Path(harbor_python).resolve(strict=True)), '-m',
        'method_discovery.curator_supervisor_convergence_v0.'
        'real_task_effect_pilot_preflight_20261010.pilot_harbor_cli',
        'jobs', 'start', '--job-name', run_id, '--jobs-dir', str((run_root / 'jobs').resolve()),
        '--path', str((run_root / 'public_agent_task').resolve()),
        '--agent', 'adapters.harbor_ga_agent:HarborGenericAgent',
        '--model', 'claude-opus-4-8', '--mounts', json.dumps(mounts),
        '--extra-docker-compose', str(compose.resolve()),
        '--n-concurrent', '1', '--max-retries', '0', '--yes', '--delete',
        '--enable-verification' if (verify_sentinel or execution_mode == 'authorized_live')
        else '--disable-verification',
    ]
    if execution_mode == 'authorized_live':
        frozen = json.loads(Path(manifest).read_text(encoding='utf-8'))
        task_asset = frozen['task_assets'][task_id]
        base_timeout = task_asset['agent_timeout_in_task_toml_seconds']
        if timeout_seconds != 10000 or base_timeout != 7200:
            raise RuntimeError('Live agent-phase ceiling differs from approved draft')
        command += ['--agent-timeout-multiplier', format(timeout_seconds / base_timeout, '.15g')]
        launcher_timeout = timeout_seconds + task_asset['verifier_timeout_in_task_toml_seconds'] + 600
    else:
        launcher_timeout = timeout_seconds
    kwargs = {
        'llm_no': 0, 'run_id': run_id, 'expected_model': 'claude-opus-4-8',
        'python_home': python_home, 'ga_source_sha256': prepared['bundle_source_sha256'],
        'task_id': task_id, 'timeout_sec': timeout_seconds,
        'baseline_condition': 'original', 'condition_id': 'pilot-neutral',
        'llm_config_name': 'native_claude_cc_vibe_opus48', 'max_turns': 300,
        'monitor_enabled': condition == 'S',
        'monitor_config': 'claude_monitor_opus48' if condition == 'S' else '',
    }
    for key, value in kwargs.items():
        command += ['--ak', f'{key}={value}']
    env = dict(os.environ)
    repo = Path(__file__).resolve().parents[3]
    env['PYTHONPATH'] = os.pathsep.join((str(repo), str(repo / 'GenericAgent-main'),
                                        str(repo / 'long_context_bench')))
    env['PILOT_HARBOR_SPEC'] = str(spec_file.resolve())
    env['PYTHONUTF8'] = '1'
    env['PYTHONIOENCODING'] = 'utf-8'
    env['NO_COLOR'] = '1'
    env['CI'] = '1'
    env['GA_RUN_ISOLATION'] = 'no-network-unix-inference-v1'
    env['GA_PILOT_MODE'] = '1' if condition == 'S' else '0'
    env['GA_MONITOR_MAX_REVIEW_TURNS'] = '20'
    env['GA_MONITOR_ROOT_MAX_REVIEW_TURNS'] = '300'
    env['GA_MONITOR_ROOT_CAPTURE_REQUIRED'] = '1' if condition == 'S' else '0'
    env['GA_MONITOR_ENABLED'] = '1' if condition == 'S' else '0'
    env['GA_MONITOR_CONFIG'] = 'claude_monitor_opus48' if condition == 'S' else ''
    env['GA_LHTB_DISABLE_CONTINUE_UNTIL_TIMEOUT'] = '0'
    if condition == 'S':
        env['GA_MONITOR_RUN_DEADLINE_EPOCH'] = str(int(time.time()) + timeout_seconds)
    archive = run_root / 'archive'
    (archive / 'pilot_command_public.json').write_text(json.dumps({
        'argv': command, 'environment_public': {key: env[key] for key in (
            'GA_RUN_ISOLATION', 'GA_PILOT_MODE', 'GA_MONITOR_ENABLED',
            'GA_MONITOR_MAX_REVIEW_TURNS', 'GA_MONITOR_ROOT_MAX_REVIEW_TURNS')},
        'gateway_mode': execution_mode,
        'native_evaluator_enabled': execution_mode == 'authorized_live',
        'agent_phase_ceiling_seconds': timeout_seconds,
        'launcher_timeout_seconds': launcher_timeout,
    }, indent=2), encoding='utf-8')
    stop = threading.Event()
    errors: list[str] = []
    worker = None
    if condition == 'S':
        worker = threading.Thread(target=_serve_spool,
            args=(run_root, TASKS[task_id][1], prepared['task_volume'],
                  run_id, stop, errors), daemon=True)
        worker.start()
    else:
        # The trusted host, not Harbor, certifies the absence of a diagnostic
        # sidecar at agent-end.  This marker is consumed only after AGENT_END.
        (control / 'sidecar_stopped.json').write_text(
            json.dumps({'run_id': run_id, 'clean': True}), encoding='utf-8')
    with (archive / 'harbor_stdout.log').open('wb') as stdout, \
         (archive / 'harbor_stderr.log').open('wb') as stderr:
        try:
            proc = subprocess.run(command, env=env, cwd=repo, stdout=stdout,
                                  stderr=stderr, timeout=launcher_timeout)
            result = {'returncode': proc.returncode, 'timed_out': False}
        except subprocess.TimeoutExpired:
            result = {'returncode': None, 'timed_out': True}
        finally:
            stop.set()
            if worker is not None:
                worker.join(timeout=30)
                if worker.is_alive():
                    errors.append('cleanup_unknown: analysis spool worker remained alive')
    result['offline_containers_removed'] = _cleanup_offline_containers(run_root)
    result['spool_errors'] = errors
    result['fake_provider_requests'] = (len(list((archive / 'fake_provider_requests').glob('*.json')))
                                        if execution_mode == 'offline_fake' else None)
    result['frozen_product'] = (archive / 'agent_end_frozen.json').exists()
    result['harbor_verifier_released'] = (archive / 'verification_released.json').exists()
    if (execution_mode == 'offline_fake' and result['returncode'] == 0 and not result['timed_out'] and
            result['frozen_product'] and not errors):
        result['fake_evaluator'] = _fake_evaluator_sentinel(run_root, run_id)
    else:
        result['fake_evaluator'] = None
    (archive / 'pilot_result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser()
    for name in ('manifest', 'task-id', 'condition', 'run-id', 'run-root', 'source-root',
                 'ga-source', 'runtime-root', 'task-profile-file',
                 'monitor-profile-file', 'python-home', 'harbor-python'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--timeout-seconds', type=int, default=360)
    parser.add_argument('--verify-sentinel', action='store_true')
    args = vars(parser.parse_args())
    for name in ('manifest', 'run_root', 'source_root', 'ga_source', 'runtime_root',
                 'task_profile_file', 'monitor_profile_file', 'harbor_python'):
        args[name] = Path(args[name])
    print(json.dumps(run_offline(**args), indent=2))


if __name__ == '__main__':
    main()
