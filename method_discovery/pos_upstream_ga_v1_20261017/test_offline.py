"""Fixed-response, no-provider checks of the released-core transfer."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
VENDOR = HERE / 'vendor'
sys.path.insert(0, str(VENDOR))
sys.path.insert(0, str(HERE / 'upstream'))
from belief.manager import BeliefManager
from prompts.react_prompt import build_belief_prompt
from episode import PoSEpisode, execution_config
from baselines.react import ReAct

INITIAL = {
    'goal_specification': 'Mug 1 must be clean.',
    'entities': [{'entity_id': 'e1', 'entity_type': 'mug', 'name': 'mug 1'}],
    'states': [{'state_id': 's1', 'entity_id': 'e1', 'description': 'Mug 1 is dirty.',
                'source_type': 'observed', 'probability': 1.0}],
    'relations': [], 'epistemic_gaps': [],
    'achievement_gaps': [{'target': 'Mug 1 must be clean', 'reason': 'Mug 1 is dirty.'}],
    'frontier': {'gap_type': 'achievement', 'target': 'Mug 1 must be clean'},
}
DELTA = {'remove_state_ids': [], 'remove_relation_ids': [],
         'upsert_entities': [], 'upsert_states': [], 'upsert_relations': [],
         'epistemic_gaps': [], 'achievement_gaps': INITIAL['achievement_gaps'],
         'frontier': INITIAL['frontier']}
PROGRESS = {'progress': 0, 'score': 0.0, 'affected_record_ids': [],
            'reason': 'No new evidence.'}


class Recorder:
    def __init__(self): self.events = []
    def log(self, event, **data): self.events.append({'event': event, **data})


def replies(count=1):
    return {'belief': [json.dumps(INITIAL), json.dumps({'belief_text': 'Mug dirty.'})] +
            [part for _ in range(count) for part in
             (json.dumps(DELTA), json.dumps({'belief_text': 'Mug dirty.'}))],
            'consistency': ['{"issues": []}'] * (count + 1),
            'progress': [json.dumps(PROGRESS)] * count}


def callers(fixed, captured):
    def role(name):
        def call(messages):
            captured.append({'role': name, 'messages': copy.deepcopy(messages)})
            return fixed[name].pop(0)
        return call
    return role


def state(observation='Mug dirty.', done=False):
    return {'case_id': 'fixed/case', 'task': 'Clean mug 1.',
            'observation': observation, 'actions': [], 'done': done,
            'success': False, 'score': 0.0}


class TransferTests(unittest.TestCase):
    def test_original_react_runner_to_ga_episode_scalar_trace(self):
        config = {**execution_config(), 'max_steps': 1}
        one, two = replies(), replies()
        role_events, adapter_events = [], []
        reference = callers(one, role_events)
        transferred = callers(two, adapter_events)
        manager = BeliefManager(config, reference('belief'), Recorder(),
            call_sentinel=reference('consistency'),
            call_progress=reference('progress'))
        action = {'name': 'inspect', 'arguments': {}}
        class Environment:
            def reset(self): return state()
            def step(self, actual):
                assert actual == action
                return state('Still dirty.') | {'done': True}
        actor_inputs = []
        def actor(messages):
            actor_inputs.append(messages)
            return json.dumps({'thought': 'Inspect.', 'action': action})
        runner = ReAct(config, actor, Recorder(), context_provider=manager)
        original = runner.run(Environment())
        episode = PoSEpisode(case_id='fixed/case', config=config, logger=Recorder(),
            belief_call=transferred('belief'), consistency_call=transferred('consistency'),
            progress_call=transferred('progress'))
        episode.reset(task='Clean mug 1.', observation='Mug dirty.', actions=[])
        native_view = episode.decision_view(current_observation='Mug dirty.', actions=[])
        episode.decision_completed(turn=1, action_count=1)
        episode.update(thought='Inspect.', action_batch=[{'id': 'native-1', **action,
            'order': 0, 'status': 'executed'}], observation='Still dirty.', done=True)
        transferred_result = episode.finish(reason='CURRENT_TASK_DONE')
        self.assertEqual([x['role'] for x in role_events],
                         [x['role'] for x in adapter_events])
        self.assertEqual(original['belief_state'], transferred_result['belief_state'])
        self.assertEqual(original['recovery_history'], transferred_result['recovery_history'])
        self.assertEqual(len(original['health_transitions']), 1)
        self.assertEqual(transferred_result['scored_transitions'], 1)
        for section in ('Current observation:', 'Belief Text:',
                        'Goal and Active-Gap structured subgraph:', 'Active Gap:'):
            self.assertIn(section, actor_inputs[0][1]['content'])
            self.assertIn(section, native_view['user'])
        self.assertEqual(original['steps'], 1)
        self.assertFalse(transferred_result['success_known'])

    def test_original_core_single_action_equivalence(self):
        config = execution_config()
        fixed1, fixed2 = replies(), replies()
        calls1, calls2 = [], []
        a, b = callers(fixed1, calls1), callers(fixed2, calls2)
        core = BeliefManager(config, a('belief'), Recorder(),
                             call_sentinel=a('consistency'), call_progress=a('progress'))
        adapted = PoSEpisode(case_id='fixed/case', config=config, logger=Recorder(),
                             belief_call=b('belief'), consistency_call=b('consistency'),
                             progress_call=b('progress'))
        core.reset(state())
        adapted.reset(task='Clean mug 1.', observation='Mug dirty.', actions=[])
        action = [{'id': 'c1', 'name': 'inspect', 'arguments': {}, 'order': 0,
                   'status': 'executed'}]
        transition = {'thought': 'Inspect.', 'action': action,
                      'observation': 'Still dirty.'}
        core.update(transition, state('Still dirty.'), 0)
        adapted.update(thought='Inspect.', action_batch=action,
                       observation='Still dirty.')
        self.assertEqual(calls1, calls2)
        self.assertEqual(core.get_context(), adapted.get_context())
        for key in ('belief_state', 'belief_update_history', 'belief_health_history',
                    'health_transitions', 'frontier_history', 'recovery_history'):
            self.assertEqual(core.get_result()[key], adapted.get_result()[key])
        view = adapted.decision_view(current_observation='Still dirty.', actions=[])
        original = build_belief_prompt(state('Still dirty.'), core.get_context(), config)
        self.assertIn(original[1]['content'].split('Belief Text:')[1].split('Goal and')[0].strip(), view['user'])
        self.assertNotIn('claim_done', view['user'])
        self.assertNotIn('exactly one', view['system'])
        self.assertIn('Mug dirty.', view['user'])
        self.assertFalse(adapted.get_result()['success_known'])

    def test_eight_actions_one_window_step_and_eight_batches(self):
        fixed = replies(8)
        role = callers(fixed, [])
        episode = PoSEpisode(case_id='fixed/case', config=execution_config(),
                             logger=Recorder(), belief_call=role('belief'),
                             consistency_call=role('consistency'),
                             progress_call=role('progress'))
        episode.reset(task='Clean mug 1.', observation='Mug dirty.', actions=[])
        batch = [{'id': str(i), 'name': 'inspect', 'arguments': {},
                  'order': i, 'status': 'executed'} for i in range(8)]
        episode.update(thought='Inspect eight.', action_batch=batch, observation='dirty')
        self.assertEqual(episode.step, 1)
        self.assertEqual(len(episode.get_result()['health_transitions']), 1)
        for i in range(1, 8):
            episode.update(thought='Inspect.', action_batch=batch[:1], observation='dirty')
        self.assertEqual(episode.step, 8)
        self.assertEqual(len(episode.get_result()['health_transitions']), 8)
        self.assertIsNotNone(episode.get_context().get('recovery'))

    def test_invalid_progress_is_unscored_not_zero(self):
        fixed = replies()
        fixed['progress'] = ['not json', 'still not json']
        role = callers(fixed, [])
        episode = PoSEpisode(case_id='unscored', config=execution_config(),
            logger=Recorder(), belief_call=role('belief'),
            consistency_call=role('consistency'), progress_call=role('progress'))
        episode.reset(task='Clean mug 1.', observation='Mug dirty.', actions=[])
        episode.decision_completed(turn=1, action_count=1)
        episode.update(thought='Inspect.', action_batch=[{'id': 'x',
            'name': 'inspect', 'arguments': {}, 'order': 0, 'status': 'executed'}],
            observation='Still dirty.')
        result = episode.get_result()
        self.assertEqual(result['completed_decision_batches'], 1)
        self.assertEqual(result['scored_transitions'], 0)
        self.assertIsNone(result['health_transitions'][0]['progress'])

    def test_worker_framing_and_no_tool_finish(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            responses = root / 'replies.json'
            responses.write_text(json.dumps(replies()), encoding='utf-8')
            cmd = [sys.executable, '-B', '-u', str(HERE / 'worker.py'),
                   '--vendor', str(VENDOR), '--episode-module', str(HERE / 'episode.py'),
                   '--archive', str(root / 'events.jsonl'), '--mode', 'fake',
                   '--fake-replies', str(responses)]
            events = [dict(kind='reset', case_id='fixed/case', task='Clean mug 1.',
                           observation='Mug dirty.', actions=[]),
                      dict(kind='decision_view', observation='Mug dirty.', actions=[]),
                      dict(kind='finish', reason='CURRENT_TASK_DONE')]
            run = subprocess.run(cmd, input=''.join(json.dumps(x) + '\n' for x in events),
                                 text=True, capture_output=True, timeout=15)
            self.assertEqual(run.returncode, 0, run.stderr)
            output = [json.loads(x) for x in run.stdout.splitlines()]
            self.assertEqual(len(output), 3)
            self.assertTrue(all(x['status'] == 'ok' for x in output))
            self.assertEqual(output[-1]['result']['completed_decision_batches'], 0)
            self.assertEqual(output[-1]['result']['scored_transitions'], 0)
            self.assertFalse(output[-1]['result']['success_known'])
            persisted = json.loads((root / 'events.result.json').read_text(encoding='utf-8'))
            self.assertEqual(persisted['case_id'], 'fixed/case')
            self.assertEqual(persisted['status'], 'completed')

    def test_sentinel_repair_before_commit_and_recovery_release(self):
        fixed = replies(9)
        issue = {'targets': ['Mug 1 must be clean'], 'issue_type': 'unsupported',
                 'problem': 'Check the claim.', 'evidence_step': 0,
                 'evidence_quote': 'Still dirty.', 'evidence': 'Still dirty.',
                 'suggestion': 'Retain uncertainty.'}
        fixed['consistency'][1] = json.dumps({'issues': [issue]})
        fixed['consistency'].insert(2, '{"issues": []}')
        fixed['belief'].insert(3, json.dumps(DELTA))
        # The final validated update removes the active gap; the original
        # health/recovery mechanism must release its prior constraint.
        terminal_delta = {**DELTA, 'achievement_gaps': [], 'frontier': None}
        fixed['belief'][-2] = json.dumps(terminal_delta)
        logger = Recorder()
        role = callers(fixed, [])
        episode = PoSEpisode(case_id='fixed/case', config=execution_config(),
            logger=logger, belief_call=role('belief'),
            consistency_call=role('consistency'), progress_call=role('progress'))
        episode.reset(task='Clean mug 1.', observation='Mug dirty.', actions=[])
        action = [{'id': 'x', 'name': 'inspect', 'arguments': {}, 'order': 0,
                   'status': 'executed'}]
        for step in range(9):
            episode.update(thought='Inspect.', action_batch=action,
                           observation='Still dirty.')
        events = [row['event'] for row in logger.events]
        self.assertIn('belief_candidate_repaired', events)
        self.assertIn('belief_recovery_started', events)
        self.assertIn('belief_recovery_finished', events)
        self.assertIsNone(episode.get_context().get('recovery'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
