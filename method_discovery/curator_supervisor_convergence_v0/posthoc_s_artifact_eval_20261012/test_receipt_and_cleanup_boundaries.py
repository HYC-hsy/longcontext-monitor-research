"""Zero-model checks for receipt ordering and pilot sidecar cleanup."""

import json
from pathlib import Path
import threading

import pytest

from method_discovery.curator_supervisor_convergence_v0.real_task_effect_pilot_preflight_20261010 import pilot_offline_harbor
from method_discovery.curator_supervisor_convergence_v0.real_task_effect_pilot_preflight_20261010.pilot_analysis_bridge import (
    PilotHostBridge, SCHEMA, SCRATCH_SCAN_LIMITS,
)


class Port:
    def __init__(self, scratch):
        self.scratch = scratch
        self.task_volume = 'offline-volume'
        self.calls = 0

    def _check_mount_sources(self):
        return None

    def execute(self, *_):
        self.calls += 1
        return {'status': 'success', 'stdout': 'known result', 'session_id': None}

    def close(self):
        return None


def _request(bridge):
    path = bridge.root / 'requests' / 'one.json'
    path.write_text(json.dumps({'schema': SCHEMA, 'run_id': 'offline',
        'request_id': 'one', 'operation': 'start', 'code': 'echo known',
        'code_type': 'bash', 'timeout': 60, 'wait_seconds': 0}), encoding='utf-8')


def test_slow_optional_scan_cannot_hold_known_receipt_or_replay(tmp_path, monkeypatch):
    scratch = tmp_path / 'scratch'
    (scratch / 'tmp').mkdir(parents=True)
    (scratch / 'output').mkdir()
    port = Port(scratch)
    bridge = PilotHostBridge(root=tmp_path / 'spool', run_id='offline', port=port)
    _request(bridge)
    entered, release = threading.Event(), threading.Event()

    def slow_scan():
        entered.set()
        assert release.wait(2)
        return {'files': {}, 'skipped': [], 'snapshot_incomplete': False,
                'limit_reached': False}

    monkeypatch.setattr(bridge, '_scratch_snapshot', slow_scan)
    worker = threading.Thread(target=bridge.serve_once)
    worker.start()
    assert entered.wait(2)
    receipt = json.loads((bridge.root / 'responses' / 'one.json').read_text())
    assert receipt['result']['stdout'] == 'known result'
    assert port.calls == 1
    release.set()
    worker.join(timeout=2)
    assert not worker.is_alive()
    (bridge.root / 'responses' / 'one.json').unlink()
    bridge.serve_once()
    uncertain = json.loads((bridge.root / 'responses' / 'one.json').read_text())
    assert uncertain['status'] == 'uncertain'
    assert port.calls == 1


def test_large_file_is_bounded_and_never_reported_as_complete_hash(tmp_path):
    scratch = tmp_path / 'scratch'
    (scratch / 'tmp').mkdir(parents=True)
    (scratch / 'output').mkdir()
    oversized = scratch / 'tmp' / 'large'
    with oversized.open('wb') as stream:
        stream.truncate(SCRATCH_SCAN_LIMITS['file_bytes'] + 1)
    bridge = PilotHostBridge(root=tmp_path / 'spool', run_id='offline', port=Port(scratch))
    snapshot = bridge._scratch_snapshot()
    assert snapshot['snapshot_incomplete'] and snapshot['limit_reached']
    assert snapshot['limits'] == SCRATCH_SCAN_LIMITS
    assert 'tmp/large' not in snapshot['files']
    assert snapshot['skipped'][0] == {'path': 'tmp/large', 'reason': 'byte_limit'}
    assert snapshot['scanned_bytes'] == 0


def test_directory_disappears_after_enumeration(tmp_path, monkeypatch):
    scratch = tmp_path / 'scratch'
    vanished = scratch / 'tmp' / 'go-temp-dir'
    vanished.mkdir(parents=True)
    (scratch / 'output').mkdir()
    bridge = PilotHostBridge(root=tmp_path / 'spool', run_id='offline', port=Port(scratch))
    original = __import__('os').scandir

    def racing_scandir(path):
        if Path(path) == vanished:
            raise FileNotFoundError(2, 'directory removed', str(path))
        return original(path)

    monkeypatch.setattr('method_discovery.curator_supervisor_convergence_v0.'
                        'real_task_effect_pilot_preflight_20261010.pilot_analysis_bridge.'
                        'os.scandir', racing_scandir)
    snapshot = bridge._scratch_snapshot()
    assert snapshot['snapshot_incomplete']
    assert {'path': 'tmp/go-temp-dir', 'reason': 'disappeared'} in snapshot['skipped']


