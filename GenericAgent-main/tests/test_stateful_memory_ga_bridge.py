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


class StatefulGATest(unittest.TestCase):
    def _client(self, url):
        backend = llmcore.NativeClaudeSession({
            'apikey': 'synthetic-only', 'apibase': url, 'model': 'claude-synthetic',
            'max_tokens': 100, 'max_retries': 0, 'stream': True,
            'timeout': 1, 'read_timeout': 5})
        client = llmcore.NativeToolClient(backend)
        client.backend.tools = [{'type': 'function', 'function': {
            'name': 'touch', 'description': 'writes isolated synthetic file',
            'parameters': {'type': 'object', 'properties': {}}}}]
        return client

    def test_actual_ga_tool_receipt_reminder_silent_and_close(self):
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
                {'role': 'maintenance', 'shape': 'empty'},
                {'role': 'audit', 'shape': 'clean'},
                {'role': 'selection', 'shape': 'silent'},
            ]), encoding='utf-8')
            env = {'GA_STATEFUL_MEMORY_ENABLED': '1',
                   'GA_STATEFUL_MEMORY_MODE': 'fake-only',
                   'GA_STATEFUL_MEMORY_DB': str(root / 'state.sqlite3'),
                   'GA_STATEFUL_FAKE_REPLIES': str(replies),
                   'GA_BENCH_RUN_ID': 'synthetic-stateful-1',
                   'GA_BENCH_TASK_ID': 'synthetic-local-task',
                   'GA_TASK_COMPLETE_RESPONSE': '1',
                   'GA_TASK_DEADLINE_EPOCH': str(time.time() + 30)}
            with mock.patch.dict(os.environ, env), ScriptedServer([
                    stream(tools=['touch']), stream(tools=['touch']),
                    stream(text='Synthetic task complete.', stop='end_turn')]) as server:
                client = self._client(server.url)
                handler = SyntheticToolHandler(root)
                events = []
                with research_context({'task_id': 'synthetic-local-task',
                                       'run_id': 'synthetic-stateful-1'}, events.append):
                    result = agent_loop.exhaust(agent_loop.agent_runner_loop(
                        client, 'Synthetic system', 'Create synthetic artifact',
                        handler, client.backend.tools, max_turns=3, verbose=False))
            self.assertEqual(len([event for event in events if event['event_type'] ==
                                  'provider_request_attempt']), 3)
            self.assertEqual(handler.calls, 2)
            self.assertEqual(len(server.payloads), 3)
            self.assertEqual((root / 'synthetic-artifact.txt').read_text(),
                             'actual GA tool result 2')
            requests = [json.loads(raw) for raw in server.payloads]
            reminder_marker = 'Auxiliary memory information; not a new user requirement.'
            self.assertNotIn(reminder_marker, json.dumps(requests[0]))
            self.assertEqual(json.dumps(requests[1]).count(reminder_marker), 1)
            self.assertEqual(json.dumps(requests[2]).count(reminder_marker), 1)
            self.assertTrue(any('tool_result' in json.dumps(item)
                for item in requests[1]['messages']))
            self.assertFalse(hasattr(handler.parent, '_stateful_memory_bridge'))
            from method_discovery.pma_stateful_memory_v1_20261021.store import MemoryStore
            store = MemoryStore(root / 'state.sqlite3')
            try:
                events = store.events_after(0)
                batches = [row for row in events if row['kind'] == 'action_batch']
                self.assertEqual(len(batches), 2)
                leaves = [leaf for leaf in store.sources().values() if
                          leaf['source_id'].endswith('/result')]
                self.assertTrue(any('"written":1' in row['text']
                                    for row in leaves))
                self.assertEqual(store.snapshot()['committed_event_seq'], 2)
                self.assertEqual([row['kind'] for row in events
                    if row['event_seq'] > 2], ['agent_report'])
                self.assertEqual(store.db.execute("SELECT COUNT(*) FROM journal "
                    "WHERE phase='delivery_attempt'").fetchone()[0], 1)
            finally:
                store.close()


if __name__ == '__main__':
    unittest.main()
