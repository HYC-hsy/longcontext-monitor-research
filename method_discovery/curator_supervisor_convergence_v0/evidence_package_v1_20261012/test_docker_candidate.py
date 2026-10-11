"""Pinned target-image A/B inquiry through fake SSE and the real pilot spool port."""

import json
import subprocess
import threading
import time
import uuid
from pathlib import Path

import pytest

from monitor_agent_core.agent import MonitorAgent
from monitor_agent_core.analysis_spool import SpoolAnalysisSessions
from monitor_agent_core.provider import MonitorProviderClient
from monitor_agent_core.runtime import _capture_pilot_payload
from monitor_agent_core.workspace import MonitorWorkspace
from method_discovery.curator_supervisor_convergence_v0.real_task_effect_pilot_preflight_20261010.pilot_analysis_bridge import (
    PilotDockerToolPort, PilotHostBridge)


IMAGES = (
    'sha256:b0da1cb31d367df38d05b81f98e68a94b0f7114efd3c82537633d1d92325efe1',
    'sha256:7ffcd70e49d77031b8e67eaa99226dc8468fa046f33e615118e8922b89fff32e',
)


def docker(*args):
    return subprocess.run(['docker', *args], text=True, capture_output=True, timeout=90)


class SSE:
    status_code = 200
    headers = {'content-type': 'text/event-stream'}

    def __init__(self, tool_id, name, arguments):
        self.tool_id, self.name, self.arguments = tool_id, name, arguments

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def iter_lines(self):
        events = [
            {'type': 'message_start', 'message': {'usage': {'input_tokens': 5}}},
            {'type': 'content_block_start', 'content_block': {
                'type': 'tool_use', 'id': self.tool_id, 'name': self.name}},
            {'type': 'content_block_delta', 'delta': {
                'type': 'input_json_delta', 'partial_json': json.dumps(self.arguments)}},
            {'type': 'content_block_stop'},
            {'type': 'message_delta', 'usage': {'output_tokens': 5}},
            {'type': 'message_stop'},
        ]
        return iter([('data: ' + json.dumps(item)).encode() for item in events])


@pytest.mark.parametrize('image', IMAGES)
def test_pinned_image_fake_provider_two_stages_and_private_probe(tmp_path, monkeypatch, image):
    inspected = docker('image', 'inspect', image, '--format', '{{.Id}}')
    if inspected.returncode:
        pytest.skip('Pinned local target image unavailable')
    volume = 'lc-evpkg-fixture-' + uuid.uuid4().hex
    assert docker('volume', 'create', volume).returncode == 0
    bridge = None
    thread = None
    stop = threading.Event()
    failures = []
    try:
        seeded = docker('run', '--rm', '--network', 'none', '--mount',
                        f'type=volume,source={volume},destination=/app',
                        '--entrypoint', 'sh', image, '-c',
                        'printf task-v1 >/app/.evidence_package_probe.txt')
        assert seeded.returncode == 0, seeded.stderr
        monitor_root = tmp_path / 'monitor'
        private, evidence = monitor_root / 'monitor_private', monitor_root / 'task_evidence'
        trusted, scratch = tmp_path / 'trusted', tmp_path / 'scratch'
        for path in (private, evidence, trusted, scratch):
            path.mkdir(parents=True)
        (evidence / 'original_task.txt').write_text('Keep the current code observable.',
                                                    encoding='utf-8')
        (evidence / 'public_events.jsonl').write_text('', encoding='utf-8')
        port = PilotDockerToolPort(image=image, task_volume=volume,
                                   trusted_root=trusted, cognition_root=private,
                                   scratch_root=scratch, evidence_root=evidence)
        run_id = 'offline-' + uuid.uuid4().hex
        bridge = PilotHostBridge(root=tmp_path / 'bridge', run_id=run_id, port=port)

        def serve():
            try:
                while not stop.is_set() and not bridge.closed:
                    bridge.serve_once()
                    time.sleep(.02)
            except Exception as exc:
                failures.append(exc)

        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        analysis = SpoolAnalysisSessions(tmp_path / 'bridge', run_id, threading.Event(),
                                         response_timeout=60)
        task_view = tmp_path / 'task_view'
        task_view.mkdir()
        (task_view / '.evidence_package_probe.txt').write_text('task-v1', encoding='utf-8')
        workspace = MonitorWorkspace(evidence, private, task_mounts={'workspace': task_view})
        config = {'apikey': 'offline', 'apibase': 'https://offline.invalid',
                  'model': 'claude-opus-4-8', 'provider': 'anthropic', 'max_retries': 0,
                  'monitor_adaptive_supervisory_environment': True,
                  'monitor_narrow_supervisor_v1': True,
                  'monitor_evidence_package_v1': True}
        client = MonitorProviderClient('offline', config)
        monitor = MonitorAgent(client, workspace)
        monitor.analysis = analysis
        monitor.task_budget_state = lambda: (1, 300)
        client.pre_send_capture = lambda request_id, payload: _capture_pilot_payload(
            private, monitor, request_id, payload)
        requests = []

        def post(_url, **kwargs):
            requests.append(kwargs['json'])
            index = len(requests)
            if index == 1:
                name, arguments = 'file_write', {'path': 'monitor/reference.md',
                                                  'content': 'Observe the current public code.'}
            elif index == 2:
                name, arguments = 'packet_ready', {}
            elif index == 3:
                name, arguments = 'code_run', {'type': 'bash', 'timeout': 300,
                    'wait_seconds': 5, 'code': (
                        'cat /app/.evidence_package_probe.txt; '
                        'if printf forbidden >/app/.evidence_package_probe.txt 2>/dev/null; '
                        'then exit 19; fi; '
                        'mkdir -p /tmp/evidence_probe; '
                        'cp /app/.evidence_package_probe.txt /tmp/evidence_probe/private.txt; '
                        'printf private-v2 >/tmp/evidence_probe/private.txt; '
                        'test "$(cat /tmp/evidence_probe/private.txt)" = private-v2; '
                        'test "$(cat /app/.evidence_package_probe.txt)" = task-v1; '
                        'cd /app; GOPROXY=off go test -run "^$" .')}
            else:
                receipts = list(monitor.evidence_frontier.state['receipts'].values())
                result = receipts[-1]['result']
                if result['status'] == 'running':
                    name, arguments = 'code_run', {'session_id': result['session_id'],
                                                    'wait_seconds': 5}
                else:
                    name, arguments = 'wait', {'after_turns': 1, 'mode': 'follow'}
            return SSE('fixture-tool-' + str(index), name, arguments)

        monkeypatch.setattr('monitor_agent_core.provider.requests.post', post)
        action = monitor.review('Public task wake.', max_turns_override=30)
        assert action.kind == 'wait'
        assert any(row['result'].get('status') == 'success'
                   for row in monitor.evidence_frontier.state['receipts'].values())
        assert (scratch / 'tmp' / 'evidence_probe' / 'private.txt').read_text() == 'private-v2'
        assert len(requests) >= 4 and 'Phase A' in requests[0]['system']
        assert 'Phase B' in requests[2]['system']
        assert not failures
        analysis.close()
        thread.join(timeout=12)
        assert not thread.is_alive() and bridge.closed
        assert not failures
    finally:
        stop.set()
        if thread is not None:
            thread.join(timeout=12)
        if bridge is not None and not bridge.closed:
            bridge.close()
        removed = docker('volume', 'rm', volume)
        assert removed.returncode == 0, removed.stderr

