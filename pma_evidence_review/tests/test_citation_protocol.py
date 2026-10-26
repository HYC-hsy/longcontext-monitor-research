"""Wire-contract regressions; scripted output does not prove entailment."""
import asyncio
import json
import unittest

from pma_evidence_review import evidence_policy as policy
from pma_evidence_review.location import locate
from pma_evidence_review.review import parse_claims, parse_results, verification_requests, review
from pma_evidence_review.tests.fixtures import packet, extraction
from pma_evidence_review.tests.no_network import install_guard
from pma_evidence_review.transport import CapturedTransport, FakeClient


def output(evidence, verdict='SUPPORTED', **extra):
    return json.dumps(dict(verdict=verdict, evidence=evidence, explanation='Scripted only.', **extra))


class CitationProtocolTests(unittest.TestCase):
    def setUp(self):
        install_guard(self)
        self.p = packet()
        self.claims, self.meta, _, _ = parse_claims(extraction(), self.p)

    def run_output(self, evidence, verdict='SUPPORTED', **extra):
        transport = CapturedTransport(FakeClient([extraction(), output(evidence, verdict, **extra)]), fake=True)
        return asyncio.run(review(self.p, transport, locator=locate))['results'][0]

    def observation_index(self):
        docs = policy.documents(self.p, 'execution')
        return next(i for i, doc in enumerate(docs, 1) if doc['role'] == 'tool_observation')

    def test_display_schema_one_based_both_modes(self):
        for mode in ('evidence-first', 'batch'):
            req = verification_requests(self.p, self.claims, self.meta, mode)[0][1]
            for i, doc in enumerate(req['citation_registry'], 1):
                self.assertIn('Document %d:' % i, req['prompt'])
            self.assertNotIn('zero-based', req['prompt'])
            self.assertNotIn('FIRST evidence', req['prompt'])
            self.assertIn('one-based', req['prompt'])
            self.assertIn('"quote":', req['prompt'])
            self.assertEqual(req['evidence_policy'], 'source-use-v3')

    def test_single_multiple_and_negative_verdict(self):
        index = self.observation_index()
        for evidence in ([{'document_index': index, 'quote': 'green'}],
                         [{'document_index': index, 'quote': q} for q in ('gr', 'een')]):
            for verdict in ('SUPPORTED', 'CONTRADICTED'):
                row = self.run_output(evidence, verdict)
                self.assertEqual(row['engineering_status'], 'ok')
                self.assertEqual(row['verdict'], verdict.lower())
                self.assertEqual(row['evidence'], [q['quote'] for q in evidence])
                self.assertFalse(row['alignment']['semantic_proof'])
                self.assertEqual(row['alignment']['citations'][0]['role'], 'tool_observation')

    def test_empty_insufficient_and_legacy_rejected(self):
        self.assertEqual(self.run_output([], 'NOT_ENOUGH_INFO')['verdict'], 'insufficient')
        self.assertEqual(self.run_output([])['engineering_status'], 'parse_failure')
        for old in ({'document_index': 0}, {'citations': []}):
            row = self.run_output(['green'], **old)
            self.assertEqual(row['reason'], 'legacy_citation_protocol')
        self.assertEqual(self.run_output(['green'])['reason'], 'invalid_evidence')

    def test_indices_and_exact_visible_offsets(self):
        index = self.observation_index()
        for invalid in (0, -1, 999, True, '1'):
            row = self.run_output([{'document_index': invalid, 'quote': 'green'}])
            self.assertIsNone(row['verdict'])
        for extra in ({'start': -1, 'end': 5}, {'start': 0}, {'start': 0, 'end': 6}):
            row = self.run_output([dict(document_index=index, quote='green', **extra)])
            self.assertEqual(row['engineering_status'], 'citation_outside_visible_range')
        row = self.run_output([{'document_index': index, 'quote': 'future'}])
        self.assertEqual(row['engineering_status'], 'citation_ambiguous_or_unmatched')

    def test_duplicate_source_and_duplicate_document_rejected(self):
        self.p['sources'].append(self.p['sources'][0])
        with self.assertRaisesRegex(ValueError, 'citation_duplicate_source_id'):
            policy.documents(self.p, 'execution')
        self.p['sources'].pop()
        source = next(s for s in self.p['sources'] if s['role'] == 'tool_observation')
        source['slices'] *= 2
        with self.assertRaisesRegex(ValueError, 'citation_duplicate_document'):
            policy.documents(self.p, 'execution')

    def test_overlapping_matches_require_explicit_offsets(self):
        source = next(s for s in self.p['sources'] if s['role'] == 'tool_observation')
        source['slices'] = [{'start': 10, 'end': 13, 'text': 'aaa'}]
        docs = policy.documents(self.p, 'execution')
        index = next(i for i, d in enumerate(docs, 1) if d['role'] == 'tool_observation')
        row = {'evidence': ['aa'], 'citations': [{'document_index': index}]}
        with self.assertRaisesRegex(ValueError, 'citation_ambiguous_or_unmatched'):
            policy.bind(row, self.p, docs, 'execution', locate)
        row['citations'][0].update(start=11, end=13)
        bound = policy.bind(row, self.p, docs, 'execution', locate)
        self.assertEqual(bound['citations'][0]['start'], 11)
