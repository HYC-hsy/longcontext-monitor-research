"""Protocol and input-boundary checks only; scripted verdicts are not semantic evidence."""
import json
import unittest

from pma_evidence_review.tests import runtime_boundary_support  # optional-import doubles
from pma_evidence_review import operation_audit as audit, claim_split_semantic as v4
from pma_evidence_review.tests import test_claim_split_semantic as helpers
from pma_evidence_review.tests.test_live_gate import TEXT


class GapAuditContractTests(unittest.TestCase):
    def test_all_rows_three_columns_and_raw_preserved(self):
        request = audit.prepare('r', {'action': 'save', 'arguments': {'content': 'x'}}, None, ['x'], [])
        for verdict in ('supported', 'insufficient', 'contradicted'):
            rows = [['O', verdict, 'Decisive basis.'], ['C1', verdict, 'Same scope.']]
            for fence in ('', 'json', 'text', None):
                raw = json.dumps(rows)
                if fence is not None:
                    raw = '```' + fence + '\n' + raw + '\n```'
                result = audit.parse_batch(request, raw, completion_request_id='r')
                self.assertEqual(result.verdict, verdict)
                self.assertEqual(result.raw, raw)
                self.assertEqual(result.audit_protocol, audit.PROTOCOL)
            malformed = [rows[:1], rows + [rows[1]], rows + [['C2', verdict, 'Extra.']]]
            for label in ('O', 'C1'):
                for bad in ([label, verdict], [label, verdict, ''], [label, verdict, ' '],
                            [label, verdict, None], [label, 'maybe', 'Reason.'], [label, 1, 'Reason.'],
                            [17, verdict, 'Reason.'],
                            [label, verdict, 'Reason.', 'Extra suggestion.']):
                    malformed.append([bad if row[0] == label else row for row in rows])
            for value in malformed:
                with self.subTest(value=value):
                    raw = json.dumps(value)
                    result = audit.parse_batch(request, raw, completion_request_id='r')
                    self.assertEqual(result.engineering_status, 'parse_error')
                    self.assertIsNone(result.verdict)
                    self.assertEqual(result.raw, raw)

    def test_only_relevant_action_guidance(self):
        for action in ('save', 'update', 'delete'):
            for category in ('gap', 'knowledge', 'status'):
                if action == 'delete' and category != 'gap':
                    continue
                request = audit.prepare('r', {'action': action, 'arguments': {'category': category,
                    'content': 'Concern.'}}, {'content': 'Before.'}, ['Concern.'], [])
                system = audit.system_for(request)
                self.assertEqual(audit.GAP_WRITE_GUIDANCE in system,
                                 category == 'gap' and action != 'delete')
                self.assertEqual('problem persists' in system, action == 'delete')
                self.assertNotIn(audit.REPAIR_GUIDANCE, system)

    def test_split_semantic_allowlist_preserves_complete_host_operation(self):
        original = helpers.material('An unresolved issue, not completion.')
        request = v4.split_request(original, 0)
        target = json.loads(request['prompt'].split('\n', 1)[1])['original_operation']
        self.assertEqual(list(target), ['action', 'content'])
        self.assertEqual(request['closed_material']['original_operation'], original['original_operation'])
        original['original_operation']['unknown_business_condition'] = 'Do not silently drop me.'
        with self.assertRaises(ValueError):
            v4.split_request(original, 0)

    def test_repair_original_issue_frozen_and_reviewer_decides(self):
        helper = helpers.SemanticSplitTests()
        helper.setUp()
        self.addCleanup(helper.doCleanups)
        original = 'Endpoint missing; availability needs repair.'
        corrected = 'Endpoint exists but returns 500; availability needs repair.'
        for verdict in ('supported', 'insufficient'):
            args = {'content': original, 'evidence': [{'quote': TEXT}]}
            agent, result, calls = helper._cycle([('memory_save_gap', args)],
                [[original], helpers.batch('insufficient'), [corrected], helpers.batch(verdict)], repair_limit=1,
                repairs=[{'decision': 'replace', 'content': corrected, 'evidence': [{'quote': TEXT}]}])
            reviews = [kw for phase, kw in calls if phase == 'citation_review'
                       and kw['prompt'].startswith('TARGET AND SHARED')]
            first, second = [json.loads(kw['prompt'].split('\n', 1)[1]) for kw in reviews]
            self.assertNotIn('repair_origin_not_evidence', first['target_context_not_evidence'])
            context = second['target_context_not_evidence']
            self.assertEqual(context['repair_origin_not_evidence'],
                             {'action': 'memory_save_gap', 'content': original})
            self.assertEqual(context['complete_operation']['arguments']['content'], corrected)
            self.assertEqual(first['shared_submitted_evidence_B'], second['shared_submitted_evidence_B'])
            self.assertIn(audit.REPAIR_GUIDANCE, reviews[1]['system'])
            self.assertEqual(sum(phase == 'citation_repair' for phase, _ in calls), 1)
            self.assertEqual(result.operations[0].success, verdict == 'supported')
            self.assertEqual(agent.last_citation_gate_report['operations'][0]['audit_protocol'], audit.PROTOCOL)
            records = [r for r in agent.review_transport.records if r['phase'] == 'citation_claim_verify_batch']
            self.assertTrue(all(r['audit_protocol'] == audit.PROTOCOL for r in records))
            self.assertNotIn('frozen_inventory', json.dumps(reviews))

    def test_preparation_failure_still_freezes_original_issue(self):
        helper = helpers.SemanticSplitTests()
        helper.setUp()
        self.addCleanup(helper.doCleanups)
        original = 'Review this unresolved question.'
        corrected = 'Review this narrower unresolved question.'
        agent, result, calls = helper._cycle([('memory_save_gap',
            {'content': original, 'evidence': [{'quote': 'not visible'}]})],
            [[corrected], helpers.batch()], repair_limit=1,
            repairs=[{'decision': 'replace', 'content': corrected, 'evidence': [{'quote': TEXT}]}])
        review = next(kw for phase, kw in calls if phase == 'citation_review'
                      and kw['prompt'].startswith('TARGET AND SHARED'))
        context = json.loads(review['prompt'].split('\n', 1)[1])['target_context_not_evidence']
        self.assertEqual(context['repair_origin_not_evidence']['content'], original)
        self.assertTrue(result.operations[0].success)


if __name__ == '__main__':
    unittest.main()
