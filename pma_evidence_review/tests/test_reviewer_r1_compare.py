import asyncio
import json
import unittest

from pma_evidence_review import claim_split_semantic as v4, claim_split_simple as v3
from pma_evidence_review import reviewer_r1_compare as compare
from pma_evidence_review.citation_inputs import identity
from pma_evidence_review.transport import CapturedTransport, FakeClient


class ReviewerR1ComparisonTests(unittest.TestCase):
    def test_fixed_cases_and_pairwise_payload(self):
        rows = compare.cases()
        self.assertEqual((len(rows), len(rows[:13]), len(rows[13:])), (22, 13, 9))
        self.assertTrue(all(r['claims'] for r in rows))
        self.assertTrue(all(r['origin']['kind'] == 'manual_constructed_control' for r in rows[13:]))
        baseline, candidate = compare.plan('baseline'), compare.plan('v4-reviewer-r1')
        self.assertEqual(baseline['review_system_sha256'],
                         'fb6a2cf9904a9f65bfb88c44c81be334ae430b7ff93ff516617114861fde9f71')
        self.assertEqual(compare.sha(v4.SPLIT_SYSTEM),
                         'b57be62604b515cd1659a989acc228740d47dd6f53dab1fd458e3349fce7602b')
        self.assertNotEqual(baseline['review_system_sha256'], candidate['review_system_sha256'])
        self.assertEqual(candidate['review_system_sha256'], compare.sha(v4.VERIFY_SYSTEM))
        self.assertTrue(v4.VERIFY_SYSTEM.startswith('Review whether the submitted evidence B'))
        self.assertNotIn(v3.BOUNDARY, v4.VERIFY_SYSTEM)
        self.assertNotIn(v3.SUPPORT_SENTENCE, v4.VERIFY_SYSTEM)
        for old, new, row in zip(baseline['entries'], candidate['entries'], rows):
            self.assertEqual(old['case_id'], new['case_id'])
            self.assertEqual(old['material_sha256'], identity(row['material']))
            self.assertEqual(old['claims_sha256'], identity(row['claims']))
            left, right = dict(old['request']), dict(new['request'])
            self.assertNotEqual(left.pop('system'), right.pop('system'))
            self.assertNotEqual(left.pop('audit_request_sha256'), right.pop('audit_request_sha256'))
            self.assertEqual(left, right)
            model_payload = json.dumps(new['request'], ensure_ascii=False)
            self.assertNotIn(row['reference_reason'], model_payload)
        self.assertEqual([r['reference_label'] for r in rows[13:]],
                         ['supported', 'insufficient', 'supported'] * 3)
        self.assertEqual(sum(r['material']['original_operation']['action'] == 'delete_gap' for r in rows[:13]), 2)

    def test_existing_split_and_protocol_untouched(self):
        self.assertIn('You will not see evidence.', v4.SPLIT_SYSTEM)
        claims = ['first', 'second']
        raw = json.dumps({'overall': {'verdict': 'supported', 'reason': 'overall'},
                          'results': [{'verdict': 'supported', 'reason': 'first'},
                                      {'verdict': 'insufficient', 'reason': 'second'}]})
        reviews, overall, verdict = v3.parse_batch(raw, claims)
        self.assertEqual((len(reviews), overall['verdict'], verdict), (2, 'supported', 'insufficient'))
        with self.assertRaisesRegex(ValueError, 'batch_cardinality'):
            v3.parse_batch(raw, ['only one'])

    def test_one_batch_call_without_split(self):
        frozen = compare.plan('v4-reviewer-r1')
        answer = json.dumps({'overall': {'verdict': 'supported', 'reason': 'yes'},
                             'results': [{'verdict': 'supported', 'reason': 'yes'}]})
        # One manually constructed control, then an intentional response shortage.
        one = {**frozen, 'entries': [frozen['entries'][13]]}
        client = FakeClient([answer])
        results = asyncio.run(compare.run(one, CapturedTransport(client, fake=True)))
        self.assertEqual((len(client.calls), results[0]['engineering_status'], results[0]['verdict']),
                         (1, 'ok', 'supported'))
        self.assertEqual(client.calls[0]['system'], v4.VERIFY_SYSTEM)
        self.assertEqual(client.calls[0]['tools'], None)

    def test_score_keeps_three_state_and_acceptance_separate(self):
        frozen = compare.plan('baseline')
        entries = frozen['entries']
        rows = []
        for entry in entries:
            rows.append({'case_id': entry['case_id'],
                         'material_sha256': entry['material_sha256'],
                         'claims_sha256': entry['claims_sha256'],
                         'audit_request_sha256': entry['request']['audit_request_sha256'],
                         'model_verdict': 'insufficient', 'verdict': 'insufficient',
                         'engineering_status': 'ok'})
        scored = compare.score({'plan_sha256': frozen['plan_sha256'], 'results': rows}, frozen)
        self.assertEqual(len(scored['results']), 22)
        self.assertEqual(sum(r['delete'] for r in scored['results']), 2)
        self.assertTrue(scored['results'][2]['three_state_agreement'])
        self.assertFalse(scored['results'][0]['acceptance_agreement'])


if __name__ == '__main__':
    unittest.main()
