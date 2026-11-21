"""No-model tests for the optional host-only provider response sidecar."""
import asyncio
from contextvars import ContextVar
import json
from pathlib import Path
from types import SimpleNamespace
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
                                              {'type': 'tool_use', 'id': 'tool-1'}]}, 'readable_text'),
                  ({'id': 'msg-2', 'content': [{'type': 'thinking', 'thinking': '',
                                               'signature': 'signed'}]}, 'empty_text_signed'),
                  ({'id': 'msg-3', 'content': [{'type': 'redacted_thinking',
                                               'data': 'opaque'}]}, 'unreadable_block'),
                  ({'id': 'msg-4', 'reasoning_content': None}, 'explicit_null'),
                  ({'id': 'msg-5', 'content': [{'type': 'tool_use', 'id': 'tool-1',
                                               'input': {'thinking': 'not reasoning',
                                                         'signature': 'tool data'}}]}, 'not_returned')]
        for number, (value, state) in enumerate(bodies, 1):
            body = json.dumps(value).encode()
            response = httpx.Response(200, content=body)
            sidecar.capture(response, {**self.meta, 'request_index': number}, stream=False)
            self.assertEqual(response.content, body)
            self.assertEqual(self.status()[-1]['reasoning_record_kind'], state)
            self.assertEqual(Path(self.status()[-1]['body_path']).read_bytes(), body)
        self.assertEqual([row['response_id'] for row in self.status()],
                         ['msg-1', 'msg-2', 'msg-3', 'msg-4', 'msg-5'])

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
            chunks = [b'event: content_block_delta\ndata: {"type":"content_block_delta",',
                      b'"delta":{"type":"thinking_delta","thinking":"private"}}\n\n',
                      b'event: message_stop\ndata: {"type":"message_stop"}\n\n']
            source = Chunks(chunks)
            response = httpx.Response(200, stream=source)
            sidecar = self.make_sidecar()
            sidecar.capture(response, self.meta, stream=True)
            output = [part async for part in response.aiter_raw()]
            self.assertEqual(output, chunks)
            self.assertEqual(source.reads, len(chunks))
            self.assertEqual(Path(self.status()[-1]['body_path']).read_bytes(), b''.join(chunks))
            self.assertEqual(self.status()[-1]['events'], len(_stream_events(b''.join(chunks))))
            self.assertEqual(self.status()[-1]['reasoning_record_kind'], 'readable_text')
            self.assertEqual(self.status()[-1]['stream_termination'], 'normal_termination')
        asyncio.run(run())

    def test_stream_error_and_interruption_are_not_success(self):
        async def run():
            existing = self.make_sidecar()
            for ordinal, chunks, expected in (
                (1, [b'event: error\ndata: {"type":"error"}\n\n'], 'stream_error'),
                (2, [b'event: message_delta\ndata: {"type":"message_delta"}\n\n'], 'interrupted')):
                response = httpx.Response(200, stream=Chunks(chunks))
                existing.capture(response, {**self.meta, 'request_index': ordinal}, stream=True)
                self.assertEqual([part async for part in response.aiter_raw()], chunks)
                self.assertEqual(self.status()[-1]['stream_termination'], expected)
                self.assertEqual(self.status()[-1]['capture_status'], 'complete')
                self.assertEqual(self.status()[-1]['reasoning_record_kind'], 'unknown')
            response = httpx.Response(200, stream=Chunks([
                b'event: message_start\ndata: {"type":"message_start"}\n\n',
                b'event: message_stop\ndata: {"type":"message_stop"}\n\n']))
            existing.capture(response, {**self.meta, 'request_index': 3}, stream=True)
            iterator = response.stream.__aiter__()
            await anext(iterator)
            await iterator.aclose()
            self.assertEqual(self.status()[-1]['stream_termination'], 'interrupted')
            self.assertEqual(self.status()[-1]['capture_status'], 'incomplete')
        asyncio.run(run())

    def test_stream_empty_signed_block(self):
        async def run():
            sidecar = self.make_sidecar()
            chunks = [
                b'event: content_block_start\ndata: {"type":"content_block_start","content_block":{"type":"thinking","thinking":""}}\n\n',
                b'event: content_block_delta\ndata: {"type":"content_block_delta","delta":{"type":"signature_delta","signature":"signed"}}\n\n',
                b'event: message_stop\ndata: {"type":"message_stop"}\n\n',
            ]
            response = httpx.Response(200, stream=Chunks(chunks))
            sidecar.capture(response, self.meta, stream=True)
            self.assertEqual([x async for x in response.aiter_raw()], chunks)
            self.assertEqual(self.status()[-1]['reasoning_record_kind'], 'empty_text_signed')
            self.assertEqual(self.status()[-1]['stream_termination'], 'normal_termination')
        asyncio.run(run())

    def test_same_route_requires_manager_owner_task(self):
        async def run():
            base = Path(__file__).resolve().parents[1]
            os.environ['LITELLM_LOCAL_MODEL_COST_MAP'] = 'True'
            sys.path[:0] = [str(base / 'vendor' / 'pma_89e5c0d' / 'src'),
                            str(base / 'vendor' / 'pma_89e5c0d' / 'external' / 'harbor' / 'src')]
            from worker_main import install_http_wire_audit
            original = httpx.AsyncClient.send
            scope = ContextVar('owner_scope', default=None)
            sidecar = self.make_sidecar()
            archive = self.root / 'scope_archive'
            archive.mkdir()
            install_http_wire_audit(archive, {'value': 7, 'wake': 20,
                                              'run_id': 'sample-1',
                                              'capture_context': scope}, sidecar)
            body = b'{"id":"msg-scope","content":[{"type":"text","text":"ok"}]}'
            manager_entered = asyncio.Event()
            unrelated_finished = asyncio.Event()
            async def handler(request):
                kind = json.loads(request.content)['source']
                if kind == 'manager':
                    manager_entered.set()
                    await unrelated_finished.wait()
                elif kind == 'unrelated':
                    await manager_entered.wait()
                    unrelated_finished.set()
                return httpx.Response(200, content=body)
            try:
                async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                    async def send(source):
                        return (await client.post('https://example.invalid/messages',
                                                  json={'model': 'test-model',
                                                        'source': source})).content
                    self.assertEqual(await send('idle'), body)  # No active manager call.
                    self.assertFalse((self.private / 'provider_capture_status.jsonl').exists())
                    token = scope.set({'owner_task': asyncio.current_task(),
                                       'call_sequence': 7, 'wake': 20})
                    try:
                        unrelated = asyncio.create_task(send('unrelated'))  # Inherits context.
                        self.assertEqual(await send('manager'), body)  # Requests overlap.
                        self.assertEqual(await unrelated, body)
                        self.assertEqual(await send('manager'), body)  # Next HTTP attempt.
                    finally:
                        scope.reset(token)
                rows = self.status()
                self.assertEqual(len(rows), 2)
                self.assertEqual((rows[0]['run_id'], rows[0]['wake'],
                                  rows[0]['call_sequence'], rows[0]['attempt_in_call']),
                                 ('sample-1', 20, 7, 1))
                self.assertIn(rows[0]['request_index'], (2, 3))
                self.assertEqual((rows[1]['request_index'], rows[1]['attempt_in_call']),
                                 (4, 2))
            finally:
                httpx.AsyncClient.send = original
        asyncio.run(run())

    def test_transport_exception_and_capture_failures_preserve_retry_and_receipt(self):
        async def run():
            base = Path(__file__).resolve().parents[1]
            os.environ['LITELLM_LOCAL_MODEL_COST_MAP'] = 'True'
            sys.path[:0] = [str(base / 'vendor' / 'pma_89e5c0d' / 'src'),
                            str(base / 'vendor' / 'pma_89e5c0d' / 'external' / 'harbor' / 'src')]
            from worker_main import install_http_wire_audit
            original = httpx.AsyncClient.send
            body = b'{"id":"msg-retry","content":[{"type":"tool_use","id":"tool-1","name":"memory_read"}]}'
            async def scenario(sidecar, name):
                scope = ContextVar(name, default=None)
                archive = self.root / name
                archive.mkdir()
                install_http_wire_audit(archive, {'value': 23, 'wake': 20,
                                                   'run_id': 'sample-1',
                                                   'capture_context': scope}, sidecar)
                attempts = 0
                def handler(request):
                    nonlocal attempts
                    attempts += 1
                    if attempts == 1:
                        raise httpx.ConnectError('original transport failure')
                    return httpx.Response(200, content=body)
                try:
                    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                        token = scope.set({'owner_task': asyncio.current_task(),
                                           'call_sequence': 23, 'wake': 20})
                        try:
                            try:
                                await client.post('https://example.invalid/messages',
                                                  json={'model': 'test-model'})
                            except httpx.ConnectError as exc:
                                failure = str(exc)
                            else:
                                self.fail('original exception was swallowed')
                            result = await client.post('https://example.invalid/messages',
                                                       json={'model': 'test-model'})
                        finally:
                            scope.reset(token)
                    return failure, attempts, result.content, result.json()['content'][0]['id']
                finally:
                    httpx.AsyncClient.send = original
            off = await scenario(None, 'retry_off')
            sidecar = self.make_sidecar()
            with (patch.object(sidecar, '_status', side_effect=OSError('capture status fails')),
                  patch.object(sidecar, 'capture', side_effect=OSError('capture body fails'))):
                on = await scenario(sidecar, 'retry_on')
            self.assertEqual(off, on)
        asyncio.run(run())

    def test_stream_write_failure_preserves_bytes(self):
        class FailingFile:
            def __init__(self, original):
                self.original = original
            def write(self, data):
                raise OSError('capture disk failure')
            def flush(self):
                return self.original.flush()
            def fileno(self):
                return self.original.fileno()
            def close(self):
                return self.original.close()
        async def run():
            chunks = [b'event: message_start\ndata: {"type":"message_start"}\n\n',
                      b'event: message_stop\ndata: {"type":"message_stop"}\n\n']
            source = Chunks(chunks)
            sidecar = self.make_sidecar()
            response = httpx.Response(200, stream=source)
            sidecar.capture(response, self.meta, stream=True)
            writer = response.stream.writer
            writer.file = FailingFile(writer.file)
            self.assertEqual([x async for x in response.aiter_raw()], chunks)
            self.assertEqual(source.reads, len(chunks))
            self.assertEqual(self.status()[-1]['capture_status'], 'incomplete')
        asyncio.run(run())

    def test_manager_transport_scope_and_existing_mandatory_audit_failure(self):
        async def run():
            base = Path(__file__).resolve().parents[1]
            os.environ['LITELLM_LOCAL_MODEL_COST_MAP'] = 'True'
            sys.path[:0] = [str(base / 'vendor' / 'pma_89e5c0d' / 'src'),
                            str(base / 'vendor' / 'pma_89e5c0d' / 'external' / 'harbor' / 'src')]
            import worker_main
            original_send = httpx.AsyncClient.send
            body = b'{"id":"msg-manager","content":[{"type":"tool_use","id":"t1"}]}'
            async def model_call(**kwargs):
                async with httpx.AsyncClient(transport=httpx.MockTransport(
                        lambda request: httpx.Response(200, content=body))) as client:
                    response = await client.post('https://example.invalid/messages',
                                                 json={'model': 'test-model'})
                return SimpleNamespace(content=response.json()['content'], tool_calls=[])
            agent = SimpleNamespace(
                _memory_llm=SimpleNamespace(call=model_call),
                _memory_agent=SimpleNamespace(_step=20, _history_transforms=[]),
                _research_candidate='not_read_context')
            archive = self.root / 'manager_archive'
            archive.mkdir()
            sidecar = self.make_sidecar()
            context = worker_main.install_transport_audit(agent, archive)
            context['run_id'] = 'sample-1'
            worker_main.install_http_wire_audit(archive, context, sidecar)
            try:
                result = await agent._memory_llm.call(prompt='task', system='system')
                self.assertEqual(result.content[0]['id'], 't1')
                self.assertEqual(self.status()[0]['call_sequence'], 1)
                self.assertEqual(self.status()[0]['wake'], 20)
                self.assertIsNone(context['capture_context'].get())
            finally:
                httpx.AsyncClient.send = original_send

            async def mandatory_failure(enabled):
                scope = ContextVar('mandatory_scope', default=None)
                archive_dir = self.root / ('mandatory_on' if enabled else 'mandatory_off')
                archive_dir.mkdir()
                worker_main.install_http_wire_audit(archive_dir, {
                    'value': 2, 'wake': 20, 'run_id': 'sample-1',
                    'capture_context': scope}, sidecar if enabled else None)
                try:
                    async with httpx.AsyncClient(transport=httpx.MockTransport(
                            lambda request: httpx.Response(200, content=body))) as client:
                        token = scope.set({'owner_task': asyncio.current_task(),
                                           'call_sequence': 2, 'wake': 20})
                        try:
                            with patch.object(worker_main, 'append_private_audit',
                                              side_effect=worker_main.PMAAuditIntegrityError('mandatory')):
                                try:
                                    await client.post('https://example.invalid/messages',
                                                      json={'model': 'test-model'})
                                except BaseException as exc:
                                    return type(exc).__name__, str(exc)
                        finally:
                            scope.reset(token)
                finally:
                    httpx.AsyncClient.send = original_send
            self.assertEqual(await mandatory_failure(False), await mandatory_failure(True))
        asyncio.run(run())

    def test_actual_http_wrapper_on_off_and_capture_error_parity(self):
        async def run():
            base = Path(__file__).resolve().parents[1]
            os.environ['LITELLM_LOCAL_MODEL_COST_MAP'] = 'True'
            sys.path[:0] = [str(base / 'vendor' / 'pma_89e5c0d' / 'src'),
                            str(base / 'vendor' / 'pma_89e5c0d' / 'external' / 'harbor' / 'src')]
            from worker_main import install_http_wire_audit
            original = httpx.AsyncClient.send
            scope = ContextVar('test_manager_scope', default=None)
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
                                                   'run_id': 'sample-1',
                                                   'capture_context': scope}, sidecar)
                try:
                    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                        token = scope.set({'owner_task': asyncio.current_task(),
                                           'call_sequence': 23, 'wake': 20})
                        try:
                            result = await client.post('https://example.invalid/messages', json=request)
                        finally:
                            scope.reset(token)
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
