"""Research-only Harbor identity and agent/evaluator boundary hooks.

Installed by an explicit subprocess bootstrap, never by sitecustomize or the
default Harbor CLI.  A verifier may run only after the stopped agent product
has been frozen and its evaluator asset identity passes the trusted hook.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time


def _atomic(path: Path, value: dict) -> None:
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True), encoding='utf-8')


def _tree_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise RuntimeError('Pilot evaluator contains redirected source')
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode() + b'\0')
            digest.update(path.read_bytes())
    return digest.hexdigest()


class PilotTrialHooks:
    def __init__(self, trial, spec):
        self.trial = trial
        self.spec = spec
        self.control = Path(spec['control_root']).resolve(strict=True)
        self.archive = Path(spec['archive_root']).resolve(strict=True)
        self.container_id = None
        self.product_sha256 = None

    async def _main_id(self):
        result = await self.trial.agent_environment._run_docker_compose_command(
            ['ps', '-q', 'main'])
        value = result.stdout.strip()
        if not re.fullmatch(r'[0-9a-f]{12,64}', value):
            raise RuntimeError('Pilot main container identity unavailable')
        return value

    async def _inspect(self):
        container = await self._main_id()
        result = await asyncio.to_thread(subprocess.run,
            ['docker', 'inspect', container], text=True, capture_output=True, timeout=30)
        if result.returncode:
            raise RuntimeError('Pilot main Docker inspect failed')
        return container, json.loads(result.stdout)[0]

    async def agent_start(self, _event):
        if getattr(self.trial.agent, 'run_id', None) != self.spec['run_id']:
            raise RuntimeError('Pilot agent/run identity mismatch')
        container, raw = await self._inspect()
        mounts = {m['Destination']: m for m in raw.get('Mounts', [])}
        app = mounts.get('/app')
        if (raw['Image'] != self.spec['image_id'] or
                raw['HostConfig']['NetworkMode'] != 'none' or
                raw['Config'].get('Cmd') != ['sh', '-c', 'sleep infinity'] or
                app is None or app.get('Type') != 'volume' or
                app.get('Name') != self.spec['task_volume'] or not app.get('RW')):
            raise RuntimeError('Pilot Task image, network or RW volume identity mismatch')
        tests = mounts.get('/tests')
        if tests is not None and tests.get('Type') != 'bind':
            raise RuntimeError('Pilot verifier mount has unexpected type')
        for destination in ('/opt/genericagent-source', '/opt/m4-runtime'):
            if destination not in mounts or mounts[destination].get('RW'):
                raise RuntimeError('Pilot source/runtime mount is absent or writable')
        if self.spec['condition'] == 'S':
            rights = {'/logs/agent/monitor_bridge/requests': True,
                      '/logs/agent/monitor_bridge/responses': False,
                      '/logs/agent/monitor_bridge/identity.json': False}
            for destination, writable in rights.items():
                if destination not in mounts or bool(mounts[destination].get('RW')) != writable:
                    raise RuntimeError('Pilot spool mount identity mismatch')
        elif any(path.startswith('/logs/agent/monitor_bridge') for path in mounts):
            raise RuntimeError('Task-only arm unexpectedly mounted Monitor spool')
        public_tests_check = ('test -z "$(find /tests -mindepth 1 -print -quit)" && '
                              if tests is not None else 'test ! -e /tests && ')
        check = await self.trial.agent_environment.exec(
            public_tests_check + 'git -C /app rev-parse HEAD && '
            'git -C /app status --porcelain=v1 --untracked-files=all',
            timeout_sec=40, user='root')
        lines = check.stdout.strip().splitlines()
        if (check.return_code or lines != [self.spec['git_head']]):
            raise RuntimeError('Pilot initial task tree or empty /tests check failed')
        self.container_id = container
        _atomic(self.archive / 'agent_start_identity.json', {
            'container_id': container, 'image_id': raw['Image'],
            'mounts': [{k: m.get(k) for k in ('Destination', 'Type', 'Name', 'RW')}
                       for m in raw.get('Mounts', [])],
            'git_head': lines[0], 'run_id': self.spec['run_id'],
            'task_volume': self.spec['task_volume'], 'condition': self.spec['condition'],
        })

    async def agent_end(self, _event):
        agent_result = getattr(self.trial.result, 'agent_result', None)
        metadata = getattr(agent_result, 'metadata', None) or {}
        legal_agent_end = (metadata.get('round_end_seen') is True and
                           metadata.get('wrapper_return_code') == 0 and
                           metadata.get('archive_status') == 'finished')
        _atomic(self.control / 'agent_end_pending.json',
                {'run_id': self.spec['run_id'], 'container_id': self.container_id})
        deadline = time.monotonic() + 120
        cleared = self.control / 'sidecar_stopped.json'
        while not cleared.is_file():
            if time.monotonic() >= deadline:
                raise RuntimeError('Pilot sidecar cleanup clearance unavailable')
            await asyncio.sleep(.05)
        clearance = json.loads(cleared.read_text(encoding='utf-8'))
        if clearance != {'run_id': self.spec['run_id'], 'clean': True}:
            raise RuntimeError('Pilot sidecar cleanup was not certified')
        before = await self._main_id()
        if before != self.container_id:
            raise RuntimeError('Pilot main container replaced before freeze')
        env = self.trial.agent_environment
        await env._run_docker_compose_command(['stop', 'main'])
        await env._run_docker_compose_command(['start', 'main'])
        after = await self._main_id()
        if after != before:
            raise RuntimeError('Pilot main container changed across stop/start')
        processes = await asyncio.to_thread(subprocess.run,
            ['docker', 'top', after], text=True, capture_output=True, timeout=30)
        if processes.returncode or any(marker in processes.stdout.lower() for marker in
                                       ('agentmain.py', 'monitor_agent', 'python3.12')):
            raise RuntimeError('Pilot Task/Monitor writer termination unconfirmed')
        destination = self.archive / 'pre_evaluation_app.tar'
        if destination.exists():
            raise FileExistsError(destination)
        with destination.open('wb') as output:
            capture = await asyncio.create_subprocess_exec(
                'docker', 'cp', f'{after}:/app/.', '-', stdout=output,
                stderr=asyncio.subprocess.PIPE)
            _, stderr = await capture.communicate()
        if capture.returncode:
            raise RuntimeError('Pilot frozen Task workspace capture failed: ' +
                               stderr.decode(errors='replace')[:200])
        digest = hashlib.sha256()
        with destination.open('rb') as frozen:
            for chunk in iter(lambda: frozen.read(1024 * 1024), b''):
                digest.update(chunk)
        self.product_sha256 = digest.hexdigest()
        _atomic(self.archive / 'agent_end_frozen.json', {
            'run_id': self.spec['run_id'], 'container_id': after,
            'sidecar_clean': True, 'writers_stopped': True,
            'tar_sha256': self.product_sha256, 'tar_bytes': destination.stat().st_size,
            'evaluator_released': False, 'legal_agent_end': legal_agent_end,
            'agent_metadata_public': {key: metadata.get(key) for key in
                ('round_end_seen', 'wrapper_return_code', 'archive_status')},
        })

    async def verification_start(self, _event):
        mode = self.spec.get('mode')
        if mode == 'offline_fake' and self.spec.get('fake_evaluator'):
            expected = self.spec['fake_evaluator_sha256']
            expected_tree = None
        elif mode == 'authorized_live' and self.spec.get('execution_authorized') is True:
            expected = self.spec['native_test_sh_sha256']
            expected_tree = self.spec['native_tests_tree_sha256']
        else:
            raise RuntimeError('Pilot evaluation is not authorized by this hook')
        frozen = json.loads((self.archive / 'agent_end_frozen.json').read_text(encoding='utf-8'))
        if (frozen.get('run_id') != self.spec['run_id'] or
                frozen.get('container_id') != self.container_id or
                frozen.get('tar_sha256') != self.product_sha256 or
                not frozen.get('writers_stopped') or not frozen.get('sidecar_clean') or
                not frozen.get('legal_agent_end')):
            raise RuntimeError('Fake evaluator barrier has no frozen, stopped product')
        script = self.trial.task.paths.tests_dir / 'test.sh'
        if not script.is_file() or hashlib.sha256(script.read_bytes()).hexdigest() != expected:
            raise RuntimeError('Pilot evaluator script identity mismatch')
        if expected_tree is not None and _tree_sha256(script.parent) != expected_tree:
            raise RuntimeError('Pilot native evaluator file tree changed')
        _atomic(self.archive / 'verification_released.json', {
            'run_id': self.spec['run_id'], 'container_id': self.container_id,
            'frozen_product_sha256': self.product_sha256,
            'test_sha256': expected, 'mode': mode, 'sidecar_clean': True,
        })


def install_trial_hooks():
    from harbor.trial.hooks import TrialEvent
    from harbor.trial.trial import Trial

    spec_path = os.environ.get('PILOT_HARBOR_SPEC')
    if not spec_path:
        raise RuntimeError('Pilot Harbor specification is missing')
    spec = json.loads(Path(spec_path).read_text(encoding='utf-8'))
    if spec.get('mode') not in {'offline_fake', 'authorized_live'}:
        raise RuntimeError('Pilot Harbor execution mode is not certified')
    if spec['mode'] == 'authorized_live':
        authorization = Path(spec.get('authorization_path') or '')
        if (spec.get('execution_authorized') is not True or
                not authorization.is_file() or
                hashlib.sha256(authorization.read_bytes()).hexdigest() !=
                    spec.get('authorization_sha256')):
            raise RuntimeError('Pilot live execution authorization is absent or changed')
        granted = json.loads(authorization.read_text(encoding='utf-8'))
        if (granted.get('execution_authorized') is not True or
                granted.get('manifest_sha256') != spec.get('manifest_sha256') or
                {'task_id': spec['task_id'], 'condition': spec['condition']} not in
                    granted.get('approved_arms', [])):
            raise RuntimeError('Pilot live arm is outside the exact authorization')
    original = Trial.create.__func__

    async def create(cls, config):
        trial = await original(cls, config)
        hooks = PilotTrialHooks(trial, spec)
        trial.add_hook(TrialEvent.AGENT_START, hooks.agent_start)
        trial.add_hook(TrialEvent.AGENT_END, hooks.agent_end)
        trial.add_hook(TrialEvent.VERIFICATION_START, hooks.verification_start)
        return trial

    Trial.create = classmethod(create)
