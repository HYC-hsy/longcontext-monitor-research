"""No external request: the private native counter uses a fake final HTTP boundary."""

import unittest
from unittest import mock
import requests

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
        reply.status_code = 200
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
        self.assertEqual(self.events[-1]['http_status'], 200)
        self.assertEqual(post.call_args.kwargs['timeout'], (5, 40))

    def test_overwindow_fails_after_count_without_generation(self):
        reply = mock.Mock()
        reply.status_code = 200
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

    def test_bound_transport_and_timeout_evidence(self):
        events = []
        counter = PrivateNativeCounter(profile={
            'apikey': 'synthetic-only', 'apibase': 'https://example.invalid',
            'model': 'claude-synthetic', 'timeout': 30, 'read_timeout': 300,
            'proxy': 'http://127.0.0.1:3128', 'verify': False},
            window=10000, record=events.append)
        with mock.patch('requests.post', side_effect=requests.exceptions.ReadTimeout(
                'synthetic timeout')) as post:
            with self.assertRaises(requests.exceptions.ReadTimeout):
                counter(self.payload)
        self.assertEqual(post.call_count, 1)
        self.assertEqual(post.call_args.kwargs['timeout'], (30, 300))
        self.assertEqual(post.call_args.kwargs['proxies'], {
            'http': 'http://127.0.0.1:3128',
            'https': 'http://127.0.0.1:3128'})
        self.assertIs(post.call_args.kwargs['verify'], False)
        self.assertEqual(events[0]['timeout_source'],
                         'bound_profile.timeout/read_timeout')
        self.assertEqual(events[-1]['error_type'], 'ReadTimeout')
        self.assertIsNone(events[-1]['http_status'])
        self.assertGreaterEqual(events[-1]['elapsed_seconds'], 0)
        self.assertIn('synthetic timeout', events[-1]['private_error_repr'])

    def test_http_error_keeps_observed_status(self):
        reply = mock.Mock(status_code=403)
        reply.raise_for_status.side_effect = requests.exceptions.HTTPError(
            'synthetic forbidden')
        with mock.patch('requests.post', return_value=reply):
            with self.assertRaises(requests.exceptions.HTTPError):
                self.counter(self.payload)
        self.assertEqual(self.events[-1]['http_status'], 403)


if __name__ == '__main__':
    unittest.main()
