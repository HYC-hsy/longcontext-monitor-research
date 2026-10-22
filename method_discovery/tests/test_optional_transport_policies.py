"""Offline transport boundary tests: no real provider or credential use."""
import contextlib
import copy
import io
import os
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'GenericAgent-main'))
import llmcore as llm


def drain(generator):
    while True:
        try:
            next(generator)
        except StopIteration as done:
            return done.value


class Response:
    status_code = 200
    headers = {'Content-Type': 'application/json'}
    text = ''

    def __init__(self, reason='end_turn'):
        self.reason = reason

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def close(self):
        pass

    def json(self):
        return {'content': [{'type': 'text', 'text': 'accepted'}],
                'stop_reason': self.reason, 'usage': {'output_tokens': 1}}


class OptionalTransportPoliciesTest(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ, {
            'GA_STATEFUL_MEMORY_ENABLED': '1',
            'GA_STATEFUL_MEMORY_MODE': 'live',
            'GA_TASK_DEADLINE_EPOCH': str(time.time() + 120),
            'GA_PMA_CAPTURE_TASK_REQUESTS': '1',
        }))
        self.stack.enter_context(patch.object(llm, '_telemetry_enabled', return_value=False))
        self.events = []
        self.fail_event = None
        self.fail_none = False
        self.emit = self.stack.enter_context(patch.object(llm, '_research_emit', side_effect=self.record))
        self.post = self.stack.enter_context(patch.object(llm.requests, 'post', return_value=Response()))
        self.session = llm.NativeClaudeSession({
            'apikey': 'test-secret', 'apibase': 'https://example.invalid',
            'model': 'claude-test', 'stream': False, 'max_retries': 3,
            'stateful_native_context_policy': 'off',
            'research_capture_policy': 'best_effort',
        })
        self.session.task_complete_response = True
        self.session.system = 'original system'
        self.session.tools = [{'name': 'test', 'description': 'test',
                               'input_schema': {'type': 'object'}}]
        self.counter = Mock(side_effect=RuntimeError('HTTP 403 count service'))
        self.session.stateful_native_preflight = self.counter
        self.message = {'role': 'user', 'content': [{'type': 'text', 'text': 'original task'}]}

    def record(self, event, data, **kwargs):
        self.events.append((event, data, kwargs))
        if event == self.fail_event:
            if self.fail_none:
                return None
            raise llm.requests.ConnectionError('test-secret https://private.invalid raw body')
        return {'event_id': 'test-event'}

    def ask(self):
        return drain(self.session.ask(copy.deepcopy(self.message)))

    def test_off_never_counts_or_synthesizes_zero(self):
        self.assertEqual(self.ask().content, 'accepted')
        self.counter.assert_not_called()
        self.post.assert_called_once()
        self.assertFalse(hasattr(self.session, 'native_input_tokens'))
        self.assertFalse(any('count' in event for event, _, _ in self.events))

    def test_off_does_not_require_preflight(self):
        del self.session.stateful_native_preflight
        self.assertEqual(self.ask().content, 'accepted')

    def test_required_and_legacy_call_counter(self):
        for explicit in (True, False):
            with self.subTest(explicit=explicit):
                if explicit:
                    self.session.stateful_native_context_policy = 'required'
                else:
                    del self.session.stateful_native_context_policy
                with self.assertRaisesRegex(RuntimeError, 'HTTP 403 count service'):
                    self.ask()
        self.assertEqual(self.counter.call_count, 2)
        self.post.assert_not_called()

    def test_invalid_policies_fail_before_generation(self):
        for field in ('research_capture_policy', 'stateful_native_context_policy'):
            for invalid in ('', None, 'disabled', 'OFF'):
                with self.subTest(field=field, invalid=invalid):
                    prior = getattr(self.session, field)
                    setattr(self.session, field, invalid)
                    with self.assertRaises(ValueError):
                        self.ask()
                    setattr(self.session, field, prior)
        self.post.assert_not_called()

    def test_off_preserves_generation_payload_headers_and_endpoint(self):
        drain(self.session.raw_ask([copy.deepcopy(self.message)]))
        off_args = copy.deepcopy(self.post.call_args.args)
        off_kwargs = copy.deepcopy(self.post.call_args.kwargs)
        self.session.stateful_native_context_policy = 'required'
        self.counter.side_effect = None
        drain(self.session.raw_ask([copy.deepcopy(self.message)]))
        self.assertEqual(off_args, self.post.call_args.args)
        self.assertEqual(off_kwargs, self.post.call_args.kwargs)
        self.counter.assert_called_once()
        self.assertEqual(self.counter.call_args.args[0], off_kwargs['json'])

    def test_best_effort_sink_failures_never_resend(self):
        for event in ('provider_request_ready', 'provider_request_attempt',
                      'task_response_integrity', 'provider_usage', 'provider_response_content', 'provider_response'):
            for missing in (False, True):
                with self.subTest(event=event, missing=missing):
                    self.fail_event, self.fail_none = event, missing
                    before = self.post.call_count
                    with contextlib.redirect_stdout(io.StringIO()) as output:
                        self.assertEqual(self.ask().content, 'accepted')
                    self.assertEqual(self.post.call_count, before + 1)
                    self.assertEqual(self.session.last_response_acceptance, 'complete')
                    self.assertNotIn('test-secret', output.getvalue())
                    self.assertNotIn('private.invalid', output.getvalue())
                    self.assertIn('[Research capture gap]', output.getvalue())
                    self.assertFalse(getattr(self.session, '_research_capture_failed', False))
        self.assertTrue(any(e == 'provider_response_content' for e, _, _ in self.events))

    def test_payload_capture_serialization_failures_are_optional(self):
        original = llm._payload_summary
        for content_only in (False, True):
            def broken(payload, **kwargs):
                if not content_only or set(payload) == {'content'}:
                    raise OSError('private payload')
                return original(payload, **kwargs)
            with self.subTest(content_only=content_only), patch.object(llm, '_payload_summary', side_effect=broken):
                before = self.post.call_count
                self.assertEqual(self.ask().content, 'accepted')
                self.assertEqual(self.post.call_count, before + 1)

    def test_required_capture_error_cannot_become_generation_retry(self):
        for event in ('provider_request_ready', 'provider_request_attempt', 'provider_usage', 'provider_response_content', 'provider_response'):
            with self.subTest(event=event):
                self.session.research_capture_policy = 'required'
                self.session._research_capture_failed = False
                self.fail_event = event
                before = self.post.call_count
                with self.assertRaises(llm.ResearchCaptureFailed):
                    self.ask()
                expected = 0 if event in ('provider_request_ready', 'provider_request_attempt') else 1
                self.assertEqual(self.post.call_count, before + expected)
                self.assertEqual(self.session.history, [])

    def test_best_effort_still_rejects_truncated_invalid_and_http_error(self):
        self.session.max_retries = 0
        self.fail_event = 'provider_response'
        for reason, expected in (('max_tokens', 'token_limit'), (None, 'incomplete_stream'), ('bogus', 'invalid_frame')):
            with self.subTest(reason=reason):
                self.post.return_value = Response(reason)
                with self.assertRaises(llm.TaskResponseRejected) as error:
                    self.ask()
                self.assertEqual(error.exception.category, expected)
                self.assertEqual(self.session.history, [])
        self.post.return_value = Response()
        self.post.return_value.status_code = 403
        with self.assertRaises(llm.TaskResponseRejected) as error:
            self.ask()
        self.assertEqual(error.exception.category, 'http_error')
        self.counter.assert_not_called()
        self.assertEqual(self.session.history, [])

    def test_required_missing_receipts_and_legacy_default_are_strict(self):
        self.fail_none = True
        del self.session.research_capture_policy
        for event in ('provider_request_ready', 'provider_request_attempt',
                      'task_response_integrity', 'provider_response_content', 'provider_response'):
            with self.subTest(event=event):
                self.session._research_capture_failed = False
                self.fail_event = event
                before = self.post.call_count
                with self.assertRaises(RuntimeError):
                    self.ask()
                expected = 0 if event in ('provider_request_ready', 'provider_request_attempt') else 1
                self.assertEqual(self.post.call_count, before + expected)
                self.assertEqual(self.session.history, [])

    def test_best_effort_requests_real_sink_receipt_and_records_gap(self):
        self.fail_event, self.fail_none = 'provider_response_content', True
        self.ask()
        content = [kwargs for event, _, kwargs in self.events if event == self.fail_event]
        self.assertEqual(content[0]['required_sink'], True)
        self.assertTrue(any(event == 'research_capture_gap' and
                            data['stage'] == self.fail_event
                            for event, data, _ in self.events))

    def test_history_archive_exception_does_not_block_best_effort(self):
        self.fail_event = 'history_transform_started'
        with patch.object(llm, '_telemetry_enabled', return_value=True):
            self.assertEqual(self.ask().content, 'accepted')
        self.post.assert_called_once()
        self.assertIsNone(llm._parser_capture_emit.get())

    def test_capture_preparation_failure_does_not_reuse_previous_call_identity(self):
        llm._register_provider_call({'llm_call_id': 'old-call',
                                     'provider_request_event_id': 'old-event'})
        with patch.object(llm, '_payload_summary', side_effect=OSError('archive')):
            self.ask()
        usage = [kwargs for event, _, kwargs in self.events if event == 'provider_usage']
        self.assertTrue(usage)
        self.assertNotEqual(usage[-1]['llm_call_id'], 'old-call')
        self.assertIsNone(usage[-1]['parent_event_id'])
        with patch.object(llm, '_research_id', side_effect=OSError('archive')):
            self.ask()
        self.assertIsNone(llm._current_provider_call())

    def test_overlay_capture_failure_restores_session(self):
        client = llm.NativeToolClient(self.session)
        client.log_path = False
        self.session.task_complete_response = True
        self.session.system = 'original system'
        self.fail_event = 'candidate_task_budget_resolved'
        for policy in ('required', 'best_effort'):
            self.session.research_capture_policy = policy
            with self.subTest(policy=policy):
                generator = client.chat([self.message], tools=self.session.tools,
                                        system_overlay='optional panel')
                if policy == 'required':
                    with self.assertRaises(llm.ResearchCaptureFailed):
                        drain(generator)
                else:
                    self.assertEqual(drain(generator).content, 'accepted')
                self.assertEqual(self.session.system, 'original system')
                self.assertIsNone(self.session.candidate_request_byte_limit)

    def test_generation_exception_is_not_swallowed_by_best_effort(self):
        self.post.side_effect = ValueError('malformed actual response')
        with self.assertRaises(llm.TaskResponseRejected) as error:
            self.ask()
        self.assertEqual(error.exception.category, 'parser_exception')
        self.post.assert_called_once()
        self.assertEqual(self.session.history, [])

    def test_auxiliary_integrity_is_not_capture_policy(self):
        self.session.task_complete_response = False
        self.session.candidate_auxiliary_integrity = True
        self.post.return_value = Response('max_tokens')
        with self.assertRaises(llm.AuxiliaryResponseRejected) as error:
            drain(self.session.raw_ask([self.message]))
        self.assertEqual(error.exception.category, 'token_limit')
        self.post.assert_called_once()


if __name__ == '__main__':
    unittest.main()
