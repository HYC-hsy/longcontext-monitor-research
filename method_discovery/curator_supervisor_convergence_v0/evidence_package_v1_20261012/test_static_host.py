"""Actual zero-model cutoff/mount probe through the reused host spool."""

import hashlib
import threading
import time

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
            'set -u\n'
            'sha256sum /app/go.mod\n'
            'test ! -e /tests/test.sh\n'
            'test ! -e /logs/agent/monitor/.evidence_package_v1/frontier.json\n'
            'test ! -e /host_spool/identity.json\n'
            'test ! -e /host_audit/dialogue.jsonl\n'
            'test ! -e /host_requests\n'
            'if printf changed >/app/go.mod 2>/dev/null; then exit 31; fi\n'
            'if printf changed >/pilot_control/identity_probe 2>/dev/null; then exit 32; fi\n'
            'printf writable >/tmp/private_probe\n'
            'test "$(cat /tmp/private_probe)" = writable\n'
        )
        result = analysis.start(script, 'bash', timeout=60, wait_seconds=5)
        output = result.get('stdout', '')
        for _ in range(20):
            if result['status'] != 'running':
                break
            result = analysis.read(result['session_id'], wait_seconds=5)
            output += result.get('stdout', '')
        assert result['status'] == 'success', (result, output)
        assert host_sha in output
        assert manifest['ordinary_files'] == 2476
        assert manifest['workspace_tree_sha256'] == port.task_volume.split(':', 1)[1]
        assert not errors
        assert not (fixture / 'trusted_control' / 'identity_probe').exists()
        print({'scene': 'C02', 'host_sha256': host_sha,
               'container_same_sha256': host_sha in output,
               'tests_masked': True, 'frontier_and_spool_unmounted': True,
               'task_and_control_read_only': True})
    finally:
        try:
            analysis.close()
        finally:
            stop.set()
            thread.join(timeout=15)
            if not bridge.closed:
                bridge.close()
    assert not thread.is_alive() and not errors and bridge.closed
