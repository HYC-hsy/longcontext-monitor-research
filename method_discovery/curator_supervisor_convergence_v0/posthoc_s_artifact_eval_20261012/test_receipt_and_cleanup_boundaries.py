"""Zero-model checks for pilot sidecar cleanup."""

import json
import threading

import pytest

from method_discovery.curator_supervisor_convergence_v0.real_task_effect_pilot_preflight_20261010 import pilot_offline_harbor
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
