"""Wire-contract regressions; scripted output does not prove entailment."""
import asyncio
import json
import hashlib
from pathlib import Path
import zipfile
import unittest

from pma_evidence_review import evidence_policy as policy
from pma_evidence_review.location import locate
from pma_evidence_review.review import parse_claims, parse_results, verification_requests, legacy_review as review
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
        for extra in ({'start': -1, 'end': 5}, {'start': 0}, {'start': None}, {'end': None},
                      {'start': None, 'end': None}, {'start': 0, 'end': 6}):
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

    def test_mixed_roles_same_quote_keep_selected_provenance(self):
        for source in self.p['sources']:
            source['slices'] = [{'start': 0, 'end': 5, 'text': 'green'}]
        docs = policy.documents(self.p, 'agent_statement')
        roles = []
        for index in range(1, len(docs) + 1):
            bound = policy.bind({'evidence': ['green'], 'citations': [
                {'document_index': index}]}, self.p, docs, 'agent_statement', locate)
            roles.append(bound['citations'][0]['role'])
        self.assertEqual(roles, [s['role'] for s in self.p['sources']])
        self.assertGreater(len(set(roles)), 1)

    def test_correct_single_quote_command_echo_is_bound_not_execution_proof(self):
        docs = policy.documents(self.p, 'execution')
        index = next(i for i, d in enumerate(docs, 1) if d['role'] == 'tool_command')
        row = self.run_output([{'document_index': index, 'quote': docs[index-1]['text']}],
                              'NOT_ENOUGH_INFO')
        self.assertEqual(row['engineering_status'], 'ok')
        self.assertEqual(row['verdict'], 'insufficient')
        self.assertEqual(row['alignment']['citations'][0]['role'], 'tool_command')
        self.assertFalse(row['alignment']['semantic_proof'])

    def test_frozen_v21_legacy_responses_not_rewritten(self):
        path = Path(__file__).resolve().parents[1] / 'diagnostic_packages' / (
            'PMA_AUDITOR_V21_SQLITE_DIAGNOSTIC_20261026.zip')
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(before, 'd9cdb4dc0fc2c1c5a62903e42f517f9e8ff73aad4c03222aa171cde06143a436')
        with zipfile.ZipFile(path) as archive:
            p = json.loads(archive.read('sqlite/input.json'))
            self.assertEqual(p['review_input_sha256'],
                '0aa854b8a7c7eb98ae5e412cdf78180597ca3400e0884046db397e9e4c2cdb90')
            old = [json.loads(line) for line in archive.read('sqlite/responses.jsonl').splitlines()]
            claims, meta, _, _ = parse_claims(old[0]['response'], p)
            requests = verification_requests(p, claims, meta)
            self.assertEqual(len(requests), 14)
            for (group, req), response in zip(requests, old[1:]):
                with self.assertRaisesRegex(ValueError, 'legacy_citation_protocol'):
                    parse_results(response['response'], group)
                roles = {d['role'] for d in req['citation_registry']}
                self.assertTrue({'task_instruction', 'tool_command', 'tool_observation'} <= roles)
                self.assertNotIn('zero-based', req['prompt'])
                context = json.loads(req['prompt'].split(
                    'INTERPRETIVE CONTEXT (not evidence):\n')[1])
                self.assertEqual(context['visible_source_context_not_independent_evidence'], p['sources'])
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)

    def test_build_directory_context_does_not_invent_movement(self):
        # Scripted transport checks preservation, not whether a model reasons correctly.
        from pma_evidence_review.inputs import build_from_data, digest
        from pma_evidence_review.tests.fixtures import bundle
        args = bundle()
        command = 'mkdir -p build; cd build && make; pwd'
        receipt = '/workspace/project/build\nbuild complete'
        prompt = args[0][0]['prompt'].replace('export PATH=/tool:$PATH; tool', command).replace('green', receipt)
        args[0][0]['prompt'] = prompt
        manifest = args[3]['gap_evidence']['manifests']['c1']
        manifest['request_sha256'] = digest(prompt)
        manifest['visible_spans'][1] = [[0, len(command)]]
        manifest['visible_spans'][2] = [[0, len(receipt)]]
        manifest['visibility_refs'] = [digest(json.dumps(['c1', digest(prompt), sid, spans],
            ensure_ascii=False, separators=(',', ':'))) for sid, spans in zip(
                manifest['ordered_source_refs'], manifest['visible_spans'])]
        p = build_from_data(*args, step=1, cycle_id='c1')
        ext = json.loads(extraction())
        ext['claims'][0]['claim'] = 'The executable was moved to the parent directory.'
        evidence = [{'document_index': 2, 'quote': command},
                    {'document_index': 3, 'quote': receipt}]
        for quotes in (evidence, []):
            client = FakeClient([json.dumps(ext), output(quotes, 'NOT_ENOUGH_INFO')])
            report = asyncio.run(review(p, CapturedTransport(client, fake=True), locator=locate))
            row = report['results'][0]
            self.assertEqual(row['verdict'], 'insufficient')
            self.assertEqual(row['engineering_status'], 'ok')
            self.assertFalse(report['memory_mutated'])
            prompt = client.calls[1]['prompt']
            self.assertIn(command, prompt)
            self.assertIn(receipt.replace('\n', '\\n'), prompt)
            self.assertNotIn('mv ', prompt)
            self.assertNotIn('cp ', prompt)
        # The host must NOT invent a semantic override either: binding is not a judge.
        client = FakeClient([json.dumps(ext), output(evidence)])
        row = asyncio.run(review(p, CapturedTransport(client, fake=True), locator=locate))['results'][0]
        self.assertEqual(row['verdict'], 'supported')
        self.assertFalse(row['alignment']['semantic_proof'])

    def test_no_scope_classification_in_new_requests(self):
        from pma_evidence_review.review import extraction_request
        self.assertNotIn('evidence_scope', extraction_request(self.p)['prompt'])
        self.assertNotIn('evidence_scope', self.meta[1])
        for label in (None, 'agent_statement', 'requirement', 'unknown_legacy_label'):
            meta = {i: dict(m) for i, m in self.meta.items()}
            if label is not None:
                meta[1]['evidence_scope'] = label
            req = verification_requests(self.p, self.claims, meta)[0][1]
            self.assertNotIn('evidence_scope', req['prompt'])
            self.assertNotIn('scope_origin', req['prompt'])
            self.assertEqual(len(req['citation_registry']), len(self.p['sources']))
