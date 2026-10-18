"""Synthetic, zero-network tests of the deployed Task SSE/parser/classifier path."""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


# These are retained packed bytes, not the current checkout or a PoS role caller.
STAGE = Path('E:/LongContext/pos_retry_two_20261018_v1/01_adaptive-rejection-sampler'
             '/runs/pos-7c969aa45b944db5/control/ga_stage')
sys.path.insert(0, str(STAGE))
import llmcore  # noqa: E402
import agent_loop  # noqa: E402


def frame(event):
    return b'data: ' + json.dumps(event, separators=(',', ':')).encode('utf-8')


START = frame({'type': 'message_start', 'message': {'usage': {
    'input_tokens': 3, 'output_tokens': 0}}})
TEXT_START = frame({'type': 'content_block_start', 'content_block': {'type': 'text'}})
TEXT = frame({'type': 'content_block_delta', 'delta': {
    'type': 'text_delta', 'text': 'synthetic public text'}})
BLOCK_STOP = frame({'type': 'content_block_stop'})
TOOL_START = frame({'type': 'content_block_start', 'content_block': {
    'type': 'tool_use', 'id': 'synthetic-t1', 'name': 'synthetic_tool'}})
TOOL_INPUT = frame({'type': 'content_block_delta', 'delta': {
    'type': 'input_json_delta', 'partial_json': '{"value":1}'}})
END = frame({'type': 'message_stop'})


class FakeResponse:
    status_code = 200
    headers = {'Content-Type': 'text/event-stream'}

    def __init__(self, lines):
        self.lines = lines
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        self.closed = True

    def iter_lines(self):
        yield from self.lines


def exhaust(generator):
    displayed = []
    try:
        while True:
            displayed.append(next(generator))
    except StopIteration as done:
        return displayed, done.value


def synthetic_call(lines):
    cfg = {'apikey': 'synthetic-only', 'apibase': 'https://synthetic.invalid',
           'model': 'claude-opus-4-8', 'stream': True,
           'thinking_type': 'adaptive', 'max_tokens': 64000,
           'max_retries': 4, 'timeout': 60, 'read_timeout': 300}
    session = llmcore.NativeClaudeSession(cfg)
    session.tools = [{'name': 'synthetic_tool', 'description': 'synthetic',
                      'input_schema': {'type': 'object', 'properties': {
                          'value': {'type': 'integer'}}}}]
    calls = []

    def fake_post(*args, **kwargs):
        calls.append({'stream': kwargs['stream'], 'timeout': kwargs['timeout']})
        return FakeResponse(lines)

    with patch.object(llmcore.requests, 'post', side_effect=fake_post), \
         contextlib.redirect_stdout(io.StringIO()):
        displayed, response = exhaust(session.ask_stateless(
            {'role': 'user', 'content': [{'type': 'text', 'text': 'synthetic'}]}))
    return {'displayed_count': len(displayed), 'content': response.content,
            'tool_count': len(response.tool_calls),
            'provider_error_classifier': agent_loop._is_provider_error_response(response),
            'attempts': len(calls), 'transport': calls}


