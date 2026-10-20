"""Zero-model budget checks, including the archived SQLite failure state."""
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parent
POS = ROOT.parent / 'pos_upstream_ga_v1_20261017'
PMA = ROOT.parent / 'curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/vendor/pma_89e5c0d/src'
sys.path[:0] = [str(POS), str(POS / 'vendor'), str(PMA)]
from types import ModuleType
shim = ModuleType('shortuuid')
shim.uuid = lambda: '00000000'
sys.modules.setdefault('shortuuid', shim)
from .candidate import (ComplementEpisode, LIMITS, _gap_records, _json,
                        _required_state, revision_packet)

PUBLIC = ROOT / 'raw_live_sqlite_stop_v1/sqlite/pos/events.result.json'
PRIVATE_SHA256 = 'b6166da3a912f4c0c7f3f5f37ded206826f329d3926d816959cf9fcfc751b849'


def archived_episode():
    path = Path(os.environ.get('CANDIDATE_SQLITE_RAW_RESULT', PUBLIC))
    data = path.read_bytes()
    if path != PUBLIC:
        assert hashlib.sha256(data).hexdigest() == PRIVATE_SHA256
    result = json.loads(data)['result']
    pos_result = result['pos']
    state = pos_result['belief_state']
    context = dict(state, recovery=pos_result['active_recovery'])
    context['accepted_revision'] = 2
    context['latest_update_outcome'] = 'rejected'
    context['latest_actor_transition'] = 'actor-transition-4'
    from belief.beliefStates import BeliefHealth, HealthTransition
    health = BeliefHealth(**pos_result['belief_health'])
    transition = HealthTransition(**pos_result['health_transitions'][-1])
    manager = SimpleNamespace(health_transitions=[transition],
                              _current=lambda: SimpleNamespace(health=health))
    episode = ComplementEpisode.__new__(ComplementEpisode)
    episode.pos = SimpleNamespace(get_context=lambda: dict(context), success_known=False)
    episode.manager = manager
    episode.accepted_revision = 2
    episode.latest_update_outcome = 'rejected'
    episode.latest_actor_transition = 'actor-transition-4'
    episode.advice_history = result['advice_history']
    episode.recent_steps = [{'source_ids': [
        'toolu_0nwD0IfSHdRsvvqvqjQwsS']}]
    episode.events = []
    return episode, result, path


