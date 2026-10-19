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
from .control_processes import (scan as scan_control_processes,
                                probe_registered, stop_registered)


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


def pos_archive_summary(run_id: str, task_id: str, terminal: dict | None,
                        result_receipt: dict, close_receipt: dict,
              terminal_error_category: str | None = None,
              provider_capture: dict | None = None) -> dict:
    """Summarize bound receipts without conflating Task completion and archive health."""
    known = terminal is not None
    finalization = terminal.get('pos_finalization') if known else None
    finalization = finalization if isinstance(finalization, dict) else {}
    errors = terminal.get('pos_auxiliary_errors') if known else None
    errors = ([{'kind': item.get('kind'), 'error_type': item.get('error_type')}
               for item in errors if isinstance(item, dict)]
              if isinstance(errors, list) else [])
    return {
        'run_id': run_id, 'task_id': task_id,
        'result_status': result_receipt.get('status'),
        'result_bound': (result_receipt.get('run_id') == run_id and
                         result_receipt.get('task_id') == task_id),
        'close_status': close_receipt.get('status'),
        'close_bound': (close_receipt.get('run_id') == run_id and
                        close_receipt.get('task_id') == task_id),
        'worker_return_code': close_receipt.get('worker_return_code'),
        'task_terminal_status': ('partial' if terminal_error_category == 'missing_fields'
                                 else 'available' if known else 'unavailable'),
        'task_terminal_error_category': terminal_error_category,
        'task_result': (terminal.get('result') if isinstance(terminal.get('result'), str)
                        else None) if known else None,
        'task_archive_incomplete': (terminal.get('pos_archive_incomplete') if
                                    type(terminal.get('pos_archive_incomplete')) is bool
                                    else None) if known else None,
        'auxiliary_errors': errors,
        'provider_capture': provider_capture,
        'archive_incomplete': (not known or terminal_error_category is not None or
            terminal.get('pos_archive_incomplete') is True or
            finalization.get('archive_incomplete') is True or
                  result_receipt.get('status') in {'missing', 'missing_or_unknown', None} or
                  (provider_capture is not None and
                   provider_capture.get('capture_complete') is not True)),
    }


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
    if frozen.get('schema') == 'pos-ga-single-manifest-v1':
        if granted.get('manifest_sha256') != spec['manifest_sha256']:
            raise RuntimeError('PoS authorization does not bind manifest bytes')
        binding = validate_plan(frozen, granted)[0]
        for key in ('order', 'task', 'repeat', 'condition', 'run_id',
                    'batch_id', 'config_sha256', 'research_candidate'):
            if spec.get(key) != binding.get(key):
                raise RuntimeError('PoS run outside exact authorized binding: ' + key)
        if (spec.get('task_id') != binding['task'] or
                Path(spec['run_root']).resolve() != Path(binding['run_root']).resolve() or
                spec.get('condition') != 'P' or
                spec.get('research_candidate') not in {'PoS', 'PoS-citation-fixed',
                    'pos_pma_complement_v1'} or
                (frozen.get('zero_model_fixture_only') is True) !=
                (granted.get('zero_model_fixture_only') is True)):
            raise RuntimeError('PoS method, root or fixture binding differs')
        checkout = Path(__file__).resolve().parents[3]
        head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=checkout,
            capture_output=True, text=True, timeout=10, check=True).stdout.strip()
        if head != granted.get('audited_code_commit') or head != spec.get('audited_code_commit'):
            raise RuntimeError('PoS running code differs from authorized commit')
        if frozen.get('zero_model_fixture_only') is not True and 'pos_binding_sha256' in spec:
            binding = Path(spec['run_root']) / 'control/pos_archive/binding.json'
            if (hashlib.sha256(binding.read_bytes()).hexdigest() !=
                    spec['pos_binding_sha256'] or
                    json.loads(binding.read_text(encoding='utf-8')).get(
                        'authorization_sha256') != spec['authorization_sha256']):
                raise RuntimeError('PoS profile binding differs from authorization')
        return
    arms = frozen.get('arms')
    bindings = granted.get('run_bindings')
    if frozen.get('schema') in {'pma-ga-live-manifest-v2',
                                'pma-ga-live-manifest-v3',
                                'pma-ga-live-manifest-v4',
                                'pma-ga-live-manifest-v5'}:
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
                spec.get('config_sha256') != frozen['config_sha256'] or
                spec.get('research_candidate', 'U') !=
                matching[0].get('research_candidate', 'U')):
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
        if condition == 'P':
            return (isinstance(terminal, dict) and
                set(terminal) == {'run_id', 'task_id', 'result',
                                  'pma_finalization', 'pos_finalization',
                                  'pos_archive_incomplete', 'pos_auxiliary_errors'} and
                terminal.get('run_id') == self.spec['run_id'] and
                terminal.get('task_id') == self.spec['task_id'] and
                terminal.get('pma_finalization') == {'status': 'not_enabled'} and
                isinstance(terminal.get('pos_finalization'), dict) and
                isinstance(terminal.get('pos_archive_incomplete'), bool) and
                isinstance(terminal.get('pos_auxiliary_errors'), list))
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

    async def _watch_ga_control(self):
        registry = self.archive / 'registered_control_processes'
        registry.mkdir(exist_ok=True)
        identities = {}
        while not self._control_watch_stop.is_set():
            snapshot = await asyncio.to_thread(scan_control_processes,
                self.container_id, self._control_python, self.spec['run_id'])
            if snapshot['pid_namespace'] != self._control_namespace:
                raise RuntimeError('GA control PID namespace changed during task')
            for row in snapshot['processes']:
                identity = {**row, 'pid_namespace': self._control_namespace,
                            'run_id': self.spec['run_id']}
                key = (row['pid'], row['start_ticks'])
                if key not in identities:
                    identities[key] = identity
                    path = registry / f"{row['pid']}-{row['start_ticks']}.json"
                    if path.exists():
                        if json.loads(path.read_text(encoding='utf-8')) != identity:
                            raise RuntimeError('GA control registration changed')
                    else:
                        _atomic(path, identity)
            await asyncio.sleep(.1)

    async def _finish_control_watch(self):
        self._control_watch_stop.set()
        try:
            await asyncio.wait_for(self._control_watch_task, timeout=35)
        except BaseException as exc:
            raise RuntimeError('trusted GA control registration incomplete') from exc

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
        candidate_profile = (self.spec['condition'] == 'P' and
            self.spec.get('research_candidate') == 'pos_pma_complement_v1' and
            (self.spec.get('zero_model_fixture_only') is not True or
             self.spec.get('candidate_profile_fixture_only') is True))
        if self.spec['condition'] == 'B' or candidate_profile:
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
        if self.spec['condition'] == 'P':
            actual = mounts.get('/run/pos-archive')
            expected = Path(self.spec['run_root']) / 'control' / 'pos_archive'
            if (actual is None or not actual.get('RW') or
                    _source_identity(str(actual.get('Source'))) !=
                    _source_identity(expected.as_posix())):
                raise RuntimeError('PoS archive mount identity differs')
            fake = mounts.get('/run/pos-fake-replies.json')
            expected_fake = (self.spec.get('zero_model_fixture_only') is True and
                self.spec.get('candidate_profile_fixture_only') is not True)
            if (fake is not None) != expected_fake:
                raise RuntimeError('PoS fake reply mount differs from fixture identity')
        elif any(path.startswith('/run/pos-') for path in mounts):
            raise RuntimeError('non-P Task sees PoS mount')
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
        self._control_python = ('/opt/m4-runtime/python/' +
            self.spec.get('python_home', 'cpython-3.12.12-linux-x86_64-gnu') +
            '/bin/python3.12')
        initial = await asyncio.to_thread(scan_control_processes,
                                          container, self._control_python,
                                          self.spec['run_id'])
        if any(row['kind'] in {'ga', 'wrapper'} for row in initial['processes']):
            raise RuntimeError('GA agent or wrapper already present before agent start')
        self._control_namespace = initial['pid_namespace']
        _atomic(self.archive / 'control_process_registry.json', {
            'run_id': self.spec['run_id'], 'container_id': container,
            'pid_namespace': self._control_namespace,
            'initial_control_count': len(initial['processes'])})
        registered = self.archive / 'registered_control_processes'
        registered.mkdir(exist_ok=False)
        for row in initial['processes']:
            identity = {**row, 'pid_namespace': self._control_namespace,
                        'run_id': self.spec['run_id']}
            _atomic(registered / f"{row['pid']}-{row['start_ticks']}.json",
                    identity)
        _atomic(self.archive / 'agent_start_identity.json', {
            'run_id': self.spec['run_id'], 'container_id': container,
            'image_id': raw['Image'], 'network_mode': raw['HostConfig']['NetworkMode'],
            'mounts': [{k: m.get(k) for k in ('Destination', 'Source', 'RW', 'Type', 'Name')}
                       for m in raw.get('Mounts', [])],
            'provider_key_env_absent': True, 'hidden_tests_absent': True,
            'baseline_pids': sorted(self.baseline_pids)})
        self._control_watch_stop = asyncio.Event()
        self._control_watch_task = asyncio.create_task(self._watch_ga_control())

    async def agent_end(self, event):
        await self._finish_control_watch()
        _atomic(self.control / 'agent_end_pending.json',
                {'run_id': self.spec['run_id'], 'container_id': self.container_id})
        cleared = self.control / 'sidecar_stopped.json'
        deadline = time.monotonic() + 120
        while not cleared.is_file():
            if time.monotonic() >= deadline:
                raise RuntimeError('native PMA sidecar clearance unavailable')
            await asyncio.sleep(.05)
        clearance = json.loads(cleared.read_text(encoding='utf-8'))
        if (clearance.get('run_id') != self.spec['run_id'] or
                clearance.get('clean') is not True or
                clearance.get('stopped') is not True):
            raise RuntimeError('native PMA sidecar not stopped')
        if await self._main_id() != self.container_id:
            raise RuntimeError('native main container replaced before verification')
        # Stop the inference gateway but preserve main, its writable layer,
        # task mounts and services for Harbor's normal collection/verifier.
        await self.trial.agent_environment._run_docker_compose_command(
            ['stop', 'model-gateway'])
        gateway = await self.trial.agent_environment._run_docker_compose_command(
            ['ps', '-a', '-q', 'model-gateway'])
        gateway_ids = gateway.stdout.strip().splitlines()
        if len(gateway_ids) != 1:
            raise RuntimeError('native model gateway identity unavailable after stop')
        gateway_state = await asyncio.to_thread(subprocess.run,
            ['docker', 'inspect', '-f', '{{.State.Running}}', gateway_ids[0]],
            text=True, capture_output=True, timeout=30)
        if gateway_state.returncode or gateway_state.stdout.strip() != 'false':
            raise RuntimeError('native model gateway stop unconfirmed')
        registry = json.loads((self.archive / 'control_process_registry.json').read_text(
            encoding='utf-8'))
        if (registry.get('run_id') != self.spec['run_id'] or
                registry.get('container_id') != self.container_id or
                registry.get('pid_namespace') != self._control_namespace):
            raise RuntimeError('trusted GA control registry identity changed')
        observed = {}
        for path in (self.archive / 'registered_control_processes').glob('*.json'):
            row = json.loads(path.read_text(encoding='utf-8'))
            if (row.get('run_id') != self.spec['run_id'] or
                    row.get('pid_namespace') != self._control_namespace):
                raise RuntimeError('trusted GA control registration identity differs')
            observed[(row['pid'], row['start_ticks'])] = row
        if not observed or not any(row['kind'] == 'transport' for row in observed.values()):
            raise RuntimeError('trusted GA control registration incomplete')
        top = await asyncio.to_thread(subprocess.run, ['docker', 'top', self.container_id],
                                      text=True, capture_output=True, timeout=30)
        first_top = top.stdout
        active = await asyncio.to_thread(scan_control_processes,
                                         self.container_id, self._control_python,
                                         self.spec['run_id'])
        if active['pid_namespace'] != self._control_namespace:
            raise RuntimeError('GA control PID namespace changed before evaluation')
        for row in active['processes']:
            identity = observed.get((row['pid'], row['start_ticks']))
            if identity is None or identity['argv_sha256'] != row['argv_sha256']:
                raise RuntimeError('unregistered or reused GA control process remains')
        probe_before = {}
        for identity in observed.values():
            state = await asyncio.to_thread(probe_registered, self.container_id,
                                            self._control_python, identity)
            probe_before[str(identity['pid'])] = state
            if state == 'identity_changed':
                raise RuntimeError('registered GA control process changed argv while alive')
            if state == 'registered_alive':
                await asyncio.to_thread(stop_registered, self.container_id,
                                        self._control_python, identity)
        if 'registered_alive' in probe_before.values():
            await asyncio.sleep(2)
            top = await asyncio.to_thread(subprocess.run,
                ['docker', 'top', self.container_id], text=True,
                capture_output=True, timeout=30)
        final_control = await asyncio.to_thread(scan_control_processes,
                                                self.container_id, self._control_python,
                                                self.spec['run_id'])
        probe_after = {str(row['pid']): await asyncio.to_thread(
            probe_registered, self.container_id, self._control_python, row)
            for row in observed.values()}
        _atomic(self.archive / 'writer_termination_check.json', {
            'run_id': self.spec['run_id'], 'before': first_top,
            'after': top.stdout, 'docker_top_return_code': top.returncode,
            'registered_control_processes': list(observed.values()),
            'registered_probe_before': probe_before,
            'registered_probe_after': probe_after,
            'control_remaining': final_control['processes'],
            'task_owned_pids_preserved': sorted(_docker_top_pids(top.stdout) - self.baseline_pids)
                if top.returncode == 0 else None})
        if (top.returncode or final_control['pid_namespace'] != self._control_namespace or
                final_control['processes'] or
                any(state not in {'exited', 'pid_reused'} for state in probe_after.values())):
            raise RuntimeError('registered GA control processes not stopped')
        _atomic(self.archive / 'agent_end_native.json', {
            'run_id': self.spec['run_id'], 'container_id': self.container_id,
            'sidecar_clean': True, 'gateway_stopped': True,
            'gateway_container_id': gateway_ids[0],
            'pma_finalization': clearance.get('pma_finalization'),
            'pma_worker_return_code': clearance.get('worker_return_code'),
            'control_processes_stopped': True, 'writers_stopped': True,
            'docker_top': top.stdout,
            'baseline_pids': sorted(self.baseline_pids),
            'agent_result_metadata': str(getattr(self.trial.result, 'agent_result', None)),
            'legal_agent_end_required': False})
        if self.spec['condition'] == 'P':
            result_path = self.control / 'pos_archive' / 'events.result.json'
            close_path = self.control / 'pos_archive' / 'events.close.json'
            def read_receipt(path):
                try:
                    return json.loads(path.read_text(encoding='utf-8'))
                except (OSError, ValueError):
                    return {'status': 'missing_or_unknown'}
            result_receipt, close_receipt = read_receipt(result_path), read_receipt(close_path)
            terminal, terminal_error = None, None
            try:
                terminal_read = await self.trial.agent_environment.exec(
                    'cat /logs/agent/task_terminal.json', timeout_sec=30, user='root')
                if terminal_read.return_code:
                    terminal_error = 'cat_nonzero'
                else:
                    try:
                        candidate = json.loads(terminal_read.stdout)
                    except (TypeError, ValueError):
                        terminal_error = 'invalid_json'
                    else:
                        if not isinstance(candidate, dict):
                            terminal_error = 'invalid_shape'
                        elif (candidate.get('run_id') not in (None, self.spec['run_id']) or
                              candidate.get('task_id') not in (None, self.spec['task_id'])):
                            raise RuntimeError('PoS Task terminal identity conflict')
                        elif self.terminal_identity_valid(candidate):
                            terminal = candidate
                        else:
                            terminal = candidate
                            terminal_error = 'missing_fields'
            except (OSError, TimeoutError):
                terminal_error = 'read_error'
            from method_discovery.pos_upstream_ga_v1_20261017.provider_capture import inspect_provider_capture
            provider_capture = inspect_provider_capture(
                self.control / 'pos_archive', self.spec['run_id'],
                self.spec['task_id'],
                profile_mode=self.spec.get('zero_model_fixture_only') is not True)
            _atomic(self.archive / 'pos_archive_status.json', pos_archive_summary(
                self.spec['run_id'], self.spec['task_id'], terminal,
                result_receipt, close_receipt, terminal_error,
                provider_capture))

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
                 spec.get('evaluation_protocol') in {'official_shared_v2',
                                                     'synthetic_shared_v1'} else
                 PMATrialHooks(trial, spec))
        trial.add_hook(TrialEvent.AGENT_START, hooks.agent_start)
        trial.add_hook(TrialEvent.AGENT_END, hooks.agent_end)
        trial.add_hook(TrialEvent.VERIFICATION_START, hooks.verification_start)
        return trial

    Trial.create = classmethod(create)
