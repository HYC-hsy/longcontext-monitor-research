"""Affected production path only: one batch, host action, mapping and publication."""
import asyncio
import json
import unittest

from pma_evidence_review import claim_split_semantic as v4
from pma_evidence_review import operation_audit
from pma_evidence_review.tests import test_claim_split_semantic as old_tests
from pma_evidence_review.tests.test_live_gate import LatestEvidenceGapMemory, TEXT
from pma_evidence_review.transport import CapturedTransport, FakeClient


class OperationAuditIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.helper = old_tests.SemanticSplitTests()
        self.helper.setUp()

    def test_single_shared_batch_and_failed_child_explanation(self):
        material = old_tests.material('The local command worked; all sessions can use it.')
        request = v4.split_request(material, 0)
        request['audit_operation_kind'] = 'save'
        request['audit_before_entry'] = None
        answer = [['O', 'supported', 'Local run observed.'],
                  ['C1', 'insufficient', 'Only one shell shown; another process could test scope.']]
        transport = CapturedTransport(FakeClient([
            json.dumps(['The local command worked; all sessions can use it.']),
            json.dumps(answer)]), fake=True)
        result = asyncio.run(v4.assess(request, transport))
        self.assertEqual(transport.calls, 2)
        self.assertEqual([x['phase'] for x in transport.records],
                         ['citation_claim_split', 'citation_claim_verify_batch'])
        self.assertEqual(result['engineering_status'], 'ok')
        self.assertEqual(result['model_verdict'], 'supported')
        self.assertEqual(result['verdict'], 'insufficient')
        self.assertIn('Only one shell shown', result['explanation'])
        self.assertEqual(result['batch']['request']['audit_request_sha256'],
                         transport.records[1]['audit_request_sha256'])
        self.assertEqual(result['batch']['raw_response'], json.dumps(answer))
        prompt = transport.records[1]['request']['prompt']
        self.assertIn('shared_submitted_evidence_B', prompt)
        self.assertIn('A succeeded.', prompt)
        self.assertNotIn('source_id', prompt)
        self.assertNotIn('A succeeded.', transport.records[0]['request']['prompt'])

    def test_host_explicit_new_vs_update_not_before_guess(self):
        for update in (False, True):
            with self.subTest(update=update):
                bank = LatestEvidenceGapMemory()
                args = {'content': 'New statement.', 'evidence': [{'quote': TEXT}]}
                if update:
                    key = bank.save_knowledge('Old statement.')
                    args['memory_id'] = key
                agent, result, requests = self.helper._cycle(
                    [('memory_save_knowledge', args)],
                    [['New statement.'], old_tests.batch()], bank=bank)
                self.assertTrue(result.operations[0].success, agent.last_citation_gate_report)
                batch_prompt = [kw['prompt'] for phase, kw in requests
                                if phase == 'citation_review'][-1]
                visible = json.loads(batch_prompt.split('\n', 1)[1])
                context = visible['target_context_not_evidence']
                self.assertEqual(context['complete_operation']['action'],
                                 'update' if update else 'save')
                self.assertEqual(context['before_entry_available'], update)
                if update:
                    self.assertEqual(context['before_entry']['content'], 'Old statement.')

    def test_delete_target_and_parse_failure_preserve_gap(self):
        bank = LatestEvidenceGapMemory()
        key = bank.save_gap('Tool must work in an independent process.')
        args = {'memory_id': key, 'reason': 'Gap resolved.',
                'evidence': [{'quote': TEXT}]}
        agent, result, requests = self.helper._cycle(
            [('memory_delete', args)], [['Gap resolved.'], {'bad': 'schema'}], bank=bank)
        self.assertFalse(result.operations[0].success)
        self.assertEqual(bank.entries[0].id, key)
        attempt = agent.last_citation_gate_report['operations'][0]['attempts'][0]
        self.assertEqual(attempt['engineering_status'], 'parse_failure')
        self.assertIsNone(attempt['verdict'])
        batch_prompt = [kw['prompt'] for phase, kw in requests
                        if phase == 'citation_review'][-1]
        context = json.loads(batch_prompt.split('\n', 1)[1])['target_context_not_evidence']
        self.assertEqual(context['complete_operation']['action'], 'delete')
        self.assertEqual(context['before_entry']['content'],
                         'Tool must work in an independent process.')

    def test_phase1_and_split_prompts_frozen(self):
        import hashlib
        from pma_evidence_review.claim_split_semantic import SPLIT_SYSTEM
        self.assertEqual(hashlib.sha256(SPLIT_SYSTEM.encode()).hexdigest(),
                         'b57be62604b515cd1659a989acc228740d47dd6f53dab1fd458e3349fce7602b')
        self.assertIn('4. Give O one concise audit basis',
                      operation_audit.system_for(operation_audit.prepare(
                          'r', {'action': 'save', 'arguments': {'content': 'x'}}, None,
                          ['x'], [])))

    def test_frozen_replay_plan_excludes_labels_and_reuses_one_b(self):
        from pma_evidence_review.operation_audit_delivery.replay_three import prepared_cases
        cases = prepared_cases()
        self.assertEqual(len(cases), 3)
        self.assertEqual(len({json.dumps(case['material']['submitted_evidence'], sort_keys=True)
                              for case in cases}), 1)
        for case in cases:
            prompt = case['model_request']['prompt']
            self.assertNotIn('reference_verdict', prompt)
            self.assertNotIn('reference_reason', prompt)
            self.assertNotIn('source_id', prompt)
            self.assertEqual(case['model_request']['phase'], 'citation_claim_verify_batch')


if __name__ == '__main__':
    unittest.main()
