"""Final payload tests with scripted responses; no semantic gold or network calls."""
import asyncio
import copy
import hashlib
import json
from pathlib import Path
import unittest
import zipfile

from pma_evidence_review import evidence_policy as policy
from pma_evidence_review.inputs import validate, build_from_data, digest
from pma_evidence_review.location import locate
from pma_evidence_review.review import extraction_request, parse_claims, verification_requests, review
from pma_evidence_review.transport import CapturedTransport, FakeClient
from pma_evidence_review.tests.fixtures import packet, extraction, result, bundle
from pma_evidence_review.tests.no_network import install_guard


class SourceBoundaryTests(unittest.TestCase):
    def setUp(self):
        install_guard(self)

    def extracted(self, scope='execution', two=False):
        data = json.loads(extraction(two))
        for claim in data['claims']:
            claim['evidence_scope'] = scope
        return json.dumps(data)

    def request(self, scope='execution', mode='evidence-first'):
        p = packet()
        claims, meta, _, _ = parse_claims(self.extracted(scope), p)
        return verification_requests(p, claims, meta, mode)[0][1]

    def run_fake(self, output, scope='execution'):
        client = FakeClient([self.extracted(scope), json.dumps(output)])
        transport = CapturedTransport(client, fake=True)
        report = asyncio.run(review(packet(), transport, locator=locate))
        self.assertEqual(transport.calls, 2)
        self.assertEqual(client.calls[1], transport.records[1]['request'])
        identity = hashlib.sha256(json.dumps(client.calls[1], ensure_ascii=False,
            sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        self.assertEqual(identity, report['audit_request_sha256s'][1])
        self.assertEqual(identity, transport.records[1]['audit_request_sha256'])
        return report['results'][0]

    def test_final_extraction_targets_only_operations(self):
        p = packet()
        prompt = extraction_request(p)['prompt']
        targets, context = prompt.split('INTERPRETIVE CONTEXT (not targets):')
        self.assertIn(p['operations'][0]['content'], targets)
        self.assertNotIn('Build the tool.', targets)
        self.assertNotIn('export PATH=', prompt)
        self.assertNotIn('maintenance_prompt', prompt)
        self.assertIn('Build the tool.', context)

    def test_final_verify_partition_both_modes(self):
        for mode in ('evidence-first', 'batch'):
            req = self.request(mode=mode)
            documents = req['prompt'].split('Source Documents:\n')[1].split('\nClaim')[0]
            self.assertIn('green', documents)
            self.assertNotIn(packet()['operations'][0]['content'], documents)
            self.assertIn('Build the tool.', documents)
            self.assertIn('Need to check the tool.', documents)
            self.assertIn('export PATH=', documents)
            self.assertNotIn('maintenance_prompt', req['prompt'])
            self.assertIn('audit_target_not_evidence', req['prompt'])
            self.assertEqual([d['role'] for d in req['citation_registry']],
                             [s['role'] for s in packet()['sources']])

    def test_role_use_projection_retains_commands_and_context(self):
        for scope, role, text in [('attempt', 'tool_command', 'export PATH='),
            ('static_behavior', 'tool_command', 'export PATH='),
            ('requirement', 'task_instruction', 'Build the tool.'),
            ('historical_record', 'memory_derived', 'Need to check the tool.')]:
            req = self.request(scope)
            self.assertIn(role, [d['role'] for d in req['citation_registry']])
            self.assertIn(text, req['prompt'].split('Source Documents:\n')[1].split('\nClaim')[0])

    def test_receipt_positive_and_self_reference_rejected(self):
        output = json.loads(result('SUPPORTED', ['green'], document_index=3))
        self.assertEqual(self.run_fake(output)['verdict'], 'supported')
        output['evidence'][0]['quote'] = packet()['operations'][0]['content']
        row = self.run_fake(output)
        self.assertIsNone(row['verdict'])
        self.assertEqual(row['engineering_status'], 'citation_ambiguous_or_unmatched')

    def test_roles_are_provenance_not_semantic_proof(self):
        # Scripted support is retained as a MODEL verdict, not host semantic proof.
        for index, quote, role in [(1, 'Build the tool.', 'task_instruction'),
                (4, 'Need to check the tool.', 'memory_derived')]:
            row = self.run_fake(json.loads(result('SUPPORTED', [quote], document_index=index)))
            self.assertEqual(row['engineering_status'], 'ok')
            self.assertEqual(row['alignment']['citations'][0]['role'], role)
            self.assertFalse(row['alignment']['semantic_proof'])
        self.assertIn('Never use\nrequirements or historical records as execution observations',
                      self.request()['prompt'])

    def test_missing_identity_empty_evidence_and_multiple_quotes(self):
        invalid = json.loads(result('SUPPORTED', ['green']))
        del invalid['evidence'][0]['document_index']
        for output in [invalid, json.loads(result('SUPPORTED'))]:
            row = self.run_fake(output)
            self.assertEqual(row['engineering_status'], 'parse_failure')
            self.assertIsNone(row['verdict'])
        row = self.run_fake(json.loads(result('SUPPORTED', ['green', 'green'])))
        self.assertEqual(row['engineering_status'], 'ok')
        self.assertEqual(len(row['alignment']['citations']), 2)

    def test_identity_role_range_and_text_failures(self):
        for fields, expected in [({'document_index': 99}, 'citation_unknown_document'),
                ({'start': -1, 'end': 5}, 'citation_outside_visible_range'),
                ({'start': 0, 'end': 4}, 'citation_text_mismatch')]:
            quote = dict(document_index=3, quote='green')
            quote.update(fields)
            row = self.run_fake(json.loads(result('SUPPORTED', [quote])))
            self.assertEqual(row['engineering_status'], expected)
            self.assertIsNone(row['verdict'])
        # The wire cannot override host-owned provenance.
        quote = dict(document_index=3, quote='green', role='task_instruction')
        self.assertEqual(self.run_fake(json.loads(result('SUPPORTED', [quote])))[
            'engineering_status'], 'parse_failure')

    def test_same_text_identity_not_string_exclusion(self):
        # Policy unit projection: identical content is not intrinsically self-reference.
        p = packet()
        text = p['operations'][0]['content']
        for source in p['sources']:
            source['slices'] = [{'start': 0, 'end': len(text), 'text': text}]
        registry = policy.documents(p, 'execution')
        self.assertEqual(len(registry), 4)
        row = {'evidence': [text], 'citations': [{'document_index': 3}]}
        self.assertEqual(policy.bind(row, p, registry, 'execution', locate)['status'], 'exact_unique')
        with self.assertRaisesRegex(ValueError, 'citation_count_mismatch'):
            policy.bind({'evidence': [text]}, p, registry, 'execution', locate)
        # No search can rescue an explicitly wrong source identity.
        row['citations'] = [{'document_index': 3, 'source_id': p['sources'][0]['source_id']}]
        with self.assertRaisesRegex(ValueError, 'citation_wrong_source_id'):
            policy.bind(row, p, registry, 'execution', locate)

    def test_static_code_and_file_creation_receipt(self):
        p = packet()
        command, observation = p['sources'][1:3]
        code = 'def add(a, b): return a + b'
        receipt = 'File created successfully'
        command['slices'] = [{'start': 10, 'end': 10+len(code), 'text': code}]
        observation['slices'] = [{'start': 0, 'end': len(receipt), 'text': receipt}]
        for scope, quote in [('static_behavior', code), ('execution', receipt)]:
            registry = policy.documents(p, scope)
            index = next(i for i, doc in enumerate(registry, 1) if doc['text'] == quote)
            row = {'evidence': [quote], 'citations': [{'document_index': index}]}
            self.assertEqual(policy.bind(row, p, registry, scope, locate)['status'], 'exact_unique')
        # Available command text does not change its provenance to observation.
        self.assertEqual(policy.documents(p, 'execution')[1]['role'], 'tool_command')

    def test_static_and_creation_full_fake_requests(self):
        args = bundle()
        prompt = args[0][0]['prompt'].replace('export PATH=/tool:$PATH; tool',
            'def add(a, b): return a + b').replace('green', 'File created successfully')
        args[0][0]['prompt'] = prompt
        manifest = args[3]['gap_evidence']['manifests']['c1']
        manifest['request_sha256'] = digest(prompt)
        manifest['visible_spans'][1] = [[0, len('def add(a, b): return a + b')]]
        manifest['visible_spans'][2] = [[0, len('File created successfully')]]
        manifest['visibility_refs'] = [digest(json.dumps(['c1', digest(prompt), sid, spans],
            ensure_ascii=False, separators=(',', ':'))) for sid, spans in zip(
                manifest['ordered_source_refs'], manifest['visible_spans'])]
        p = build_from_data(*args, step=1, cycle_id='c1')
        for scope, quote in [('static_behavior', 'def add(a, b): return a + b'),
                             ('execution', 'File created successfully')]:
            ext = json.loads(self.extracted(scope))
            ext['claims'][0]['claim'] = ('The function returns the sum of its arguments'
                if scope == 'static_behavior' else 'A file was created')
            client = FakeClient([json.dumps(ext), result('SUPPORTED', [quote],
                document_index=2 if scope == 'static_behavior' else 3)])
            transport = CapturedTransport(client, fake=True)
            report = asyncio.run(review(p, transport, locator=locate))
            self.assertEqual(report['results'][0]['engineering_status'], 'ok')
            self.assertIn(quote, client.calls[1]['prompt'].split('Source Documents:\n')[1].split('\nClaim')[0])

    def test_execution_retains_original_command_and_receipt_context(self):
        req = self.request('execution')
        context = json.loads(req['prompt'].split('INTERPRETIVE CONTEXT (not evidence):\n')[1])
        sources = context['visible_source_context_not_independent_evidence']
        self.assertEqual(sources, packet()['sources'])
        self.assertIn('export PATH=/tool:$PATH; tool', req['prompt'])
        self.assertEqual([d['text'] for d in req['citation_registry']],
                         [part['text'] for source in packet()['sources'] for part in source['slices']])
        row = self.run_fake(json.loads(result('SUPPORTED',
            ['export PATH=/tool:$PATH; tool'], document_index=3)))
        self.assertIsNone(row['verdict'])
        self.assertEqual(row['engineering_status'], 'citation_ambiguous_or_unmatched')
        for scope in policy.SCOPES:
            context = json.loads(self.request(scope)['prompt'].split(
                'INTERPRETIVE CONTEXT (not evidence):\n')[1])
            self.assertEqual(context['visible_source_context_not_independent_evidence'], sources)

    def test_wrong_legacy_scope_cannot_hide_sources_or_split_batch(self):
        baseline = self.request()['citation_registry']
        for scope in policy.SCOPES:
            self.assertEqual(self.request(scope)['citation_registry'], baseline)
            for quote, index in [('green', 3), ('Build the tool.', 1)]:
                row = self.run_fake(json.loads(result('SUPPORTED', [quote],
                    document_index=index)), scope)
                self.assertEqual(row['engineering_status'], 'ok')
                self.assertFalse(row['alignment']['semantic_proof'])
        p = packet()
        ext = json.loads(self.extracted(two=True))
        ext['claims'][0]['evidence_scope'] = 'agent_statement'
        ext['claims'][1]['evidence_scope'] = 'requirement'
        claims, metadata, _, _ = parse_claims(json.dumps(ext), p)
        requests = verification_requests(p, claims, metadata, 'batch')
        self.assertEqual(len(requests), 1)
        self.assertEqual(len(requests[0][0]), 2)
        self.assertEqual(requests[0][1]['citation_registry'], baseline)

    def test_frozen_inputs_old_identity_new_request(self):
        root = Path(__file__).resolve().parents[1]
        path = root/'diagnostic_packages/PMA_AUDITOR_FIRST_REAL_DIAGNOSTIC_PACKAGE_20261025.zip'
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
            'b29cf429b00e0f9b6fa7db818762201510799253a9f659d875d245eaf574a848')
        identities = {'sqlite': '0aa854b8a7c7eb98ae5e412cdf78180597ca3400e0884046db397e9e4c2cdb90',
            'html': '4760d69e0e47f1e0ede15e9fd800270b89768a6307c45b4c8d4223803cc1494b'}
        with zipfile.ZipFile(path) as archive:
            for sample, expected in identities.items():
                p = json.loads(archive.read(sample+'/input.json'))
                validate(p)
                self.assertEqual(p['review_input_sha256'], expected)
                old = [json.loads(line) for line in archive.read(sample+'/requests.jsonl').splitlines()]
                responses = [json.loads(line) for line in archive.read(sample+'/responses.jsonl').splitlines()]
                claims, meta, _, _ = parse_claims(responses[0]['response'], p)
                requests = verification_requests(p, claims, meta)
                self.assertEqual(len(requests), len(claims))
                self.assertNotEqual(extraction_request(p)['prompt'], old[0]['request']['prompt'])
                for _, req in requests:
                    self.assertEqual({d['role'] for d in req['citation_registry']},
                                     {s['role'] for s in p['sources']})
                    self.assertNotIn('maintenance_prompt', req['prompt'])
                    self.assertNotEqual(req['prompt'], old[1]['request']['prompt'])
                    context = json.loads(req['prompt'].split(
                        'INTERPRETIVE CONTEXT (not evidence):\n')[1])
                    visible = context['visible_source_context_not_independent_evidence']
                    self.assertEqual(visible, p['sources'])
                    commands = [piece['text'] for source in visible
                                if source['role'] == 'tool_command' for piece in source['slices']]
                    self.assertTrue(commands)
                    if sample == 'sqlite':
                        self.assertTrue(any('export PATH' in text and 'which sqlite3' in text
                                            for text in commands))
                    for source in visible:
                        if source['role'] == 'tool_observation':
                            for piece in source['slices']:
                                self.assertTrue(any(doc['source_id'] == source['source_id'] and
                                    doc['text'] == piece['text'] for doc in req['citation_registry']))
