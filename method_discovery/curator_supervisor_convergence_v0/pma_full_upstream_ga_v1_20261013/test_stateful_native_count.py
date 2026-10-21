"""No external request: the private native counter uses a fake final HTTP boundary."""

import unittest
from unittest import mock

from .stateful_native_count import PrivateNativeCounter, count_projection


class NativeCountTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.counter = PrivateNativeCounter(profile={
            'apikey': 'synthetic-only', 'apibase': 'http://127.0.0.1:1',
            'model': 'claude-synthetic'}, window=10000,
            record=self.events.append)
        self.payload = {'model': 'claude-synthetic',
            'messages': [{'role': 'user', 'content': 'one'}],
            'system': [{'type': 'text', 'text': 'system'}],
            'tools': [{'name': 'test', 'input_schema': {'type': 'object'}}],
            'thinking': {'type': 'adaptive'}, 'max_tokens': 100,
            'stream': True, 'metadata': {'user_id': 'opaque'}}

    def test_count_projection_and_accept(self):
        reply = mock.Mock()
        reply.json.return_value = {'input_tokens': 50}
        with mock.patch('requests.post', return_value=reply) as post:
            result = self.counter(self.payload)
        self.assertEqual(post.call_count, 1)
        counted = post.call_args.kwargs['json']
        self.assertEqual(counted, count_projection(self.payload))
        self.assertNotIn('metadata', counted)
        self.assertNotIn('stream', counted)
        self.assertNotIn('max_tokens', counted)
        self.assertEqual(result['native_input_tokens'], 50)
        self.assertEqual(self.events[-1]['kind'], 'native_count_accepted')

    def test_overwindow_fails_after_count_without_generation(self):
        reply = mock.Mock()
        reply.json.return_value = {'input_tokens': 9000}
        with mock.patch('requests.post', return_value=reply) as post:
            with self.assertRaisesRegex(Exception, 'native_context_limit'):
                self.counter(self.payload)
        self.assertEqual(post.call_count, 1)
        self.assertEqual(self.events[-1]['kind'], 'native_count_failed')

    def test_wrong_model_fails_without_http(self):
        payload = dict(self.payload, model='another-model')
        with mock.patch('requests.post') as post:
            with self.assertRaisesRegex(ValueError, 'model identity'):
                self.counter(payload)
        post.assert_not_called()


if __name__ == '__main__':
    unittest.main()
