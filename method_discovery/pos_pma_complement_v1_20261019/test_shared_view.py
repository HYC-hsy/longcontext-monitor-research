"""Offline shared-view order, freeze, audit and panel checks with pinned cores."""
import asyncio
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(Path(__file__).resolve().parent),
                str(ROOT / 'pos_upstream_ga_v1_20261017'),
                str(ROOT / 'pos_upstream_ga_v1_20261017/vendor'),
                str(ROOT / ('curator_supervisor_convergence_v0/'
                    'pma_full_upstream_ga_v1_20261013/vendor/pma_89e5c0d/src'))]
from .test_candidate_core import INITIAL, UPDATE, Logger, SyncRole, AsyncRole, response
from episode import PoSEpisode, execution_config
from memory_agent.memory.trigger import MemoryAgentTrigger, TriggerConfig
from memory_agent.memory.universal_memory import UniversalMemory
from .memory_adapter import SharedViewMemoryAgent
from .shared_view import SharedViewBeliefManager, SharedViewEpisode, shared_panel


def tool(name, arguments):
    return SimpleNamespace(function=SimpleNamespace(name=name, arguments=arguments))


class Tests(unittest.TestCase):
    def make(self, *, interval=1, initial_advice='<no_intervention/>'):
        log = Logger()
        belief = SyncRole([json.dumps(INITIAL), json.dumps(UPDATE)])
        consistency = SyncRole(['{"issues": []}', '{"issues": []}'])
        progress = SyncRole(['{"progress": 0, "score": 0.0, '
                             '"affected_record_ids": [], "reason": "no change"}'])
        pma = AsyncRole([response('', [tool('memory_save_knowledge',
            {'content': 'Remember actual tool output'})]), response(initial_advice),
            response(), response('<no_intervention/>')])
        pos = PoSEpisode(case_id='shared-test', config=execution_config(),
            logger=log, belief_call=belief, consistency_call=consistency,
            progress_call=progress, manager_class=SharedViewBeliefManager)
        bank = SharedViewMemoryAgent(llm=pma, memory=UniversalMemory())
        trigger = MemoryAgentTrigger(TriggerConfig(interval=interval,
                                                   trigger_on_first_step=True))
        episode = SharedViewEpisode(pos_episode=pos, memory_agent=bank,
            trigger=trigger, logger=log)
        return episode, belief, consistency, pma

    def test_phase_order_and_frozen_bank_panel(self):
        ep, belief, consistency, pma = self.make(initial_advice=
            '<context_for_action>Check the tool result.</context_for_action>')
        first = asyncio.run(ep.reset(task='Clean mug.',
                                     observation='Clean mug.', actions=[]))
        self.assertEqual(ep.phase1_status, 'completed')
        self.assertEqual(ep.phase2_status, 'reminder')
        self.assertEqual(len(pma.requests), 2)
        self.assertIn('Check the tool result.', first['panel'])
        self.assertIn('recovery', first['panel'])
        self.assertNotIn('memory_update_status', [item['function']['name']
            for item in pma.requests[0]['tools']])
        self.assertEqual(ep.memory.memory.status, '')
        task_only = ep.manager.sentinel._compact_trajectory([{
            'step': -1, 'action': None, 'observation': 'Clean mug.'}])
        self.assertEqual(task_only[0]['citable_sources'], [])
        self.assertEqual(task_only[0]['source_origin'],
                         'original_task_not_tool_result')
        self.assertEqual([row['phase'] for row in ep.memory.rendered_entry_ids],
                         ['phase1', 'shared_selection', 'phase2'])
        self.assertEqual(ep.memory.rendered_entry_ids[1]['knowledge'],
                         ep.memory.rendered_entry_ids[2]['knowledge'])
        ep.request_accepted(panel=first, event_id='accepted-task-1')
        source = {'origin': 'GA_tool_outcome', 'tool_use_id': 'tool-1',
                  'result': {'stdout': 'Mug is still dirty.'},
                  'next_prompt': 'NOT A TOOL CITATION'}
        asyncio.run(ep.update(actor_attempt=1, transition_id='joint-1',
            thought='Inspect', action_batch=[{'id': 'tool-1', 'name': 'inspect',
                'arguments': {}, 'order': 0, 'status': 'executed'}],
            observation=json.dumps({'tool_results': [source]}),
            source_events=[source]))
        self.assertEqual(len(belief.requests), 2)
        self.assertIn('shared_selection', json.dumps(belief.requests[1]))
        self.assertIn('tool-1', json.dumps(belief.requests[1]))
        self.assertEqual(ep.advice_history[0]['reviewed_transition'], 'joint-1')
        self.assertIn('accepted-task-1', pma.requests[-1]['prompt'])
        self.assertNotIn('Check the tool result.', ep.decision_panel(
            observation='Mug is still dirty.')['panel'])
        compact = ep.manager.sentinel._compact_trajectory([{
            'step': 0, 'action': None,
            'observation': 'Clean mug.'}])
        self.assertFalse(any('NOT A TOOL CITATION' in json.dumps(row)
                             for row in compact))

    def test_partial_bank_before_pos_initialization(self):
        ep, *_ = self.make()
        async def failing_call(**_kwargs):
            raise RuntimeError('synthetic Phase 1 failure')
        ep.memory.llm.call = failing_call
        with self.assertRaisesRegex(RuntimeError, 'synthetic Phase 1 failure'):
            asyncio.run(ep.reset(task='Clean mug.', observation='Clean mug.',
                                 actions=[]))
        partial = ep.get_result()
        self.assertEqual(partial['phase1_status'], 'failed')
        self.assertEqual(partial['initialization_stage'], 'not_attempted')
        self.assertEqual(partial['pos']['status'], 'unavailable')
        self.assertEqual(partial['bank']['knowledge'], [])

    def test_interval_skip_selects_unchanged_bank_once(self):
        ep, belief, _, pma = self.make(interval=3)
        asyncio.run(ep.reset(task='Clean mug.', observation='Clean mug.',
                             actions=[]))
        asyncio.run(ep.update(actor_attempt=1, transition_id='joint-skip',
            thought='Inspect', action_batch=[{'id': 'tool-1', 'name': 'inspect',
                'arguments': {}, 'order': 0, 'status': 'executed'}],
            observation='Mug remains dirty.', source_events=[]))
        self.assertEqual(ep.phase1_status, 'not_triggered')
        self.assertEqual(ep.phase2_status, 'not_triggered')
        self.assertEqual(len(pma.requests), 2)
        self.assertEqual(len(belief.requests), 2)
        self.assertEqual(ep.frozen_selection['bank_version'], 1)
        self.assertEqual([row['phase'] for row in ep.memory.rendered_entry_ids],
                         ['phase1', 'shared_selection', 'phase2',
                          'shared_selection'])

    def test_audit_uses_only_visible_tool_fields_and_one_step_budget(self):
        ep, *_ = self.make()
        sentinel = ep.manager.sentinel
        sentinel.shared_sources = ({'event_id': 'old-tool', 'origin': 'tool_result',
            'sha256': 'a' * 64, 'pos_step': 3,
            'raw': {'result': {'stdout': 'A' * 7000 + 'VISIBLE_TAIL'},
                    'next_prompt': 'FAKE_HOST_NOTE'}},
            {'event_id': 'initial-task', 'origin': 'original_task',
             'sha256': 'b' * 64, 'pos_step': None,
             'raw': {'result': {'stdout': 'TASK_NOT_TOOL'}}})
        compact = sentinel._compact_trajectory([])
        self.assertEqual(len(compact), 1)
        fields = compact[0]['citable_sources']
        self.assertLessEqual(sum(len(field['text']) for field in fields),
                             sentinel.audit_observation_max_chars)
        self.assertFalse(any('FAKE_HOST_NOTE' in field['text'] or
                             'TASK_NOT_TOOL' in field['text'] for field in fields))
        self.assertEqual(compact[0]['step'], 3)
        self.assertTrue(all(field['source_path'].startswith('old-tool:result.')
                            for field in fields))
        self.assertNotIn('A' * 7000, ''.join(field['text'] for field in fields))
        # A current observation already projected at step 3 cannot gain a
        # second audit allowance through its registry copy.
        current = sentinel._compact_trajectory([{'step': 3, 'action': None,
            'observation': 'Original actual observation'}])
        self.assertEqual(len(current), 1)
        self.assertNotIn('VISIBLE_TAIL', json.dumps(current))

    def test_recovery_survives_silence_and_no_cap(self):
        context = {'goal': {'user_input': 'Original Task'},
            'epistemic_gaps': [], 'achievement_gaps': [],
            'frontier_gap': {'target': 'keep-going'},
            'world': {'entities': {}, 'states': {}, 'relations': {}},
            'recovery': {'instruction': 'R' * 18000},
            'accepted_revision': 2, 'latest_update_outcome': 'accepted'}
        panel = shared_panel(context)
        self.assertIn('R' * 18000, panel['panel'])
        self.assertIsNone(panel['included_advice'])
        self.assertGreater(len(panel['panel']), 16000)


if __name__ == '__main__':
    unittest.main()
