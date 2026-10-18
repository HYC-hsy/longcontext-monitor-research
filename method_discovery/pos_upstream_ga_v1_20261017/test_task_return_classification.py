"""Zero-model tests for conservative archive-only return categories."""
import unittest

from .classify_task_returns import classify_call, INCOMPLETE_MARKER, MAX_TOKENS_MARKER


def events(*, outcome='success', text='', stop_reason=None, message_stop=None):
    response = {'outcome': outcome}
    if stop_reason is not None:
        response['stop_reason'] = stop_reason
    if message_stop is not None:
        response['message_stop'] = message_stop
    return [
        {'event_type': 'provider_request_ready', 'payload': {}},
        {'event_type': 'provider_request_attempt', 'payload': {'attempt': 1}},
        {'event_type': 'provider_response_content', 'payload': {
            'parsed_visible_blocks': [{'type': 'text', 'text': text}]}},
        {'event_type': 'provider_response', 'payload': response},
    ]


class ClassificationTests(unittest.TestCase):
    def test_complete_requires_terminal_evidence(self):
        row = classify_call(events(text='answer', stop_reason='end_turn',
                                   message_stop=True))
        self.assertEqual(row['category'], 'complete_valid_return')

    def test_success_capture_without_terminal_marker_is_unknown(self):
        row = classify_call(events(text='answer'))
        self.assertEqual(row['category'], 'terminal_unproven_or_unknown')
        self.assertEqual(row['return_records'], 1)

    def test_incomplete_stream_marker_overrides_success_capture(self):
        row = classify_call(events(text=INCOMPLETE_MARKER + '，未收到完整响应 !!!]'))
        self.assertEqual(row['category'], 'incomplete_stream_marker')

    def test_explicit_provider_error(self):
        self.assertEqual(classify_call(events(outcome='http_error', text=''))['category'],
                         'explicit_provider_error')

    def test_max_tokens(self):
        self.assertEqual(classify_call(events(text=MAX_TOKENS_MARKER))['category'],
                         'max_tokens')
        self.assertEqual(classify_call(events(text='partial', stop_reason='max_tokens'))['category'],
                         'max_tokens')


if __name__ == '__main__':
    unittest.main(verbosity=2)
