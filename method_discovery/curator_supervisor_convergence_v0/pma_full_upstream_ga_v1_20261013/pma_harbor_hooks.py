"""PMA pilot identity overlay on the existing Harbor stop/freeze/evaluate hooks."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import asyncio
import time

from method_discovery.curator_supervisor_convergence_v0.real_task_effect_pilot_preflight_20261010.pilot_harbor_hooks import (
    PilotTrialHooks, _atomic, _tree_sha256,
)
from .six_task_plan import validate_plan


def _source_identity(value: str) -> str:
    return value.replace('\\', '/').lower().replace('/run/desktop/mnt/host/', '').replace(':', '')


def _docker_top_pids(output: str) -> set[str]:
    lines = output.splitlines()
    if not lines:
        raise RuntimeError('docker top returned no process header')
    columns = lines[0].split()
    if 'PID' not in columns:
        raise RuntimeError('docker top PID column unavailable')
    index = columns.index('PID')
    pids = set()
    for row in lines[1:]:
        cells = row.split()
        if len(cells) <= index or not cells[index].isdigit():
            raise RuntimeError('docker top process row malformed')
        pids.add(cells[index])
    return pids


def verify_live_spec(spec: dict) -> None:
    if spec.get('schema') != 'pma-ga-live-run-v1' or spec.get('mode') != 'authorized_live':
        raise RuntimeError('PMA live Harbor spec is not authorized')
    manifest = Path(spec['manifest_path']).resolve(strict=True)
    authorization = Path(spec['authorization_path']).resolve(strict=True)
    if (hashlib.sha256(manifest.read_bytes()).hexdigest() != spec['manifest_sha256'] or
            hashlib.sha256(authorization.read_bytes()).hexdigest() != spec['authorization_sha256']):
        raise RuntimeError('PMA frozen manifest or authorization changed')
    frozen = json.loads(manifest.read_text(encoding='utf-8'))
    granted = json.loads(authorization.read_text(encoding='utf-8'))
    arms = frozen.get('arms')
    bindings = granted.get('run_bindings')
    if frozen.get('schema') == 'pma-ga-live-manifest-v2':
        if granted.get('manifest_sha256') != spec['manifest_sha256']:
            raise RuntimeError('six-task approval does not bind manifest bytes')
        bindings = validate_plan(frozen, granted)
        identity = {key: spec.get(key) for key in
                    ('order', 'task', 'repeat', 'condition', 'run_id',
                     'batch_id', 'config_sha256')}
        matching = [b for b in bindings if all(b.get(k) == v for k, v in identity.items())
                    and Path(b['run_root']).resolve() == Path(spec['run_root']).resolve()]
        if (len(matching) != 1 or spec.get('task_id') != spec.get('task') or
                spec.get('batch_id') != granted['batch_id'] or
                spec.get('config_sha256') != frozen['config_sha256']):
            raise RuntimeError('six-task run outside exact authorized binding')
        checkout = Path(__file__).resolve().parents[3]
        head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=checkout,
                              capture_output=True, text=True, timeout=10,
                              check=True).stdout.strip()
        if head != granted.get('audited_code_commit') or head != spec.get('audited_code_commit'):
            raise RuntimeError('PMA running code differs from authorized commit')
        return
    if (frozen.get('schema') != 'pma-ga-live-manifest-v1' or
            frozen.get('execution_authorized') is not False or
            granted.get('execution_authorized') is not True or
            granted.get('manifest_sha256') != spec['manifest_sha256'] or
            not isinstance(arms, list) or len(arms) != 4 or
            len({(a['task'], a['condition']) for a in arms}) != 4 or
            granted.get('approved_arms') != arms or
            not isinstance(bindings, list) or len(bindings) != 4):
        raise RuntimeError('PMA four-arm authorization or order mismatch')
    expected_order = [(1, 'db-wal-recovery', 'A'), (2, 'db-wal-recovery', 'B'),
                      (3, 'fix-code-vulnerability', 'B'),
                      (4, 'fix-code-vulnerability', 'A')]
    if ([(a.get('order'), a.get('task'), a.get('condition')) for a in arms] !=
            expected_order or
            len({(b.get('order'), b.get('task'), b.get('condition'),
                  b.get('run_id'), b.get('run_root')) for b in bindings}) != 4 or
            [(b.get('order'), b.get('task'), b.get('condition')) for b in bindings] !=
            expected_order):
        raise RuntimeError('PMA arm order or run bindings changed')
    identity = {key: spec[key] for key in ('order', 'task', 'condition', 'run_id')}
    selected = [a for a in arms if a['order'] == spec['order'] and
                a['task'] == spec['task'] and a['condition'] == spec['condition']]
    bound = [b for b in bindings if all(b.get(k) == v for k, v in identity.items()) and
             Path(b.get('run_root', '')).resolve() == Path(spec['run_root']).resolve()]
    if len(selected) != 1 or len(bound) != 1 or spec['task_id'] != spec['task']:
        raise RuntimeError('PMA run is outside its unique authorized slot')
    checkout = Path(__file__).resolve().parents[3]
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=checkout,
                          capture_output=True, text=True, timeout=10, check=True).stdout.strip()
    if head != granted.get('audited_code_commit') or head != spec['audited_code_commit']:
        raise RuntimeError('PMA running code differs from authorized commit')


class PMATrialHooks(PilotTrialHooks):
    def terminal_identity_valid(self, terminal):
        condition = self.spec.get('condition')
        pma_status = {'A': 'not_enabled', 'B': 'saved'}.get(condition)
        return (pma_status is not None and isinstance(terminal, dict) and
                set(terminal) == {'run_id', 'task_id', 'result', 'pma_finalization'} and
                terminal.get('run_id') == self.spec['run_id'] and
                terminal.get('task_id') == self.spec['task_id'] and
                terminal.get('pma_finalization') == {'status': pma_status})

    def legal_terminal(self, metadata, terminal, terminal_identity_valid, incomplete):
        if not terminal_identity_valid:
            return False
        return super().legal_terminal(metadata, terminal, terminal_identity_valid, incomplete)

    async def agent_start(self, _event):
        if getattr(self.trial.agent, 'run_id', None) != self.spec['run_id']:
            raise RuntimeError('PMA agent/run identity mismatch')
        container, raw = await self._inspect()
        mounts = {m['Destination']: m for m in raw.get('Mounts', [])}
        if raw['Image'] != self.spec['image_id'] or raw['HostConfig']['NetworkMode'] != 'none':
            raise RuntimeError('PMA task image or network identity mismatch')
        for destination in ('/opt/genericagent-source', '/opt/m4-runtime'):
            if destination not in mounts or mounts[destination].get('RW'):
                raise RuntimeError('PMA source/runtime mount absent or writable')
        for mount in raw.get('Mounts', []):
            if any(secret in str(mount.get('Source', '')).lower() for secret in (
                    'host_private', 'vendor/pma_', 'assets/evaluator')):
                raise RuntimeError('PMA private source mounted into Task')
        if self.spec['condition'] == 'B':
            for destination, expected_rw, source in (
                    ('/run/pma-bridge/requests', True, 'requests'),
                    ('/run/pma-bridge/responses', False, 'responses')):
                actual = mounts.get(destination)
                expected = Path(self.spec['run_root']) / 'control' / 'spool' / source
                if (actual is None or bool(actual.get('RW')) != expected_rw or
                        _source_identity(str(actual.get('Source'))) !=
                        _source_identity(expected.as_posix())):
                    raise RuntimeError('PMA spool source or permissions differ')
        elif any(path.startswith('/run/pma-bridge') for path in mounts):
            raise RuntimeError('Task-only arm unexpectedly sees PMA spool')
        tests = mounts.get('/tests')
        if tests is not None and tests.get('Type') != 'bind':
            raise RuntimeError('PMA evaluator mount type unexpected')
        check = ('test -z "$(find /tests -mindepth 1 -print -quit)"' if tests is not None
                 else 'test ! -e /tests') + ' && test ! -e /solution'
        result = await self.trial.agent_environment.exec(check, timeout_sec=30, user='root')
        if result.return_code:
            raise RuntimeError('PMA hidden evaluator or solution visible before request')
        self.container_id = container
        _atomic(self.archive / 'agent_start_identity.json', {
            'run_id': self.spec['run_id'], 'container_id': container,
            'image_id': raw['Image'], 'network_mode': raw['HostConfig']['NetworkMode'],
            'mounts': [{k: m.get(k) for k in ('Destination', 'Source', 'RW', 'Type', 'Name')}
                       for m in raw.get('Mounts', [])],
            'hidden_tests_absent': True, 'private_source_absent': True})


class NativeSharedTrialHooks(PMATrialHooks):
    """New-protocol lifecycle only; never stop/restart the Task container."""

    async def agent_start(self, event):
        # Reuse the original PMA mount/public-test checks, with only the
        # network expectation changed for an official-network Task.
        if getattr(self.trial.agent, 'run_id', None) != self.spec['run_id']:
            raise RuntimeError('PMA agent/run identity mismatch')
        container, raw = await self._inspect()
        mounts = {m['Destination']: m for m in raw.get('Mounts', [])}
        if raw['Image'] != self.spec['image_id'] or raw['HostConfig']['NetworkMode'] == 'none':
            raise RuntimeError('native Task image or official network identity mismatch')
        for destination in ('/opt/genericagent-source', '/opt/m4-runtime'):
            if destination not in mounts or mounts[destination].get('RW'):
                raise RuntimeError('native GA source/runtime mount absent or writable')
        for mount in raw.get('Mounts', []):
            source = str(mount.get('Source', '')).lower()
            if any(private in source for private in
                   ('host_private', 'vendor/pma_', 'assets/evaluator', 'bundle/gateway')):
                raise RuntimeError('native Task sees host private source')
        env_names = [value.split('=', 1)[0] for value in raw.get('Config', {}).get('Env', [])]
        if any(name.endswith('_API_KEY') for name in env_names):
            raise RuntimeError('provider credential environment exposed to Task')
        if self.spec['condition'] == 'B':
            for destination, expected_rw, source in (
                    ('/run/pma-bridge/requests', True, 'requests'),
                    ('/run/pma-bridge/responses', False, 'responses')):
                actual = mounts.get(destination)
                expected = Path(self.spec['run_root']) / 'control' / 'spool' / source
                if (actual is None or bool(actual.get('RW')) != expected_rw or
                        _source_identity(str(actual.get('Source'))) !=
                        _source_identity(expected.as_posix())):
                    raise RuntimeError('native PMA spool mount identity differs')
        elif any(path.startswith('/run/pma-bridge') for path in mounts):
            raise RuntimeError('GA-only Task sees PMA spool')
        result = await self.trial.agent_environment.exec(
            'test ! -e /solution && '
            '(test ! -e /tests || test -z "$(find /tests -mindepth 1 -print -quit)") && '
            'test ! -e /var/run/docker.sock', timeout_sec=30, user='root')
        if result.return_code:
            raise RuntimeError('native hidden material or Docker socket visible to Task')
        top = await asyncio.to_thread(subprocess.run, ['docker', 'top', container],
                                      text=True, capture_output=True, timeout=30)
        if top.returncode:
            raise RuntimeError('native baseline process inventory unavailable')
        self.baseline_pids = _docker_top_pids(top.stdout)
        self.container_id = container
        _atomic(self.archive / 'agent_start_identity.json', {
            'run_id': self.spec['run_id'], 'container_id': container,
            'image_id': raw['Image'], 'network_mode': raw['HostConfig']['NetworkMode'],
            'mounts': [{k: m.get(k) for k in ('Destination', 'Source', 'RW', 'Type', 'Name')}
                       for m in raw.get('Mounts', [])],
            'provider_key_env_absent': True, 'hidden_tests_absent': True,
            'baseline_pids': sorted(self.baseline_pids)})

    async def agent_end(self, event):
        _atomic(self.control / 'agent_end_pending.json',
                {'run_id': self.spec['run_id'], 'container_id': self.container_id})
        cleared = self.control / 'sidecar_stopped.json'
        deadline = time.monotonic() + 120
        while not cleared.is_file():
            if time.monotonic() >= deadline:
                raise RuntimeError('native PMA sidecar clearance unavailable')
            await asyncio.sleep(.05)
        clearance = json.loads(cleared.read_text(encoding='utf-8'))
        if clearance != {'run_id': self.spec['run_id'], 'clean': True}:
            raise RuntimeError('native PMA sidecar not stopped')
        if await self._main_id() != self.container_id:
            raise RuntimeError('native main container replaced before verification')
        # Stop the inference gateway but preserve main, its writable layer,
        # task mounts and services for Harbor's normal collection/verifier.
        await self.trial.agent_environment._run_docker_compose_command(
            ['stop', 'model-gateway'])
        top = await asyncio.to_thread(subprocess.run, ['docker', 'top', self.container_id],
                                      text=True, capture_output=True, timeout=30)
        if top.returncode or 'agentmain.py' in top.stdout.lower() or (
                _docker_top_pids(top.stdout) - self.baseline_pids):
            raise RuntimeError('native Task writer termination unconfirmed')
        _atomic(self.archive / 'agent_end_native.json', {
            'run_id': self.spec['run_id'], 'container_id': self.container_id,
            'sidecar_clean': True, 'gateway_stopped': True,
            'writers_stopped': True, 'docker_top': top.stdout,
            'baseline_pids': sorted(self.baseline_pids),
            'agent_result_metadata': str(getattr(self.trial.result, 'agent_result', None)),
            'legal_agent_end_required': False})

    async def verification_start(self, event):
        ended = json.loads((self.archive / 'agent_end_native.json').read_text(encoding='utf-8'))
        if (ended.get('run_id') != self.spec['run_id'] or
                ended.get('container_id') != await self._main_id() or
                not ended.get('sidecar_clean') or not ended.get('writers_stopped')):
            raise RuntimeError('native shared verifier has no stopped Task')
        source = self.trial.task.paths.tests_dir
        if (_tree_sha256(source) != self.spec['native_tests_tree_sha256'] or
                hashlib.sha256((source / 'test.sh').read_bytes()).hexdigest() !=
                self.spec['native_test_sh_sha256']):
            raise RuntimeError('native shared evaluator source changed')
        _atomic(self.archive / 'verification_released.json', {
            'run_id': self.spec['run_id'], 'container_id': self.container_id,
            'source_tree_sha256': self.spec['native_tests_tree_sha256'],
            'native_shared': True, 'upload_still_pending': True})


def install_trial_hooks() -> None:
    from harbor.trial.hooks import TrialEvent
    from harbor.trial.trial import Trial

    path = os.environ.get('PMA_HARBOR_SPEC')
    if not path:
        raise RuntimeError('PMA Harbor spec missing')
    spec = json.loads(Path(path).read_text(encoding='utf-8'))
    verify_live_spec(spec)
    original = Trial.create.__func__

    async def create(cls, config):
        trial = await original(cls, config)
        hooks = (NativeSharedTrialHooks(trial, spec) if
                 spec.get('evaluation_protocol') == 'official_shared_v2' else
                 PMATrialHooks(trial, spec))
        trial.add_hook(TrialEvent.AGENT_START, hooks.agent_start)
        trial.add_hook(TrialEvent.AGENT_END, hooks.agent_end)
        trial.add_hook(TrialEvent.VERIFICATION_START, hooks.verification_start)
        return trial

    Trial.create = classmethod(create)