def synthetic_dispatch(lines):
    """Use the actual GA loop with a harmless local tool, never a Task tool."""
    cfg = {'apikey': 'synthetic-only', 'apibase': 'https://synthetic.invalid',
           'model': 'claude-opus-4-8', 'stream': True, 'max_retries': 4,
           'timeout': 60, 'read_timeout': 300}
    session = llmcore.NativeClaudeSession(cfg)
    session.tools = [{'name': 'synthetic_tool', 'description': 'synthetic',
                      'input_schema': {'type': 'object', 'properties': {
                          'value': {'type': 'integer'}}}}]
    attempts = []

    def fake_post(*args, **kwargs):
        attempts.append(1)
        return FakeResponse(lines)

    class Client:
        last_tools = ''

        def chat(self, **kwargs):
            return (yield from session.ask_stateless(
                {'role': 'user', 'content': [{'type': 'text', 'text': 'synthetic'}]}))

    class Handler(agent_loop.BaseHandler):
        parent = SimpleNamespace(task_dir='', research_condition=None,
                                 monitor_runtime=None)
        _done_hooks = []

        def __init__(self):
            self.executions = 0

        def do_synthetic_tool(self, args, response):
            self.executions += 1
            return agent_loop.StepOutcome('synthetic result', next_prompt='')

    handler = Handler()
    with patch.object(llmcore.requests, 'post', side_effect=fake_post), \
         patch.dict(os.environ, {'GA_POS_ENABLED': '0',
                                 'GA_PMA_UPSTREAM_ENABLED': '0',
                                 'GA_PMA_ENABLED': '0',
                                 'GA_MONITOR_ENABLED': '0'}), \
         contextlib.redirect_stdout(io.StringIO()):
        _, final = exhaust(agent_loop.agent_runner_loop(
            Client(), 'synthetic system', 'synthetic task', handler,
            session.tools, max_turns=1, verbose=False))
    return {'attempts': len(attempts), 'tool_executions': handler.executions,
            'terminal': final['result']}


class SyntheticTaskSSE(unittest.TestCase):
    def test_complete_text_and_tool(self):
        lines = [START, TEXT_START, TEXT, BLOCK_STOP, TOOL_START, TOOL_INPUT,
                 BLOCK_STOP, frame({'type': 'message_delta', 'delta': {
                     'stop_reason': 'tool_use'}, 'usage': {'output_tokens': 9}}), END]
        result = synthetic_call(lines)
        self.assertEqual((result['attempts'], result['tool_count']), (1, 1))
        self.assertFalse(result['provider_error_classifier'])

    def test_body_then_eof_without_terminal_marker(self):
        result = synthetic_call([START, TEXT_START, TEXT, BLOCK_STOP])
        self.assertEqual(result['attempts'], 1)
        self.assertIn('[!!! 流异常中断', result['content'])
        self.assertTrue(result['provider_error_classifier'])
        self.assertEqual(result['tool_count'], 0)

    def test_partial_tool_then_eof(self):
        result = synthetic_call([START, TOOL_START, TOOL_INPUT])
        self.assertEqual(result['attempts'], 1)
        self.assertTrue(result['provider_error_classifier'])
        # Parsing still returns the tool block; this classifier alone does not
        # remove it. Production dispatch risk is reported, not silently fixed.
        self.assertEqual(result['tool_count'], 1)

    def test_partial_tool_dispatch_is_not_suppressed_by_classifier(self):
        result = synthetic_dispatch([START, TOOL_START, TOOL_INPUT])
        self.assertEqual(result['attempts'], 1)
        self.assertEqual(result['tool_executions'], 1)
        self.assertEqual(result['terminal'], 'PROVIDER_FAILURE')

    def test_explicit_sse_error(self):
        result = synthetic_call([START, frame({'type': 'error', 'error': {
            'message': 'synthetic upstream error'}})])
        self.assertEqual(result['attempts'], 1)
        self.assertTrue(result['provider_error_classifier'])
        self.assertEqual(result['tool_count'], 0)

    def test_max_tokens(self):
        result = synthetic_call([START, TEXT_START, TEXT, BLOCK_STOP,
            frame({'type': 'message_delta', 'delta': {'stop_reason': 'max_tokens'},
                   'usage': {'output_tokens': 12}}), END])
        self.assertEqual(result['attempts'], 1)
        self.assertIn('Response truncated: max_tokens', result['content'])
        self.assertFalse(result['provider_error_classifier'])

    def test_malformed_and_multiline_data_are_not_reassembled(self):
        result = synthetic_call([START, b'data: {bad-json}',
            b'data: {"type":"message_delta",',
            b'data: "delta":{"stop_reason":"end_turn"}}',
            TEXT_START, TEXT, BLOCK_STOP])
        self.assertEqual(result['attempts'], 1)
        self.assertTrue(result['provider_error_classifier'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
