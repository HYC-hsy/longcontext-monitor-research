"""No-provider checks for the opt-in released-PoS citation representation fix."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'vendor'))
from belief.beliefSentinel import BeliefSentinel, SentinelIssue
from .citation_fix import CitationFixedBeliefManager, CitationFixedSentinel
from .episode import PoSEpisode, execution_config


def issue(quote, *, target='s107', step=64):
    return SentinelIssue(targets=[target], issue_type='inconsistent',
        problem='candidate conflicts with receipt', evidence_step=step,
        evidence_quote=quote, evidence=quote, suggestion='review')


def trajectory(result, *, action=None):
    return {'step': 64, 'action': action or {'name': 'code_run'},
            'observation': json.dumps({'tool_results': [
                {'role': 'tool', 'result': result}]}, ensure_ascii=False)}


class Recorder:
    def __init__(self): self.events = []
    def log(self, kind, **data): self.events.append((kind, data))


class CitationTests(unittest.TestCase):
    def valid(self, row, quote, **changes):
        evidence = {64: CitationFixedSentinel._trajectory_text(row)}
        return CitationFixedSentinel._valid_issue(issue(quote, **changes),
                                                   {'s107'}, evidence)

    def test_decoded_newline_and_unchanged_vendor_difference(self):
        row = trajectory('line one\nline two')
        quote = 'line one\nline two'
        self.assertTrue(self.valid(row, quote))
        self.assertFalse(BeliefSentinel._valid_issue(issue(quote), {'s107'},
                         {64: BeliefSentinel._trajectory_text(row)}))

    def test_literal_backslash_n_quotes_unicode_and_case(self):
        # Earlier test incorrectly treated a literal backslash-n as a newline.
        self.assertFalse(self.valid(trajectory('alpha\\nbeta'), 'ALPHA\nbeta'))
        self.assertTrue(self.valid(trajectory('alpha\\nbeta'), 'ALPHA\\nbeta'))
        self.assertTrue(self.valid(trajectory('He said "你好".\nDone.'),
                                   'he said "你好".\nDONE.'))

    def test_single_field_and_no_cross_field_stitching(self):
        row = {'step': 64, 'action': {'arguments': {'left': 'alpha'}},
               'observation': json.dumps({'tool_results': [
                   {'result': 'beta'}, {'result': 'gamma'}]})}
        self.assertTrue(self.valid(row, 'beta'))
        self.assertFalse(self.valid(row, 'alpha beta'))
        self.assertFalse(self.valid(row, 'beta gamma'))
        self.assertFalse(self.valid(row, 'delta'))
        self.assertFalse(self.valid(row, 'alpha'))
        wrapped = {'step': 64, 'action': {'arguments': {'text': 'not a receipt'}},
                   'observation': json.dumps({'content': 'host prose only',
                       'tool_results': [{'content': 'actual receipt'}]})}
        self.assertTrue(self.valid(wrapped, 'actual receipt'))
        self.assertFalse(self.valid(wrapped, 'host prose only'))
        self.assertFalse(self.valid(wrapped, 'not a receipt'))

    def test_nested_host_fields_never_become_tool_evidence(self):
        row = trajectory({'stdout': 'actual\nline', 'next_prompt': 'fake quote',
                          'arguments': {'text': 'argument quote'},
                          'metadata': {'content': 'metadata quote'}})
        self.assertTrue(self.valid(row, 'actual\nline'))
        for quote in ('fake quote', 'argument quote', 'metadata quote'):
            self.assertFalse(self.valid(row, quote))

    def test_truncated_wrapper_and_segment_boundary(self):
        row = trajectory('HEAD' + 'x' * 100 + 'TAIL')
        sentinel = CitationFixedSentinel({'consistency_enabled': True,
            'audit_observation_max_chars': 20}, lambda messages: '{}', Recorder())
        compact = sentinel._compact_trajectory([row])[0]
        fields = sentinel._trajectory_text(compact)
        self.assertTrue(any('HEAD' in field for field in fields))
        self.assertTrue(any('TAIL' in field for field in fields))
        self.assertFalse(any('HEADTAIL' in field for field in fields))
        self.assertFalse(any('x' * 50 in field for field in fields))
        broken = {'step': 64, 'observation': '{"tool_results": [{"result": "fake"',
                  'action': {'name': 'code_run'}}
        self.assertFalse(self.valid(broken, 'fake'))

    def test_target_step_and_cropped_scope(self):
        row = trajectory('short retained fragment')
        self.assertFalse(self.valid(row, 'short retained fragment', target='s999'))
        self.assertFalse(self.valid(row, 'short retained fragment', step=63))
        self.assertFalse(self.valid(row, 'text outside cropped scope'))
        self.assertFalse(self.valid({'step': 64, 'observation': 'visible',
                                     'derived_suggestion': 'fake quote'}, 'fake quote'))
        self.assertFalse(self.valid({'step': 64, 'observation': json.dumps(
            {'role': 'assistant', 'content': 'not a tool receipt'})},
            'not a tool receipt'))

    def test_real_audit_dispatch_and_mode_isolation(self):
        row = trajectory('first\nsecond')
        payload = json.dumps({'issues': [dict(targets=['s107'], issue_type='inconsistent',
            problem='candidate conflicts', evidence_step=64,
            evidence_quote='first\nsecond', evidence='first\nsecond',
            suggestion='review')]})
        before = {'world': {'entities': {}, 'states': {'s107': {'description': 'x'}},
                            'relations': {}}, 'goal': {}, 'epistemic_gaps': [],
                  'achievement_gaps': []}
        logger = Recorder()
        config = {'consistency_enabled': True, 'progress_enabled': False,
                  'model': {'max_json_retries': 1}}
        base = BeliefSentinel(config, lambda messages: payload, logger)
        fixed = CitationFixedSentinel(config, lambda messages: payload, logger)
        args = dict(case_id='fixed/case', base_step=64, mode='local',
                    belief_before=before, candidate_belief=before,
                    raw_trajectory=[row])
        self.assertEqual(base.audit_candidate(**args), [])
        self.assertEqual(len(fixed.audit_candidate(**args)), 1)
        manager = CitationFixedBeliefManager(execution_config(),
            lambda messages: '{}', logger, call_sentinel=lambda messages: payload,
            call_progress=lambda messages: '{}')
        self.assertIsInstance(manager.sentinel, CitationFixedSentinel)
        episode = PoSEpisode(case_id='fixed/case', config=execution_config(),
            logger=logger, belief_call=lambda messages: '{}',
            consistency_call=lambda messages: payload,
            progress_call=lambda messages: '{}', citation_fixed=False)
        self.assertIs(type(episode.manager), type(manager).__base__)
        repaired = PoSEpisode(case_id='fixed/case', config=execution_config(),
            logger=logger, belief_call=lambda messages: '{}',
            consistency_call=lambda messages: payload,
            progress_call=lambda messages: '{}', citation_fixed=True)
        self.assertIsInstance(repaired.manager.sentinel, BeliefSentinel)
        self.assertIs(type(repaired.manager.sentinel).__base__, BeliefSentinel)


if __name__ == '__main__':
    unittest.main(verbosity=2)
