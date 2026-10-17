"""Actual GA loop/native-send seams with fake responses only."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
GA = HERE.parents[1] / 'GenericAgent-main'
sys.path.insert(0, str(GA))
from agent_loop import BaseHandler, StepOutcome, agent_runner_loop, exhaust
from ga import GenericAgentHandler
from llmcore import NativeClaudeSession, NativeToolClient
from pos_bridge import PoSBridge, PoSBridgeError
from test_offline import replies, Recorder, callers
from episode import PoSEpisode, execution_config


class Handler(BaseHandler):
    def __init__(self):
        self.parent = SimpleNamespace(task_dir=None)
        self._done_hooks = []
        self.code_stop_signal = SimpleNamespace(clear=lambda: None)
    def do_probe(self, args, response):
        if False: yield None
        return StepOutcome({'stdout': 'CURRENT_OBSERVATION_MARKER'},
                           next_prompt='Current user instruction remains in effect.')
    def do_stop(self, args, response):
        if False: yield None
        return StepOutcome({'stdout': 'PARTIAL_RESULT', 'exit_code': None,
                            'process_state': 'still_running'}, next_prompt=None)
    def do_no_tool(self, args, response):
        if False: yield None
        return StepOutcome(response, next_prompt=None)
    def turn_end_callback(self, response, tool_calls, tool_results, turn,
                          next_prompt, exit_reason):
        return next_prompt


class Client:
    last_tools = ''
    def __init__(self, responses):
        self.responses = iter(responses)
        self.views = []
    def chat(self, messages, tools, request_view=None):
        self.views.append(request_view)
        if False: yield None
        return next(self.responses)


def response(content, tools=()):
    return SimpleNamespace(content=content, thinking='HIDDEN_THINKING_CANARY',
                           tool_calls=list(tools))


class SeamTests(unittest.TestCase):
    def test_actual_ga_current_instruction_source_and_lifetime(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / '_keyinfo'
            path.write_text('FILE_CURRENT_INSTRUCTION', encoding='utf-8')
            parent = SimpleNamespace(task_dir=tmp, extrakeyinfo='DIRECT_CURRENT_INSTRUCTION',
                                     pos_decision_context=True,
                                     obligation_ledger=None,
                                     evidence_completion_kernel=None)
            handler = GenericAgentHandler(parent)
            fresh = handler.consume_pos_current_instruction()
            self.assertIn('DIRECT_CURRENT_INSTRUCTION', fresh)
            self.assertIn('FILE_CURRENT_INSTRUCTION', fresh)
            self.assertNotIn('WORKING MEMORY', fresh)
            self.assertIsNone(parent.extrakeyinfo)
            self.assertFalse(path.exists())
            self.assertEqual(handler.consume_pos_current_instruction(), '')

    def test_http_boundary_hybrid_view_thinking_and_native_tools(self):
        fixed = replies()
        role = callers(fixed, [])
        episode = PoSEpisode(case_id='http-fixture', config=execution_config(),
            logger=Recorder(), belief_call=role('belief'),
            consistency_call=role('consistency'), progress_call=role('progress'))
        tools = [{'type': 'function', 'function': {'name': 'probe',
            'description': 'native probe', 'parameters': {'type': 'object'}}}]
        episode.reset(task='ORIGINAL_TASK clean mug', observation='initial', actions=tools)
        view = episode.decision_view(current_observation='CURRENT_OBSERVATION_MARKER',
            actions=tools, runtime_constraints='[MASTER] NEW_CURRENT_INSTRUCTION')
        backend = NativeClaudeSession({'apibase': 'https://fixture.invalid',
            'apikey': 'SYNTHETIC-NO-ACCESS', 'model': 'claude-opus-4-8',
            'max_tokens': 64, 'max_retries': 0, 'stream': False})
        backend.history = [{'role': 'user', 'content': [{'type': 'text',
            'text': 'OLD_BACKEND_HISTORY_CANARY'}]}]
        captured = []
        class HTTP:
            status_code = 200
            headers = {}
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def json(self):
                return {'content': [
                    {'type': 'thinking', 'thinking': 'HIDDEN_NATIVE_THINKING_CANARY'},
                    {'type': 'tool_use', 'name': 'probe', 'id': 'a', 'input': {}},
                    {'type': 'tool_use', 'name': 'probe', 'id': 'b', 'input': {}}],
                    'usage': {'input_tokens': 1, 'output_tokens': 1}}
            def close(self): pass
        def post(url, **kwargs):
            captured.append(kwargs['json'])
            return HTTP()
        client = NativeToolClient(backend)
        with patch('llmcore.requests.post', side_effect=post):
            result = exhaust(client.chat(messages=[{'role': 'user',
                'content': 'OLD_WORKING_MEMORY_CANARY'}], tools=tools,
                request_view={'system': 'RUN_CONSTRAINT\n' + view['system'],
                              'user': view['user']}))
        self.assertEqual(result.content, '')
        self.assertEqual(len(result.tool_calls), 2)
        self.assertIn('HIDDEN_NATIVE_THINKING_CANARY', result.thinking)
        payload = json.dumps(captured)
        for marker in ('OLD_BACKEND_HISTORY_CANARY', 'OLD_WORKING_MEMORY_CANARY',
                       'HIDDEN_NATIVE_THINKING_CANARY', 'claim_done', '<summary>'):
            self.assertNotIn(marker, payload)
        for marker in ('ORIGINAL_TASK', 'CURRENT_OBSERVATION_MARKER',
                       'NEW_CURRENT_INSTRUCTION', 'RUN_CONSTRAINT', 'Active Gap'):
            self.assertIn(marker, payload)
        self.assertEqual(len(captured[0]['tools']), 1)
        if os.environ.get('POS_AUDIT_HTTP_CAPTURE'):
            Path(os.environ['POS_AUDIT_HTTP_CAPTURE']).write_text(json.dumps({
                'request_payload': captured[0],
                'response_blocks': HTTP().json()['content'],
                'parsed_public_content': result.content,
                'parsed_tool_calls': [call.function.name for call in result.tool_calls],
                'hidden_thinking_excluded_from_request': True},
                ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    def test_same_parent_pos_on_then_off_restores_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixed = root / 'replies.json'
            fixed.write_text(json.dumps(replies()), encoding='utf-8')
            handler = Handler()
            handler.parent.pos_decision_context = False
            env = {'GA_POS_ENABLED': '1', 'GA_PMA_ENABLED': '0',
                   'GA_PMA_UPSTREAM_ENABLED': '0', 'GA_MONITOR_ENABLED': '0',
                   'GA_M0_MONITOR_ENABLED': '0', 'GA_POS_TRANSPORT': 'fake',
                   'GA_POS_WORKER_SCRIPT': str(HERE / 'worker.py'),
                   'GA_POS_VENDOR_ROOT': str(HERE / 'vendor'),
                   'GA_POS_EPISODE_MODULE': str(HERE / 'episode.py'),
                   'GA_POS_ARCHIVE': str(root / 'events.jsonl'),
                   'GA_POS_FAKE_REPLIES': str(fixed)}
            with patch.dict(os.environ, env):
                exhaust(agent_runner_loop(Client([response('done')]), 'system',
                    'task', handler, [], max_turns=1, verbose=False))
            self.assertFalse(handler.parent.pos_decision_context)
            self.assertFalse(hasattr(handler.parent, '_pos_bridge'))
            with patch.dict(os.environ, {'GA_POS_ENABLED': '0'}):
                client = Client([response('done')])
                exhaust(agent_runner_loop(client, 'system', 'task', handler,
                    [], max_turns=1, verbose=False))
            self.assertEqual(client.views, [None])

    def test_default_off_does_not_create_pos(self):
        with patch.dict(os.environ, {'GA_POS_ENABLED': '0', 'GA_PMA_ENABLED': '0',
                                     'GA_PMA_UPSTREAM_ENABLED': '0'}):
            client = Client([response('done')])
            outcome = exhaust(agent_runner_loop(client, 'RUN_CONSTRAINT', 'ORIGINAL_TASK',
                         Handler(), [], max_turns=1, verbose=False))
        self.assertEqual(outcome['result'], 'CURRENT_TASK_DONE')
        self.assertEqual(client.views, [None])

    def test_profile_env_boolean_cannot_authorize_pos(self):
        env = {'GA_POS_TRANSPORT': 'profile', 'GA_POS_LIVE_AUTHORIZED': '1',
               'GA_POS_WORKER_SCRIPT': str(HERE / 'worker.py'),
               'GA_POS_VENDOR_ROOT': str(HERE / 'vendor'),
               'GA_POS_EPISODE_MODULE': str(HERE / 'episode.py'),
               'GA_POS_ARCHIVE': 'unused-events.jsonl'}
        with patch.dict(os.environ, env):
            with self.assertRaisesRegex(PoSBridgeError, 'unfinished'):
                PoSBridge.from_environment()

    def test_native_final_send_is_stateless_with_old_canaries(self):
        backend = NativeClaudeSession({'apibase': 'https://fixture.invalid',
            'apikey': 'SYNTHETIC-NO-ACCESS', 'model': 'claude-opus-4-8',
            'max_tokens': 64, 'max_retries': 0})
        backend.history = [{'role': 'user', 'content': [
            {'type': 'text', 'text': 'OLD_BACKEND_HISTORY_CANARY'}]}]
        seen = []
        def fake_raw(messages):
            seen.append({'messages': messages, 'system': backend.system,
                         'tools': backend.tools})
            if False: yield None
            return [{'type': 'text', 'text': 'done'}]
        backend.raw_ask = fake_raw
        client = NativeToolClient(backend)
        client._pending_tool_ids = ['OLD_TOOL_ID_CANARY']
        tools = [{'type': 'function', 'function': {'name': 'probe',
                   'description': 'probe', 'parameters': {'type': 'object'}}}]
        result = exhaust(client.chat(messages=[{'role': 'user',
            'content': '[WORKING MEMORY] OLD_SUMMARY_CANARY'}], tools=tools,
            request_view={'system': 'RUN_CONSTRAINT',
                          'user': 'ORIGINAL_TASK CURRENT_OBSERVATION_MARKER ACTIVE_GAP'}))
        self.assertEqual(result.content, 'done')
        payload = json.dumps(seen)
        for canary in ('OLD_BACKEND_HISTORY_CANARY', 'OLD_TOOL_ID_CANARY',
                       'OLD_SUMMARY_CANARY'):
            self.assertNotIn(canary, payload)
        for required in ('RUN_CONSTRAINT', 'ORIGINAL_TASK',
                         'CURRENT_OBSERVATION_MARKER', 'ACTIVE_GAP', 'probe'):
            self.assertIn(required, payload)
        self.assertEqual(len(backend.history), 1)

    def test_loop_one_joint_batch_and_terminal_no_fake_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixed = root / 'replies.json'
            fixed.write_text(json.dumps(replies()), encoding='utf-8')
            env = {'GA_POS_ENABLED': '1', 'GA_PMA_ENABLED': '0',
                   'GA_PMA_UPSTREAM_ENABLED': '0', 'GA_MONITOR_ENABLED': '0',
                   'GA_M0_MONITOR_ENABLED': '0', 'GA_POS_TRANSPORT': 'fake',
                   'GA_POS_WORKER_SCRIPT': str(HERE / 'worker.py'),
                   'GA_POS_VENDOR_ROOT': str(HERE / 'vendor'),
                   'GA_POS_EPISODE_MODULE': str(HERE / 'episode.py'),
                   'GA_POS_ARCHIVE': str(root / 'pos_events.jsonl'),
                   'GA_POS_FAKE_REPLIES': str(fixed), 'GA_BENCH_TASK_ID': 'fixture'}
            tool = SimpleNamespace(id='tool-1', function=SimpleNamespace(
                name='probe', arguments='{}'))
            client = Client([response('inspect', [tool]), response('done')])
            with patch.dict(os.environ, env):
                outcome = exhaust(agent_runner_loop(client, 'RUN_CONSTRAINT',
                    'ORIGINAL_TASK', Handler(), [{'type': 'function',
                    'function': {'name': 'probe', 'parameters': {'type': 'object'}}}],
                    max_turns=2, verbose=False))
            self.assertEqual(outcome['result'], 'CURRENT_TASK_DONE')
            self.assertEqual(len(client.views), 2)
            self.assertIn('ORIGINAL_TASK', client.views[0]['user'])
            self.assertIn('CURRENT_OBSERVATION_MARKER', client.views[1]['user'])
            self.assertNotIn('HIDDEN_THINKING_CANARY', client.views[1]['user'])
            records = [json.loads(x) for x in (root / 'pos_events.jsonl').read_text(
                encoding='utf-8').splitlines()]
            result = next(x['result'] for x in records if x['event'] == 'pos_episode_result')
            self.assertEqual(result['completed_decision_batches'], 2)
            self.assertFalse(result['success_known'])

    def test_terminal_joint_batch_keeps_unexecuted_suffix_and_partial_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixed = root / 'replies.json'
            fixed.write_text(json.dumps(replies()), encoding='utf-8')
            env = {'GA_POS_ENABLED': '1', 'GA_PMA_ENABLED': '0',
                   'GA_PMA_UPSTREAM_ENABLED': '0', 'GA_MONITOR_ENABLED': '0',
                   'GA_M0_MONITOR_ENABLED': '0', 'GA_POS_TRANSPORT': 'fake',
                   'GA_POS_WORKER_SCRIPT': str(HERE / 'worker.py'),
                   'GA_POS_VENDOR_ROOT': str(HERE / 'vendor'),
                   'GA_POS_EPISODE_MODULE': str(HERE / 'episode.py'),
                   'GA_POS_ARCHIVE': str(root / 'events.jsonl'),
                   'GA_POS_FAKE_REPLIES': str(fixed)}
            calls = [SimpleNamespace(id='id-' + str(i),
                function=SimpleNamespace(name=name, arguments='{}'))
                for i, name in enumerate(('stop', 'probe'))]
            client = Client([response('MIXED_TEXT', calls)])
            with patch.dict(os.environ, env):
                outcome = exhaust(agent_runner_loop(client, 'RUN_CONSTRAINT',
                    'ORIGINAL_TASK', Handler(), [], max_turns=1, verbose=False))
            self.assertEqual(outcome['result'], 'CURRENT_TASK_DONE')
            rows = [json.loads(x) for x in (root / 'events.jsonl').read_text(
                encoding='utf-8').splitlines()]
            result = next(x['result'] for x in rows if x['event'] == 'pos_episode_result')
            self.assertEqual(result['completed_decision_batches'], 1)
            batch = result['raw_trajectory'][-1]['action']
            self.assertEqual([x['status'] for x in batch],
                             ['executed', 'not_executed'])
            self.assertNotIn('result', batch[0])
            receipt = json.loads(result['raw_trajectory'][-1]['observation'])['tool_results'][0]
            self.assertIsNone(receipt['result']['exit_code'])
            self.assertEqual(receipt['result']['process_state'], 'still_running')
            self.assertEqual(batch[1]['id'], 'id-1')

    def test_worker_failure_never_replays_accepted_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixed = root / 'replies.json'
            fixed.write_text(json.dumps({'belief': [], 'consistency': [],
                                         'progress': []}), encoding='utf-8')
            bridge = PoSBridge(worker_script=HERE / 'worker.py', vendor=HERE / 'vendor',
                episode_module=HERE / 'episode.py', archive=root / 'events.jsonl',
                mode='fake', fake_replies=fixed, timeout=10)
            with self.assertRaises(PoSBridgeError):
                bridge.exchange('reset', case_id='case', task='task',
                                observation='initial', actions=[])
            self.assertEqual(bridge.sent, 1)
            self.assertTrue(bridge.closed)
            rows = [json.loads(x) for x in (root / 'events.jsonl').read_text(
                encoding='utf-8').splitlines()]
            self.assertEqual(len([x for x in rows if x['event'] == 'pos_role_request']), 1)

    def test_terminal_auxiliary_update_failure_keeps_host_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixed = root / 'replies.json'
            fixture = replies()
            fixture['belief'] = fixture['belief'][:2]  # reset works; update cannot.
            fixed.write_text(json.dumps(fixture), encoding='utf-8')
            env = {'GA_POS_ENABLED': '1', 'GA_PMA_ENABLED': '0',
                   'GA_PMA_UPSTREAM_ENABLED': '0', 'GA_MONITOR_ENABLED': '0',
                   'GA_M0_MONITOR_ENABLED': '0', 'GA_POS_TRANSPORT': 'fake',
                   'GA_POS_WORKER_SCRIPT': str(HERE / 'worker.py'),
                   'GA_POS_VENDOR_ROOT': str(HERE / 'vendor'),
                   'GA_POS_EPISODE_MODULE': str(HERE / 'episode.py'),
                   'GA_POS_ARCHIVE': str(root / 'events.jsonl'),
                   'GA_POS_FAKE_REPLIES': str(fixed)}
            tool = SimpleNamespace(id='one', function=SimpleNamespace(
                name='stop', arguments='{}'))
            with patch.dict(os.environ, env):
                outcome = exhaust(agent_runner_loop(Client([response('', [tool])]),
                    'system', 'task', Handler(), [], max_turns=1, verbose=False))
            self.assertEqual(outcome['result'], 'CURRENT_TASK_DONE')
            persisted = json.loads((root / 'events.result.json').read_text(encoding='utf-8'))
            self.assertEqual(persisted['status'], 'partial')
            self.assertIn('fake PoS reply exhausted', json.dumps(persisted))
            host = [json.loads(x) for x in (root / 'events.host.jsonl').read_text(
                encoding='utf-8').splitlines()]
            self.assertEqual(host[-1]['payload']['host_exit_reason']['result'],
                             'CURRENT_TASK_DONE')
            tool_outcome = next(row for row in host if row['kind'] == 'tool_outcome')
            self.assertIsNone(tool_outcome['payload']['result']['exit_code'])

    def test_unknown_tool_is_rejected_observation_not_scored_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixed = root / 'replies.json'
            fixed.write_text(json.dumps(replies()), encoding='utf-8')
            env = {'GA_POS_ENABLED': '1', 'GA_PMA_ENABLED': '0',
                   'GA_PMA_UPSTREAM_ENABLED': '0', 'GA_MONITOR_ENABLED': '0',
                   'GA_M0_MONITOR_ENABLED': '0', 'GA_POS_TRANSPORT': 'fake',
                   'GA_POS_WORKER_SCRIPT': str(HERE / 'worker.py'),
                   'GA_POS_VENDOR_ROOT': str(HERE / 'vendor'),
                   'GA_POS_EPISODE_MODULE': str(HERE / 'episode.py'),
                   'GA_POS_ARCHIVE': str(root / 'events.jsonl'),
                   'GA_POS_FAKE_REPLIES': str(fixed)}
            tool = SimpleNamespace(id='unknown-1', function=SimpleNamespace(
                name='not_mounted', arguments='{}'))
            client = Client([response('', [tool]), response('done')])
            with patch.dict(os.environ, env):
                outcome = exhaust(agent_runner_loop(client, 'system', 'task',
                    Handler(), [], max_turns=2, verbose=False))
            self.assertEqual(outcome['result'], 'CURRENT_TASK_DONE')
            self.assertIn('not_mounted', client.views[1]['user'])
            persisted = json.loads((root / 'events.result.json').read_text(encoding='utf-8'))
            self.assertEqual(persisted['result']['scored_transitions'], 0)
            self.assertEqual(persisted['result']['completed_decision_batches'], 2)

    def test_tool_exception_records_started_unknown_and_partial(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixed = root / 'replies.json'
            fixed.write_text(json.dumps(replies()), encoding='utf-8')
            env = {'GA_POS_ENABLED': '1', 'GA_PMA_ENABLED': '0',
                   'GA_PMA_UPSTREAM_ENABLED': '0', 'GA_MONITOR_ENABLED': '0',
                   'GA_M0_MONITOR_ENABLED': '0', 'GA_POS_TRANSPORT': 'fake',
                   'GA_POS_WORKER_SCRIPT': str(HERE / 'worker.py'),
                   'GA_POS_VENDOR_ROOT': str(HERE / 'vendor'),
                   'GA_POS_EPISODE_MODULE': str(HERE / 'episode.py'),
                   'GA_POS_ARCHIVE': str(root / 'events.jsonl'),
                   'GA_POS_FAKE_REPLIES': str(fixed)}
            class Raises(Handler):
                def do_boom(self, args, response):
                    raise RuntimeError('synthetic tool failure after dispatch')
                    yield None
            call = SimpleNamespace(id='boom-1', function=SimpleNamespace(
                name='boom', arguments='{}'))
            handler = Raises()
            with patch.dict(os.environ, env):
                with self.assertRaisesRegex(RuntimeError, 'synthetic tool failure'):
                    exhaust(agent_runner_loop(Client([response('', [call])]),
                        'system', 'task', handler, [], max_turns=1, verbose=False))
            self.assertFalse(hasattr(handler.parent, 'pos_decision_context'))
            host = [json.loads(x) for x in (root / 'events.host.jsonl').read_text(
                encoding='utf-8').splitlines()]
            self.assertIn('tool_started', [x['kind'] for x in host])
            self.assertIn('tool_result_unknown_after_start', [x['kind'] for x in host])
            self.assertFalse(any(x['kind'] == 'tool_outcome' for x in host))
            persisted = json.loads((root / 'events.result.json').read_text(encoding='utf-8'))
            self.assertEqual(persisted['status'], 'partial')


if __name__ == '__main__': unittest.main(verbosity=2)
