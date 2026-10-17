"""Bounded PoS role contract, historical replay and actual HTTP serialization."""
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE / 'vendor'),
                str(HERE.parents[1] / 'GenericAgent-main')]
import llmcore
from belief.manager import BeliefManager
from episode import PoSEpisode, execution_config
from test_offline import replies, Recorder
from worker import RoleTransport, _adapt_role_json
from method_discovery.pos_upstream_ga_v1_20261017 import serial_live


def fenced(value):
    return '```json\n' + value + '\n```'


class RoleContractTests(unittest.TestCase):
    def test_historical_two_public_answers_replayed_without_rewriting(self):
        rows = [json.loads(line) for line in
            (HERE / 'raw_compat_v1/role_events.jsonl').read_text(
                encoding='utf-8').splitlines()]
        original = [row['response'] for row in rows
                    if row['event'] == 'pos_role_response']
        self.assertEqual(len(original), 2)
        for raw in original:
            with self.subTest(length=len(raw)):
                with self.assertRaises(json.JSONDecodeError): json.loads(raw)
                body, status, removed = _adapt_role_json(raw)
                self.assertEqual(status, 'outer_fence_removed')
                self.assertEqual(raw, removed['leading'] + removed['opening'] +
                                 body + removed['closing'] + removed['trailing'])
                parsed = json.loads(body)
                BeliefManager._validate_model_payload(parsed, 'initialize')

    def test_only_one_complete_strict_object_fence_is_accepted(self):
        valid = ['```json\n{"x": 1}\n```',
                 ' \t\r\n```\r\n{"x": "line\\nvalue"}\r\n```\t\n']
        for raw in valid:
            with self.subTest(raw=raw):
                body, status, boundary = _adapt_role_json(raw)
                self.assertEqual(status, 'outer_fence_removed')
                self.assertEqual(raw, boundary['leading'] + boundary['opening'] +
                                 body + boundary['closing'] + boundary['trailing'])
        plain = '{"x":1,"x":2}'
        self.assertEqual(_adapt_role_json(plain), (plain, 'unchanged', None))
        rejected = [
            'before\n' + fenced('{"x":1}'), fenced('{"x":1}') + '\nafter',
            fenced('{"x":1}') + '\n' + fenced('{"y":2}'),
            fenced('{"x":1} {"y":2}'), fenced('{"x":'),
            fenced('{"x":1,"x":2}'), fenced('{"x":NaN}'),
            fenced('{"x":Infinity}'), fenced('{"x":1e999}'),
            fenced('[1,2]'), fenced('3'), fenced('null'),
            fenced('{"x":1}') + '\n[!!! Response truncated: max_tokens !!!]',
            '````json\n{"x":1}\n````',
        ]
        for raw in rejected:
            with self.subTest(raw=raw):
                self.assertIs(_adapt_role_json(raw)[0], raw)

    def test_original_role_parsers_receive_adapter_input_and_still_validate(self):
        fixed = {role: [fenced(value) for value in sequence]
                 for role, sequence in replies().items()}
        logger = Recorder()
        transport = RoleTransport(mode='fake', replies=fixed, archive=logger)
        episode = PoSEpisode(case_id='role-contract', config=execution_config(),
            logger=logger, belief_call=transport.caller('belief'),
            consistency_call=transport.caller('consistency'),
            progress_call=transport.caller('progress'))
        episode.reset(task='Clean mug 1.', observation='Mug dirty.', actions=[])
        episode.update(thought='Inspect.', action_batch=[{'id':'c1',
            'name':'inspect', 'arguments':{}, 'order':0, 'status':'executed'}],
            observation='Still dirty.')
        episode.manager.close()
        events = logger.events
        adapted = [row for row in events if row['event'] == 'pos_role_json_adapter']
        self.assertTrue(adapted)
        self.assertTrue(all(row['transform'] == 'outer_fence_removed' for row in adapted))
        self.assertTrue(all(row['raw_response'].startswith('```json\n') and
                            row['parser_input'].startswith('{') for row in adapted))
        self.assertTrue(any(row['event'] == 'belief_model_input' and
                            row.get('operation') == 'textualize' for row in events))
        self.assertTrue(any(row['event'] == 'belief_model_response' and
                            row['raw_response'].startswith('{') for row in events))
        self.assertTrue(any(row['event'] == 'belief_sentinel_model_response' and
                            row['raw_response'].startswith('{') for row in events))
        self.assertTrue(any(row['event'] == 'belief_sentinel_progress_model_response' and
                            row['raw_response'].startswith('{') for row in events))
        self.assertEqual(episode.get_result()['scored_transitions'], 1)

    def test_rejected_fence_gets_original_upstream_correction_not_new_retry(self):
        fixed = replies()
        fixed['belief'].insert(0, fenced('{"x":1,"x":2}'))
        logger = Recorder()
        transport = RoleTransport(mode='fake', replies=fixed, archive=logger)
        episode = PoSEpisode(case_id='reject-contract', config=execution_config(),
            logger=logger, belief_call=transport.caller('belief'),
            consistency_call=transport.caller('consistency'),
            progress_call=transport.caller('progress'))
        episode.reset(task='Clean mug 1.', observation='Mug dirty.', actions=[])
        self.assertEqual(len([row for row in transport.calls if row['role'] == 'belief']), 3)
        self.assertTrue(any(row['event'] == 'belief_model_parse_error' and
                            row['attempt'] == 0 for row in logger.events))
        self.assertTrue(any(row['event'] == 'pos_role_json_adapter' and
                            row['transform'] == 'fence_rejected' for row in logger.events))

    def test_actual_raw_ask_payload_changes_only_pos_role_copy(self):
        payloads = []
        class HTTP:
            status_code = 200
            headers = {}
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def close(self): pass
            def json(self): return {'content': [{'type':'text', 'text':'{"issues":[]}'}],
                                    'usage': {'input_tokens':1, 'output_tokens':1}}
        def post(_url, **kwargs):
            payloads.append(kwargs['json'])
            return HTTP()
        profile = {'apibase':'https://fixture.invalid', 'apikey':'OFFLINE-ONLY',
                   'model':'claude-opus-4-8', 'max_tokens':1000,
                   'temperature':1, 'thinking_type':'adaptive',
                   'max_retries':0, 'stream':False}
        logger = Recorder()
        transport = RoleTransport(mode='profile', profile=profile, archive=logger)
        with patch('llmcore.requests.post', side_effect=post):
            for role in ('belief', 'consistency', 'progress'):
                self.assertEqual(transport.caller(role)([{'role':'user',
                    'content':'Synthetic role request.'}]), '{"issues":[]}')
            task = llmcore.NativeClaudeSession(profile)
            generator = task.raw_ask([{'role':'user','content':[{'type':'text',
                'text':'Synthetic Task request.'}]}])
            with self.assertRaises(StopIteration):
                while True: next(generator)
        self.assertEqual(len(payloads), 4)
        for role, payload in zip(('belief','consistency','progress'), payloads[:3]):
            self.assertEqual(payload['thinking'], {'type':'disabled'})
            self.assertEqual(payload['temperature'], 0)
            self.assertEqual(payload['max_tokens'], 4096 if role == 'belief' else 512)
        self.assertEqual(payloads[-1]['thinking'], {'type':'adaptive'})
        self.assertNotIn('temperature', payloads[-1])
        self.assertEqual(payloads[-1]['max_tokens'], 1000)
        self.assertEqual(profile['temperature'], 1)
        self.assertEqual(profile['thinking_type'], 'adaptive')
        capture = os.environ.get('POS_ROLE_HTTP_CAPTURE')
        if capture:
            with Path(capture).open('x', encoding='utf-8', newline='\n') as stream:
                json.dump({'schema': 'pos-role-http-boundary-offline-v1',
                           'transport': 'patched_requests_post_no_provider',
                           'payloads': payloads}, stream, ensure_ascii=False, indent=2)
                stream.write('\n')

    def test_old_status_bit_cannot_authorize_new_serial_run(self):
        old = HERE / 'raw_compat_v1'
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'authorized_serial_scope.json').write_text(
                json.dumps({'schema':'pos-ga-user-authorized-serial-scope-v1',
                            'code_commit':'stale'}), encoding='utf-8')
            for name in ('http_attempts.json', 'role_events.jsonl'):
                shutil.copyfile(old / name, root / name)
            result = json.loads((old / 'result.json').read_text(encoding='utf-8'))
            result['status'] = 'passed'
            (root / 'result.json').write_text(json.dumps(result), encoding='utf-8')
            args = SimpleNamespace(output=str(root), compatibility_result=str(root / 'result.json'),
                                   task_profile_file=str(root / 'private-not-present'),
                                   certification=str(root / 'not-certified'))
            with self.assertRaisesRegex(RuntimeError, 'bound PoS compatibility'):
                serial_live.run(args)
            self.assertFalse(any(root.glob('authorization.json')))


if __name__ == '__main__': unittest.main(verbosity=2)
