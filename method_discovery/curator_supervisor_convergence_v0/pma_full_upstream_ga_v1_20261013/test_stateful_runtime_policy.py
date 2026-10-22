"""Offline policy tests: no native-count route or model server is contacted."""

import argparse
import asyncio
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from . import stateful_memory_worker as worker
from . import stateful_role_provider as roles
from . import stateful_native_count as count_module
from .stateful_runtime_policy import ResearchArchive, policies, require_same_policies
from stateful_memory_bridge import StatefulLiveBridge, StatefulBridgeError


class RuntimePolicyTests(unittest.TestCase):
    def test_strict_defaults_and_mismatch(self):
        self.assertEqual(policies({}), dict(native_context_policy='required',
            research_capture_policy='required'))
        for name in policies({}):
            for value in (None, '', True, 'OFF', 'disabled'):
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    policies({name: value})
        with self.assertRaises(ValueError):
            require_same_policies({'native_context_policy': 'off'}, {})

    def test_archive_is_best_effort_not_a_generic_error_guard(self):
        archive = ResearchArchive('best_effort')
        with contextlib.redirect_stderr(io.StringIO()) as output:
            archive.write(mock.Mock(side_effect=OSError('secret/path')), None, {})
        self.assertEqual(archive.evidence_gaps, 1)
        self.assertIn('evidence_gap: OSError', output.getvalue())
        self.assertNotIn('secret', output.getvalue())
        with self.assertRaises(OSError):
            ResearchArchive().write(mock.Mock(side_effect=OSError()), None, {})

    def test_fsynced_research_archive_failure_is_optional_only(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'events.jsonl'
            with mock.patch.object(worker.os, 'fsync', side_effect=OSError('disk')), \
                    contextlib.redirect_stderr(io.StringIO()):
                capture = ResearchArchive('best_effort')
                capture.write(worker._durable, path, {'kind': 'observed'})
                self.assertEqual(capture.evidence_gaps, 1)
                with self.assertRaises(OSError):
                    ResearchArchive().write(worker._durable, path, {})

    def test_role_off_skips_counter_and_optional_archive_failure(self):
        seen = []
        class Session:
            def __init__(self, cfg):
                self._research_capture_failed = True
                seen.append(self)
            def raw_ask(self, messages):
                if False:
                    yield
                return [{'type': 'text', 'text': 'valid response'}]
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(roles, 'PrivateNativeCounter', side_effect=AssertionError('count')), \
                mock.patch.object(roles, '_write_event', side_effect=OSError('private')), \
                mock.patch('llmcore.NativeClaudeSession', Session), \
                contextlib.redirect_stderr(io.StringIO()):
            provider = roles.StatefulRoleProvider(profile={'model': 'synthetic'},
                context_window=None, archive=directory, run_id='r', task_id='t',
                native_context_policy='off', research_capture_policy='best_effort')
            self.assertIsNone(provider.counter)
            self.assertEqual(provider('audit', [dict(role='system', content='contract'),
                dict(role='user', content='candidate')], 'call-1', 8192), 'valid response')
            self.assertEqual(provider.capture.evidence_gaps, 2)
            self.assertEqual(seen[0].stateful_native_context_policy, 'off')
            self.assertEqual(seen[0].research_capture_policy, 'best_effort')
            self.assertFalse(hasattr(seen[0], 'stateful_native_preflight'))

    def test_worker_off_constructs_neither_task_nor_aux_counter(self):
        async def once(dispatcher):
            (private / 'stop.request').touch()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            requests, responses, private = root/'spool/requests', root/'spool/responses', root/'private'
            requests.mkdir(parents=True)
            responses.mkdir()
            args = argparse.Namespace(private_root=private, requests=requests,
                responses=responses, run_id='r', task_id='t', fake_replies=None,
                task_profile_file='unused', task_profile_name='task',
                task_profile_sha256='unused', pma_profile_file='unused',
                pma_profile_sha256='unused', context_window=None,
                native_context_policy='off', research_capture_policy='best_effort')
            with mock.patch.object(worker, 'load_bound_profile', return_value={'model':'synthetic'}), \
                    mock.patch.object(worker.EventDispatcher, 'serve_once', once), \
                    mock.patch.object(roles, 'PrivateNativeCounter', side_effect=AssertionError('aux count')), \
                    mock.patch.object(count_module, 'PrivateNativeCounter',
                                      side_effect=AssertionError('task count')):
                asyncio.run(worker.serve(args))
            import json
            ready = json.loads((private/'worker_ready.json').read_text())
            self.assertEqual(policies(ready), policies(vars(args)))
            self.assertFalse((private/'archive/native_count.jsonl').exists())

    def test_worker_best_effort_does_not_swallow_essential_journal_failure(self):
        bridge = mock.Mock()
        bridge.record_incomplete.side_effect = OSError('SQLite unavailable')
        episode = worker.StatefulEpisode(run_id='r', task_id='t', archive=Path('.'),
            private=Path('.'), provider=None, native_context_policy='off',
            research_capture_policy='best_effort')
        episode.bridge = bridge
        with mock.patch.object(worker, '_durable', side_effect=OSError('archive')), \
                contextlib.redirect_stderr(io.StringIO()), self.assertRaisesRegex(OSError, 'SQLite'):
            asyncio.run(episode.handle(dict(kind='incomplete_batch', sequence=1,
                event_id='e', batch_id='b', turn=1, reason='interrupted')))
        self.assertEqual(episode.capture.evidence_gaps, 2)
        with self.assertRaisesRegex(RuntimeError, 'disabled'):
            episode._handle(dict(kind='count_tokens', payload={}))

    def test_real_task_client_backend_honors_off_and_best_effort(self):
        import llmcore
        import os
        class Response:
            status_code = 200
            headers = {'Content-Type': 'application/json'}
            def __enter__(self):
                return self
            def __exit__(self, *_):
                pass
            def close(self):
                pass
            def json(self):
                return {'content': [{'type': 'text', 'text': 'accepted'}],
                        'stop_reason': 'end_turn', 'usage': {'output_tokens': 1}}
        spool = mock.Mock()
        spool.exchange.return_value = {'has_reminder': False}
        bridge = StatefulLiveBridge(spool, episode_id='r', native_context_policy='off',
            research_capture_policy='best_effort')
        with mock.patch.dict(os.environ, {'GA_TASK_COMPLETE_RESPONSE': '1',
                'GA_STATEFUL_MEMORY_ENABLED': '1', 'GA_STATEFUL_MEMORY_MODE': 'live',
                'GA_STATEFUL_UNCAPPED_TOTAL': '1', 'GA_PMA_CAPTURE_TASK_REQUESTS': '1'}), \
                mock.patch.object(llmcore.requests, 'post', return_value=Response()) as post, \
                mock.patch.object(llmcore, '_research_emit', side_effect=OSError('archive')), \
                mock.patch.object(llmcore, '_telemetry_enabled', return_value=False), \
                contextlib.redirect_stdout(io.StringIO()):
            backend = llmcore.NativeClaudeSession(dict(apikey='synthetic',
                apibase='https://example.invalid', model='claude-synthetic',
                stream=False, max_retries=0))
            backend.stateful_native_preflight = mock.Mock(side_effect=AssertionError('count'))
            client = llmcore.NativeToolClient(backend)
            generator = bridge.chat(client, [{'role': 'user', 'content': 'task'}], [], 1)
            while True:
                try:
                    next(generator)
                except StopIteration as done:
                    result = done.value
                    break
            self.assertTrue(result.complete_response_accepted)
            self.assertEqual(result.content, 'accepted')
            post.assert_called_once()
            backend.stateful_native_preflight.assert_not_called()
            self.assertEqual(backend.stateful_native_context_policy, 'off')
            self.assertEqual(backend.research_capture_policy, 'best_effort')

    def test_task_off_policy_propagates_without_counter_or_fake_acceptance(self):
        spool = mock.Mock()
        spool.exchange.return_value = {'has_reminder': False}
        bridge = StatefulLiveBridge(spool, episode_id='r', native_context_policy='off',
            research_capture_policy='best_effort')
        class Session:
            def chat(self, **kwargs):
                self.calls = getattr(self, 'calls', 0) + 1
                if False:
                    yield
                return argparse.Namespace(complete_response_accepted=True)
        session = Session()
        session.backend = argparse.Namespace()
        with self.assertRaises(StopIteration):
            next(bridge.chat(session, [], [], 1))
        self.assertEqual(session.calls, 1)
        self.assertEqual(session.backend.stateful_native_context_policy, 'off')
        self.assertEqual(session.backend.research_capture_policy, 'best_effort')
        with self.assertRaisesRegex(StatefulBridgeError, 'disabled'):
            bridge.native_preflight({})
        self.assertEqual([call.args[0] for call in spool.exchange.call_args_list], ['prepare_task'])


if __name__ == '__main__':
    unittest.main()
