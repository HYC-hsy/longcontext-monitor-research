"""Candidate-only final-payload guard and uncapped total deadline contract."""

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import llmcore


class NativePreflightTests(unittest.TestCase):
    def backend(self):
        backend = llmcore.NativeClaudeSession({
            'apikey': 'synthetic-only', 'apibase': 'http://127.0.0.1:1',
            'model': 'claude-synthetic', 'max_tokens': 32, 'max_retries': 0,
        })
        backend.tools = [{'type': 'function', 'function': {
            'name': 'touch', 'description': 'synthetic',
            'parameters': {'type': 'object', 'properties': {}}}}]
        return backend

    def test_final_payload_guard_rejects_before_generation_attempt(self):
        with mock.patch.dict(os.environ, {
            'GA_STATEFUL_MEMORY_ENABLED': '1',
            'GA_STATEFUL_MEMORY_MODE': 'live',
            'GA_STATEFUL_UNCAPPED_TOTAL': '1',
        }), mock.patch.object(llmcore.requests, 'post') as post:
            backend = self.backend()
            backend.task_complete_response = True
            self.assertIsNone(llmcore._task_deadline(backend))
            self.assertRaisesRegex(RuntimeError, 'preflight unavailable',
                lambda: list(backend.raw_ask([{'role': 'user', 'content': [
                    {'type': 'text', 'text': 'synthetic'}]}])))
            seen = []
            def reject(payload):
                seen.append(payload)
                raise ValueError('synthetic context limit')
            backend.stateful_native_preflight = reject
            with self.assertRaisesRegex(ValueError, 'synthetic context limit'):
                list(backend.raw_ask([{'role': 'user', 'content': [
                    {'type': 'text', 'text': 'synthetic'}]}]))
            self.assertEqual(len(seen), 1)
            self.assertEqual(seen[0]['model'], 'claude-synthetic')
            self.assertIn('system', seen[0])
            self.assertIn('tools', seen[0])
            self.assertEqual(post.call_count, 0)

    def test_uncapped_check_preserves_cancel(self):
        backend = self.backend()
        backend._cancel_response.set()
        with self.assertRaises(llmcore.ProviderResponseCancelled):
            llmcore._task_check_wait(backend, None)


if __name__ == '__main__':
    unittest.main()
