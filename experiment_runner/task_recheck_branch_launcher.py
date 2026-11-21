"""Run one isolated four-turn financial Task branch from a frozen checkpoint.

The original full Task and native verifier are never invoked here. This
launcher has no retry loop. Private gateway configuration is mounted only into
the gateway container; it is never copied into the Task clone or printed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time
import uuid


def _docker(*args: str, timeout: float | None = 60, check: bool = True) -> str:
    result = subprocess.run(['docker', *args], capture_output=True, text=True,
                            encoding='utf-8', errors='replace', timeout=timeout)
    if check and result.returncode:
        raise RuntimeError(f'docker {args[0]} failed ({result.returncode}): '
                           f'{result.stderr[:500]}')
    return result.stdout.strip()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _mount_bind(source: Path, target: str, readonly: bool) -> str:
    return (f'type=bind,src={source.resolve(strict=True).as_posix()},dst={target}'
            + (',readonly' if readonly else ''))


def _validate(run_root: Path, capture: Path):
    run_root = run_root.resolve(strict=True)
    capture = capture.resolve(strict=True)
    if capture in run_root.parents or run_root in capture.parents:
        raise ValueError('private checkpoint must be outside the original run')
    record = json.loads((capture / 'capture.json').read_text(encoding='utf-8'))
    if record.get('status') != 'captured':
        raise RuntimeError('checkpoint image was not captured completely')
    if record.get('run_id') != run_root.name:
        raise RuntimeError('checkpoint run identity mismatch')
    actor = int(record['actor_attempt'])
    found = list(run_root.rglob(f'task_recheck_before_actor_{actor:04d}.json'))
    if len(found) != 1:
        raise RuntimeError('pre-request native Task state missing or ambiguous')
    from sys import path as sys_path
    source = run_root / 'bundle/source'
    if not source.is_dir() or not (source / 'task_recheck_branch_entry.py').is_file():
        raise RuntimeError('fixed Task continuation code not staged in original run')
    sys_path.insert(0, str(source))
    try:
        from task_recheck_branch import load_frozen
        state = load_frozen(found[0])
    finally:
        sys_path.pop(0)
    if state['run_id'] != record['run_id'] or state['actor_attempt'] != actor:
        raise RuntimeError('Task state and Docker checkpoint do not align')
    bank = capture / 'knowledge.json'
    if _sha(bank) != record['knowledge_sha256']:
        raise RuntimeError('frozen knowledge bank hash mismatch')
    image = json.loads(_docker('image', 'inspect', record['snapshot_image_id']))[0]
    if image['Id'] != record['snapshot_image_id']:
        raise RuntimeError('checkpoint image identity mismatch')
    compose = json.loads((run_root / 'bundle/isolation.compose.json').read_text(encoding='utf-8'))
    gateway = compose['services']['model-gateway']
    gateway_dir = run_root / 'bundle/gateway'
    if not (gateway_dir / 'config.json').is_file() or not (gateway_dir / 'transport.py').is_file():
        raise RuntimeError('original private gateway bundle unavailable')
    runtime = [m for m in record['original_mounts']
               if m['Destination'] in ('/opt/m2-runtime', '/opt/m4-runtime')]
    if len(runtime) != 1 or runtime[0]['Type'] != 'bind' or runtime[0]['RW']:
        raise RuntimeError('original Task runtime mount identity unavailable')
    runtime_source = Path(runtime[0]['Source']).resolve(strict=True)
    runtime_target = runtime[0]['Destination']
    entrypoint = gateway.get('entrypoint')
    if not isinstance(entrypoint, list) or not entrypoint:
        raise RuntimeError('gateway entrypoint unavailable')
    if not gateway.get('image'):
        raise RuntimeError('gateway image identity unavailable')
    policy = record.get('original_network_policy') or {}
    if record.get('original_network_mode') not in ('none', 'bridge'):
        if policy.get('Driver') != 'bridge':
            raise RuntimeError('original Task network policy is not reproducible as bridge')
    if state.get('task_environment', {}).get('GA_TASK_DEADLINE_EPOCH') != 'uncapped':
        raise RuntimeError('Task checkpoint does not establish uncapped task deadline')
    return (record, found[0], bank, gateway_dir, gateway,
            runtime_source, runtime_target, state['task_environment'])


def run_one(run_root: Path, capture: Path, output_root: Path,
            arm: str, replicate: int, *, dry_run: bool = False) -> dict:
    if arm not in ('none', 'fixed', 'targeted') or replicate not in (1, 2):
        raise ValueError('branch arm or replicate outside frozen six-branch design')
    record, state_path, bank, gateway_dir, gateway, runtime, runtime_target, task_env = _validate(
        run_root, capture)
    output_root = output_root.resolve()
    run_root = run_root.resolve(strict=True)
    if output_root == run_root or run_root in output_root.parents:
        raise ValueError('branch output must not touch original run')
    label = f'{arm}-{replicate}'
    output = output_root / label
    if output.exists():
        raise FileExistsError('branch output already exists; no automatic rerun')
    plan = {'parent_run_id': record['run_id'], 'label': label,
            'checkpoint_actor_attempt': record['actor_attempt'],
            'snapshot_image_id': record['snapshot_image_id'],
            'state_sha256': _sha(state_path), 'bank_sha256': _sha(bank),
            'gateway_image': gateway['image'], 'gateway_config_sha256':
                _sha(gateway_dir / 'config.json'), 'runtime_destination': runtime_target,
            'original_network_policy': record.get('original_network_policy'),
            'max_task_turns': 4, 'native_verifier': 'not_run'}
    if dry_run:
        return {'status': 'validated_no_model', **plan}
    output.mkdir(parents=True, exist_ok=False)
    agent_log = output / 'agent'
    agent_log.mkdir()
    private = output / 'private'
    private.mkdir()
    shutil.copy2(state_path, private / 'state.json')
    knowledge = private / 'responses/knowledge'
    knowledge.mkdir(parents=True)
    shutil.copy2(bank, knowledge / 'memory.json')
    (output / 'plan.json').write_text(json.dumps(plan, indent=2), encoding='utf-8')
    token = uuid.uuid4().hex[:12]
    volume = f'lc-recheck-channel-{token}'
    network = f'lc-recheck-network-{token}'
    gateway_name = f'lc-recheck-gateway-{token}'
    task_name = f'lc-recheck-task-{token}'
    volume_created = False
    network_created = False
    gateway_created = False
    task_created = False
    try:
        _docker('volume', 'create', volume)
        volume_created = True
        network_args = ['network', 'create', '--driver', 'bridge']
        if (record.get('original_network_policy') or {}).get('Internal'):
            network_args.append('--internal')
        _docker(*network_args, network)
        network_created = True
        runtime_mount = _mount_bind(runtime, runtime_target, True)
        _docker('run', '-d', '--name', gateway_name, '--network', 'bridge',
                '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
                '--read-only', '--tmpfs', '/tmp:rw,nosuid,nodev',
                '--mount', runtime_mount,
                '--mount', _mount_bind(gateway_dir, '/gateway', True),
                '--mount', f'type=volume,src={volume},dst=/run/model-channel',
                '--entrypoint', gateway['entrypoint'][0], gateway['image'],
                *gateway['entrypoint'][1:])
        gateway_created = True
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                _docker('exec', gateway_name, gateway['entrypoint'][0], '-c',
                        "import socket;s=socket.socket(socket.AF_UNIX);"
                        "s.connect('/run/model-channel/gateway.sock');s.close()",
                        timeout=5)
                break
            except RuntimeError:
                pass
            time.sleep(.5)
        else:
            raise RuntimeError('branch model gateway not ready')
        forwarded = []
        for key in ('GA_LLM_CONFIG_NAME', 'GA_LANG', 'GA_TASK_COMPLETE_RESPONSE',
                    'GA_PROVIDER_MAX_RETRIES', 'GA_RUN_ISOLATION'):
            if task_env.get(key) is not None:
                forwarded.extend(['--env', f'{key}={task_env[key]}'])
        _docker('run', '-d', '--name', task_name, '--network', network,
                '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
                '--workdir', '/app',
                '--env', 'GA_PMA_UPSTREAM_ENABLED=0',
                '--env', 'GA_PMA_ENABLED=0', '--env', 'GA_MONITOR_ENABLED=0',
                '--env', 'GA_STATEFUL_MEMORY_ENABLED=0', '--env', 'GA_POS_ENABLED=0',
                '--env', 'GA_TASK_RECHECK_CAPTURE=0',
                '--env', 'GA_EXPERIMENT_RUNTIME_POLICY=v1',
                '--env', 'GA_EXPERIMENT_TASK_TURNS=4',
                '--env', 'GA_TASK_DEADLINE_EPOCH=uncapped',
                '--env', f'GA_BENCH_RUN_ID={task_name}',
                '--env', 'PYTHONPATH=/opt/genericagent:/opt/m4-runtime/ga-env/lib/python3.12/site-packages',
                *forwarded,
                '--mount', runtime_mount,
                '--mount', f'type=volume,src={volume},dst=/run/model-channel,readonly',
                '--mount', _mount_bind(private / 'responses',
                                       '/run/pma-bridge/responses', True),
                '--mount', _mount_bind(agent_log, '/logs/agent', False),
                '--entrypoint', 'sleep', record['snapshot_image_id'], 'infinity')
        task_created = True
        _docker('cp', str(private / 'state.json'),
                task_name + ':/tmp/task_recheck_state.json')
        # The original local HTTP-to-Unix relay was a process, not image data.
        _docker('exec', '-d', task_name, gateway['entrypoint'][0],
                '/opt/genericagent/isolated_transport.py', 'local')
        local_deadline = time.monotonic() + 15
        while time.monotonic() < local_deadline:
            try:
                _docker('exec', task_name, gateway['entrypoint'][0], '-c',
                        "import socket;s=socket.create_connection(('127.0.0.1',18765),1);s.close()",
                        timeout=5)
                break
            except RuntimeError:
                time.sleep(.25)
        else:
            raise RuntimeError('Task local inference relay not ready')
        _docker('exec', task_name, 'test', '-f',
                '/opt/genericagent/task_recheck_branch_entry.py')
        command = [gateway['entrypoint'][0],
                   '/opt/genericagent/task_recheck_branch_entry.py',
                   '--packet', '/tmp/task_recheck_state.json', '--arm', arm,
                   '--output', '/logs/agent/branch_result.json', '--remove-packet']
        task_output = _docker('exec', task_name, *command, timeout=None)
        result_file = agent_log / 'branch_result.json'
        if not result_file.is_file():
            raise RuntimeError('branch ended without a bound result record')
        result = json.loads(result_file.read_text(encoding='utf-8'))
        result['branch_output_sha256'] = _sha(result_file)
        return {'status': 'completed', **plan, 'result': result,
                'docker_stdout': task_output[-1000:]}
    finally:
        cleanup = []
        def clear(resource, args):
            try:
                result = subprocess.run(['docker', *args], capture_output=True,
                                        timeout=60)
                removed = result.returncode == 0
            except (OSError, subprocess.TimeoutExpired):
                removed = False
            cleanup.append({'resource': resource, 'removed': removed})
        if task_created:
            clear('task_container', ['rm', '-f', task_name])
        if gateway_created:
            clear('gateway_container', ['rm', '-f', gateway_name])
        if volume_created:
            clear('model_channel_volume', ['volume', 'rm', '-f', volume])
        if network_created:
            clear('task_network', ['network', 'rm', network])
        (output / 'cleanup.json').write_text(json.dumps(cleanup, indent=2),
                                             encoding='utf-8')
        if any(not row['removed'] for row in cleanup):
            raise RuntimeError('branch resource cleanup incomplete; stop the queue')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-root', type=Path, required=True)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--arm', required=True)
    parser.add_argument('--replicate', type=int, required=True)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    print(json.dumps(run_one(args.run_root, args.capture, args.output_root,
                             args.arm, args.replicate, dry_run=args.dry_run),
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
