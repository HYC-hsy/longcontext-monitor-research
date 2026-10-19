"""Finite model fixtures exercise the real pinned PoS and PMA classes together."""
import asyncio
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
POS = ROOT / 'pos_upstream_ga_v1_20261017'
PMA = ROOT / 'curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/vendor/pma_89e5c0d/src'
sys.path[:0] = [str(POS), str(POS / 'vendor'), str(PMA)]
shim = ModuleType('shortuuid')
counter = iter(range(1000))
shim.uuid = lambda: f'{next(counter):08d}'
sys.modules.setdefault('shortuuid', shim)
from episode import PoSEpisode, execution_config
from memory_agent.memory.trigger import MemoryAgentTrigger, TriggerConfig
from memory_agent.memory.universal_memory import UniversalMemory
from .candidate import ComplementBeliefManager, ComplementEpisode, render_task_panel
from .memory_adapter import ComplementMemoryAgent


INITIAL = {'goal_specification': 'Keep mug clean.',
           'entities': [{'entity_id': 'e1', 'entity_type': 'mug', 'name': 'mug'}],
           'states': [], 'relations': [], 'epistemic_gaps': [],
           'achievement_gaps': [{'target': 'clean', 'reason': 'not yet verified'}],
           'frontier': {'gap_type': 'achievement', 'target': 'clean'}}
UPDATE = {'remove_state_ids': [], 'remove_relation_ids': [],
          'upsert_entities': [], 'upsert_states': [], 'upsert_relations': [],
          'epistemic_gaps': [], 'achievement_gaps': INITIAL['achievement_gaps'],
          'frontier': INITIAL['frontier']}


class Logger:
    def __init__(self): self.rows = []
    def log(self, event, **data): self.rows.append((event, data))


class SyncRole:
    def __init__(self, replies): self.replies, self.requests = list(replies), []
    def __call__(self, messages):
        self.requests.append(messages)
        return self.replies.pop(0)


class AsyncRole:
    def __init__(self, replies): self.replies, self.requests = list(replies), []
    async def call(self, **kwargs):
        self.requests.append(kwargs)
        return self.replies.pop(0)


def response(content='', calls=()):
    return SimpleNamespace(content=content, tool_calls=list(calls))


class CandidateTests(unittest.TestCase):
    def make(self):
        logger = Logger()
        belief = SyncRole([json.dumps(INITIAL), json.dumps(UPDATE)])
        consistency = SyncRole(['{"issues": []}', '{"issues": []}'])
        progress = SyncRole(['{"progress": 0, "score": 0.0, '
                             '"affected_record_ids": [], "reason": "no change"}'])
        manager_holder = {}
        def consistency_with_revision(messages):
            manager = manager_holder.get('manager')
            if manager and manager.revision_context:
                messages = [*messages, {'role': 'system',
                    'content': 'Fallible previously delivered suggestion:\n' +
                               manager.revision_context}]
            return consistency(messages)
        pos = PoSEpisode(case_id='case', config=execution_config(), logger=logger,
            belief_call=belief, consistency_call=consistency_with_revision,
            progress_call=progress, manager_class=ComplementBeliefManager)
        manager_holder['manager'] = pos.manager
        pma = AsyncRole([response(), response('<context_for_action>Inspect again</context_for_action>'),
                         response(), response('<no_intervention/>')])
        memory = ComplementMemoryAgent(llm=pma, memory=UniversalMemory())
        trigger = MemoryAgentTrigger(TriggerConfig(interval=1, trigger_on_first_step=True))
        return ComplementEpisode(pos_episode=pos, memory_agent=memory,
            trigger=trigger, logger=logger), belief, consistency, pma

    def test_initial_and_next_transition_order_and_revision(self):
        episode, belief, consistency, pma = self.make()
        initial = asyncio.run(episode.reset(task='Clean mug.', observation='Mug dirty.',
                                           actions=[]))
        self.assertEqual(len(belief.requests), 1)
        self.assertEqual(len(pma.requests), 2)
        self.assertNotIn('"goal"', pma.requests[0]['prompt'])
        self.assertIn('"goal"', pma.requests[1]['prompt'])
        self.assertIn('Inspect again', initial['panel'])
        self.assertEqual(episode.delivered, None)
        episode.request_accepted(panel=initial, event_id='task-response-1')
        asyncio.run(episode.update(actor_attempt=1, transition_id='joint-1',
            thought='inspect', action_batch=[{'id': 'tool-1', 'name': 'inspect',
              'arguments': {}, 'order': 0, 'status': 'executed'}],
            observation='Still dirty.', source_events=['host-tool-1']))
        self.assertIn('task-response-1', belief.requests[1][1]['content'])
        self.assertIn('host-tool-1', consistency.requests[1][-1]['content'])
        self.assertEqual(len(pma.requests), 4)
        self.assertNotIn('Inspect again', episode.decision_panel(
            observation='Still dirty.')['panel'])
        self.assertEqual(episode.delivered, None)

    def test_prepared_not_delivered_and_required_gap_budget(self):
        episode, belief, _consistency, _pma = self.make()
        asyncio.run(episode.reset(task='Clean mug.', observation='Mug dirty.', actions=[]))
        asyncio.run(episode.update(actor_attempt=1, transition_id='joint-1',
            thought='inspect', action_batch=[{'id': 't', 'name': 'inspect',
              'arguments': {}, 'order': 0, 'status': 'executed'}],
            observation='Still dirty.'))
        self.assertNotIn('Inspect again', belief.requests[1][1]['content'])
        view = episode.pos.get_context()
        view['achievement_gaps'][0]['reason'] = 'x' * 20000
        with self.assertRaisesRegex(ValueError, 'budget'):
            render_task_panel(view)

    def test_oversized_actual_observation_cannot_create_false_delivery(self):
        episode, _belief, _consistency, _pma = self.make()
        asyncio.run(episode.reset(task='Clean mug.', observation='Mug dirty.', actions=[]))
        panel = render_task_panel(episode.pos.get_context(), advice='Inspect again',
                                  original_observation='x' * 16000)
        self.assertIn('latest_observation_panel_copy', panel['omitted'])
        self.assertEqual(panel['included_advice'], 'Inspect again')
        self.assertIn('Inspect again', panel['panel'])
        too_long = render_task_panel(episode.pos.get_context(), advice='negative caveat ' * 1500)
        self.assertIsNone(too_long['included_advice'])
        self.assertTrue(too_long['budget_suppressed'])
        episode.request_accepted(panel=too_long, event_id='task-accepted')
        self.assertIsNone(episode.delivered)


if __name__ == '__main__':
    unittest.main(verbosity=2)
