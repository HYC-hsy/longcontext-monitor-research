"""Scripted protocol tests; no semantic model-effect claim."""
import asyncio
from copy import deepcopy
import json
import unittest

from pma_evidence_review import claim_split_simple as cs
from pma_evidence_review.tests.test_claim_split import material
from pma_evidence_review.tests.no_network import install_guard
from pma_evidence_review.transport import CapturedTransport, FakeClient


def decision(verdict='supported'):
    return {'verdict': verdict, 'reason': 'Scripted judgment only.'}


def batch(count=1, overall='supported'):
    return {'overall': decision(overall), 'results': [decision() for _ in range(count)]}


def run(values, content='Step 1: A succeeded. Success criteria: task completed.'):
    m = material(content)
    transport = CapturedTransport(FakeClient([json.dumps(v) for v in values]), fake=True)
    result = asyncio.run(cs.assess(cs.split_request(m, 0), transport))
    return m, result, transport


class SimpleSplitTests(unittest.TestCase):
    def setUp(self): install_guard(self)

    def test_ordered_strings_no_span_or_id_contract(self):
        claims = ['A succeeded.', 'Task completed.']
        m, result, transport = run([claims, batch(2)])
        self.assertEqual(result['verdict'], 'supported')
        self.assertEqual(result['claims'], claims)
        self.assertEqual(transport.calls, 2)
        feedback = result['repair_feedback']
        self.assertEqual(feedback['original_operation'], m['original_operation'])
        self.assertEqual(feedback['submitted_evidence'], m['submitted_evidence'])
        self.assertEqual([r['claim'] for r in feedback['claims']], claims)
        self.assertNotIn('uncovered_original_spans', transport.records[1]['request']['prompt'])
        self.assertNotIn('claim_index', transport.records[1]['request']['prompt'])
        self.assertIn(cs.SUPPORT_SENTENCE, transport.records[1]['request']['system'])

    def test_omitted_completion_not_approved_by_supported_subset(self):
        _, result, _ = run([['A succeeded.'], batch(overall='insufficient')])
        self.assertEqual(result['verdict'], 'insufficient')
        value = batch(); value['results'][0] = decision('contradicted')
        _, result, _ = run([['A succeeded.'], value])
        self.assertEqual(result['verdict'], 'contradicted')

    def test_types_cardinality_and_nonempty_are_strict(self):
        for value in ([], {}, [''], ['  '], [False], [{'claim': 'x'}]):
            with self.subTest(value=value), self.assertRaises(ValueError):
                cs.parse_split(json.dumps(value))
        for mutate in (lambda d: d['results'].clear(),
                       lambda d: d['results'].append(decision()),
                       lambda d: d['results'][0].update(claim_index=1),
                       lambda d: d['results'][0].update(evidence_ids=['E1']),
                       lambda d: d['results'][0].update(reason=' '),
                       lambda d: d['overall'].update(verdict=True),
                       lambda d: d['overall'].update(reason=None)):
            value = batch(); mutate(value)
            with self.assertRaises(ValueError): cs.parse_batch(json.dumps(value), ['x'])

    def test_no_claim_cap_or_punctuation_normalization(self):
        claims = ['x < 3', 'x > 3'] + [f'Claim {i}' for i in range(101)]
        _, result, transport = run([claims, batch(len(claims))])
        self.assertEqual(result['claims'], claims)
        self.assertEqual(len(result['claim_reviews']), 103)
        self.assertEqual(transport.calls, 2)

    def test_split_failure_does_not_call_review(self):
        _, result, transport = run([{'claims': ['x']}])
        self.assertEqual(result['engineering_status'], 'parse_failure')
        self.assertEqual(transport.calls, 1)

    def test_frozen_material_and_uncut_evidence(self):
        m = material(); m['submitted_evidence'][0]['submitted_quote'] = 'x' * 110000
        request = cs.split_request(m, 0)
        m['submitted_evidence'][0]['submitted_quote'] = 'mutated'
        prompt = cs.verification_request(request['closed_material'], ['x'])['prompt']
        self.assertIn('x' * 110000, prompt)
        self.assertNotIn('mutated', prompt)

    def test_cancel_propagates(self):
        class Cancel:
            async def send(self, request): raise asyncio.CancelledError()
        with self.assertRaises(asyncio.CancelledError):
            asyncio.run(cs.assess(cs.split_request(material(), 0), Cancel()))

    def test_truncated_valid_json_is_not_accepted(self):
        class Truncated:
            async def call(self, **kwargs):
                return type('Response', (), {'content': '["x"]', 'tool_calls': [],
                                              'finish_reason': 'length'})()
        transport = CapturedTransport(Truncated(), fake=True)
        result = asyncio.run(cs.assess(cs.split_request(material(), 0), transport))
        self.assertEqual(result['engineering_status'], 'protocol_error')
        self.assertEqual(result['split']['reason'], 'truncated_response')
        self.assertEqual(transport.calls, 1)
