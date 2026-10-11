"""Zero-model receipt-path checks after disabling live scratch statistics."""

import json
import os
from pathlib import Path
import subprocess
import threading
from unittest import mock

import pytest

from method_discovery.curator_supervisor_convergence_v0.real_task_effect_pilot_preflight_20261010 import pilot_analysis_bridge
from method_discovery.curator_supervisor_convergence_v0.real_task_effect_pilot_preflight_20261010.pilot_analysis_bridge import (
    PilotDockerToolPort, PilotHostBridge, SCHEMA,
)


def _request(bridge, operation, request_id):
    payload = {'schema': SCHEMA, 'run_id': 'offline', 'request_id': request_id,
               'operation': operation}
    if operation == 'start':
        payload.update(code='echo known', code_type='bash', timeout=60, wait_seconds=0)
    elif operation == 'read':
        payload.update(session_id='session-one', wait_seconds=0, cancel=False)
    (bridge.root / 'requests' / f'{request_id}.json').write_text(json.dumps(payload), encoding='utf-8')


class ReceiptPort:
    task_volume = 'offline-volume'

    def __init__(self):
        self.calls, self.mirrors, self.checks = [], [], 0

    def _check_mount_sources(self):
        self.checks += 1

    def execute(self, name, args):
        self.calls.append(dict(args))
        return {'status': 'running' if 'code' in args else 'success',
                'session_id': 'session-one', 'stdout': 'known result'}

    def mirror_output(self, session):
        self.mirrors.append(session)

    def close(self):
        self.calls.append({'close': True})


def test_start_running_read_and_close_never_scan_scratch(tmp_path, monkeypatch):
    port = ReceiptPort()
    bridge = PilotHostBridge(root=tmp_path / 'spool', run_id='offline', port=port)
    monkeypatch.setattr(bridge, '_scratch_files',
                        lambda: pytest.fail('live scratch scan invoked'), raising=False)
    monkeypatch.setattr(bridge, '_scratch_snapshot',
                        lambda: pytest.fail('live scratch snapshot invoked'), raising=False)
    for operation, request_id in [('start', 'one'), ('read', 'two'), ('close', 'three')]:
        _request(bridge, operation, request_id)
        bridge.serve_once()
        receipt = json.loads((bridge.root / 'responses' / f'{request_id}.json').read_text())
        assert receipt['status'] == 'ok'
    assert port.calls == [
        {'code': 'echo known', 'type': 'bash', 'timeout': 60, 'wait_seconds': 0},
        {'session_id': 'session-one', 'wait_seconds': 0, 'cancel': False},
        {'close': True},
    ]
    assert port.mirrors == ['session-one', 'session-one']
    assert port.checks == 6
    assert json.loads((bridge.root / 'scratch_statistics_policy.json').read_text())[
        'scratch_content_statistics'] == 'disabled'
    assert not (bridge.root / 'scratch_observations').exists()
    assert all('scratch' not in json.loads(path.read_text()).get('result', {})
               for path in (bridge.root / 'responses').glob('*.json'))


@pytest.mark.parametrize('operation', ['start', 'read'])
@pytest.mark.parametrize('fault', ['identity', 'missing', 'permission'])
def test_real_spool_path_fails_closed_on_protected_root_fault(tmp_path, monkeypatch,
                                                               operation, fault):
    protected = tmp_path / 'protected'
    protected.mkdir()
    port = object.__new__(PilotDockerToolPort)
    port.task_volume = 'offline-volume'
    identity = port._safe_mount_identity(protected)
    port._mount_identities = {str(protected): identity}
    calls = []
    port.execute = lambda name, args: calls.append(args) or {'status': 'success', 'session_id': None}
    bridge = PilotHostBridge(root=tmp_path / 'spool', run_id='offline', port=port)
    _request(bridge, operation, 'one')
    if fault == 'identity':
        port._mount_identities[str(protected)] = (identity[0], identity[1] + 1)
        expected = RuntimeError
    elif fault == 'missing':
        protected.rmdir()
        expected = FileNotFoundError
    else:
        original = os.scandir

        def denied(path):
            if Path(path) == protected:
                raise PermissionError(13, 'protected root unreadable', str(path))
            return original(path)

        monkeypatch.setattr(pilot_analysis_bridge.os, 'scandir', denied)
        expected = PermissionError
    with pytest.raises(expected):
        bridge.serve_once()
    assert calls == []
    assert (bridge.root / 'accepted' / 'one.json').exists()
    assert not (bridge.root / 'responses' / 'one.json').exists()
    bridge.serve_once()
    assert json.loads((bridge.root / 'responses' / 'one.json').read_text())['status'] == 'uncertain'
    assert calls == []


def test_identity_change_after_execution_prevents_normal_receipt(tmp_path):
    protected = tmp_path / 'protected'
    protected.mkdir()
    port = object.__new__(PilotDockerToolPort)
    port.task_volume = 'offline-volume'
    port._mount_identities = {str(protected): port._safe_mount_identity(protected)}
    calls = []

    def execute(name, args):
        calls.append(args)
        protected.rmdir()
        return {'status': 'success', 'session_id': None}

    port.execute = execute
    bridge = PilotHostBridge(root=tmp_path / 'spool', run_id='offline', port=port)
    _request(bridge, 'start', 'one')
    with pytest.raises(FileNotFoundError):
        bridge.serve_once()
    assert len(calls) == 1
    assert not (bridge.root / 'responses' / 'one.json').exists()
    bridge.serve_once()
    assert json.loads((bridge.root / 'responses' / 'one.json').read_text())['status'] == 'uncertain'
    assert len(calls) == 1


def test_cleanup_error_cannot_receive_clean_certificate():
    port = object.__new__(PilotDockerToolPort)
    done = threading.Event()
    done.set()
    port.new_sessions = {'static-fixture': {'done': done, 'reason': 'cleanup_error'}}

    def docker_result(argv, **kwargs):
        if argv[1] == 'inspect':
            return subprocess.CompletedProcess(argv, 1, '', 'No such object')
        return subprocess.CompletedProcess(argv, 0, 'daemon-id', '')

    with mock.patch('method_discovery.curator_supervisor_convergence_v0.'
                    'diagnostic_static_adapter_v1_20261009.docker_tool.DockerToolPort.close'), \
         mock.patch('method_discovery.curator_supervisor_convergence_v0.'
                    'real_task_effect_pilot_preflight_20261010.pilot_analysis_bridge.'
                    'subprocess.run', side_effect=docker_result):
        with pytest.raises(RuntimeError, match='cleanup_unknown'):
            port.close()
