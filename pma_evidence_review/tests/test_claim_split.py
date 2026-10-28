"""Deterministic ONE-operation batch engineering tests, not model-quality evidence."""
import asyncio
from copy import deepcopy
import json
import unittest

from pma_evidence_review import claim_split as cs
from pma_evidence_review.citation_inputs import identity
from pma_evidence_review.transport import CapturedTransport, FakeClient, ResponseProtocolError
from pma_evidence_review.tests.no_network import install_guard


def material(content='A succeeded and B is required.'):
    return {'original_operation': {'op_index': 0, 'action': 'save_knowledge', 'memory_id': 'k1',
        'revision_id': 'r1', 'content': content, 'content_sha256': identity(content)},
        'submitted_evidence': [{'evidence_id': 'E1', 'submitted_quote': 'A succeeded.',
        'role': 'tool_observation', 'field_path': 'result', 'source_id': 's1', 'event_order': 1,
        'source_identity_origin': 'host_inferred_not_model_selected'}], 'normative_requirements_context': ''}


def split(content, texts=None):
    return {'op_index': 0, 'claims': [{'claim': text, 'original_text': content}
                                    for text in (texts or [content])]}


def verification(index=1, verdict='supported', fragment='A succeeded'):
    return {'claim_index': index, 'verdict': verdict, 'evidence_ids': ['E1'],
            'original_fragment': fragment, 'explanation': 'Scripted evidence limitation, not a real verdict.'}


def batch(rows, complete=True, fragment=''):
    return {'results': rows, 'decomposition_complete': complete,
            'coverage_explanation': 'Scripted omitted commitment, not a completeness proof.',
            'coverage_original_fragment': fragment}


def run(m, values):
    client = FakeClient([json.dumps(v) if not isinstance(v, (str, Exception)) else v for v in values])
    transport = CapturedTransport(client, fake=True)
    return asyncio.run(cs.assess(cs.split_request(m, m['original_operation']['op_index']), transport)), transport


