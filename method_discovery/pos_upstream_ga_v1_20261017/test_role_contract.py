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
from prompts.prompt_generation import build_belief_update_prompt, build_initial_belief_prompt, build_belief_text_prompt
from episode import PoSEpisode, execution_config
from test_offline import replies, Recorder
from worker import (RoleTransport, _adapt_role_json, _role_input_contract,
                    ROLE_OBJECT_INSTRUCTION, ROLE_UPDATE_FIELDS_INSTRUCTION)
from method_discovery.pos_upstream_ga_v1_20261017 import serial_live
from method_discovery.pos_upstream_ga_v1_20261017.compatibility_probe import compatibility_checks


def fenced(value):
    return '```json\n' + value + '\n```'


class RoleContractTests(unittest.TestCase):
    def test_six_historical_responses_remain_original_failures(self):
        rows = [json.loads(line) for line in
            (HERE / 'raw_compat_v2/probe/role_events.jsonl').read_text(
                encoding='utf-8').splitlines()]
        answers = [row for row in rows if row['event'] == 'pos_role_response']
        self.assertEqual(len(answers), 6)
        self.assertEqual([row['response'] for row in answers],
                         [row['raw_response'] for row in rows
                          if row['event'] == 'pos_role_json_adapter'])
        self.assertTrue(any(_adapt_role_json(row['response'])[0] == row['response']
                            for row in answers))
        self.assertTrue(any(row['event'] == 'belief_sentinel_audit_failed'
                            for row in rows))
        self.assertTrue(any(row['event'] == 'belief_model_schema_error'
                            for row in rows))

    def test_update_interface_scope_covers_repair_without_changing_upstream(self):
        config = execution_config()
        update = build_belief_update_prompt({}, {'action':'x','observation':'y'},
                                            {'done':False}, config)
        initial = build_initial_belief_prompt({'task':'x','observation':'y'}, config)
        textual = build_belief_text_prompt({}, {}, [], [], config)
        for source, expected in ((update, 'update_records'),
                                 (update + [{'role':'user','content':'repair'}], 'update_records'),
                                 (initial, 'object_only'), (textual, 'object_only')):
            effective, note, scope = _role_input_contract('belief', source)
            self.assertEqual(scope, expected)
            self.assertEqual(effective[:-1], source)
            self.assertEqual(effective[-1], {'role':'system','content':note})
            self.assertIn(ROLE_OBJECT_INSTRUCTION, note)
            self.assertEqual(ROLE_UPDATE_FIELDS_INSTRUCTION in note,
                             expected == 'update_records')
        for role in ('consistency', 'progress'):
            self.assertEqual(_role_input_contract(role, update)[2], 'object_only')

    def test_original_minimal_optional_alias_and_invalid_fields(self):
        minimum = {'remove_state_ids': [], 'remove_relation_ids': [],
            'upsert_entities': [{'entity_id':'e1','entity_type':'object','name':'item'}],
            'upsert_states': [{'state_id':'s1','entity_id':'e1','description':'visible'}],
            'upsert_relations': [{'relation_id':'r1','src':'e1','dst':'e1',
                                  'relation':'self'}],
            'epistemic_gaps': [], 'achievement_gaps': [], 'frontier': None}
        normalized = BeliefManager._normalize_model_payload(json.loads(json.dumps(minimum)),
                                                             'update')
        self.assertEqual(normalized['upsert_relations'][0]['source_id'], 'e1')
        self.assertEqual(normalized['upsert_relations'][0]['target_id'], 'e1')
        BeliefManager._validate_model_payload(normalized, 'update')
        for wrong in ({**minimum, 'unknown': 1},
                      {**minimum, 'upsert_entities':[{'entity_id':'e1','name':'item'}]}):
            with self.assertRaises((TypeError, ValueError)):
                BeliefManager._validate_model_payload(wrong, 'update')

    def test_probe_final_outcomes_not_merely_roles_seen(self):
        fixed = replies()
        fixed['belief'].insert(0, 'not JSON')
        logger = Recorder()
        transport = RoleTransport(mode='fake', replies=fixed, archive=logger)
        episode = PoSEpisode(case_id='probe-gate', config=execution_config(),
            logger=logger, belief_call=transport.caller('belief'),
            consistency_call=transport.caller('consistency'),
            progress_call=transport.caller('progress'))
        initial = episode.reset(task='Clean mug 1.', observation='Mug dirty.', actions=[])
        updated = episode.update(thought='Inspect.', action_batch=[{'id':'c1',
            'name':'inspect','arguments':{},'order':0,'status':'executed'}],
            observation='Still dirty.')
        episode.manager.close()
        result = episode.get_result()
        wire = [{'http_status':200,'returned_model':'claude-opus-4-8',
                 'stop_reason':'end_turn'}]
        roles = [row['role'] for row in transport.calls]
        def gate(rows=logger.events, state=result, finished=True):
            return compatibility_checks(rows, state, initial, updated, wire,
                                        roles, work_finished=finished)
        self.assertEqual(gate()['status'], 'passed', (gate(),
            [(row['event'], row.get('step'), row.get('operation')) for row in logger.events]))
        self.assertTrue(any(row['event']=='belief_model_parse_error'
                            for row in logger.events))
        self.assertEqual(gate(finished=False)['status'], 'failed')
        no_audit = [row for row in logger.events if
                    row['event'] != 'belief_sentinel_audit_completed']
        no_audit.append({'event':'belief_sentinel_audit_failed','step':0})
        self.assertFalse(gate(rows=no_audit)['checks']['sentinel_final_audit_resolved'])
        no_progress = json.loads(json.dumps(result))
        no_progress['health_transitions'][0]['progress'] = None
        self.assertFalse(gate(state=no_progress)['checks']['valid_nonterminal_progress'])
        rejected = logger.events + [{'event':'belief_candidate_rejected','step':0,
                                     'issues':[{'reason':'legitimate'}]}]
        self.assertEqual(gate(rows=rejected)['status'], 'passed')

    def test_original_correction_exhaustion_and_sentinel_text_fallback(self):
        fixed = replies()
        fixed['belief'] = ['not JSON', 'still not JSON']
        logger = Recorder()
        transport = RoleTransport(mode='fake', replies=fixed, archive=logger)
        episode = PoSEpisode(case_id='exhaustion', config=execution_config(),
            logger=logger, belief_call=transport.caller('belief'),
            consistency_call=transport.caller('consistency'),
            progress_call=transport.caller('progress'))
        with self.assertRaises(json.JSONDecodeError):
            episode.reset(task='Clean mug 1.', observation='Mug dirty.', actions=[])
        self.assertEqual(len([row for row in logger.events if
            row['event']=='belief_model_parse_error']), 2)

        fixed = replies()
        fixed['consistency'] = ['invalid audit', 'invalid audit']
        logger = Recorder()
        transport = RoleTransport(mode='fake', replies=fixed, archive=logger)
        episode = PoSEpisode(case_id='audit-fallback', config=execution_config(),
            logger=logger, belief_call=transport.caller('belief'),
            consistency_call=transport.caller('consistency'),
            progress_call=transport.caller('progress'))
        context = episode.reset(task='Clean mug 1.', observation='Mug dirty.', actions=[])
        self.assertTrue(context['belief_text'])
        self.assertTrue(any(row['event']=='belief_sentinel_audit_failed'
                            for row in logger.events))

        fixed = replies()
        fixed['progress'][0] = '{"progress":2}'
        logger = Recorder()
        transport = RoleTransport(mode='fake', replies=fixed, archive=logger)
        episode = PoSEpisode(case_id='unscored', config=execution_config(),
            logger=logger, belief_call=transport.caller('belief'),
            consistency_call=transport.caller('consistency'),
            progress_call=transport.caller('progress'))
        episode.reset(task='Clean mug 1.', observation='Mug dirty.', actions=[])
        episode.update(thought='Inspect.', action_batch=[{'id':'c1',
            'name':'inspect','arguments':{},'order':0,'status':'executed'}],
            observation='Still dirty.')
        self.assertEqual(episode.get_result()['scored_transitions'], 0)
        self.assertTrue(any(row['event']=='belief_sentinel_progress_failed'
                            for row in logger.events))

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
            update_prompt = build_belief_update_prompt({},
                {'action':'synthetic','observation':'synthetic'},
                {'done':False}, execution_config())
            self.assertEqual(transport.caller('belief')(update_prompt), '{"issues":[]}')
            task = llmcore.NativeClaudeSession(profile)
            generator = task.raw_ask([{'role':'user','content':[{'type':'text',
                'text':'Synthetic Task request.'}]}])
            with self.assertRaises(StopIteration):
                while True: next(generator)
        self.assertEqual(len(payloads), 5)
        for role, payload in zip(('belief','consistency','progress'), payloads[:3]):
            self.assertEqual(payload['thinking'], {'type':'disabled'})
            self.assertEqual(payload['temperature'], 0)
            self.assertEqual(payload['max_tokens'], 4096 if role == 'belief' else 512)
        self.assertIn(ROLE_OBJECT_INSTRUCTION, payloads[3]['system'][0]['text'])
        self.assertIn(ROLE_UPDATE_FIELDS_INSTRUCTION, payloads[3]['system'][0]['text'])
        self.assertTrue(any(item['content'][0]['text'] == update_prompt[1]['content']
                            for item in payloads[3]['messages']))
        self.assertNotIn(ROLE_UPDATE_FIELDS_INSTRUCTION, payloads[0]['system'][0]['text'])
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

    def test_required_pos_provider_capture_binds_worker_request_before_send(self):
        class HTTP:
            status_code = 200
            headers = {}
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def close(self): pass
            def json(self): return {'content': [{'type': 'text',
                'text': '{"issues":[]}'}],
                'usage': {'input_tokens': 1, 'output_tokens': 1}}
        profile = {'apibase': 'https://fixture.invalid', 'apikey': 'OFFLINE-SECRET',
                   'model': 'claude-opus-4-8', 'max_tokens': 1000,
                   'thinking_type': 'adaptive', 'max_retries': 0, 'stream': False}
        with tempfile.TemporaryDirectory() as tmp:
            capture_path = Path(tmp) / 'role.provider.jsonl'
            transport = RoleTransport(mode='profile', profile=profile,
                archive=Recorder(), capture_path=capture_path,
                run_id='fixture-run', task_id='fixture-task')
            with patch.dict(os.environ, {'GA_PMA_CAPTURE_TASK_REQUESTS': '1'}), \
                 patch('llmcore.requests.post', return_value=HTTP()) as post:
                self.assertEqual(transport.caller('belief')([
                    {'role': 'user', 'content': 'Synthetic role request.'}]),
                    '{"issues":[]}')
                self.assertEqual(post.call_count, 1)
            rows = [json.loads(line) for line in capture_path.read_text(
                encoding='utf-8').splitlines()]
            kinds = [row['event_type'] for row in rows]
            self.assertLess(kinds.index('provider_request_ready'),
                            kinds.index('provider_request_attempt'))
            self.assertLess(kinds.index('provider_request_attempt'),
                            kinds.index('provider_response'))
            self.assertTrue(all(row['run_id'] == 'fixture-run' and
                                row['task_id'] == 'fixture-task' for row in rows))
            public = capture_path.read_text(encoding='utf-8')
            self.assertNotIn('OFFLINE-SECRET', public)
            self.assertNotIn('https://fixture.invalid', public)
            missing = RoleTransport(mode='profile', profile=profile,
                archive=Recorder(), run_id='fixture-run', task_id='fixture-task')
            with patch.dict(os.environ, {'GA_PMA_CAPTURE_TASK_REQUESTS': '1'}), \
                 patch('llmcore.requests.post') as post:
                with self.assertRaisesRegex(RuntimeError,
                                            'capture binding unavailable before send'):
                    missing.caller('belief')([{'role': 'user',
                        'content': 'Synthetic role request.'}])
                post.assert_not_called()

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
