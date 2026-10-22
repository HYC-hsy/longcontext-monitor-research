"""The private role adapter is tested without external model networking."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from .stateful_role_provider import StatefulRoleProvider
from method_discovery.pma_stateful_memory_v1_20261021.source import ContractError


class RoleProviderTests(unittest.TestCase):
    def test_structured_refusal_does_not_return_text_or_retry(self):
        sessions = []
        class Blocks(list):
            integrity = {'stop_reason': 'refusal'}
        class Session:
            def __init__(self, cfg):
                sessions.append(self)
            def raw_ask(self, messages):
                if False:
                    yield None
                return Blocks([{'type': 'text', 'text': 'I cannot discuss that.'}])
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch('llmcore.NativeClaudeSession', Session):
            provider = StatefulRoleProvider(profile={'model': 'synthetic'},
                context_window=10000, archive=Path(directory),
                run_id='synthetic-run', task_id='synthetic-task',
                native_context_policy='off')
            with self.assertRaisesRegex(ContractError, 'model_refusal'):
                provider('audit', [{'role': 'system', 'content': 'contract'},
                    {'role': 'user', 'content': 'candidate'}], 'cycle/2/audit', 8192)
            self.assertEqual(len(sessions), 1)
            self.assertIn('"status": "refused"', (Path(directory) /
                'role_calls.jsonl').read_text(encoding='utf-8'))

    def test_role_messages_and_call_identity(self):
        seen = []
        class Session:
            def __init__(self, cfg):
                self.cfg = cfg
                seen.append(self)
            def raw_ask(self, messages):
                seen.append((self.system, messages,
                    self.max_retries, self.total_response_timeout))
                if False:
                    yield None
                return [{'type': 'text', 'text': '{"status":"clean"}'}]
        profile = {'apikey': 'synthetic-only',
                   'apibase': 'http://127.0.0.1:1',
                   'model': 'claude-synthetic', 'read_timeout': 9}
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch('llmcore.NativeClaudeSession', Session):
            provider = StatefulRoleProvider(profile=profile, context_window=10000,
                archive=Path(directory), run_id='synthetic-run', task_id='synthetic-task')
            result = provider('audit', [{'role': 'system', 'content': 'contract'},
                {'role': 'user', 'content': 'candidate'}], 'cycle/2/audit', 8192)
            self.assertEqual(result, '{"status":"clean"}')
            self.assertEqual(seen[-1], ('contract', [{'role': 'user',
                'content': [{'type': 'text', 'text': 'candidate'}]}], 0, 9.0))
            with self.assertRaisesRegex(RuntimeError, 'already attempted'):
                provider('audit', [{'role': 'system', 'content': 'contract'},
                    {'role': 'user', 'content': 'candidate'}], 'cycle/2/audit', 8192)
            self.assertEqual(len(seen), 2)
            self.assertEqual(len((Path(directory) / 'role_calls.jsonl').read_text(
                encoding='utf-8').splitlines()), 2)


if __name__ == '__main__':
    unittest.main()
