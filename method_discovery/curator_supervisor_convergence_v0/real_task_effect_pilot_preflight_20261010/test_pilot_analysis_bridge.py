"""No-model end-to-end Monitor analysis port probes on the two pinned images."""

from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'GenericAgent-main'))

from monitor_agent_core.analysis_spool import (  # noqa: E402
    AnalysisPortIntegrityError, SpoolAnalysisSessions,
)
from monitor_agent_core.agent import MonitorAgent  # noqa: E402
from monitor_agent_core.provider import MonitorProviderClient  # noqa: E402
from monitor_agent_core.workspace import MonitorWorkspace  # noqa: E402
from .pilot_analysis_bridge import PilotDockerToolPort, PilotHostBridge  # noqa: E402


IMAGES = (
    'sha256:b0da1cb31d367df38d05b81f98e68a94b0f7114efd3c82537633d1d92325efe1',
    'sha256:7ffcd70e49d77031b8e67eaa99226dc8468fa046f33e615118e8922b89fff32e',
)


def docker(*args):
    return subprocess.run(['docker', *args], text=True, capture_output=True, timeout=45)


class PilotAnalysisBridgeFixture(unittest.TestCase):
    def test_malformed_or_misowned_spool_receipt_is_integrity_failure(self):
        for payload in ([], {'run_id': 'wrong', 'request_id': 'wrong',
                             'status': 'ok', 'result': {}}):
            with self.subTest(payload=payload), tempfile.TemporaryDirectory(prefix='lc_spool_bad_') as name:
                root = pathlib.Path(name) / 'bridge'
                root.mkdir()
                (root / 'requests').mkdir()
                (root / 'responses').mkdir()
                (root / 'identity.json').write_text(json.dumps({
                    'schema': 'pilot-analysis-spool-v1', 'run_id': 'offline-run'}), encoding='utf-8')
                client = SpoolAnalysisSessions(root, 'offline-run', threading.Event(),
                                               response_timeout=1)

                def respond():
                    requests = root / 'requests'
                    for _ in range(100):
                        found = list(requests.glob('*.json'))
                        if found:
                            (root / 'responses' / found[0].name).write_text(
                                json.dumps(payload), encoding='utf-8')
                            return
                        time.sleep(.01)

                thread = threading.Thread(target=respond)
                thread.start()
                with self.assertRaises(AnalysisPortIntegrityError):
                    client.start('echo harmless', 'bash')
                thread.join(timeout=2)
                self.assertFalse(thread.is_alive())

    def test_unanswered_accepted_request_never_falls_back_to_local_process(self):
        with tempfile.TemporaryDirectory(prefix='lc_pilot_spool_') as name:
            root = pathlib.Path(name) / 'bridge'
            root.mkdir()
            (root / 'requests').mkdir()
            (root / 'responses').mkdir()
            (root / 'identity.json').write_text(json.dumps({
                'schema': 'pilot-analysis-spool-v1', 'run_id': 'offline-run'}), encoding='utf-8')
            evidence, private = pathlib.Path(name) / 'evidence', pathlib.Path(name) / 'private'
            evidence.mkdir()
            private.mkdir()
            monitor = MonitorAgent(MonitorProviderClient('anthropic', {
                'apikey': 'offline', 'apibase': 'https://offline.invalid',
                'model': 'offline', 'max_retries': 0}), MonitorWorkspace(evidence, private))
            monitor.analysis = SpoolAnalysisSessions(root, 'offline-run', threading.Event(),
                                                     response_timeout=.05)
            with self.assertRaises(AnalysisPortIntegrityError):
                monitor.dispatch('code_run', {'code': 'echo never-run', 'type': 'bash'})
            self.assertTrue(monitor._analysis_integrity_failure)
            with self.assertRaises(AnalysisPortIntegrityError):
                monitor.review('queued wake')
            self.assertEqual(len(list((root / 'requests').glob('*.json'))), 1)

    def _completed(self, client, code, timeout=120):
        receipt = client.start(code, 'bash', timeout=timeout, wait_seconds=1)
        chunks = [receipt.get('stdout', '')]
        for _ in range(150):
            if receipt['status'] != 'running':
                receipt['stdout'] = ''.join(chunks)
                return receipt
            receipt = client.read(receipt['session_id'], wait_seconds=1)
            chunks.append(receipt.get('stdout', ''))
        self.fail('Analysis session did not reach a terminal receipt')

    def test_target_image_read_only_monitor_dispatch(self):
        for image in IMAGES:
            with self.subTest(image=image):
                volume = 'lc_pilot_bridge_' + uuid.uuid4().hex
                self.assertEqual(docker('volume', 'create', volume).returncode, 0)
                temp = pathlib.Path(tempfile.mkdtemp(prefix='lc_pilot_bridge_')).resolve()
                stop = threading.Event()
                thread = None
                bridge = None
                error = []
                try:
                    init = docker('run', '--rm', '--network', 'none', '--mount',
                                  f'type=volume,source={volume},destination=/app',
                                  '--entrypoint', 'sh', image, '-c',
                                  'printf task-v1 >/app/.pilot_probe.txt')
                    self.assertEqual(init.returncode, 0, init.stderr)
                    private, evidence = temp / 'monitor_private', temp / 'task_evidence'
                    trusted, scratch = temp / 'trusted_control', temp / 'scratch'
                    private.mkdir()
                    evidence.mkdir()
                    trusted.mkdir()
                    scratch.mkdir()
                    port = PilotDockerToolPort(image=image, task_volume=volume,
                                               trusted_root=trusted, cognition_root=private,
                                               scratch_root=scratch, evidence_root=evidence)
                    bridge = PilotHostBridge(root=temp / 'monitor_bridge',
                                             run_id='fixture-' + volume, port=port)

                    def serve():
                        try:
                            while not stop.is_set() and not bridge.closed:
                                bridge.serve_once()
                                time.sleep(.02)
                        except Exception as exc:
                            error.append(exc)

                    thread = threading.Thread(target=serve, daemon=True)
                    thread.start()
                    client = SpoolAnalysisSessions(temp / 'monitor_bridge',
                                                   'fixture-' + volume, threading.Event(),
                                                   response_timeout=30)
                    workspace = MonitorWorkspace(evidence, private)
                    monitor_client = MonitorProviderClient('anthropic', {
                        'apikey': 'offline', 'apibase': 'https://offline.invalid',
                        'model': 'offline', 'max_retries': 0})
                    monitor = MonitorAgent(monitor_client, workspace)
                    monitor.analysis = client
                    read = monitor.dispatch('code_run', {
                        'code': 'cat /app/.pilot_probe.txt; sha256sum /app/.pilot_probe.txt',
                        'type': 'bash', 'timeout': 120, 'wait_seconds': 1}).data
                    chunks = [read.get('stdout', '')]
                    while read['status'] == 'running':
                        read = monitor.dispatch('code_run', {
                            'session_id': read['session_id'], 'wait_seconds': 1}).data
                        chunks.append(read.get('stdout', ''))
                    read['stdout'] = ''.join(chunks)
                    self.assertEqual(read['status'], 'success', read)
                    self.assertEqual(read['source_version']['status'], 'version_uncertain')
                    self.assertIn('task-v1', read['stdout'])
                    denied = self._completed(client,
                        'if printf bad >/app/.pilot_probe.txt 2>/dev/null; then exit 9; fi; '
                        'test "$(cat /app/.pilot_probe.txt)" = task-v1')
                    self.assertEqual(denied['status'], 'success', denied)
                    private_test = self._completed(client,
                        'mkdir -p /tmp/probe; cp /app/.pilot_probe.txt /tmp/probe/source.txt; '
                        'printf private-v2 >/tmp/probe/source.txt; '
                        'test "$(cat /tmp/probe/source.txt)" = private-v2; '
                        'test "$(cat /app/.pilot_probe.txt)" = task-v1; '
                        'cd /tmp/probe; printf "package probe\\nfunc Value() int { return 7 }\\n" >probe.go; '
                        'printf "package probe\\nimport \\\"testing\\\"\\nfunc TestValue(t *testing.T) '
                        '{ if Value()!=7 { t.Fatal() } }\\n" >probe_test.go; '
                        'GO111MODULE=off go test .')
                    self.assertEqual(private_test['status'], 'success', private_test)
                    self.assertIn('ok', private_test['stdout'])
                    self.assertIn('tmp/probe/source.txt',
                                  private_test['private_scratch_diff']['added'])
                    public_build = self._completed(client,
                        'cd /app; go env GOMODCACHE; go test -run "^$" .', timeout=300)
                    self.assertEqual(public_build['status'], 'success', public_build)
                    self.assertIn('/go/pkg/mod', public_build['stdout'])
                    protected = self._completed(client,
                        'if mv /pilot_control /tmp/redirected 2>/dev/null; then exit 13; fi; '
                        'if printf forged >/pilot_control/audit/commands/forged 2>/dev/null; '
                        'then exit 14; fi; '
                        'if printf forged >/logs/agent/monitor/monitor_private/reference.md '
                        '2>/dev/null; then exit 15; fi; '
                        'printf still-private >/tmp/protected-probe; '
                        'test "$(cat /tmp/protected-probe)" = still-private')
                    self.assertEqual(protected['status'], 'success', protected)
                    port._check_mount_sources()
                    update = docker('run', '--rm', '--network', 'none', '--mount',
                                    f'type=volume,source={volume},destination=/app',
                                    '--entrypoint', 'sh', image, '-c',
                                    'printf task-v2 >/app/.pilot_probe.txt')
                    self.assertEqual(update.returncode, 0, update.stderr)
                    fresh = self._completed(client, 'cat /app/.pilot_probe.txt; sha256sum /app/.pilot_probe.txt')
                    self.assertEqual(fresh['status'], 'success', fresh)
                    self.assertIn('task-v2', fresh['stdout'])
                    self.assertNotEqual(read['stdout'].splitlines()[-1], fresh['stdout'].splitlines()[-1])
                    client.close()
                    thread.join(timeout=10)
                    self.assertFalse(thread.is_alive())
                    self.assertFalse(error, error)
                    self.assertTrue(bridge.closed)
                    self.assertTrue(list(trusted.glob('audit/commands/*/script_identity.json')))
                    self.assertTrue(list(private.glob('audit/commands/*/output.log')))
                finally:
                    stop.set()
                    if thread is not None:
                        thread.join(timeout=10)
                    if bridge is not None:
                        bridge.close()
                    removed = docker('volume', 'rm', volume)
                    self.assertEqual(removed.returncode, 0, removed.stderr)
                    # Only the exact generated temporary directory may be removed.
                    self.assertEqual(temp.parent, pathlib.Path(tempfile.gettempdir()).resolve())
                    self.assertTrue(temp.name.startswith('lc_pilot_bridge_'))
                    shutil.rmtree(temp)


if __name__ == '__main__':
    unittest.main()
