"""Zero-model replay of the archived v3 native unscored progress and next step."""
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE / 'vendor')]

from belief.beliefSentinel import BeliefSentinel
from episode import PoSEpisode, execution_config
from test_offline import Recorder
from worker import RoleTransport, _adapt_role_json


PROBE = HERE / 'raw_compat_v3/probe'
FIRST_OBSERVATION = ('SYNTHETIC PUBLIC OBSERVATION: marker is visible; '
                     'no real environment action occurred.')
SECOND_OBSERVATION = ('SYNTHETIC SECOND OBSERVATION: a later distinct '
                      'inspection now confirms the marked item was inspected once.')


def rows():
    return [json.loads(line) for line in (PROBE / 'role_events.jsonl').read_text(
        encoding='utf-8').splitlines()]


class NativeUnscoredContinuity(unittest.TestCase):
    def test_exact_archived_progress_rejected_then_new_synthetic_score_accepted(self):
        archived = rows()
        original = json.loads((PROBE / 'result.json').read_text(encoding='utf-8'))
        self.assertEqual(original['status'], 'failed')  # Never rewrite history.
        original_responses = [r for r in archived if r['event'] == 'pos_role_response']
        self.assertEqual(len(original_responses), 9)
        replies = {role: [r['response'] for r in original_responses
                          if r['role'] == role]
                   for role in ('belief', 'consistency', 'progress')}
        exact_progress = replies['progress'][0]
        replies['belief'] += [json.dumps({
            'remove_state_ids': [], 'remove_relation_ids': [],
            'upsert_entities': [],
            'upsert_states': [{'state_id': 's2', 'entity_id': 'e1',
                               'description': 'marked item was inspected once'}],
            'upsert_relations': [], 'epistemic_gaps': [],
            'achievement_gaps': [], 'frontier': None}),
            json.dumps({'belief_text': 'Synthetic later observation: the marked '
                        'item was inspected once; no active gap remains.'})]
        replies['consistency'].append('{"issues":[]}')
        replies['progress'].append(json.dumps({
            'progress': 1, 'score': 1.0, 'affected_record_ids': ['s2'],
            'reason': 'SYNTHETIC: the later observation added state s2.'}))

        log = Recorder()
        transport = RoleTransport(mode='fake', replies=replies, archive=log)
        episode = PoSEpisode(case_id='synthetic-compatibility',
            config=execution_config(), logger=log,
            belief_call=transport.caller('belief'),
            consistency_call=transport.caller('consistency'),
            progress_call=transport.caller('progress'))
        episode.reset(task='SYNTHETIC GOAL: inspect a marked item once.',
            observation='SYNTHETIC INITIAL OBSERVATION: item state unknown.',
            actions=[{'name':'probe', 'description':
                      'Synthetic observation marker; not executed.'}])
        first = episode.update(thought='Synthetic inspection decision.',
            action_batch=[{'id':'synthetic-action-1', 'name':'probe',
                           'arguments':{}, 'order':0,
                           'status':'synthetic_observation_only'}],
            observation=FIRST_OBSERVATION, done=False)
        current = episode.get_result()
        first_prompt = next(r for r in log.events if r['event'] ==
                            'belief_sentinel_progress_model_input')
        archived_prompt = next(r for r in archived if r['event'] ==
                               'belief_sentinel_progress_model_input')
        actual_input = json.loads(first_prompt['messages'][1]['content'].splitlines()[0])
        archived_input = json.loads(archived_prompt['messages'][1]['content'].splitlines()[0])
        self.assertEqual(actual_input['belief_before'], archived_input['belief_before'])
        self.assertEqual(actual_input['belief_after'], archived_input['belief_after'])
        self.assertEqual(next(r['response'] for r in log.events if
            r['event'] == 'pos_role_response' and r['role'] == 'progress'), exact_progress)
        parser_input = _adapt_role_json(exact_progress)[0]
        with self.assertRaisesRegex(ValueError,
                                    "affected_record_ids did not change: \\['e1'\\]"):
            BeliefSentinel._validate_progress_payload(json.loads(parser_input),
                actual_input['belief_before'], actual_input['belief_after'])
        self.assertTrue(any(r['event'] == 'belief_sentinel_progress_failed' and
                            r['step'] == 0 for r in log.events))
        self.assertEqual(current['belief_update_history'][-1]['status'], 'repaired')
        first_update_status = current['belief_update_history'][-1]['status']
        self.assertTrue(any(r['event'] == 'belief_text_updated' and r['step'] == 0
                            for r in log.events))
        self.assertTrue(first['belief_text'])
        first_transition = current['health_transitions'][0]
        self.assertIsNone(first_transition['progress'])
        self.assertIsNone(first_transition['score'])
        self.assertIsNone(first_transition['scoring_method'])
        self.assertEqual(current['scored_transitions'], 0)
        self.assertEqual(current['belief_sentinel']['progress_history'], [])
        self.assertFalse(current['belief_health']['window_ready'])
        self.assertIsNone(current['active_recovery'])

        second = episode.update(thought='SYNTHETIC next distinct action.',
            action_batch=[{'id':'synthetic-action-2', 'name':'probe',
                           'arguments':{}, 'order':0,
                           'status':'synthetic_observation_only'}],
            observation=SECOND_OBSERVATION, done=False)
        later = episode.get_result()
        self.assertEqual(len([r for r in log.events if r['event'] ==
                              'belief_sentinel_progress_model_input']), 2)
        self.assertEqual(later['health_transitions'][0], first_transition)
        self.assertEqual(later['health_transitions'][1]['progress'], 1)
        self.assertEqual(later['health_transitions'][1]['scoring_method'],
                         'execution_llm')
        self.assertEqual(later['health_transitions'][1]['affected_record_ids'], ('s2',))
        self.assertEqual(later['scored_transitions'], 1)
        self.assertEqual(len(later['belief_sentinel']['progress_history']), 1)
        self.assertEqual(later['belief_sentinel']['progress_history'][0]['step'], 1)
        self.assertFalse(later['belief_health']['window_ready'])
        self.assertIsNone(later['active_recovery'])
        self.assertTrue(second['belief_text'])
        view = episode.decision_view(current_observation=SECOND_OBSERVATION,
            actions=[{'name':'probe', 'description':'synthetic'}])
        self.assertIn('SYNTHETIC SECOND OBSERVATION', view['user'])
        self.assertIn('Belief Text:', view['user'])

        capture = os.environ.get('POS_CONTINUITY_CAPTURE')
        if capture:
            record = {'schema':'pos-native-unscored-continuity-v1',
                'model_calls':0, 'archived_probe_status':original['status'],
                'archived_role_events_sha256':hashlib.sha256(
                    (PROBE/'role_events.jsonl').read_bytes()).hexdigest(),
                'exact_archived_progress_sha256':hashlib.sha256(
                    exact_progress.encode('utf-8')).hexdigest(),
                'first_progress':first_transition['progress'],
                'first_score':first_transition['score'],
                'first_scoring_method':first_transition['scoring_method'],
                'first_update_status':first_update_status,
                'first_progress_failed':True, 'first_window_ready':False,
                'second_progress':later['health_transitions'][1]['progress'],
                'second_affected_record_ids':later['health_transitions'][1][
                    'affected_record_ids'], 'second_scored_transitions':later[
                    'scored_transitions'], 'second_window_ready':False,
                'recovery':later['active_recovery'],
                'next_decision_view_generated':True}
            with Path(capture).open('x', encoding='utf-8', newline='\n') as stream:
                json.dump(record, stream, ensure_ascii=False, indent=2)
                stream.write('\n')


if __name__ == '__main__':
    unittest.main(verbosity=2)
