"""Real GA loop/tool/request assembly with finite local HTTP and role scripts."""
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import agent_loop
import llmcore
from research_runtime import research_context
from tests.test_task_complete_response import ScriptedServer, stream


class SyntheticToolHandler(agent_loop.BaseHandler):
    def __init__(self, root):
        self.parent = SimpleNamespace(task_dir=str(root))
        self.root = root
        self._done_hooks = []
        self.calls = 0

    def do_touch(self, args, response):
        self.calls += 1
        (self.root / 'synthetic-artifact.txt').write_text(
            f'actual GA tool result {self.calls}', encoding='utf-8')
        return agent_loop.StepOutcome(
            {'path': 'synthetic-artifact.txt', 'written': self.calls},
            next_prompt='Continue the synthetic task.')


def run_fixture(root, run_id='synthetic-stateful-1'):
    """Single bounded fake-only trial, also used by single_run's offline route."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=False)
    replies = root / 'roles.json'
    replies.write_text(json.dumps([
                {'role': 'maintenance', 'shape': 'empty'},
                {'role': 'audit', 'shape': 'clean'},
                {'role': 'selection', 'shape': 'silent'},
                {'role': 'maintenance', 'shape': 'observed_state'},
                {'role': 'audit', 'shape': 'clean'},
                {'role': 'selection', 'shape': 'remind'},
                {'role': 'maintenance', 'shape': 'empty'},
                {'role': 'audit', 'shape': 'clean'},
                {'role': 'selection', 'shape': 'silent'},
    ]), encoding='utf-8')
    env = {'GA_STATEFUL_MEMORY_ENABLED': '1',
                   'GA_STATEFUL_MEMORY_MODE': 'fake-only',
                   'GA_STATEFUL_MEMORY_DB': str(root / 'state.sqlite3'),
                   'GA_STATEFUL_FAKE_REPLIES': str(replies),
                   'GA_BENCH_RUN_ID': run_id,
                   'GA_BENCH_TASK_ID': 'synthetic-local-task',
                   'GA_TASK_COMPLETE_RESPONSE': '1',
                   'GA_TASK_DEADLINE_EPOCH': str(time.time() + 30),
                   'GA_POS_ENABLED': '0', 'GA_PMA_ENABLED': '0',
                   'GA_PMA_UPSTREAM_ENABLED': '0', 'GA_MONITOR_ENABLED': '0'}
    with mock.patch.dict(os.environ, env), ScriptedServer([
                    stream(tools=['touch']), stream(tools=['touch']),
                    stream(text='Synthetic task complete.', stop='end_turn')]) as server:
        backend = llmcore.NativeClaudeSession({
            'apikey': 'synthetic-only', 'apibase': server.url,
            'model': 'claude-synthetic', 'max_tokens': 100, 'max_retries': 0,
            'stream': True, 'timeout': 1, 'read_timeout': 5})
        client = llmcore.NativeToolClient(backend)
        client.backend.tools = [{'type': 'function', 'function': {
            'name': 'touch', 'description': 'writes isolated synthetic file',
            'parameters': {'type': 'object', 'properties': {}}}}]
        handler = SyntheticToolHandler(root)
        telemetry = []
        with research_context({'task_id': 'synthetic-local-task',
                               'run_id': run_id}, telemetry.append):
            result = agent_loop.exhaust(agent_loop.agent_runner_loop(
                client, 'Synthetic system', 'Create synthetic artifact',
                handler, client.backend.tools, max_turns=3, verbose=False))
    from method_discovery.pma_stateful_memory_v1_20261021.store import MemoryStore
    store = MemoryStore(root / 'state.sqlite3')
    try:
        events = store.events_after(0)
        sources = store.sources()
        facts = {'task_posts': len(server.payloads), 'tool_calls': handler.calls,
            'task_attempt_events': sum(e['event_type'] == 'provider_request_attempt'
                                       for e in telemetry),
            'reminder_counts': [json.dumps(json.loads(raw)).count(
                'Auxiliary memory information; not a new user requirement.')
                for raw in server.payloads],
            'tool_result_in_next_request': any('tool_result' in json.dumps(item)
                for item in json.loads(server.payloads[1])['messages']),
            'artifact': (root / 'synthetic-artifact.txt').read_text(),
            'action_batches': sum(row['kind'] == 'action_batch' for row in events),
            'result_sources': [row for row in sources.values()
                               if row['source_id'].endswith('/result')],
            'committed_event_seq': store.snapshot()['committed_event_seq'],
            'pending_kinds': [row['kind'] for row in events if row['event_seq'] >
                              store.snapshot()['committed_event_seq']],
            'delivery_attempts': store.db.execute("SELECT COUNT(*) FROM journal "
                "WHERE phase='delivery_attempt'").fetchone()[0],
            'role_attempts': store.db.execute("SELECT COUNT(*) FROM journal "
                "WHERE phase='call_attempt'").fetchone()[0],
            'bridge_closed': not hasattr(handler.parent, '_stateful_memory_bridge'),
            'task_terminal': result}
        return facts
    finally:
        store.close()


class StatefulGATest(unittest.TestCase):
    def test_single_run_fake_gate_rejects_unarmed_or_reused_output(self):
        from method_discovery.curator_supervisor_convergence_v0.\
            pma_full_upstream_ga_v1_20261013.single_run import (
                prepare_stateful_fake, run_stateful_fake)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'plan'
            args = SimpleNamespace(output=str(root), fake_only=False)
            with self.assertRaisesRegex(RuntimeError, 'fake-only'):
                prepare_stateful_fake(args)
            self.assertFalse(root.exists())
            args.fake_only = True
            plan = prepare_stateful_fake(args)
            self.assertFalse(plan['execution_authorized'])
            args.fake_only = False
            with self.assertRaisesRegex(RuntimeError, 'fake-only'):
                run_stateful_fake(args)
            self.assertFalse((root / 'fixture').exists())

    def test_fake_only_and_initialization_failure_before_task_send(self):
        with tempfile.TemporaryDirectory() as temp, ScriptedServer([]) as server:
            root = Path(temp)
            backend = llmcore.NativeClaudeSession({
                'apikey': 'synthetic-only', 'apibase': server.url,
                'model': 'claude-synthetic', 'max_tokens': 100,
                'max_retries': 0, 'stream': True})
            with mock.patch.dict(os.environ, {'GA_TASK_COMPLETE_RESPONSE': '1'}):
                client = llmcore.NativeToolClient(backend)
            client.backend.tools = []
            handler = SyntheticToolHandler(root)
            replies = root / 'roles.json'
            replies.write_text(json.dumps([{'role': 'audit', 'shape': 'clean'}]),
                               encoding='utf-8')
            base = {'GA_STATEFUL_MEMORY_ENABLED': '1',
                    'GA_TASK_COMPLETE_RESPONSE': '1',
                    'GA_STATEFUL_MEMORY_DB': str(root / 'state.sqlite3'),
                    'GA_STATEFUL_FAKE_REPLIES': str(replies),
                    'GA_BENCH_RUN_ID': 'synthetic-init-fail',
                    'GA_BENCH_TASK_ID': 'synthetic-local-task'}
            with mock.patch.dict(os.environ, {**base,
                                              'GA_STATEFUL_MEMORY_MODE': 'profile'}):
                with self.assertRaisesRegex(ValueError, 'fake-only'):
                    agent_loop.exhaust(agent_loop.agent_runner_loop(
                        client, 'system', 'task', handler, [], max_turns=1))
            self.assertFalse((root / 'state.sqlite3').exists())
            with mock.patch.dict(os.environ, {**base,
                                              'GA_STATEFUL_MEMORY_MODE': 'fake-only'}):
                with self.assertRaisesRegex(Exception, 'init_failed'):
                    agent_loop.exhaust(agent_loop.agent_runner_loop(
                        client, 'system', 'task', handler, [], max_turns=1))
            self.assertEqual(len(server.payloads), 0)
            self.assertFalse(hasattr(handler.parent, '_stateful_memory_bridge'))

    def test_actual_ga_tool_receipt_reminder_silent_and_close(self):
        with tempfile.TemporaryDirectory() as temp:
            facts = run_fixture(Path(temp) / 'run')
        self.assertEqual(facts['task_attempt_events'], 3)
        self.assertEqual(facts['task_posts'], 3)
        self.assertEqual(facts['tool_calls'], 2)
        self.assertEqual(facts['artifact'], 'actual GA tool result 2')
        self.assertEqual(facts['reminder_counts'], [0, 1, 1])
        self.assertTrue(facts['tool_result_in_next_request'])
        self.assertEqual(facts['action_batches'], 2)
        self.assertTrue(any('"written":1' in row['text']
                            for row in facts['result_sources']))
        self.assertEqual(facts['committed_event_seq'], 2)
        self.assertEqual(facts['pending_kinds'], ['agent_report'])
        self.assertEqual(facts['delivery_attempts'], 1)
        self.assertEqual(facts['role_attempts'], 9)
        self.assertTrue(facts['bridge_closed'])

    def test_complete_multi_tool_batch_idempotent_and_failure_pending(self):
        from stateful_memory_bridge import StatefulMemoryBridge
        from method_discovery.pma_stateful_memory_v1_20261021.store import MemoryStore
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            replies = root / 'roles.json'
            replies.write_text(json.dumps([
                {'role': 'maintenance', 'shape': 'empty'},
                {'role': 'audit', 'shape': 'clean'},
                {'role': 'selection', 'shape': 'silent'},
                {'role': 'maintenance', 'shape': 'observed_state'},
                {'role': 'audit', 'shape': 'clean'},
                {'role': 'selection', 'shape': 'remind'},
            ]), encoding='utf-8')
            env = {'GA_STATEFUL_MEMORY_ENABLED': '1',
                   'GA_STATEFUL_MEMORY_MODE': 'fake-only',
                   'GA_STATEFUL_MEMORY_DB': str(root / 'state.sqlite3'),
                   'GA_STATEFUL_FAKE_REPLIES': str(replies),
                   'GA_BENCH_RUN_ID': 'synthetic-multi',
                   'GA_BENCH_TASK_ID': 'synthetic-local-task'}
            with mock.patch.dict(os.environ, env):
                bridge = StatefulMemoryBridge.from_environment('Synthetic task')
                try:
                    actions = [{'id': 't1', 'name': 'touch', 'arguments': {}},
                               {'id': 't2', 'name': 'touch', 'arguments': {}}]
                    receipts = [{'tool_use_id': 't1', 'status': 'executed',
                                 'result': {'written': 1}},
                                {'tool_use_id': 't2', 'status': 'executed',
                                 'result': {'written': 2}}]
                    with self.assertRaisesRegex(Exception, 'incomplete GA action batch'):
                        bridge.complete_batch(1, actions, receipts[:1])
                    self.assertEqual(len(bridge.provider.calls), 3)
                    first = bridge.complete_batch(1, actions, receipts)
                    again = bridge.complete_batch(1, actions, receipts)
                    self.assertEqual(first, again)
                    self.assertEqual(len(bridge.provider.calls), 6)
                    batches = [row for row in bridge.store.events_after(0)
                               if row['kind'] == 'action_batch']
                    self.assertEqual(len(batches), 1)
                    leaves = list(bridge.store.sources().values())
                    self.assertEqual(len([row for row in leaves if row['source_kind'] ==
                                          'tool_result']), 2)
                    self.assertEqual(len({row['event_id'] for row in leaves if
                        row['source_kind'] == 'tool_result'}), 2)
                    self.assertIsNotNone(bridge.pending)
                    class UnknownTaskClient:
                        def __init__(self): self.calls = 0
                        def chat(self, **kwargs):
                            self.calls += 1
                            raise RuntimeError('synthetic unknown response')
                            yield  # pragma: no cover
                    task = UnknownTaskClient()
                    for _ in range(2):
                        with self.assertRaises(Exception):
                            agent_loop.exhaust(bridge.chat(task, [
                                {'role': 'user', 'content': 'synthetic'}], [], 2))
                    self.assertEqual(task.calls, 1)
                finally:
                    bridge.finish({'result': 'synthetic_done'})
            store = MemoryStore(root / 'state.sqlite3')
            try:
                self.assertEqual(store.snapshot()['committed_event_seq'], 1)
            finally:
                store.close()

    def test_update_role_exhaustion_keeps_pending_without_reminder(self):
        from stateful_memory_bridge import StatefulMemoryBridge
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            replies = root / 'roles.json'
            replies.write_text(json.dumps([
                {'role': 'maintenance', 'shape': 'empty'},
                {'role': 'audit', 'shape': 'clean'},
                {'role': 'selection', 'shape': 'silent'}]), encoding='utf-8')
            env = {'GA_STATEFUL_MEMORY_ENABLED': '1',
                   'GA_STATEFUL_MEMORY_MODE': 'fake-only',
                   'GA_STATEFUL_MEMORY_DB': str(root / 'state.sqlite3'),
                   'GA_STATEFUL_FAKE_REPLIES': str(replies),
                   'GA_BENCH_RUN_ID': 'synthetic-exhausted',
                   'GA_BENCH_TASK_ID': 'synthetic-local-task'}
            with mock.patch.dict(os.environ, env):
                bridge = StatefulMemoryBridge.from_environment('Synthetic task')
                try:
                    with self.assertRaisesRegex(Exception, 'fake_script_exhausted'):
                        bridge.complete_batch(1,
                            [{'id': 't1', 'name': 'touch', 'arguments': {}}],
                            [{'tool_use_id': 't1', 'status': 'executed',
                              'result': {'written': 1}}])
                    self.assertIsNone(bridge.pending)
                    self.assertEqual(bridge.store.snapshot()['committed_event_seq'], 0)
                    self.assertEqual(len(bridge.store.events_after(0)), 1)
                finally:
                    bridge.finish({'result': 'role_failure'})


if __name__ == '__main__':
    unittest.main()
