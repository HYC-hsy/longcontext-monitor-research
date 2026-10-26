"""No-network integration with existing public files; never copy their text to fixtures."""
import asyncio
import copy
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from pma_evidence_review.inputs import build, build_from_data, load, D, SAMPLES, validate
from pma_evidence_review.location import locate
from pma_evidence_review.review import legacy_review as review, extraction_request, parse_claims, verification_requests
from pma_evidence_review.transport import CapturedTransport, FakeClient, load_profile_client
from pma_evidence_review.tests.fixtures import packet, extraction, result
from pma_evidence_review.tests.no_network import install_guard

ROOT = Path(__file__).resolve().parents[2]


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        install_guard(self)

    def test_graded_locator_original_implementation(self):
        p = packet()
        self.assertEqual(locate(['green'],p)['status'],'exact_unique')
        p['sources'][2]['slices'][0]['text'] = 'green green'
        self.assertEqual(locate(['green'],p)['status'],'exact_multiple')
        p['sources'][2]['slices'][0]['text'] = 'alpha  beta'
        p['sources'][2]['slices'][0]['end'] = len('alpha  beta')
        self.assertEqual(locate(['alpha beta'],p)['status'],'normalized_unique')
        p['sources'][2]['slices'][0]['text'] = 'alpha beta gamma delta epsilon zeta'
        p['sources'][2]['slices'][0]['end'] = len(p['sources'][2]['slices'][0]['text'])
        self.assertEqual(locate(['alpha beta gamma delta zeta'],p)['status'],'fuzzy_candidate')
        self.assertEqual(locate(['never visible'],p)['status'],'unbound')

    def test_partial_visibility_coordinates_and_gaps(self):
        p = packet()
        p['sources'][2]['slices'] = [{'start':10,'end':15,'text':'green'},
                                   {'start':30,'end':34,'text':'blue'}]
        row = locate(['green'],p)['items'][0]['candidates'][0]
        self.assertEqual((row['start'],row['end']),(10,15))
        self.assertEqual(row['role'],'tool_observation')
        self.assertIsNone(row['source_text_sha256'])
        self.assertNotEqual(locate(['green blue'],p)['status'],'exact_unique')
        self.assertEqual(locate(['secret hidden content'],p)['status'],'unbound')

    def test_decisive_result_requires_bound_quote(self):
        for quote,expected in [('green','ok'),('never visible','citation_ambiguous_or_unmatched')]:
            transport=CapturedTransport(FakeClient([extraction(),result('SUPPORTED',[quote],document_index=3)]),fake=True)
            report=asyncio.run(review(packet(),transport,locator=locate))
            row=report['results'][0]
            self.assertEqual(row['engineering_status'],expected)
            if expected != 'ok':
                self.assertIsNone(row['verdict'])
                self.assertEqual(row['model_verdict'],'supported')

    def test_nonfactual_no_semantic_verification_call(self):
        data=json.loads(extraction());data['claims'][0]['kind']='plan'
        transport=CapturedTransport(FakeClient([json.dumps(data)]),fake=True)
        report=asyncio.run(review(packet(),transport,locator=locate))
        self.assertEqual(transport.calls,1)
        self.assertEqual(report['results'][0]['engineering_status'],'not_applicable_nonfactual')
        self.assertIsNone(report['results'][0]['verdict'])
        claims, metadata, _, _ = parse_claims(json.dumps(data), packet())
        self.assertEqual(verification_requests(packet(), claims, metadata), [])

    def test_whitelist_ignores_unknown_developer_labels(self):
        p=packet(); expected=extraction_request(p)
        p['reward']='SENTINEL'
        p['operations'][0]['expected_verdict']='SENTINEL'
        p['memory_before'][0]['future_label']='SENTINEL'
        self.assertEqual(extraction_request(p),expected)
        p['sources'][0]['slices'][0]['text']='SENTINEL'
        with self.assertRaisesRegex(ValueError,'sources_not_from_visible_prompt'):
            extraction_request(p)

    def test_profile_adapter_uses_existing_factory_with_fake_client(self):
        fake=FakeClient([result()])
        module=types.ModuleType('episode')
        calls=[]
        def construct(logs_dir, *, memory_profile):
            calls.append((logs_dir,memory_profile))
            return types.SimpleNamespace(_memory_llm=fake)
        module.construct_upstream=construct
        with tempfile.TemporaryDirectory() as temp, patch.dict(sys.modules,{'episode':module}):
            profile=Path(temp,'profile.json');profile.write_text('{"test":{"apikey":"synthetic"}}')
            oldpath=list(sys.path)
            try:
                client=load_profile_client(ROOT,profile,'test',Path(temp,'client'),authorized=True)
            finally:
                sys.path[:]=oldpath
            self.assertIs(client,fake)
            self.assertEqual(len(calls),1)
            transport=CapturedTransport(client,fake=True)
            asyncio.run(transport.send(extraction_request(packet())))
            self.assertNotIn('apikey',json.dumps(transport.records))

    def test_public_development_samples_fake_end_to_end(self):
        for sample,expected_count in [('sqlite',54),('html',12)]:
            with self.subTest(sample=sample):
                p=build(ROOT,sample)
                self.assertEqual(p['replay_status'],'exact_public_prompt')
                self.assertEqual(len(p['sources']),expected_count)
                # Scripted fake claims are a plumbing probe, not human or semantic labels.
                claims=[{'claim':op['content'],'original_text':op['content'],
                    'op_index':op['op_index'],'kind':'deletion' if op['action'].startswith('delete_') else 'fact',
                    'conditions':[],'dependencies':[]} for op in p['operations'] if op['success']]
                ext=json.dumps({'claims':claims,'coverage':[{'op_index':op['op_index'],
                    'status':'complete','reason':'synthetic transport probe, no semantic claim'}
                    for op in p['operations']]})
                client=FakeClient([ext]+[result() for _ in claims])
                transport=CapturedTransport(client,fake=True)
                report=asyncio.run(review(p,transport,locator=locate))
                self.assertEqual(transport.calls,1+len(claims))
                self.assertEqual(len(report['results']),len(claims))
                self.assertTrue(all(x['engineering_status']=='ok' for x in report['results']))
                self.assertEqual(client.calls[0],transport.records[0]['request'])
                self.assertNotIn('actual_phase2_prompt',client.calls[0]['prompt'])

    def test_real_future_mutation_invariance(self):
        slot,step,cycle_id=SAMPLES['sqlite'];root=ROOT/D/'source_window_two_real_20261025'/slot
        args=[load(root/'memory_payload.jsonl.gz',True),load(root/'trajectory_memory.json.gz'),
              load(root/'gap_cycle.jsonl.gz',True),load(root/'memory.json.gz')]
        before=extraction_request(build_from_data(*args,step=step,cycle_id=cycle_id))
        for payload in args[0]:
            if payload['phase']!='maintenance' or payload['cycle_step']>step:
                payload['prompt']='FUTURE_SENTINEL'
        for row in args[1]['steps']:
            row.update(raw_response_phase2='FUTURE_SENTINEL',context_for_action='FUTURE_SENTINEL',
                       should_inject='FUTURE_SENTINEL',user_prompt_phase2='FUTURE_SENTINEL')
            if row['step_id']>step:
                row['operations']='FUTURE_SENTINEL'
        for row in args[2]:
            row['report']={'actual_phase2_prompt':'FUTURE_SENTINEL'}
        args[3].update(status='FUTURE_SENTINEL',selection='FUTURE_SENTINEL',reward='FUTURE_SENTINEL')
        args[3]['gap_evidence']['active_revisions']={'status':'FUTURE_SENTINEL'}
        args[3]['gap_evidence']['revisions']['unrelated_future']={'content':'FUTURE_SENTINEL'}
        self.assertEqual(before,extraction_request(build_from_data(*args,step=step,cycle_id=cycle_id)))


if __name__ == '__main__':
    unittest.main()
