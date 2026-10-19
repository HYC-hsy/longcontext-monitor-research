"""Candidate-only role integrity at the actual NativeClaudeSession HTTP seam."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import threading
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'GenericAgent-main'),
                str(ROOT / 'method_discovery/pos_upstream_ga_v1_20261017'),
                str(ROOT / 'method_discovery/pos_upstream_ga_v1_20261017/vendor'),
                str(Path(__file__).resolve().parent)]
import llmcore
from worker import RoleTransport, _DurableProviderSink
from episode import PoSEpisode, execution_config
from candidate import ComplementBeliefManager


class Ledger:
    def __init__(self): self.rows = []
    def log(self, event, **data): self.rows.append((event, data))


def sse(answer, *, complete=True):
    events = [
        {'type': 'message_start', 'message': {'usage': {'input_tokens': 1}}},
        {'type': 'content_block_start', 'index': 0,
         'content_block': {'type': 'text', 'text': ''}},
        {'type': 'content_block_delta', 'index': 0,
         'delta': {'type': 'text_delta', 'text': answer}},
        {'type': 'content_block_stop', 'index': 0},
    ]
    if complete:
        events += [{'type': 'message_delta', 'delta': {'stop_reason': 'end_turn'},
                    'usage': {'output_tokens': 2}}, {'type': 'message_stop'}]
    return ''.join('data: ' + json.dumps(row) + '\n\n' for row in events).encode()


class AuxiliaryTransportTests(unittest.TestCase):
    def setUp(self):
        self.script = []
        self.posts = []
        testcase = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def do_POST(self):
                testcase.posts.append(json.loads(self.rfile.read(
                    int(self.headers['Content-Length']))))
                code, body = testcase.script.pop(0)
                self.send_response(code)
                self.send_header('Content-Type', 'text/event-stream')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.env = patch.dict(os.environ, {'GA_PMA_CAPTURE_TASK_REQUESTS': '0',
                                           'GA_POS_TIMEOUT': '180'})
        self.env.start()
        self.ledger = Ledger()
        self.transport = RoleTransport(mode='profile', archive=self.ledger,
            profile={'apibase': f'http://127.0.0.1:{self.server.server_port}',
                     'apikey': 'SYNTHETIC-NOT-A-SECRET', 'model': 'claude-opus-4-8',
                     'stream': True, 'max_retries': 0})
        self.transport.candidate_mode = True

    def tearDown(self):
        self.env.stop()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def call(self):
        return self.transport.caller('belief')([
            {'role': 'system', 'content': 'Synthetic role system.'},
            {'role': 'user', 'content': 'Synthetic role input.'}])

    def test_http_failure_is_not_model_json_or_correction(self):
        self.script = [(503, b'upstream unavailable')]
        with self.assertRaises(llmcore.AuxiliaryResponseRejected) as caught:
            self.call()
        self.assertEqual(caught.exception.category, 'http_error')
        self.assertEqual(len(self.posts), 1)
        self.assertFalse(any(kind == 'pos_role_response' for kind, _ in self.ledger.rows))

    def test_eof_is_not_complete_role_answer(self):
        self.script = [(200, sse('{"goal_specification":"synthetic"}', complete=False))]
        with self.assertRaises(llmcore.AuxiliaryResponseRejected) as caught:
            self.call()
        self.assertEqual(caught.exception.category, 'incomplete_stream')
        self.assertEqual(len(self.posts), 1)

    def test_real_model_text_is_not_classified_by_error_words(self):
        answer = '{"note":"!!!Error: is quoted task data"}'
        self.script = [(200, sse(answer))]
        self.assertEqual(self.call(), answer)
        self.assertEqual(len(self.posts), 1)

    def test_complete_bad_json_remains_format_input(self):
        self.script = [(200, sse('{bad json}'))]
        self.assertEqual(self.call(), '{bad json}')
        self.assertEqual(len(self.posts), 1)

    def test_transport_timeout_is_not_retried_or_corrected(self):
        self.script = [(200, sse('{}'))]
        with patch.object(llmcore.requests, 'post', side_effect=llmcore.requests.Timeout(
                'synthetic timeout')):
            with self.assertRaises(llmcore.AuxiliaryResponseRejected) as caught:
                self.call()
        self.assertEqual(caught.exception.category, 'transport_error')
        self.assertEqual(len(self.posts), 0)

    def test_accepted_response_capture_failure_is_not_replayed(self):
        self.script = [(200, sse('{"ok":true}'))]
        original = _DurableProviderSink.__call__

        def fail_after_send(sink, event):
            if event.get('event_type') == 'provider_response_content':
                raise OSError('synthetic durable capture failure')
            return original(sink, event)

        with tempfile.TemporaryDirectory() as directory:
            self.transport.capture_path = Path(directory) / 'provider.jsonl'
            self.transport.run_id = 'synthetic-run'
            self.transport.task_id = 'synthetic-task'
            with patch.dict(os.environ, {'GA_PMA_CAPTURE_TASK_REQUESTS': '1'}), \
                    patch.object(_DurableProviderSink, '__call__', fail_after_send):
                with self.assertRaises(llmcore.AuxiliaryResponseRejected) as caught:
                    self.call()
        self.assertEqual(caught.exception.category, 'capture_failed')
        self.assertEqual(len(self.posts), 1)

    def test_initial_audit_http_failure_stops_core(self):
        initial = {'goal_specification': 'Clean mug.', 'entities': [],
                   'states': [], 'relations': [], 'epistemic_gaps': [],
                   'achievement_gaps': [], 'frontier': None}
        self.script = [(503, b'synthetic unavailable')]
        episode = PoSEpisode(case_id='synthetic', config=execution_config(),
            logger=self.ledger, belief_call=lambda _: json.dumps(initial),
            consistency_call=self.transport.caller('consistency'),
            progress_call=lambda _: '{}', manager_class=ComplementBeliefManager)
        with self.assertRaises(llmcore.AuxiliaryResponseRejected):
            episode.reset(task='Clean mug.', observation='Dirty.', actions=[])
        self.assertEqual(len(self.posts), 1)
        self.assertFalse(any(kind == 'pos_role_json_adapter'
                             for kind, _ in self.ledger.rows))

    def test_complete_bad_json_uses_original_format_correction(self):
        initial = {'goal_specification': 'Clean mug.', 'entities': [],
                   'states': [], 'relations': [], 'epistemic_gaps': [],
                   'achievement_gaps': [], 'frontier': None}
        self.script = [(200, sse('{bad json}')),
                       (200, sse(json.dumps(initial)))]
        episode = PoSEpisode(case_id='synthetic', config=execution_config(),
            logger=self.ledger, belief_call=self.transport.caller('belief'),
            consistency_call=lambda _: '{"issues": []}',
            progress_call=lambda _: '{}', manager_class=ComplementBeliefManager)
        episode.reset(task='Clean mug.', observation='Dirty.', actions=[])
        self.assertEqual(len(self.posts), 2)
        self.assertEqual(episode.get_context()['goal']['specification'], 'Clean mug.')

    def test_reaudit_http_failure_does_not_become_semantic_rejection(self):
        initial = {'goal_specification': 'Clean mug.', 'entities': [],
                   'states': [], 'relations': [], 'epistemic_gaps': [],
                   'achievement_gaps': [{'target': 'clean', 'reason': 'unverified'}],
                   'frontier': {'gap_type': 'achievement', 'target': 'clean'}}
        update = {'remove_state_ids': [], 'remove_relation_ids': [],
                  'upsert_entities': [], 'upsert_states': [],
                  'upsert_relations': [], 'epistemic_gaps': [],
                  'achievement_gaps': initial['achievement_gaps'],
                  'frontier': initial['frontier']}
        issue = {'targets': ['clean'], 'issue_type': 'unsupported',
                 'problem': 'Unverified.', 'evidence_step': 0,
                 'evidence_quote': 'Still dirty.', 'evidence': 'Still dirty.',
                 'suggestion': 'Keep the gap.'}
        self.script = [(200, sse('{"issues": []}')),
                       (200, sse(json.dumps({'issues': [issue]}))),
                       (503, b'synthetic unavailable')]
        belief = iter([json.dumps(initial), json.dumps(update), json.dumps(update)])
        episode = PoSEpisode(case_id='synthetic', config=execution_config(),
            logger=self.ledger, belief_call=lambda _: next(belief),
            consistency_call=self.transport.caller('consistency'),
            progress_call=lambda _: '{}', manager_class=ComplementBeliefManager)
        episode.reset(task='Clean mug.', observation='Dirty.', actions=[])
        with self.assertRaises(llmcore.AuxiliaryResponseRejected):
            episode.update(thought='Inspect', action_batch=[{'id': 'c1',
                'name': 'inspect', 'arguments': {}, 'order': 0,
                'status': 'executed'}], observation='Still dirty.')
        self.assertEqual(len(self.posts), 3)


if __name__ == '__main__': unittest.main(verbosity=2)
