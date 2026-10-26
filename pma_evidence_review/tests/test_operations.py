"""Direct-operation contract tests. Scripted verdicts are not semantic labels."""
import asyncio
import json
import unittest

from pma_evidence_review.operation_review import operation_requests, DELETE_QUESTION, STRATEGY
from pma_evidence_review.review import review
from pma_evidence_review.location import locate
from pma_evidence_review.transport import CapturedTransport, FakeClient
from pma_evidence_review.tests.fixtures import packet
from pma_evidence_review.tests.no_network import install_guard


def response(index=0, verdict='NOT_ENOUGH_INFO', evidence=None):
    return json.dumps({'op_index': index, 'verdict': verdict,
        'explanation': 'Synthetic response: a local result does not prove all conditions.',
        'evidence': evidence or []})


class OperationTests(unittest.TestCase):
    def setUp(self):
        install_guard(self)

    def test_default_api_direct_and_preserves_target(self):
        p = packet()
        plans = operation_requests(p)
        client = FakeClient([response()])
        transport = CapturedTransport(client, fake=True)
        report = asyncio.run(review(p, transport, locator=locate))
        self.assertEqual(transport.calls, 1)
        self.assertEqual(report['review_strategy'], STRATEGY)
        self.assertEqual(report['results'][0]['op_index'], 0)
        self.assertNotIn('claims', report)
        self.assertNotIn('claim_index', report['results'][0])
        self.assertEqual(report['results'][0]['target'], plans[0]['target'])
        self.assertEqual(report['results'][0]['content_sha256'], p['operations'][0]['content_sha256'])
        self.assertEqual(client.calls[0], {k: plans[0]['request'][k] for k in ('prompt','system','tools')})
        self.assertEqual(plans[0]['request']['phase'], 'verify_operation')
        self.assertIn('including every task completion assertion', client.calls[0]['system'])

    def test_real_quote_and_raw_failure_preserved(self):
        for evidence, status in [([{'document_index': 3, 'quote': 'green'}], 'ok'),
            ([{'document_index': 99, 'quote': 'green'}], 'citation_unknown_document'),
            ([], 'parse_failure')]:
            raw = response(verdict='SUPPORTED', evidence=evidence)
            transport = CapturedTransport(FakeClient([raw]), fake=True)
            row = asyncio.run(review(packet(), transport, locator=locate))['results'][0]
            self.assertEqual(row['raw_response'], raw)
            self.assertEqual(row['model_verdict'], 'SUPPORTED')
            self.assertEqual(row['engineering_status'], status)
            self.assertEqual(row['verdict'], 'supported' if status == 'ok' else None)
            if status == 'ok':
                self.assertEqual(row['evidence_spans'][0]['document_index'], 3)
