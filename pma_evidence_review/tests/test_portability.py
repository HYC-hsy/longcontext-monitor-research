"""UTF-8 I/O and simulated Windows wakeup guard; not a native Windows run."""
import asyncio
import json
import socket
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from pma_evidence_review.inputs import digest
from pma_evidence_review.tests import no_network
from pma_evidence_review.transport import CapturedTransport, FakeClient, load_profile_client


class PortabilityTests(unittest.TestCase):
    def test_utf8_durable_capture_roundtrip(self):
        no_network.install_guard(self)
        response = json.dumps({'explanation': '证据不足；路径：目录/报告.txt',
                               'verdict': 'NOT_ENOUGH_INFO', 'evidence': []},
                              ensure_ascii=False)
        payload = {'system': '只审查证据，不执行命令。',
                   'prompt': '原任务：构建工具。观察：完成 ✓', 'tools': None}
        identity = digest(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')))
        request = dict(payload, phase='verify', audit_request_sha256=identity,
                       evidence_policy='source-use-v3')
        with tempfile.TemporaryDirectory() as directory:
            client = FakeClient([response])
            transport = CapturedTransport(client, directory, fake=True)
            self.assertEqual(asyncio.run(transport.send(request)), response)
            request_bytes = Path(directory, 'requests.jsonl').read_bytes()
            response_bytes = Path(directory, 'responses.jsonl').read_bytes()
            self.assertIn('原任务'.encode('utf-8'), request_bytes)
            self.assertIn('证据不足'.encode('utf-8'), response_bytes)
            recorded_request = json.loads(request_bytes.decode('utf-8'))
            recorded_response = json.loads(response_bytes.decode('utf-8'))
            self.assertEqual(recorded_request['request'], payload)
            self.assertEqual(recorded_request['audit_request_sha256'], identity)
            self.assertEqual(recorded_response['response'], response)
            self.assertEqual(recorded_response['status'], 'returned')

    def test_utf8_profile_mock_factory_only(self):
        no_network.install_guard(self)
        fake = FakeClient([])
        calls = []
        module = types.ModuleType('episode')
        def construct(logs_dir, *, memory_profile):
            calls.append((logs_dir, memory_profile))
            return types.SimpleNamespace(_memory_llm=fake)
        module.construct_upstream = construct
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory, '配置.json')
            profile.write_text(json.dumps({'测试': {'model': '离线模拟',
                'apikey': 'synthetic-not-a-credential'}}, ensure_ascii=False), encoding='utf-8')
            oldpath = list(sys.path)
            try:
                with patch.dict(sys.modules, {'episode': module}):
                    client = load_profile_client('.', profile, '测试',
                        Path(directory, '日志'), authorized=True)
            finally:
                sys.path[:] = oldpath
            self.assertIs(client, fake)
            self.assertEqual(calls[0][1]['model'], '离线模拟')
            self.assertEqual(len(calls), 1)
            self.assertEqual(fake.calls, [])

    def test_windows_socketpair_guard_branch_without_sockets(self):
        # No socket is created. The saved connect implementation is a local spy,
        # and only the simulated CPython fallback's stack frame is exempted.
        connected = []
        def local_connect(sock, address):
            connected.append(address)
            return 'local-wakeup-only'
        def fallback(sock):
            return socket.socket.connect(sock, ('127.0.0.1', 12345))
        probe = unittest.TestCase()
        with patch.object(socket.socket, 'connect', new=local_connect), \
             patch.object(socket, '_fallback_socketpair', new=fallback, create=True), \
             patch.object(no_network.os, 'name', 'nt'):
            no_network.install_guard(probe)
            try:
                self.assertEqual(fallback(object()), 'local-wakeup-only')
                self.assertEqual(connected, [('127.0.0.1', 12345)])
            finally:
                self.assertTrue(probe.doCleanups())


if __name__ == '__main__':
    unittest.main()
