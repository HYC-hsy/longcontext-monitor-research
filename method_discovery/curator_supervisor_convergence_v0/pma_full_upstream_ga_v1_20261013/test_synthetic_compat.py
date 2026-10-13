"""No-network exercise of the actual synthetic request serialization paths."""

import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from . import synthetic_compat


class FakeResponse:
    status_code = 200
    headers = {}
    text = ''

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def close(self):
        pass

    def iter_lines(self):
        events = [
            {'type': 'message_start', 'message': {'usage': {'input_tokens': 1}}},
            {'type': 'content_block_start', 'content_block': {'type': 'text'}},
            {'type': 'content_block_delta', 'delta': {'type': 'text_delta',
                                                      'text': 'synthetic reply'}},
            {'type': 'content_block_stop'},
            {'type': 'message_delta', 'delta': {'stop_reason': 'end_turn'},
             'usage': {'output_tokens': 2}},
            {'type': 'message_stop'},
        ]
        for event in events:
            yield ('data: ' + json.dumps(event)).encode()


class SyntheticCompatTests(unittest.TestCase):
    def test_task_uses_native_ga_serializer_once_without_tool_execution(self):
        import llmcore
        with TemporaryDirectory() as directory:
            root = Path(directory)
            profile = root / 'task_profile.py'
            profile.write_text("native_claude_cc_vibe_opus48 = " + repr(dict(
                apikey='offline', apibase='https://offline.invalid/v1',
                model='claude-opus-4-8', max_tokens=64000, temperature=1,
                thinking_type='adaptive', reasoning_effort='high',
                max_retries=4, stream=True)), encoding='utf-8')
            calls = []

            def fake_post(_url, **kwargs):
                calls.append(kwargs)
                return FakeResponse()

            with patch.object(llmcore.requests, 'post', side_effect=fake_post):
                result = synthetic_compat._task_check(root, profile)
            self.assertEqual(result['actual_attempts'], 1)
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0]['json']['model'], 'claude-opus-4-8')
            self.assertEqual(calls[0]['json']['thinking'], {'type': 'adaptive'})
            self.assertTrue((root / 'task_sse.jsonl').is_file())

    def test_pma_uses_two_original_phases_with_fake_litellm_boundary(self):
        import litellm
        with TemporaryDirectory() as directory:
            root = Path(directory)
            profile = root / 'pma.json'
            profile.write_text(json.dumps({'claude_monitor_opus48': dict(
                provider='anthropic', api_mode='messages', model='claude-opus-4-8',
                thinking_type='adaptive', reasoning_effort='high', temperature=1,
                max_tokens=8192, read_timeout=300, apibase='https://offline.invalid/v1',
                apikey='offline')}), encoding='utf-8')
            calls = []

            async def fake_completion(**kwargs):
                calls.append(kwargs)
                content = '' if kwargs.get('tools') else '<no_intervention/>'
                return {'choices': [{'message': {'content': content,
                                                 'tool_calls': []},
                                     'finish_reason': 'stop'}],
                        'model': 'claude-opus-4-8'}

            with patch.object(litellm, 'acompletion', side_effect=fake_completion):
                result = asyncio.run(synthetic_compat._pma_check(root, profile))
            self.assertEqual(result['logical_phases'], 2)
            self.assertEqual(len(calls), 2)
            self.assertTrue(calls[0].get('tools'))
            self.assertFalse(calls[1].get('tools'))
            for call in calls:
                self.assertEqual(call['model'], 'anthropic/claude-opus-4-8')
                self.assertEqual(call['thinking'], {'type': 'adaptive'})
                self.assertEqual(call['reasoning_effort'], 'high')


if __name__ == '__main__':
    unittest.main()
