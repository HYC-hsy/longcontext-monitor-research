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
from belief.manager import BeliefManager
from prompts.react_prompt import build_belief_prompt
from episode import PoSEpisode, execution_config

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
                   'status': 'executed', 'result': 'Still dirty.'}]
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
        self.assertEqual(view['upstream_messages'], original)
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
                  'order': i, 'status': 'executed', 'result': 'dirty'} for i in range(8)]
        episode.update(thought='Inspect eight.', action_batch=batch, observation='dirty')
        self.assertEqual(episode.step, 1)
        self.assertEqual(len(episode.get_result()['health_transitions']), 1)
        for i in range(1, 8):
            episode.update(thought='Inspect.', action_batch=batch[:1], observation='dirty')
        self.assertEqual(episode.step, 8)
        self.assertEqual(len(episode.get_result()['health_transitions']), 8)
        self.assertIsNotNone(episode.get_context().get('recovery'))

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
            self.assertEqual(output[-1]['result']['scored_decision_batches'], 0)
            self.assertFalse(output[-1]['result']['success_known'])

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
                   'status': 'executed', 'result': 'Still dirty.'}]
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
