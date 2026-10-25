"""Local no-network regression, including adapted upstream mock tests (see REUSE)."""
import asyncio
import copy
import json
import tempfile
import unittest
from pathlib import Path

from pma_evidence_review.inputs import build_from_data, validate, digest
from pma_evidence_review.review import (parse_claims, parse_results, extraction_request,
    verification_requests, review)
from pma_evidence_review.transport import FakeClient, CapturedTransport, load_profile_client
from pma_evidence_review.vendor.rag_models import Claim, VerificationResult
from pma_evidence_review.vendor.sourcecheck_types import Verdict, ReasonCode
from pma_evidence_review.tests.fixtures import bundle, packet, extraction, result
from pma_evidence_review.tests.no_network import install_guard


class OfflineTests(unittest.TestCase):
    def setUp(self):
        install_guard(self)

    def test_upstream_extract_claims_basic(self):
        # Adapted TestClaimExtractor.test_extract_claims_basic, async fake exercised below.
        claims, _, _, _ = parse_claims(extraction(), packet())
        self.assertGreaterEqual(len(claims), 1)
        self.assertTrue(all(isinstance(c, Claim) for c in claims))
        self.assertEqual(claims[0].index, 1)

    def test_upstream_multiple_claims_same_span(self):
        claims, _, _, _ = parse_claims(extraction(True), packet())
        self.assertEqual([c.index for c in claims], [1, 2])
        self.assertEqual(claims[0].span, claims[1].span)
        self.assertNotEqual(claims[0].text, claims[1].text)

    def test_upstream_verify_contradicted(self):
        claims, _, _, _ = parse_claims(extraction(), packet())
        rows = parse_results(result('CONTRADICTED', ['green']), claims)
        self.assertEqual(rows[0]['verdict'], 'contradicted')
        self.assertEqual(rows[0]['claim_index'], 1)

    def test_sourcecheck_three_states_and_reasons(self):
        self.assertEqual({v.value for v in Verdict}, {'supported','contradicted','not_verifiable'})
        self.assertNotEqual(ReasonCode.NO_CONTENT, ReasonCode.LOW_GROUNDING)

    def test_parser_boundaries(self):
        claims, _, _, _ = parse_claims(extraction(), packet())
        for label in ('UNSUPPORTED', 'NOT SUPPORTED', 'SUPPORTED probably', '', 'unsupported',
                      'supported\ncontradicted'):
            with self.subTest(label=label), self.assertRaises(ValueError):
                parse_results(result(label, ['green']), claims)
        for raw in ('', '{}', '[]', 'not JSON', '{"verdict":"SUPPORTED","verdict":"CONTRADICTED"}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_results(raw, claims)

    def test_missing_duplicate_unknown_results(self):
        claims, _, _, _ = parse_claims(extraction(True), packet())
        row = json.loads(result(claim_index=2))
        rows = parse_results(json.dumps([row]), claims, True)
        self.assertEqual(rows[0]['engineering_status'], 'missing_result')
        self.assertIsNone(rows[0]['verdict'])
        for data in ([row, row], [dict(row, claim_index=3)], [dict(row, claim_index=True)]):
            with self.assertRaises(ValueError):
                parse_results(json.dumps(data), claims, True)

    def test_empty_incomplete_extraction_visible(self):
        data = json.loads(extraction()); data['claims'] = []
        _, _, _, errors = parse_claims(json.dumps(data), packet())
        self.assertIn('extraction_empty_unverified', errors)
        data['coverage'] = []
        with self.assertRaises(ValueError):
            parse_claims(json.dumps(data), packet())

    def test_duplicate_claim_and_missing_conditions(self):
        data = json.loads(extraction())
        data['claims'] *= 2
        with self.assertRaisesRegex(ValueError, 'duplicate_claim'):
            parse_claims(json.dumps(data), packet())
        data['claims'] = data['claims'][:1]
        del data['claims'][0]['conditions']
        with self.assertRaises(ValueError):
            parse_claims(json.dumps(data), packet())

    def test_plan_hypothesis_question_are_typed(self):
        for kind in ('plan', 'hypothesis', 'question'):
            data = json.loads(extraction()); data['claims'][0]['kind'] = kind
            _, meta, _, _ = parse_claims(json.dumps(data), packet())
            self.assertEqual(meta[1]['kind'], kind)

    def test_deletion_uses_historical_tombstone(self):
        args = bundle(); raw = args[1]['steps'][0]['operations'][0]
        raw.update(action='delete_gap', content=None)
        aligned = args[2][0]['evidence_report']['operations'][0]
        aligned.pop('revision_id')
        args[3]['gap_evidence']['tombstones']['t1'] = {
            'cycle_id':'c1','op_index':0,'memory_id':'m1','revision_id':'old'}
        p = build_from_data(*args, step=1, cycle_id='c1')
        self.assertEqual(p['operations'][0]['content'], 'Need to check the tool.')
        self.assertEqual(p['operations'][0]['revision_id'], 'old')
        args[3]['gap_evidence']['tombstones'].clear()
        with self.assertRaisesRegex(ValueError, 'tombstone'):
            build_from_data(*args, step=1, cycle_id='c1')

    def test_commands_receipts_separate(self):
        p = packet()
        self.assertEqual([s['role'] for s in p['sources']],
                         ['task_instruction', 'tool_command', 'tool_observation', 'memory_derived'])
        self.assertIn('Commands establish attempted actions', extraction_request(p)['system'])

    def test_future_information_isolation(self):
        args = bundle(); before = extraction_request(build_from_data(*args, step=1, cycle_id='c1'))
        args[0].append({'phase':'judgment','cycle_step':1,'prompt':'SENTINEL'})
        args[1]['steps'][0].update(raw_response_phase2='SENTINEL',should_inject='SENTINEL',
                                  context_for_action='SENTINEL', user_prompt_phase2='SENTINEL')
        args[1]['steps'].append({'step_id':2,'operations':'SENTINEL'})
        args[2][0]['report']['actual_phase2_prompt']='SENTINEL'
        args[3].update(status='SENTINEL', reward='SENTINEL', selection='SENTINEL')
        args[3]['gap_evidence']['active_revisions'] = {'m1':'SENTINEL'}
        args[3]['gap_evidence']['revisions']['future'] = {'content':'SENTINEL'}
        after = extraction_request(build_from_data(*args, step=1, cycle_id='c1'))
        self.assertEqual(before, after)
        self.assertNotIn('SENTINEL', json.dumps(after))

    def test_input_missing_and_redacted(self):
        args = bundle(); args[0][0]['prompt'] = args[0][0]['prompt'].replace('green','[REDACTED]')
        with self.assertRaisesRegex(ValueError,'hash_mismatch'):
            build_from_data(*args, step=1, cycle_id='c1')
        p = build_from_data(*args, step=1, cycle_id='c1',allow_redacted=True)
        self.assertEqual(p['sources'], [])
        self.assertEqual(p['replay_status'],'degraded_replay')
        args = bundle(); del args[3]['gap_evidence']['revisions']['old']
        with self.assertRaises(ValueError):
            build_from_data(*args,step=1,cycle_id='c1')

    def test_fake_end_to_end_actual_requests_and_raw_responses(self):
        with tempfile.TemporaryDirectory() as directory:
            client = FakeClient([extraction(True), result(), result()])
            transport = CapturedTransport(client,directory,fake=True)
            report = asyncio.run(review(packet(),transport))
            self.assertEqual(transport.calls,3)
            self.assertEqual(len(report['results']),2)
            self.assertTrue(all(r['verdict']=='insufficient' for r in report['results']))
            self.assertEqual(client.calls[0], transport.records[0]['request'])
            self.assertIn('Step 1: Extract relevant evidence',client.calls[1]['prompt'])
            self.assertEqual(transport.records[0]['response'],extraction(True))
            self.assertEqual(len(Path(directory,'requests.jsonl').read_text().splitlines()),3)
            self.assertFalse(report['memory_mutated'])

    def test_batch_is_explicit_and_aligns_out_of_order(self):
        responses = json.dumps([dict(json.loads(result()),claim_index=i) for i in (2,1)])
        transport=CapturedTransport(FakeClient([extraction(True),responses]),fake=True)
        report=asyncio.run(review(packet(),transport,mode='batch'))
        self.assertEqual(transport.calls,2)
        self.assertEqual([r['claim_index'] for r in report['results']],[1,2])
        self.assertIn('Claims to verify:',transport.records[1]['request']['prompt'])

    def test_errors_never_become_semantic_pass(self):
        for response,status in [(RuntimeError('private error'), 'call_error'),('', 'parse_failure')]:
            transport=CapturedTransport(FakeClient([extraction(),response]),fake=True)
            report=asyncio.run(review(packet(),transport))
            self.assertEqual(report['results'][0]['engineering_status'],status)
            self.assertIsNone(report['results'][0]['verdict'])
            self.assertNotIn('private error',json.dumps(transport.records))

    def test_hidden_historical_content_refused(self):
        args = bundle()
        rev = args[3]['gap_evidence']['revisions']['old']
        rev['content_sha256'] = digest('HIDDEN_FUTURE_CONTENT')
        args[3]['gap_evidence']['blobs'][rev['content_sha256']] = 'HIDDEN_FUTURE_CONTENT'
        with self.assertRaisesRegex(ValueError, 'historical_memory_not_fully_visible'):
            build_from_data(*args, step=1, cycle_id='c1')

    def test_single_unknown_index_and_task_substitution(self):
        claims, _, _, _ = parse_claims(extraction(), packet())
        with self.assertRaisesRegex(ValueError, 'unknown_result_index'):
            parse_results(result(claim_index=999), claims)
        p = packet()
        p['original_task'] = 'FUTURE_TASK'
        with self.assertRaisesRegex(ValueError, 'task_not_visible'):
            validate(p)

    def test_live_flag_checked_before_credentials(self):
        with self.assertRaisesRegex(ValueError,'authorization'):
            load_profile_client('.', '/no-such-profile', 'x', '/unused')


if __name__ == '__main__':
    unittest.main()
