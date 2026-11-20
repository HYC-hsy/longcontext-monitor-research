"""No-model tests for the optional host-only provider response sidecar."""
import asyncio
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import os

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from provider_response_sidecar import ResponseSidecar, _stream_events


class Chunks(httpx.AsyncByteStream):
    def __init__(self, values):
        self.values = values
        self.reads = 0

    async def __aiter__(self):
        for value in self.values:
            self.reads += 1
            yield value

    async def aclose(self):
        pass


class SidecarTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.private = self.root / 'run' / 'private'
        (self.private / 'archive').mkdir(parents=True)
        self.spool = self.root / 'run' / 'spool'
        self.spool.mkdir()
        self.meta = {'run_id': 'sample-1', 'wake': 20, 'call_sequence': 23,
                     'request_index': 1, 'attempt_in_call': 1,
                     'route_kind': 'anthropic_messages', 'model': 'test-model',
                     'thinking_present': True, 'thinking': {'type': 'adaptive'},
                     'http_status': 200}

    def make_sidecar(self):
        return ResponseSidecar.from_environment(
            {'PMA_PROVIDER_RESPONSE_CAPTURE': '1',
             'PMA_PROVIDER_RESPONSE_CAPTURE_ROOT': str(self.root / 'controlled')},
            run_id='sample-1', private=self.private,
            requests=self.spool / 'requests', responses=self.spool / 'responses')

    def status(self):
        return [json.loads(line) for line in
                (self.private / 'provider_capture_status.jsonl').read_text(
                    encoding='utf-8').splitlines()]

    def test_default_off_and_field_presence(self):
        self.assertIsNone(ResponseSidecar.from_environment(
            {}, run_id='sample-1', private=self.private,
            requests=self.spool / 'requests', responses=self.spool / 'responses'))
        sidecar = self.make_sidecar()
        bodies = [({'id': 'msg-1', 'content': [{'type': 'thinking', 'thinking': 'private'},
                                              {'type': 'tool_use', 'id': 'tool-1'}]}, 'present'),
                  ({'id': 'msg-2', 'content': [{'type': 'tool_use', 'id': 'tool-1'}]}, 'absent'),
                  ({'id': 'msg-3', 'reasoning_content': None}, 'null')]
        for number, (value, state) in enumerate(bodies, 1):
            body = json.dumps(value).encode()
            response = httpx.Response(200, content=body)
            sidecar.capture(response, {**self.meta, 'request_index': number}, stream=False)
            self.assertEqual(response.content, body)
            self.assertEqual(self.status()[-1]['reasoning_field_presence'], state)
            self.assertEqual(Path(self.status()[-1]['body_path']).read_bytes(), body)
        self.assertEqual([row['response_id'] for row in self.status()],
                         ['msg-1', 'msg-2', 'msg-3'])

    def test_retry_association_and_capture_failure_do_not_change_response(self):
        sidecar = self.make_sidecar()
        body = b'{"id":"msg-r","content":[{"type":"tool_use","id":"tool-r"}]}'
        for number in (1, 2):
            response = httpx.Response(200, content=body)
            sidecar.capture(response, {**self.meta, 'request_index': number,
                                       'attempt_in_call': number}, stream=False)
            self.assertEqual(response.json()['content'][0]['id'], 'tool-r')
        self.assertEqual([row['attempt_in_call'] for row in self.status()], [1, 2])
        response = httpx.Response(200, content=body)
        with patch.object(sidecar, '_base', side_effect=OSError('simulated')):
            try:
                sidecar.capture(response, {**self.meta, 'request_index': 3}, stream=False)
            except OSError:
                pass  # The HTTP wrapper catches this and records it separately.
        self.assertEqual(response.content, body)

    def test_stream_preserves_order_and_single_consumption(self):
        async def run():
            chunks = [b'event: a\ndata: {"id":"msg-s",',
                      b'"thinking":"private"}\n\n',
                      b'event: b\ndata: {"content":[]}\n\n']
            source = Chunks(chunks)
            response = httpx.Response(200, stream=source)
            sidecar = self.make_sidecar()
            sidecar.capture(response, self.meta, stream=True)
            output = [part async for part in response.aiter_raw()]
            self.assertEqual(output, chunks)
            self.assertEqual(source.reads, len(chunks))
            self.assertEqual(Path(self.status()[-1]['body_path']).read_bytes(), b''.join(chunks))
            self.assertEqual(self.status()[-1]['events'], len(_stream_events(b''.join(chunks))))
            self.assertEqual(self.status()[-1]['reasoning_field_presence'], 'present')
        asyncio.run(run())

    def test_actual_http_wrapper_on_off_and_capture_error_parity(self):
        async def run():
            base = Path(__file__).resolve().parents[1]
            os.environ['LITELLM_LOCAL_MODEL_COST_MAP'] = 'True'
            sys.path[:0] = [str(base / 'vendor' / 'pma_89e5c0d' / 'src'),
                            str(base / 'vendor' / 'pma_89e5c0d' / 'external' / 'harbor' / 'src')]
            from worker_main import install_http_wire_audit
            original = httpx.AsyncClient.send
            request = {'model': 'test-model', 'thinking': {'type': 'adaptive'},
                       'tools': [{'name': 'memory_read'}]}
            body = b'{"id":"msg-1","content":[{"type":"tool_use","id":"t1","name":"memory_read"}]}'
            seen = []
            def handler(inbound):
                seen.append(inbound.content)
                return httpx.Response(200, content=body)
            async def once(sidecar, archive):
                archive.mkdir(parents=True)
                install_http_wire_audit(archive, {'value': 23, 'wake': 20,
                                                   'run_id': 'sample-1'}, sidecar)
                try:
                    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                        result = await client.post('https://example.invalid/messages', json=request)
                    return result.content, result.json()['content'][0]['id']
                finally:
                    httpx.AsyncClient.send = original
            try:
                off = await once(None, self.root / 'off')
                sidecar = self.make_sidecar()
                on = await once(sidecar, self.root / 'on')
                self.assertEqual(off, on)
                self.assertEqual(seen[0], seen[1])
                self.assertEqual(self.status()[-1]['thinking'], {'type': 'adaptive'})
                with patch.object(sidecar, 'capture', side_effect=OSError('simulated')):
                    failed_capture = await once(sidecar, self.root / 'failed')
                self.assertEqual(off, failed_capture)
                self.assertEqual(self.status()[-1]['capture_status'], 'failed')
            finally:
                httpx.AsyncClient.send = original
        asyncio.run(run())


if __name__ == '__main__':
    unittest.main()
