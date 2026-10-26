"""Direct-operation contract tests. Scripted verdicts are not semantic labels."""
import asyncio
import json
import unittest
import copy
import contextlib
import hashlib
import io
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch

from pma_evidence_review.operation_review import operation_requests, DELETE_QUESTION, STRATEGY
from pma_evidence_review.review import review
from pma_evidence_review.location import locate
from pma_evidence_review.transport import CapturedTransport, FakeClient
from pma_evidence_review.tests.fixtures import packet, bundle
from pma_evidence_review.inputs import build_from_data, review_input_identity, validate
from pma_evidence_review.__main__ import main
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


    def test_failed_unknown_and_call_error_keep_all_operations(self):
        args = bundle()
        args[1]['steps'][0]['operations'][0]['success'] = False
        args[2][0]['evidence_report']['operations'][0]['success'] = False
        failed = build_from_data(*args, step=1, cycle_id='c1')
        unknown = packet()
        unknown['operations'][0]['action'] = 'unexpected_action'
        unknown['review_input_sha256'] = review_input_identity(unknown)
        for p, status in [(failed, 'not_reviewed_failed_operation'),
                          (unknown, 'not_reviewed_unknown_action')]:
            transport = CapturedTransport(FakeClient([]), fake=True)
            report = asyncio.run(review(p, transport, locator=locate))
            self.assertEqual(transport.calls, 0)
            self.assertEqual(len(report['results']), 1)
            self.assertEqual(report['results'][0]['engineering_status'], status)
            self.assertIsNone(report['results'][0]['verdict'])
            self.assertIsNone(operation_requests(p)[0]['request'])
        transport = CapturedTransport(FakeClient([RuntimeError('synthetic')]), fake=True)
        row = asyncio.run(review(packet(), transport, locator=locate))['results'][0]
        self.assertEqual(row['engineering_status'], 'call_error')
        self.assertIsNone(row['raw_response'])
        self.assertEqual(row['op_index'], 0)

    def test_partial_unknown_and_contradiction_remain_distinct(self):
        for verdict, expected in [('NOT_ENOUGH_INFO', 'insufficient'), ('CONTRADICTED','contradicted')]:
            raw = response(verdict=verdict, evidence=[{'document_index':3,'quote':'green'}])
            row = asyncio.run(review(packet(), CapturedTransport(FakeClient([raw]), fake=True),
                                      locator=locate))['results'][0]
            self.assertEqual(row['verdict'], expected)
            self.assertIn('all conditions', row['explanation'])
        prompt = operation_requests(packet())[0]['request']['prompt']
        self.assertIn('ALL judgments requiring evidence', prompt)
        self.assertIn('Plans, questions and hypotheses are not automatically false', prompt)

    def test_missing_unknown_duplicate_and_old_result_rejected(self):
        responses = ['', response(index=1), response().replace('"op_index": 0',
            '"op_index": 0, "op_index": 0'),
            response().replace('"op_index": 0', '"claim_index": 0'),
            json.dumps([json.loads(response()), json.loads(response())])]
        for raw in responses:
            row = asyncio.run(review(packet(), CapturedTransport(FakeClient([raw]), fake=True),
                                      locator=locate))['results'][0]
            self.assertEqual(row['engineering_status'], 'parse_failure')
            self.assertIsNone(row['verdict'])
            self.assertEqual(row['raw_response'], raw)

    def test_default_profile_export_fake_share_payload_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            p = packet()
            inp = root/'input.json'
            inp.write_text(json.dumps(p), encoding='utf-8')
            replies = root/'responses.json'
            replies.write_text(json.dumps([response()]), encoding='utf-8')
            export = root/'export.json'
            def cli(*args):
                with patch('sys.argv', ['pma', *map(str,args)]), contextlib.redirect_stdout(io.StringIO()):
                    main()
            cli('export','--input',inp,'--out',export)
            plans = json.loads(export.read_text(encoding='utf-8'))
            cli('fake','--input',inp,'--responses',replies,'--out',root/'fake')
            capture = json.loads((root/'fake/requests.jsonl').read_text(encoding='utf-8'))
            self.assertEqual(capture['request'], {k: plans[0]['request'][k]
                                                for k in ('prompt','system','tools')})
            self.assertEqual(capture['op_index'], 0)
            self.assertEqual(capture['review_strategy'], STRATEGY)
            self.assertEqual(capture['phase'], 'verify_operation')
            self.assertEqual(capture['audit_request_sha256'], hashlib.sha256(json.dumps(
                capture['request'], ensure_ascii=False, sort_keys=True,
                separators=(',', ':')).encode()).hexdigest())
            fake = FakeClient([response()])
            with patch('pma_evidence_review.__main__.load_profile_client', return_value=fake) as loader:
                cli('run-profile','--input',inp,'--out',root/'profile', '--profile',root/'absent',
                    '--execute-authorized-real-model')
                loader.assert_called_once()
                self.assertEqual(fake.calls[0], capture['request'])
            for command in [('export','--input',inp,'--out',export),
                ('fake','--input',inp,'--responses',replies,'--out',root/'fake')]:
                with self.assertRaises(FileExistsError):
                    cli(*command)
            with patch('pma_evidence_review.__main__.load_profile_client') as loader:
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    cli('run-profile','--input',inp,'--out',root/'no-call','--profile',root/'absent')
                loader.assert_not_called()
            for old in [('--mode','batch'), ('--extraction-response','old.json')]:
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    cli('export','--input',inp,'--out',root/'bad',*old)

    def test_frozen_v3_packets_direct_3_and_4_complete_operations(self):
        archive = Path(__file__).resolve().parents[1]/'diagnostic_packages'/(
            'PMA_AUDITOR_V3_FIRST_REAL_DIAGNOSTIC_20261026.zip')
        self.assertEqual(archive.stat().st_size, 391376)
        self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(),
            'df5f19558b751529244518cb85a99f0568937715a2471706af9f57c4542049f1')
        ids = {'sqlite': '0aa854b8a7c7eb98ae5e412cdf78180597ca3400e0884046db397e9e4c2cdb90',
               'html': '4760d69e0e47f1e0ede15e9fd800270b89768a6307c45b4c8d4223803cc1494b'}
        with zipfile.ZipFile(archive) as z:
            for sample, count in [('sqlite',3),('html',4)]:
                p = json.loads(z.read(sample+'-input.json'))
                validate(p)
                self.assertEqual(p['review_input_sha256'],ids[sample])
                plans = operation_requests(p)
                self.assertEqual(len(plans),count)
                for op, plan in zip(p['operations'],plans):
                    target = json.loads(plan['request']['prompt'].split('\nOPERATION TARGET (not evidence):\n')[1].split(
                        '\nINTERPRETIVE CONTEXT')[0])
                    self.assertEqual(target['original_operation']['content'],op['content'])
                    self.assertEqual(target['original_operation']['before'],op['before'])
                    self.assertNotIn('kind',target)
                    self.assertNotIn('conditions',target)
                    self.assertNotIn('dependencies',target)
                    self.assertNotIn('evidence_scope',plan['request']['prompt'])
                    self.assertEqual(plan['request']['phase'],'verify_operation')
                    example = json.loads(plan['request']['prompt'].split(
                        'OUTPUT EXAMPLE (shape only; decide the verdict from evidence):\n')[1])
                    self.assertEqual(example['op_index'],op['op_index'])
                    self.assertEqual(set(example),{'op_index','verdict','explanation','evidence'})
                    if op['action'].startswith('delete_'):
                        self.assertEqual(target['question'],DELETE_QUESTION)
                        self.assertIn('old gap once existed is NOT a reason',plan['request']['prompt'])
                if sample == 'sqlite':
                    self.assertIn('Task completed successfully',plans[0]['request']['prompt'])
                client = FakeClient([response(i) for i in range(count)])
                report = asyncio.run(review(p,CapturedTransport(client,fake=True),locator=locate))
                self.assertEqual(len(client.calls),count)
                self.assertEqual([r['op_index'] for r in report['results']],list(range(count)))
                self.assertTrue(all(r['engineering_status']=='ok' for r in report['results']))


    def test_direct_binding_bounds_wrong_document_and_missing_locator(self):
        cases = [({'document_index':0,'quote':'green'},'citation_unknown_document'),
            ({'document_index':1,'quote':'green'},'citation_ambiguous_or_unmatched'),
            ({'document_index':3,'quote':'green','start':-1,'end':5},'citation_outside_visible_range'),
            ({'document_index':3,'quote':'green','start':0,'end':4},'citation_text_mismatch'),
            ({'document_index':3,'quote':'green','source_id':'invented'},'parse_failure')]
        for citation, status in cases:
            raw = response(verdict='SUPPORTED', evidence=[citation])
            row = asyncio.run(review(packet(),CapturedTransport(FakeClient([raw]),fake=True),
                                   locator=locate))['results'][0]
            self.assertEqual(row['engineering_status'],status)
            self.assertIsNone(row['verdict'])
            self.assertEqual(row['model_verdict'],'SUPPORTED')
        raw = response(verdict='SUPPORTED',evidence=[{'document_index':3,'quote':'green'}])
        row = asyncio.run(review(packet(),CapturedTransport(FakeClient([raw]),fake=True)))['results'][0]
        self.assertEqual(row['engineering_status'],'locator_unavailable')

    def test_invalid_input_never_calls_client(self):
        p = packet()
        p['operations'][0]['content'] += 'unauthorized change'
        client = FakeClient([])
        with self.assertRaises(ValueError):
            asyncio.run(review(p,CapturedTransport(client,fake=True),locator=locate))
        self.assertEqual(client.calls,[])


    def test_final_request_has_one_operation_output_contract(self):
        plans = operation_requests(packet())
        for plan in plans:
            prompt = plan['request']['prompt']
            self.assertEqual(prompt.count('Return one JSON object with exactly'), 1)
            self.assertEqual(prompt.count('OUTPUT EXAMPLE ('), 1)
            self.assertNotIn('Return JSON:', prompt)
            self.assertNotIn('claim_index', prompt)
            self.assertNotIn('overrides', prompt)
            self.assertNotIn('Claim:', prompt)
            self.assertNotIn('coverage', prompt)
            example = json.loads(prompt.split(
                'OUTPUT EXAMPLE (shape only; decide the verdict from evidence):\n')[1])
            self.assertEqual(set(example), {'op_index','verdict','explanation','evidence'})
            self.assertEqual(example['op_index'],plan['op_index'])
            from pma_evidence_review.operation_review import parse_operation
            self.assertEqual(parse_operation(example,plan['op_index'])['verdict'],'insufficient')


    def test_tool_response_text_captured_before_protocol_rejection(self):
        raw = response(verdict='SUPPORTED',evidence=[{'document_index':3,'quote':'green'}])
        executed = []
        class UnexpectedToolsClient:
            async def call(self, **kwargs):
                # An opaque object that must never be executed or serialized.
                def tool():
                    executed.append(True)
                    raise AssertionError('must not execute')
                return type('Response',(),{'content':raw,'tool_calls':[tool]})()
        with tempfile.TemporaryDirectory() as temp:
            transport = CapturedTransport(UnexpectedToolsClient(),temp,fake=True)
            row = asyncio.run(review(packet(),transport,locator=locate))['results'][0]
            self.assertEqual(row['engineering_status'],'protocol_error')
            self.assertEqual(row['reason'],'unexpected_tool_calls')
            self.assertEqual(row['raw_response'],raw)
            self.assertEqual(row['model_verdict'],'SUPPORTED')
            self.assertIsNone(row['verdict'])
            capture = json.loads(Path(temp,'responses.jsonl').read_text(encoding='utf-8'))
            self.assertEqual(capture['response'],raw)
            self.assertEqual(capture['status'],'protocol_error')
            self.assertNotIn('tool_calls',capture)
            self.assertEqual(executed,[])
        transport = CapturedTransport(FakeClient([RuntimeError('synthetic')]),fake=True)
        row = asyncio.run(review(packet(),transport,locator=locate))['results'][0]
        self.assertEqual(row['engineering_status'],'call_error')
        self.assertIsNone(row['raw_response'])

    def test_nontext_response_is_protocol_error_without_object_serialization(self):
        transport = CapturedTransport(FakeClient([{'opaque':'not text'}]),fake=True)
        row = asyncio.run(review(packet(),transport,locator=locate))['results'][0]
        self.assertEqual(row['engineering_status'],'protocol_error')
        self.assertEqual(row['reason'],'response_content_type')
        self.assertIsNone(row['raw_response'])
        self.assertNotIn('opaque',json.dumps(transport.records))
