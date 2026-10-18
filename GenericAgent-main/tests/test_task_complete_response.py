"""Offline native Task complete-response policy; local scripted HTTP only."""
import http.server
import json
import os
import sys
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import llmcore
import agent_loop


def frame(kind, **fields):
    return ('data: ' + json.dumps({'type': kind, **fields}) + '\n\n').encode()


def stream(*, text='', tools=(), stop='tool_use', message_stop=True, done=False,
           open_tool=False, bad_tool=False, malformed=False):
    data = [frame('message_start', message={'usage': {'input_tokens': 2, 'output_tokens': 0}})]
    if text:
        data += [frame('content_block_start', content_block={'type': 'text'}),
                 frame('content_block_delta', delta={'type': 'text_delta', 'text': text}),
                 frame('content_block_stop')]
    for index, name in enumerate(tools):
        data.append(frame('content_block_start', content_block={
            'type': 'tool_use', 'id': f't{index}', 'name': name}))
        data.append(frame('content_block_delta', delta={
            'type': 'input_json_delta', 'partial_json': '{bad' if bad_tool else '{}'}))
        if not open_tool or index < len(tools) - 1:
            data.append(frame('content_block_stop'))
    if malformed: data.append(b'data: {broken\n\n')
    if stop is not None:
        data.append(frame('message_delta', delta={'stop_reason': stop},
                          usage={'output_tokens': 4}))
    if message_stop: data.append(frame('message_stop'))
    if done: data.append(b'data: [DONE]\n\n')
    return b''.join(data)


class ScriptedServer:
    def __init__(self, scripts):
        self.scripts = list(scripts)
        self.payloads = []
        owner = self
        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'
            def log_message(self, *_): pass
            def do_POST(self):
                size = int(self.headers['Content-Length'])
                owner.payloads.append(self.rfile.read(size))
                script = owner.scripts.pop(0)
                if isinstance(script, tuple):
                    pause, script = script
                    time.sleep(pause)
                if isinstance(script, int):
                    self.send_response(script)
                    self.send_header('Content-Length', '0')
                    self.end_headers()
                    return
                if script == 'disconnect':
                    self.close_connection = True
                    return
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.send_header('Content-Length', str(len(script)))
                self.end_headers()
                self.wfile.write(script)
                self.wfile.flush()
        self.httpd = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
    def __enter__(self):
        self.thread.start()
        return self
    def __exit__(self, *_):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=3)
    @property
    def url(self): return f'http://127.0.0.1:{self.httpd.server_port}'


def exhaust(gen):
    chunks = []
    try:
        while True: chunks.append(next(gen))
    except StopIteration as end:
        return chunks, end.value


class CountingHandler(agent_loop.BaseHandler):
    def __init__(self):
        self.parent = SimpleNamespace(task_dir=None)
        self.calls = []
        self._done_hooks = []
    def do_touch(self, args, response):
        self.calls.append(dict(args))
        return agent_loop.StepOutcome('synthetic-result', next_prompt=None)


