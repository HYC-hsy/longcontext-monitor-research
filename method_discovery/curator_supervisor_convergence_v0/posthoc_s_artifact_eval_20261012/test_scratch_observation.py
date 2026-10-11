"""Zero-model regression for optional pilot scratch observation."""

import json
from pathlib import Path
import subprocess
import threading
from unittest import mock

from method_discovery.curator_supervisor_convergence_v0.real_task_effect_pilot_preflight_20261010.pilot_analysis_bridge import PilotDockerToolPort, PilotHostBridge, SCHEMA


class Port:
    def __init__(self, scratch):
        self.scratch = scratch
        self.task_volume = 'offline-volume'
        self.calls = 0

    def _check_mount_sources(self):
        return None

    def execute(self, name, args):
        self.calls += 1
        return {'status': 'error', 'session_id': None, 'stdout': 'known command failure'}

    def close(self):
        return None


def test_vanished_file_marks_incomplete_without_losing_receipt(tmp_path, monkeypatch):
    scratch = tmp_path / 'scratch'
    (scratch / 'tmp').mkdir(parents=True)
    (scratch / 'output').mkdir()
    vanished = scratch / 'tmp' / 'go-temp-file'
    vanished.write_text('temporary')
    port = Port(scratch)
    bridge = PilotHostBridge(root=tmp_path / 'spool', run_id='offline', port=port)
    original = Path.read_bytes

    def racing_read(path):
        if path == vanished:
            raise FileNotFoundError(2, 'removed during scan', str(path))
        return original(path)

    monkeypatch.setattr(Path, 'read_bytes', racing_read)
    request = {'schema': SCHEMA, 'run_id': 'offline', 'request_id': 'one',
               'operation': 'start', 'code': 'echo known', 'code_type': 'bash',
               'timeout': 60, 'wait_seconds': 0}
    (bridge.root / 'requests' / 'one.json').write_text(json.dumps(request))
    bridge.serve_once()
    receipt = json.loads((bridge.root / 'responses' / 'one.json').read_text())
    assert receipt['status'] == 'ok'
    assert receipt['result']['stdout'] == 'known command failure'
    assert receipt['result']['private_scratch_diff_at_return']['snapshot_incomplete']
    assert receipt['result']['private_scratch_diff_at_return']['skipped_after'][0]['reason'] == 'disappeared'
    assert port.calls == 1
    (bridge.root / 'responses' / 'one.json').unlink()
    bridge.serve_once()
    uncertain = json.loads((bridge.root / 'responses' / 'one.json').read_text())
    assert uncertain['status'] == 'uncertain'
    assert port.calls == 1


def test_mount_identity_error_remains_hard_failure(tmp_path):
    scratch = tmp_path / 'scratch'
    (scratch / 'tmp').mkdir(parents=True)
    (scratch / 'output').mkdir()
    port = Port(scratch)
    port._check_mount_sources = lambda: (_ for _ in ()).throw(RuntimeError('mount changed'))
    bridge = PilotHostBridge(root=tmp_path / 'spool', run_id='offline', port=port)
    try:
        bridge._scratch_snapshot()
    except RuntimeError as exc:
        assert 'mount changed' in str(exc)
    else:
        raise AssertionError('identity error swallowed')


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
        try:
            port.close()
        except RuntimeError as exc:
            assert 'cleanup_unknown' in str(exc)
        else:
            raise AssertionError('cleanup_error accepted')
