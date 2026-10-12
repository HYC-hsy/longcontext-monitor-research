"""Actual zero-model cutoff/mount probe through the reused host spool."""

import hashlib
import json
import os
import subprocess
import threading
import time
from pathlib import Path

from monitor_agent_core.analysis_spool import SpoolAnalysisSessions

from .static_host import prepare_static


def test_c02_host_and_container_read_same_cutoff_without_control_mount(tmp_path):
    fixture = tmp_path / 'cutoff'
    manifest, port, bridge = prepare_static('C02', fixture)
    stop = threading.Event()
    errors = []

    def serve():
        try:
            while not stop.is_set() and not bridge.closed:
                bridge.serve_once()
                time.sleep(.02)
        except Exception as exc:
            errors.append(exc)

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    analysis = SpoolAnalysisSessions(bridge.root, bridge.run_id, threading.Event(),
                                    response_timeout=90)
    try:
        host = port.workspace.read_text('task/workspace/go.mod', 1, 1, max_chars=1)
        host_sha = hashlib.sha256((fixture / 'app' / 'go.mod').read_bytes()).hexdigest()
        assert host['sha256'] == host_sha
        script = (
            'set -eu\n'
            'sha256sum /app/go.mod\n'
            'test ! -e /tests/test.sh && echo tests_masked=pass\n'
            'test ! -e /logs/agent/monitor/.evidence_package_v1/frontier.json && echo frontier_hidden=pass\n'
            'test ! -e /host_spool/identity.json && echo spool_hidden=pass\n'
            'test ! -e /host_audit/dialogue.jsonl && echo audit_hidden=pass\n'
            'test ! -e /host_requests && echo requests_hidden=pass\n'
            'if printf changed >/app/go.mod 2>/dev/null; then exit 31; fi\n'
            'if printf changed >/pilot_control/identity_probe 2>/dev/null; then exit 32; fi\n'
            'printf writable >/tmp/private_probe\n'
            'test "$(cat /tmp/private_probe)" = writable && echo scratch_writable=pass\n'
            'sleep 8\n'
        )
        result = analysis.start(script, 'bash', timeout=60, wait_seconds=1)
        inspected = subprocess.run(['docker', 'inspect', result['session_id']],
                                   capture_output=True, timeout=20)
        assert inspected.returncode == 0, inspected.stderr
        state = json.loads(inspected.stdout)[0]
        mounts = [{'destination': mount['Destination'], 'source': mount['Source'],
                   'rw': mount['RW'], 'type': mount['Type']}
                  for mount in state['Mounts']]
        assert state['HostConfig']['ReadonlyRootfs'] is True
        assert state['HostConfig']['NetworkMode'] == 'none'
        assert any(item['destination'] == '/app' and not item['rw'] for item in mounts)
        assert not any('host_spool' in item['source'] or 'host_requests' in item['source']
                       for item in mounts)
        if os.environ.get('STATIC_AUDIT_ROOT'):
            output = Path(os.environ['STATIC_AUDIT_ROOT']) / 'C02_MOUNTS.json'
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps({'mounts': mounts,
                'readonly_rootfs': True, 'network_mode': 'none'}, indent=2) + '\n',
                encoding='utf-8')
        output = result.get('stdout', '')
        for _ in range(20):
            if result['status'] != 'running':
                break
            result = analysis.read(result['session_id'], wait_seconds=5)
            output += result.get('stdout', '')
        assert result['status'] == 'success', (result, output)
        assert host_sha in output
        for name in ('tests_masked', 'frontier_hidden', 'spool_hidden',
                     'audit_hidden', 'requests_hidden', 'scratch_writable'):
            assert output.count(name + '=pass') == 1, (name, output)
        (port.scratch / 'tmp' / 'exposed_sentinel').write_text('synthetic-only', encoding='ascii')
        negative = analysis.start('set -eu\ntest ! -e /tmp/exposed_sentinel\n',
                                  'bash', timeout=60, wait_seconds=5)
        for _ in range(20):
            if negative['status'] != 'running':
                break
            negative = analysis.read(negative['session_id'], wait_seconds=5)
        assert negative['status'] != 'success', negative
        assert manifest['ordinary_files'] == 2476
        assert manifest['workspace_tree_sha256'] == port.task_volume.split(':', 1)[1]
        assert not errors
        assert not (fixture / 'trusted_control' / 'identity_probe').exists()
        print({'scene': 'C02', 'host_sha256': host_sha,
               'checks': output, 'exposed_sentinel_status': negative['status'],
               'task_and_control_read_only': result['status'] == 'success'})
    finally:
        try:
            analysis.close()
        finally:
            stop.set()
            thread.join(timeout=15)
            if not bridge.closed:
                bridge.close()
    assert not thread.is_alive() and not errors and bridge.closed
