"""Real GA loop/tool/request assembly with finite local HTTP and role scripts."""
import json
import os
import tempfile
import time
import unittest
from contextlib import nullcontext
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
                   'GA_PROVIDER_MAX_RETRIES': '0',
                   'GA_TASK_DEADLINE_EPOCH': str(time.time() + 30),
                   'GA_POS_ENABLED': '0', 'GA_PMA_ENABLED': '0',
                   'GA_PMA_UPSTREAM_ENABLED': '0', 'GA_MONITOR_ENABLED': '0'}
    with mock.patch.dict(os.environ, env), ScriptedServer([
                    stream(text='GA_PLAN_MARKER_ALPHA', tools=['touch']),
                    stream(tools=['touch']),
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
            'retrieval_queries': [json.loads(body) for (body,) in
                store.db.execute("SELECT body FROM journal WHERE phase='retrieval_query' "
                                 "ORDER BY rowid")],
            'effective_task_retries': backend.max_retries,
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
    def test_actual_ga_receipts_reach_both_retrieval_queries(self):
        with tempfile.TemporaryDirectory() as temp:
            facts = run_fixture(Path(temp) / 'run')
        self.assertGreaterEqual(len(facts['retrieval_queries']), 4)
        for stage in ('maintenance', 'selection'):
            queries = [row['query'] for row in facts['retrieval_queries']
                       if row['stage'] == stage]
            self.assertTrue(any('GA_PLAN_MARKER_ALPHA' in query for query in queries))
            self.assertTrue(any('synthetic-artifact.txt' in query for query in queries))
            self.assertTrue(any('"name":"touch"' in query for query in queries))

    def test_external_retry_override_is_scoped_to_zero(self):
        with tempfile.TemporaryDirectory() as temp, mock.patch.dict(
                os.environ, {'GA_PROVIDER_MAX_RETRIES': '2'}):
            facts = run_fixture(Path(temp) / 'run')
            self.assertEqual(facts['effective_task_retries'], 0)
            self.assertEqual(facts['task_posts'], 3)
            self.assertEqual(os.environ['GA_PROVIDER_MAX_RETRIES'], '2')

    def test_effective_nonzero_task_retries_rejected_before_any_role_or_post(self):
        with tempfile.TemporaryDirectory() as temp, ScriptedServer([]) as server:
            root = Path(temp)
            replies = root / 'roles.json'
            replies.write_text(json.dumps([
                {'role': 'maintenance', 'shape': 'empty'}]), encoding='utf-8')
            env = {'GA_STATEFUL_MEMORY_ENABLED': '1',
                   'GA_STATEFUL_MEMORY_MODE': 'fake-only',
                   'GA_STATEFUL_MEMORY_DB': str(root / 'state.sqlite3'),
                   'GA_STATEFUL_FAKE_REPLIES': str(replies),
                   'GA_BENCH_RUN_ID': 'synthetic-nonzero-retries',
                   'GA_BENCH_TASK_ID': 'synthetic-local-task',
                   'GA_TASK_COMPLETE_RESPONSE': '1',
                   'GA_PROVIDER_MAX_RETRIES': '2'}
            with mock.patch.dict(os.environ, env):
                backend = llmcore.NativeClaudeSession({
                    'apikey': 'synthetic-only', 'apibase': server.url,
                    'model': 'claude-synthetic', 'max_tokens': 100,
                    'max_retries': 0, 'stream': True})
                self.assertEqual(backend.max_retries, 2)
                client = llmcore.NativeToolClient(backend)
                handler = SyntheticToolHandler(root)
                with self.assertRaisesRegex(ValueError,
                                            'effective max_retries=0'):
                    agent_loop.exhaust(agent_loop.agent_runner_loop(
                        client, 'system', 'task', handler, [], max_turns=1))
            self.assertFalse((root / 'state.sqlite3').exists())
            self.assertEqual(len(server.payloads), 0)

    def _incomplete_ga_case(self, root, *, second_raises, cancel_second=False,
                            explicit_exit=False, diagnostic_fails=False):
        from method_discovery.pma_stateful_memory_v1_20261021.store import MemoryStore
        from stateful_memory_bridge import StatefulMemoryBridge
        replies = root / 'roles.json'
        replies.write_text(json.dumps([
            {'role': 'maintenance', 'shape': 'empty'},
            {'role': 'audit', 'shape': 'clean'},
            {'role': 'selection', 'shape': 'silent'}]), encoding='utf-8')
        run_id = 'synthetic-incomplete-' + ('error' if second_raises else
                                          'cancel' if cancel_second else
                                          'should-exit' if explicit_exit else 'exit')
        env = {'GA_STATEFUL_MEMORY_ENABLED': '1',
               'GA_STATEFUL_MEMORY_MODE': 'fake-only',
               'GA_STATEFUL_MEMORY_DB': str(root / 'state.sqlite3'),
               'GA_STATEFUL_FAKE_REPLIES': str(replies),
               'GA_BENCH_RUN_ID': run_id,
               'GA_BENCH_TASK_ID': 'synthetic-local-task',
               'GA_TASK_COMPLETE_RESPONSE': '1',
               'GA_PROVIDER_MAX_RETRIES': '0',
               'GA_TASK_DEADLINE_EPOCH': str(time.time() + 30)}
        class TwoTools(SyntheticToolHandler):
            def do_first(self, args, response):
                self.calls += 1
                (self.root / 'first.txt').write_text('first result', encoding='utf-8')
                return agent_loop.StepOutcome({'first': 'real receipt'},
                    next_prompt='Continue.' if second_raises or cancel_second or
                                explicit_exit else None, should_exit=explicit_exit)
            def do_second(self, args, response):
                self.calls += 1
                raise ValueError('synthetic second tool exception')
        with mock.patch.dict(os.environ, env), ScriptedServer([
                stream(tools=['first', 'second'])]) as server:
            backend = llmcore.NativeClaudeSession({
                'apikey': 'synthetic-only', 'apibase': server.url,
                'model': 'claude-synthetic', 'max_tokens': 100,
                'max_retries': 0, 'stream': True, 'timeout': 1,
                'read_timeout': 5})
            client = llmcore.NativeToolClient(backend)
            client.backend.tools = [{'type': 'function', 'function': {
                'name': name, 'description': 'synthetic',
                'parameters': {'type': 'object', 'properties': {}}}}
                for name in ('first', 'second')]
            handler = TwoTools(root)
            if cancel_second:
                class Barrier:
                    calls = 0
                    def is_active(self):
                        self.calls += 1
                        return self.calls >= 2
                handler.parent.monitor_correction_barrier = Barrier()
            diagnostic_patch = (mock.patch.object(StatefulMemoryBridge,
                'record_incomplete', side_effect=OSError('synthetic journal failure'))
                if diagnostic_fails else nullcontext())
            with diagnostic_patch, research_context({
                    'task_id': 'synthetic-local-task',
                    'run_id': run_id}, lambda event: None):
                if second_raises:
                    with self.assertRaisesRegex(ValueError,
                                                'synthetic second tool exception'):
                        agent_loop.exhaust(agent_loop.agent_runner_loop(
                            client, 'system', 'task', handler, client.backend.tools,
                            max_turns=1, verbose=False))
                    terminal = None
                else:
                    terminal = agent_loop.exhaust(agent_loop.agent_runner_loop(
                        client, 'system', 'task', handler, client.backend.tools,
                        max_turns=1, verbose=False))
        store = MemoryStore(root / 'state.sqlite3')
        try:
            diagnostics = [row['body'] for row in store.journal_rows('host-' + run_id)
                           if row['phase'] == 'incomplete_batch']
            return {'diagnostics': diagnostics, 'terminal': terminal,
                'tool_calls': handler.calls, 'task_posts': len(server.payloads),
                'frontier': store.snapshot()['committed_event_seq'],
                'action_batches': sum(row['kind'] == 'action_batch'
                    for row in store.events_after(0)),
                'role_attempts': store.db.execute("SELECT COUNT(*) FROM journal "
                    "WHERE phase='call_attempt'").fetchone()[0]}
        finally:
            store.close()

    def test_second_tool_exception_preserves_first_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            facts = self._incomplete_ga_case(Path(temp), second_raises=True)
        self.assertEqual((facts['task_posts'], facts['tool_calls'],
                          facts['role_attempts']), (1, 2, 3))
        self.assertEqual((facts['frontier'], facts['action_batches']), (0, 0))
        self.assertEqual(len(facts['diagnostics']), 1)
        diagnostic = facts['diagnostics'][0]
        self.assertEqual(len(diagnostic['actions']), 2)
        self.assertEqual(diagnostic['receipts'][0]['result'],
                         {'first': 'real receipt'})
        self.assertEqual(diagnostic['started_result_unknown_ids'], ['t1'])
        self.assertEqual(diagnostic['not_executed_ids'], [])
        self.assertEqual(diagnostic['error_type'], 'ValueError')
        self.assertEqual(diagnostic['error_message'],
                         'synthetic second tool exception')

    def test_tool_exception_survives_cleanup_error(self):
        from stateful_memory_bridge import StatefulMemoryBridge
        original = StatefulMemoryBridge.finish
        def failing_finish(bridge, terminal):
            original(bridge, terminal)
            raise OSError('synthetic cleanup failure')
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(
                StatefulMemoryBridge, 'finish', failing_finish):
            facts = self._incomplete_ga_case(Path(temp), second_raises=True)
        self.assertEqual(facts['diagnostics'][0]['error_type'], 'ValueError')

    def test_tool_exception_survives_diagnostic_error(self):
        with tempfile.TemporaryDirectory() as temp:
            facts = self._incomplete_ga_case(Path(temp), second_raises=True,
                                             diagnostic_fails=True)
        self.assertEqual(facts['diagnostics'], [])
        self.assertEqual((facts['frontier'], facts['role_attempts']), (0, 3))

    def test_first_tool_normal_exit_preserves_reason_and_remaining_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            facts = self._incomplete_ga_case(Path(temp), second_raises=False)
        self.assertEqual((facts['task_posts'], facts['tool_calls'],
                          facts['role_attempts']), (1, 1, 3))
        self.assertEqual((facts['frontier'], facts['action_batches']), (0, 0))
        self.assertEqual(len(facts['diagnostics']), 1)
        diagnostic = facts['diagnostics'][0]
        self.assertEqual(diagnostic['receipts'][0]['result'],
                         {'first': 'real receipt'})
        self.assertEqual(diagnostic['started_result_unknown_ids'], [])
        self.assertEqual(diagnostic['not_executed_ids'], ['t1'])
        self.assertEqual(diagnostic['terminal']['result'], 'CURRENT_TASK_DONE')

    def test_second_tool_cancel_keeps_first_receipt_without_cycle(self):
        with tempfile.TemporaryDirectory() as temp:
            facts = self._incomplete_ga_case(Path(temp), second_raises=False,
                                             cancel_second=True)
        self.assertEqual((facts['tool_calls'], facts['role_attempts']), (1, 3))
        self.assertEqual((facts['frontier'], facts['action_batches']), (0, 0))
        diagnostic = facts['diagnostics'][0]
        self.assertEqual(diagnostic['receipts'][0]['result'],
                         {'first': 'real receipt'})
        self.assertEqual(diagnostic['not_executed_ids'], ['t1'])
        self.assertEqual(diagnostic['reason'], 'cancelled_before_execution')

    def test_first_tool_should_exit_keeps_exit_reason(self):
        with tempfile.TemporaryDirectory() as temp:
            facts = self._incomplete_ga_case(Path(temp), second_raises=False,
                                             explicit_exit=True)
        self.assertEqual((facts['tool_calls'], facts['role_attempts']), (1, 3))
        self.assertEqual((facts['frontier'], facts['action_batches']), (0, 0))
        diagnostic = facts['diagnostics'][0]
        self.assertEqual(diagnostic['not_executed_ids'], ['t1'])
        self.assertEqual(diagnostic['terminal']['result'], 'EXITED')

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
        self.assertEqual(facts['committed_event_seq'], 3)
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
