"""Synthetic public-projection guards; no provider or official evaluator."""

import copy
import json
import unittest

from .archive_ordered_real import Projector, project_event


class PublicProjectionTests(unittest.TestCase):
    def test_request_removes_nested_hidden_blocks_and_private_transport(self):
        private = {
            'event_id': 'evt-1', 'event_type': 'provider_request_ready',
            'payload': {'model': 'claude-opus-4-8', 'provider_url': 'https://private.example',
                        'content_availability': 'complete', 'content': {
                'model': 'claude-opus-4-8', 'max_tokens': 8192, 'stream': True,
                'metadata': {'user_id': 'private-user'},
                'system': [{'type': 'text', 'text': 'public system'}],
                'messages': [
                    {'role': 'assistant', 'content': [
                        {'type': 'thinking', 'thinking': 'HIDDEN_THOUGHT',
                         'signature': 'HIDDEN_SIGNATURE'},
                        {'type': 'redacted_thinking', 'data': 'HIDDEN_ENCRYPTED'},
                        {'type': 'text', 'text': 'VISIBLE_ANSWER'}]},
                    {'role': 'user', 'content': [
                        {'type': 'tool_result', 'tool_use_id': 'call-1',
                         'content': 'VISIBLE_TOOL_RESULT'}]}],
                'tools': [{'name': 'read_file', 'description': 'visible tool',
                           'input_schema': {'type': 'object'}}]}}}
        original = copy.deepcopy(private)
        projection = project_event(private, Projector(['private.example']), 1)
        shown = json.dumps(projection)
        self.assertIn('VISIBLE_ANSWER', shown)
        self.assertIn('VISIBLE_TOOL_RESULT', shown)
        for secret in ('HIDDEN_THOUGHT', 'HIDDEN_SIGNATURE', 'HIDDEN_ENCRYPTED',
                       'private.example', 'private-user'):
            self.assertNotIn(secret, shown)
        self.assertEqual(private, original)

    def test_embedded_transport_and_unknown_payload_fail_closed(self):
        projector = Projector(['private.example'])
        for value in ('data: {"type":"thinking","data":"HIDDEN"}',
                      'Authorization: Bearer SECRETSECRETSECRET',
                      '{"signature":"HIDDEN_SIGNATURE"}',
                      'https://private.example/v1'):
            result = projector.text(value, 'test')
            self.assertIsInstance(result, dict)
            self.assertNotIn('HIDDEN', json.dumps(result))
            self.assertNotIn('private.example', json.dumps(result))
        unknown = project_event({'event_type': 'unhandled',
            'payload': {'secret': 'HIDDEN_UNKNOWN'}}, projector, 4)
        self.assertNotIn('HIDDEN_UNKNOWN', json.dumps(unknown))

    def test_missing_usage_distinct_from_actual_zero(self):
        projector = Projector([])
        row = {'event_type': 'provider_usage', 'payload': {
            'input_tokens': 0, 'output_tokens': 7}}
        shown = project_event(row, projector, 1)['payload']
        self.assertEqual(shown['input_tokens'], 0)
        self.assertIsNone(shown['cached_input_tokens'])
        self.assertEqual(shown['output_tokens'], 7)

    def test_reminder_link_is_kept_without_private_provider_url(self):
        row = {'event_type': 'provider_request_ready', 'llm_call_id': 'llm-1',
               'payload': {'pma_reminder_event_id': 'pma-1', 'actor_attempt': 2,
                           'provider_url': 'https://private.example',
                           'content': {'model': 'claude-opus-4-8', 'messages': [],
                                       'system': [], 'tools': []}}}
        shown = project_event(row, Projector(['private.example']), 1)
        self.assertEqual(shown['llm_call_id'], 'llm-1')
        self.assertEqual(shown['payload']['pma_reminder_event_id'], 'pma-1')
        self.assertNotIn('private.example', json.dumps(shown))


if __name__ == '__main__':
    unittest.main()