def test_optional_scan_error_does_not_change_durable_result(tmp_path, monkeypatch):
    scratch = tmp_path / 'scratch'
    (scratch / 'tmp').mkdir(parents=True)
    (scratch / 'output').mkdir()
    port = Port(scratch)
    bridge = PilotHostBridge(root=tmp_path / 'spool', run_id='offline', port=port)
    _request(bridge)
    monkeypatch.setattr(bridge, '_scratch_snapshot',
                        lambda: (_ for _ in ()).throw(OSError('optional scan failed')))
    bridge.serve_once()
    receipt = json.loads((bridge.root / 'responses' / 'one.json').read_text())
    assert receipt['status'] == 'ok' and receipt['result']['stdout'] == 'known result'
    assert bridge.scratch_observation_errors[0]['error_type'] == 'OSError'
    assert port.calls == 1


@pytest.mark.parametrize('cleanup_fails', [False, True])
def test_abnormal_spool_exit_certifies_only_positive_cleanup(tmp_path, monkeypatch, cleanup_fails):
    root = tmp_path / 'run'
    (root / 'control').mkdir(parents=True)
    (root / 'monitor' / 'monitor_private').mkdir(parents=True)
    (root / 'monitor' / 'task_evidence').mkdir()
    (root / 'monitor' / 'task_identity.json').write_text('{}')
    closes = []

    class FakePort:
        def __init__(self, **_):
            pass

        def close(self):
            closes.append('port')

    class FakeBridge:
        def __init__(self, **_):
            self.closed = False

        def serve_once(self):
            raise RuntimeError('primary spool failure')

        def close(self):
            closes.append('bridge')
            if cleanup_fails:
                raise RuntimeError('cleanup unknown')
            self.closed = True

    monkeypatch.setattr(pilot_offline_harbor, 'PilotDockerToolPort', FakePort)
    monkeypatch.setattr(pilot_offline_harbor, 'PilotHostBridge', FakeBridge)
    stopped, errors = threading.Event(), []
    pilot_offline_harbor._serve_spool(root, 'offline-image', 'offline-volume',
                                      'offline-run', stopped, errors)
    assert stopped.is_set()
    assert closes == ['bridge']
    assert any('primary spool failure' in error for error in errors)
    certificate = root / 'control' / 'sidecar_stopped.json'
    if cleanup_fails:
        assert not certificate.exists()
        assert any('cleanup unknown' in error for error in errors)
    else:
        assert json.loads(certificate.read_text()) == {'run_id': 'offline-run', 'clean': True}
        assert not any('cleanup:' in error for error in errors)


def test_normal_spool_exit_uses_same_cleanup_certificate(tmp_path, monkeypatch):
    root = tmp_path / 'run'
    (root / 'control').mkdir(parents=True)
    (root / 'control' / 'agent_end_pending.json').write_text('{}')
    (root / 'monitor' / 'monitor_private').mkdir(parents=True)
    (root / 'monitor' / 'task_evidence').mkdir()
    (root / 'monitor' / 'task_identity.json').write_text('{}')
    closes = []

    class FakePort:
        def __init__(self, **_):
            pass

    class FakeBridge:
        def __init__(self, **_):
            self.closed = False

        def serve_once(self):
            pass

        def close(self):
            closes.append('bridge')
            self.closed = True

    monkeypatch.setattr(pilot_offline_harbor, 'PilotDockerToolPort', FakePort)
    monkeypatch.setattr(pilot_offline_harbor, 'PilotHostBridge', FakeBridge)
    stopped, errors = threading.Event(), []
    pilot_offline_harbor._serve_spool(root, 'offline-image', 'offline-volume',
                                      'offline-run', stopped, errors)
    assert errors == []
    assert closes == ['bridge']
    assert json.loads((root / 'control' / 'sidecar_stopped.json').read_text()) == {
        'run_id': 'offline-run', 'clean': True}