class BudgetTests(unittest.TestCase):
    def test_archived_sqlite_fourth_action_phase2_request(self):
        episode, result, path = archived_episode()
        before = json.dumps(result, ensure_ascii=False, sort_keys=True)
        context = episode._context()
        required = _json(_required_state(context, include_recovery=True))
        related = ''.join('\nDirectly related model-state record: ' + _json(record)
                          for record in _gap_records(context))
        prior = result['advice_history'][-1]
        recap = '\nLast delivered suggestion and actual consequence: ' + _json({
            'advice': prior['advice'], 'delivery_event_id': prior['delivery_event_id'],
            'reviewed_transition': prior.get('reviewed_transition'),
            'actual_results': prior.get('actual_result_excerpts', []),
            'review_outcome': prior.get('review_outcome')})
        transition = result['pos']['health_transitions'][-1]
        signal = '\nExisting PoS health/progress (unscored is not zero): ' + _json({
            'health': result['pos']['belief_health'], 'progress': transition,
            'progress_status': 'scored' if transition['progress'] in (0, 1)
                else 'unscored'})
        old_size = len(required + related + recap + signal)
        self.assertGreater(old_size, LIMITS['phase2_advisory_chars'])
        self.assertGreater(len(transition['observation']), 11000)
        rendered = episode._phase2_context()
        self.assertLessEqual(len(rendered), LIMITS['phase2_advisory_chars'])
        self.assertIn('health_score', rendered)
        self.assertIn('progress_status', rendered)
        self.assertIn('actor-transition-4', rendered)
        self.assertIn('observation_sha256', rendered)
        self.assertNotIn(transition['observation'], rendered)
        from memory_agent.memory.universal_memory import UniversalMemory
        from .memory_adapter import ComplementMemoryAgent
        memory = ComplementMemoryAgent(memory=UniversalMemory.from_dict(result['bank']))
        memory._advisory_context = rendered
        # The precise unsent Phase-2 prompt cannot be recovered. This uses
        # the archived bank and exact last saved observation through the real
        # upstream prompt builder, without shortening the failed input.
        phase2 = memory._build_phase2_prompt(transition['observation'], 5)
        self.assertIn(rendered, phase2)
        self.assertIn('sqlite', phase2.lower())
        self.assertLess(len(phase2.encode('utf-8')), 90000)
        self.assertEqual(before, json.dumps(result, ensure_ascii=False, sort_keys=True))
        print(json.dumps({'source': str(path), 'source_sha256': hashlib.sha256(
            path.read_bytes()).hexdigest(), 'old_required_chars': len(required),
            'old_related_chars': len(related), 'old_recap_chars': len(recap),
            'old_signal_chars': len(signal), 'old_total_chars': old_size,
            'new_advisory_chars': len(rendered), 'phase2_prompt_bytes': len(
                phase2.encode('utf-8')), 'limit': LIMITS['phase2_advisory_chars'],
            'new_advisory_sha256': hashlib.sha256(rendered.encode()).hexdigest()},
            ensure_ascii=False))

    def test_long_and_escaped_observation_not_copied(self):
        episode, *_ = archived_episode()
        for progress in (None, 0, 1):
            episode.manager.health_transitions[-1].progress = progress
            episode.manager.health_transitions[-1].observation = ('"\\\n汉字' * 7000)
            rendered = episode._phase2_context()
            self.assertLessEqual(len(rendered), 16000)
            self.assertNotIn('"\\\n汉字' * 100, rendered)
            self.assertIn('"progress_status":"unscored"' if progress is None
                          else '"progress_status":"scored"', rendered)
            self.assertIn('observation_sha256', rendered)

    def test_optional_state_cannot_displace_core_and_required_fails(self):
        episode, *_ = archived_episode()
        original = episode.pos.get_context()
        original['world'] = {'states': {f's{i}': {'description': 'x' * 3000}
                                             for i in range(8)}}
        original['frontier_gap'] = {'target': 's0'}
        episode.pos.get_context = lambda: original
        rendered = episode._phase2_context()
        self.assertIn('health_score', rendered)
        self.assertIn('Optional advisory details omitted', rendered)
        self.assertTrue(any(row['kind'] == 'phase2_optional_omitted'
                            for row in episode.events))
        original['goal'] = {'user_input': 'Y' * 17000}
        with self.assertRaisesRegex(ValueError, 'required Phase 2'):
            episode._phase2_context()

    def test_revision_four_long_receipts_keep_frozen_source(self):
        delivered = {'state_version': 3, 'delivery_event_id': 'sent',
                     'advice': 'Keep the condition, not only the first result.',
                     'advice_sha256': 'a' * 64,
                     'source_pack': [{'event_id': f'h{i}', 'segments': [
                         {'text': 'z' * 1700, 'source_path': 'result.stdout',
                          'segment': 0, 'truncated': False}]} for i in range(4)]}
        sources = [{'tool_use_id': f'now{i}', 'result': {'stdout':
            '"\\\n汉字' * 900}} for i in range(4)]
        packet = json.loads(revision_packet(delivered=delivered,
            completed_transition_id='joint-next', source_events=sources))
        self.assertLessEqual(len(_json(packet)), LIMITS['revision_chars'])
        self.assertEqual(packet['frozen_memory_sources'], delivered['source_pack'])
        self.assertEqual(packet['advice_sha256'], delivered['advice_sha256'])
        self.assertGreater(len(packet['source_events']), 0)
        self.assertTrue(any(row['truncated'] for row in packet['source_events']))
        self.assertEqual(len(packet['source_events']) + packet['optional_receipts_omitted'], 4)
        for row in packet['source_events']:
            self.assertIn('full_receipt_sha256', row)
            self.assertTrue(all('start' in part for part in row['segments']))

    def test_revision_zero_one_and_odd_remaining_budget(self):
        delivered = {'state_version': 1, 'delivery_event_id': 'sent',
                     'advice': 'Do not drop this condition.', 'source_pack': []}
        source = [{'tool_use_id': 'call', 'result': {'stdout': 'x' * 5000}}]
        baseline = len(revision_packet(delivered=delivered,
            completed_transition_id='joint', source_events=[]))
        previous = LIMITS['revision_chars']
        try:
            for extra in (0, 1, 3):
                LIMITS['revision_chars'] = baseline + extra
                packet = json.loads(revision_packet(delivered=delivered,
                    completed_transition_id='joint', source_events=source))
                self.assertLessEqual(len(_json(packet)), baseline + extra)
                self.assertEqual(packet['optional_receipts_omitted'], 1)
                self.assertEqual(packet['source_events'], [])
        finally:
            LIMITS['revision_chars'] = previous


if __name__ == '__main__':
    unittest.main(verbosity=2)