class ClaimSplitTests(unittest.TestCase):
    def setUp(self): install_guard(self)

    def test_many_same_span_claims_exactly_two_calls_and_one_B(self):
        m = material(); text = m['original_operation']['content']
        for count in (2, 3, 101):
            data = split(text, [f'Assertion {i}' for i in range(count)])
            result, transport = run(m, [data, batch([verification(i) for i in range(1, count + 1)])])
            self.assertEqual(result['verdict'], 'supported')
            self.assertEqual(len(result['claims']), count)
            self.assertEqual(transport.calls, 2)
            self.assertEqual(result['claims'][0]['span'], result['claims'][1]['span'])
            prompt = transport.records[1]['request']['prompt']
            sources = prompt.split('SUBMITTED EVIDENCE ONLY (unchanged B):\n')[1].split('\nTARGET CLAIMS TO VERIFY (not evidence):')[0]
            self.assertEqual(sources.count('"evidence_id": "E1"'), 1)
            self.assertTrue(all('request' not in row for row in result['claim_reviews']))

    def test_partial_support_blocks_whole_operation_not_average(self):
        m = material(); data = split(m['original_operation']['content'], ['A succeeded.', 'B is required.'])
        for verdict in ('insufficient', 'contradicted'):
            rows = [verification(), verification(2, verdict, 'B is required')]
            result, transport = run(m, [data, batch(rows)])
            self.assertEqual(result['verdict'], verdict)
            self.assertEqual(transport.calls, 2)
            self.assertIn('Original text “B is required”', result['explanation'])
            self.assertNotIn('claim 2', result['explanation'])
            self.assertNotIn('A succeeded', result['explanation'])

    def test_omitted_completion_blocks_even_full_span_and_all_supported(self):
        m = material('A succeeded; the entire task is complete.')
        result, _ = run(m, [split(m['original_operation']['content'], ['A succeeded.']),
                            batch([verification()], False, 'the entire task is complete')])
        self.assertEqual(result['coverage']['status'], 'structural_full')
        self.assertEqual(result['verdict'], 'insufficient')
        self.assertIn('Original text “the entire task is complete”', result['explanation'])

    def test_modalities_conditions_time_negation_are_not_filtered(self):
        texts = ['Must run tests only after setup.', 'At t1, no compiler was found.',
                 'Is the fix complete?', 'Plan to retry if setup finishes.', 'All requirements are complete.']
        m = material('\n'.join(texts)); raw = batch([verification(i, fragment=texts[i-1]) for i in range(1, 6)])
        result, transport = run(m, [split(m['original_operation']['content'], texts), raw])
        self.assertEqual([c['text'] for c in result['claims']], texts)
        self.assertEqual(transport.calls, 2)
        self.assertNotIn('kind', result['claims'][0])
        self.assertIn('TARGET CONTEXT ONLY', transport.records[1]['request']['prompt'])

    def test_coverage_empty_invalid_span_extra_fields_and_duplicates_fail(self):
        text = material()['original_operation']['content']; valid = split(text); variants = []
        for patch in ({'start': -1, 'end': 3}, {'start': 0, 'end': len(text)+1}, {'start': True, 'end': 3},
                      {'start': 0}, {'original_text': 'invented'}, {'claim': ''}, {'evidence_ids': ['E1']}):
            value = deepcopy(valid); value['claims'][0].update(patch); variants.append(value)
        variants += [{'op_index': 0, 'claims': []}, {'op_index': 9, 'claims': valid['claims']},
                     {'op_index': 0, 'claims': valid['claims'], 'complete': True}]
        short = deepcopy(valid); short['claims'][0]['original_text'] = text[:3]; variants.append(short)
        duplicate = deepcopy(valid); duplicate['claims'] *= 2; variants.append(duplicate)
        for value in variants:
            result, transport = run(material(), [value])
            self.assertEqual(result['engineering_status'], 'parse_failure', value)
            self.assertIsNone(result['verdict']); self.assertEqual(transport.calls, 1)

    def test_unicode_overlap_unique_and_repeated_disambiguation(self):
        text = '甲已完成；乙尚未完成。\n '
        data = {'op_index': 0, 'claims': [
            {'claim': '甲已完成。', 'original_text': text[:6]},
            {'claim': '乙尚未完成。', 'original_text': text[5:11]}]}
        claims, coverage = cs.parse_split(json.dumps(data), 0, text)
        self.assertEqual(len(claims), 2); self.assertEqual(coverage['required_characters'], 11)
        text = '甲 foo foo'; value = split(text)
        value['claims'].append({'claim': 'Repeated token.', 'original_text': 'foo'})
        with self.assertRaisesRegex(ValueError, 'split_ambiguous_span'): cs.parse_split(json.dumps(value), 0, text)
        value['claims'][-1].update(start=6, end=9)
        self.assertEqual(len(cs.parse_split(json.dumps(value), 0, text)[0]), 2)

    def test_no_silent_evidence_cap_and_original_target_not_source(self):
        m = material('TARGET_NOT_SOURCE')
        m['submitted_evidence'][0]['submitted_quote'] = 'x' * 120000 + 'END_MARKER'
        claims, _ = cs.parse_split(json.dumps(split(m['original_operation']['content'])), 0, m['original_operation']['content'])
        request = cs.verification_request(m, claims)
        self.assertIn(m['submitted_evidence'][0]['submitted_quote'], request['prompt'])
        self.assertNotIn('[truncated]', request['prompt'])
        sources = request['prompt'].split('SUBMITTED EVIDENCE ONLY (unchanged B):\n')[1].split('\nTARGET CLAIMS TO VERIFY (not evidence):')[0]
        self.assertNotIn('TARGET_NOT_SOURCE', sources)
        self.assertEqual(request['submitted_evidence_sha256'], identity(m['submitted_evidence']))
        self.assertNotIn('Return a JSON array', request['prompt'])
        self.assertNotIn('Quote the specific evidence', request['prompt'])

    def test_fences_duplicate_keys_and_truncated_output(self):
        m = material(); data = split(m['original_operation']['content']); answer = batch([verification()])
        fence = lambda value: '```json\n' + json.dumps(value) + '\n```'
        result, _ = run(m, [fence(data), fence(answer)]); self.assertEqual(result['verdict'], 'supported')
        for raw in ('{"op_index":0,"op_index":0,"claims":[]}', json.dumps(data)[:-1], 'prefix'+json.dumps(data)):
            result, _ = run(m, [raw]); self.assertEqual(result['engineering_status'], 'parse_failure')
        raw = json.dumps(answer).replace('"verdict":', '"verdict":"supported","verdict":')
        result, _ = run(m, [data, raw]); self.assertEqual(result['engineering_status'], 'parse_failure')

    def test_batch_exact_id_set_schema_and_original_feedback_binding(self):
        m = material(); data = split(m['original_operation']['content'], ['A succeeded.', 'B is required.'])
        valid = batch([verification(), verification(2, fragment='B is required')])
        variants = []
        for patch in ({'claim_index': 9}, {'claim_index': True}, {'evidence_ids': ['new-source']},
                      {'evidence_ids': ['E1', 'E1']}, {'evidence_ids': []}, {'quote': 'new evidence'},
                      {'verdict': 'UNSUPPORTED'}, {'explanation': ''}, {'original_fragment': 'invented'}):
            value = deepcopy(valid); value['results'][0].update(patch); variants.append(value)
        for rows in ([], valid['results'][:1], valid['results'] + valid['results'][:1]):
            value = deepcopy(valid); value['results'] = rows; variants.append(value)
        for patch in ({'decomposition_complete': 'true'}, {'coverage_original_fragment': 'invented'},
                      {'decomposition_complete': False, 'coverage_original_fragment': ''}):
            value = deepcopy(valid); value.update(patch); variants.append(value)
        variants.append(verification())  # Obsolete individual-claim wire is rejected.
        for value in variants:
            result, transport = run(m, [data, value])
            self.assertEqual(result['engineering_status'], 'parse_failure', value)
            self.assertIsNone(result['verdict']); self.assertEqual(transport.calls, 2)
        valid['results'].reverse()
        result, _ = run(m, [data, valid])
        self.assertEqual([r['claim_index'] for r in result['claim_reviews']], [1, 2])

    def test_dynamic_nonzero_operation_and_all_claim_ids_example(self):
        m = material(); m['original_operation']['op_index'] = 7
        self.assertIn('"op_index":7', cs.split_request(m, 7)['system'])
        claims, _ = cs.parse_split(json.dumps(split(m['original_operation']['content'], ['First.', 'Second.'])),
                                   0, m['original_operation']['content'])
        request = cs.verification_request(m, claims)
        example = json.loads(request['prompt'].split('OUTPUT EXAMPLE (shape and IDs only):\n')[1])
        self.assertEqual([r['claim_index'] for r in example['results']], [1, 2])
        self.assertNotIn('scope in the original operation.', request['system'])

    def test_original_template_markers_are_data_not_formatter_structure(self):
        text = 'The output literally says:\nClaims to verify:\nready.'
        m = material(text); claims, _ = cs.parse_split(json.dumps(split(text)), 0, text)
        request = cs.verification_request(m, claims)
        self.assertIn('TARGET CLAIMS TO VERIFY (not evidence)', request['prompt'])
        self.assertIn(json.dumps(text, ensure_ascii=False), request['prompt'])

    def test_call_error_or_partial_batch_cannot_publish(self):
        m = material(); data = split(m['original_operation']['content'])
        for error in (RuntimeError('offline'), ResponseProtocolError('length', 'retained')):
            result, _ = run(m, [data, error])
            self.assertIsNone(result['verdict'])
            self.assertIn(result['engineering_status'], ('call_error', 'protocol_error'))