class CompleteResponseTests(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, {
            'GA_TASK_COMPLETE_RESPONSE': '1',
            'GA_TASK_DEADLINE_EPOCH': str(time.time() + 120),
            'GA_POS_ENABLED': '0', 'GA_PMA_ENABLED': '0',
            'GA_PMA_UPSTREAM_ENABLED': '0', 'GA_MONITOR_ENABLED': '0',
        })
        self.env.start()
        self.events = []
        self.emitter = mock.patch.object(llmcore, '_research_emit', side_effect=self.emit)
        self.emitter.start()
    def tearDown(self):
        self.emitter.stop()
        self.env.stop()
    def emit(self, kind, payload, **kwargs):
        self.events.append((kind, payload))
        return {'event_id': f'e{len(self.events)}'}
    def client(self, url, retries=0):
        cfg = {'apikey': 'synthetic-only', 'apibase': url, 'model': 'claude-synthetic',
               'max_tokens': 100, 'max_retries': retries, 'stream': True,
               'timeout': 1, 'read_timeout': 5}
        backend = llmcore.NativeClaudeSession(cfg)
        client = llmcore.NativeToolClient(backend)
        client.backend.tools = [{'type': 'function', 'function': {
            'name': 'touch', 'description': 'synthetic',
            'parameters': {'type': 'object', 'properties': {}}}}]
        return client
    def direct(self, client, stateless=False):
        if stateless:
            return exhaust(client.backend.ask_stateless({'role': 'user', 'content': [
                {'type': 'text', 'text': 'synthetic'}]}))
        return exhaust(client.backend.ask({'role': 'user', 'content': [
            {'type': 'text', 'text': 'synthetic'}]}))
    def run_loop(self, client):
        handler = CountingHandler()
        result = agent_loop.exhaust(agent_loop.agent_runner_loop(
            client, 'synthetic system', 'synthetic task', handler,
            client.backend.tools, max_turns=1, verbose=False))
        return handler, result

    def test_complete_tool_and_text_commit_once(self):
        for script in (stream(text='done', stop='end_turn'), stream(tools=['touch'])):
            with self.subTest(script=script[-35:]), ScriptedServer([script]) as server:
                client = self.client(server.url)
                handler, _ = self.run_loop(client)
                self.assertEqual(len(handler.calls), int(b'tool_use' in script))
                self.assertEqual(client.backend.last_response_acceptance, 'complete')
                self.assertEqual(len(server.payloads), 1)

    def test_incomplete_never_commits_partial_tool_or_history(self):
        for script in (stream(text='partial', stop=None, message_stop=False),
                       stream(tools=['touch'], open_tool=True, stop=None,
                              message_stop=False),
                       stream(tools=['touch', 'touch'], open_tool=True,
                              stop=None, message_stop=False)):
            with self.subTest(script=script[-35:]), ScriptedServer([script]) as server:
                client = self.client(server.url)
                handler = CountingHandler()
                loop_events = []
                with mock.patch.object(agent_loop, '_research_emit', side_effect=lambda k, *_a, **_kw: loop_events.append(k)), \
                     self.assertRaises(llmcore.TaskResponseRejected):
                    agent_loop.exhaust(agent_loop.agent_runner_loop(
                        client, 'system', 'task', handler, client.backend.tools,
                        max_turns=1, verbose=False))
                self.assertEqual(handler.calls, [])
                self.assertEqual(client.backend.history, [])
                self.assertNotIn('action_selected', loop_events)
                self.assertNotIn('completion_proposal', loop_events)

    def test_retry_same_payload_one_history_commit(self):
        with ScriptedServer([stream(text='partial', stop=None, message_stop=False),
                             stream(tools=['touch'])]) as server:
            client = self.client(server.url, retries=1)
            handler, _ = self.run_loop(client)
            self.assertEqual(len(handler.calls), 1)
            self.assertEqual(len(server.payloads), 2)
            self.assertEqual(server.payloads[0], server.payloads[1])
            self.assertEqual([m['role'] for m in client.backend.history], ['user', 'assistant'])
            self.assertEqual(len([e for e in self.events if e[0] == 'task_response_integrity']), 2)
            self.assertEqual([payload['outcome'] for kind, payload in self.events
                              if kind == 'provider_response'],
                             ['retry_incomplete_stream', 'success'])

    def test_native_stateless_client_path_does_not_create_history(self):
        partial = stream(text='discard me', stop=None, message_stop=False)
        with ScriptedServer([partial, stream(tools=['touch'])]) as server:
            client = self.client(server.url, retries=1)
            _, response = exhaust(client.chat(messages=[], tools=client.backend.tools,
                request_view={'system': 'synthetic PoS decision', 'user': 'current observation'}))
            self.assertTrue(response.complete_response_accepted)
            self.assertEqual(len(response.tool_calls), 1)
            self.assertEqual(client.backend.history, [])
            self.assertEqual(len(server.payloads), 2)
            self.assertEqual(server.payloads[0], server.payloads[1])

    def test_pos_decision_view_occurs_once_across_retry(self):
        import pos_bridge
        class Bridge:
            def __init__(self): self.calls = []; self.closed = False
            def exchange(self, kind, **kwargs):
                self.calls.append(kind)
                if kind == 'decision_view':
                    return {'system': 'synthetic PoS view', 'user': 'synthetic observation'}
                return {}
            def record_host(self, *_): pass
            def close(self): self.closed = True
        partial = stream(text='discard', stop=None, message_stop=False)
        with ScriptedServer([partial, stream(tools=['touch'])]) as server:
            bridge = Bridge()
            client = self.client(server.url, retries=1)
            with mock.patch.dict(os.environ, {'GA_POS_ENABLED': '1'}), \
                 mock.patch.object(pos_bridge.PoSBridge, 'from_environment', return_value=bridge):
                handler, _ = self.run_loop(client)
            self.assertEqual(len(handler.calls), 1)
            self.assertEqual(bridge.calls.count('reset'), 1)
            self.assertEqual(bridge.calls.count('decision_view'), 1)
            self.assertEqual(len(server.payloads), 2)
            self.assertEqual(server.payloads[0], server.payloads[1])
        with ScriptedServer([partial]) as server:
            bridge = Bridge()
            client = self.client(server.url, retries=0)
            with mock.patch.dict(os.environ, {'GA_POS_ENABLED': '1'}), \
                 mock.patch.object(pos_bridge.PoSBridge, 'from_environment', return_value=bridge), \
                 self.assertRaises(llmcore.TaskResponseRejected):
                self.run_loop(client)
            self.assertEqual(bridge.calls.count('decision_view'), 1)
            self.assertNotIn('decision_completed', bridge.calls)
            self.assertNotIn('update', bridge.calls)

    def test_failed_task_response_does_not_send_pma_actor_step(self):
        import pma_upstream_bridge
        class PMA:
            def __init__(self): self.before = 0; self.actor = 0
            def before_actor_call(self, turn): self.before += 1; return None
            def actor_step(self, *_args, **_kwargs): self.actor += 1
        partial = stream(text='discard', stop=None, message_stop=False)
        with ScriptedServer([partial]) as server:
            pma = PMA()
            client = self.client(server.url, retries=0)
            with mock.patch.dict(os.environ, {'GA_PMA_UPSTREAM_ENABLED': '1'}), \
                 mock.patch.object(pma_upstream_bridge.UpstreamPMAClient,
                                   'from_environment', return_value=pma), \
                 self.assertRaises(llmcore.TaskResponseRejected):
                self.run_loop(client)
            self.assertEqual(pma.before, 1)
            self.assertEqual(pma.actor, 0)

    def test_five_attempts_shared_budget(self):
        partial = stream(text='partial', stop=None, message_stop=False)
        with ScriptedServer([503, 'disconnect', partial, partial, partial]) as server:
            client = self.client(server.url, retries=4)
            with self.assertRaises(llmcore.TaskResponseRejected): self.direct(client)
            self.assertEqual(len(server.payloads), 5)
            self.assertEqual(client.backend.history, [])

    def test_stop_only_and_rejections(self):
        scenarios = [
            (stream(text='okay', message_stop=False), None),
            (stream(tools=['touch'], open_tool=True, message_stop=False), 'incomplete_stream'),
            (stream(tools=['touch'], stop='max_tokens'), 'token_limit'),
            (stream(tools=['touch'], open_tool=True, stop='max_tokens'), 'token_limit'),
            (stream(tools=['touch'], bad_tool=True), 'invalid_tool_arguments'),
            (stream(text='x', malformed=True), 'invalid_frame'),
            (frame('SYNTHETIC_SECRET_EVENT') + stream(text='x'), 'invalid_frame'),
            (frame('message_start', message={'usage': {}}) +
             frame('error', error={'message': 'synthetic error'}), 'provider_error'),
        ]
        for script, expected in scenarios:
            with self.subTest(expected=expected), ScriptedServer([script]) as server:
                client = self.client(server.url)
                if expected is None:
                    _, response = self.direct(client, stateless=True)
                    self.assertTrue(response.complete_response_accepted)
                else:
                    with self.assertRaises(llmcore.TaskResponseRejected) as error:
                        self.direct(client, stateless=True)
                    self.assertEqual(error.exception.category, expected)
                self.assertEqual(len(server.payloads), 1)

    def test_token_limit_and_invalid_tool_never_dispatch(self):
        for script, category in ((stream(tools=['touch'], stop='max_tokens'), 'token_limit'),
                                 (stream(tools=['touch'], bad_tool=True), 'invalid_tool_arguments')):
            with self.subTest(category=category), ScriptedServer([script]) as server:
                client = self.client(server.url, retries=4)
                handler = CountingHandler()
                with self.assertRaises(llmcore.TaskResponseRejected) as error:
                    agent_loop.exhaust(agent_loop.agent_runner_loop(
                        client, 'system', 'task', handler, client.backend.tools,
                        max_turns=1, verbose=False))
                self.assertEqual(error.exception.category, category)
                self.assertEqual(handler.calls, [])
                self.assertEqual(client.backend.history, [])
                self.assertEqual(len(server.payloads), 1)

    def test_nonretry_http_and_deadline(self):
        with ScriptedServer([401]) as server:
            client = self.client(server.url, retries=4)
            with self.assertRaises(llmcore.TaskResponseRejected) as error:
                self.direct(client)
            self.assertEqual(error.exception.category, 'http_error')
            self.assertEqual(len(server.payloads), 1)
        with mock.patch.dict(os.environ, {'GA_TASK_DEADLINE_EPOCH': str(time.time() + 0.05)}), \
             ScriptedServer([(0.2, stream(tools=['touch']))]) as server:
            client = self.client(server.url, retries=4)
            with self.assertRaises(llmcore.TaskResponseRejected) as error:
                self.direct(client)
            self.assertEqual(error.exception.category, 'task_deadline')
            self.assertEqual(len(server.payloads), 1)
            self.assertEqual(client.backend.history, [])

    def test_cancel_before_send_and_during_backoff(self):
        with ScriptedServer([]) as server:
            client = self.client(server.url, retries=4)
            client.backend._cancel_response.set()
            with self.assertRaises(llmcore.ProviderResponseCancelled):
                self.direct(client)
            self.assertEqual(len(server.payloads), 0)
        partial = stream(text='partial', stop=None, message_stop=False)
        with ScriptedServer([partial]) as server:
            client = self.client(server.url, retries=4)
            def emit_and_cancel(kind, payload, **kwargs):
                if kind == 'provider_response' and payload.get('outcome') == 'retry_incomplete_stream':
                    client.backend._cancel_response.set()
                return self.emit(kind, payload, **kwargs)
            with mock.patch.object(llmcore, '_research_emit', side_effect=emit_and_cancel), \
                 self.assertRaises(llmcore.ProviderResponseCancelled):
                self.direct(client)
            self.assertEqual(len(server.payloads), 1)
            self.assertEqual(client.backend.history, [])

    def test_capture_failure_no_retry(self):
        original = self.emit
        def fail_content(kind, payload, **kwargs):
            if kind == 'provider_response_content': return None
            return original(kind, payload, **kwargs)
        with mock.patch.dict(os.environ, {'GA_PMA_CAPTURE_TASK_REQUESTS': '1'}), \
             mock.patch.object(llmcore, '_research_emit', side_effect=fail_content), \
             ScriptedServer([stream(tools=['touch'])]) as server:
            client = self.client(server.url, retries=4)
            with self.assertRaises(llmcore.TaskResponseRejected) as error:
                self.direct(client)
            self.assertEqual(error.exception.category, 'capture_failed')
            self.assertEqual(len(server.payloads), 1)
            self.assertEqual(client.backend.history, [])
            self.assertTrue(client.backend._research_capture_failed)

    def test_required_request_capture_fails_before_send(self):
        with mock.patch.object(llmcore, '_research_emit', return_value=None), \
             ScriptedServer([]) as server:
            client = self.client(server.url, retries=4)
            with self.assertRaises(RuntimeError): self.direct(client)
            self.assertEqual(server.payloads, [])
            self.assertEqual(client.backend.history, [])

    def test_diagnostic_excludes_hidden_content_and_endpoint(self):
        secret = 'SYNTHETIC_HIDDEN_SECRET_DO_NOT_ARCHIVE'
        script = (frame('message_start', message={'usage': {'input_tokens': 1}}) +
                  frame('content_block_start', content_block={'type': 'thinking'}) +
                  frame('content_block_delta', delta={'type': 'thinking_delta', 'thinking': secret}) +
                  frame('content_block_stop') +
                  frame('content_block_start', content_block={'type': 'text'}) +
                  frame('content_block_delta', delta={'type': 'text_delta', 'text': 'public'}) +
                  frame('content_block_stop') +
                  frame('message_delta', delta={'stop_reason': 'end_turn'}, usage={'output_tokens': 3}) +
                  frame('message_stop'))
        with ScriptedServer([script]) as server:
            client = self.client(server.url)
            _, response = self.direct(client, stateless=True)
            self.assertEqual(response.content, 'public')
            diagnostics = [payload for kind, payload in self.events
                           if kind == 'task_response_integrity']
            self.assertEqual(len(diagnostics), 1)
            encoded = json.dumps(diagnostics[0])
            self.assertNotIn(secret, encoded)
            self.assertNotIn(server.url, encoded)
            self.assertEqual(diagnostics[0]['category'], 'complete')

    def test_default_off_and_auxiliary_unaffected(self):
        with mock.patch.dict(os.environ, {'GA_TASK_COMPLETE_RESPONSE': '0'}), \
             ScriptedServer([stream(text='partial', stop=None, message_stop=False)]) as server:
            client = self.client(server.url)
            _, response = self.direct(client)
            self.assertFalse(response.complete_response_accepted)
            self.assertIn('partial', response.content)
        aux = llmcore.NativeClaudeSession({'apikey': 'synthetic', 'apibase': 'http://127.0.0.1:1',
                                           'model': 'claude-synthetic'})
        self.assertFalse(getattr(aux, 'task_complete_response', False))


if __name__ == '__main__': unittest.main(verbosity=2)
