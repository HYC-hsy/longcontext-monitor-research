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
from llmcore import NativeClaudeSession, NativeToolClient
from pos_bridge import PoSBridge, PoSBridgeError
from test_offline import replies


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
    def test_default_off_does_not_create_pos(self):
        with patch.dict(os.environ, {'GA_POS_ENABLED': '0', 'GA_PMA_ENABLED': '0',
                                     'GA_PMA_UPSTREAM_ENABLED': '0'}):
            client = Client([response('done')])
            outcome = exhaust(agent_runner_loop(client, 'RUN_CONSTRAINT', 'ORIGINAL_TASK',
                         Handler(), [], max_turns=1, verbose=False))
        self.assertEqual(outcome['result'], 'CURRENT_TASK_DONE')
        self.assertEqual(client.views, [None])

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
            self.assertEqual(result['scored_decision_batches'], 1)
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
            self.assertEqual(result['scored_decision_batches'], 1)
            batch = result['raw_trajectory'][-1]['action']
            self.assertEqual([x['status'] for x in batch],
                             ['executed', 'not_executed'])
            self.assertIsNone(batch[0]['result']['exit_code'])
            self.assertEqual(batch[0]['result']['process_state'], 'still_running')
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


if __name__ == '__main__': unittest.main(verbosity=2)
