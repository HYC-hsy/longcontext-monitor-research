import asyncio
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pma_evidence_review.benchmark import core,experiment as ex
from pma_evidence_review.transport import CapturedTransport,FakeClient,ResponseProtocolError
from pma_evidence_review.tests.no_network import install_guard

DATA=Path('pma_evidence_review/benchmark/candidate_data')
PIN='dcadeb1fabe2c2518307e8763ea5f6118688027394e514b575ce07d4fe482928'


class CitationExperimentTests(unittest.TestCase):
    def setUp(self):install_guard(self)

    def test_a_unchanged_b_only_system_and_strategy(self):
        cases=core.load_dataset(DATA,PIN)['cases.json']
        a=ex.plan(DATA,PIN);b=ex.plan(DATA,PIN,ex.CANDIDATE)
        for case,ea,eb in zip(cases,a['entries'],b['entries']):
            self.assertEqual(ea['request'],case['request'])
            restored=copy.deepcopy(eb['request'])
            self.assertIn(ex.CLARIFICATION,restored['system'])
            restored['system']=restored['system'].replace(ex.CLARIFICATION,'',1)
            restored['review_strategy']=case['request']['review_strategy']
            restored['audit_request_sha256']=core.ci.identity({k:restored[k] for k in ('system','prompt','tools')})
            self.assertEqual(restored,case['request'])
            self.assertEqual(eb['parent_benchmark_input_sha256'],case['benchmark_input_sha256'])
            self.assertNotEqual(eb['request']['audit_request_sha256'],ea['request']['audit_request_sha256'])

    def test_labels_never_used_and_no_sample_specific_prompt(self):
        a=ex.plan(DATA,PIN,ex.CANDIDATE)
        original=core.load_dataset
        def guarded(*args,**kwargs):
            self.assertFalse(kwargs.get('include_evaluation',False))
            return original(*args,**kwargs)
        with patch.object(core,'load_dataset',side_effect=guarded):self.assertEqual(ex.plan(DATA,PIN,ex.CANDIDATE),a)
        for word in ('SQLite','HTML','Critical constraint','h-html','d-path','reference_label','matched_pair'):
            self.assertNotIn(word,ex.CLARIFICATION)

    def test_fake_payload_identity_and_wrong_strategy_score(self):
        for strategy in (ex.BASELINE,ex.CANDIDATE):
            plan=ex.plan(DATA,PIN,strategy)
            responses=[json.dumps({'op_index':e['request']['op_index'],'verdict':'insufficient','explanation':'fixture'}) for e in plan['entries']]
            client=FakeClient(responses)
            results=asyncio.run(ex.run(DATA,PIN,CapturedTransport(client,fake=True),strategy))
            self.assertEqual(client.calls,[{k:e['request'][k] for k in ('system','prompt','tools')} for e in plan['entries']])
            self.assertEqual(ex.score(DATA,PIN,results,strategy)['valid_samples'],29)
            other=ex.CANDIDATE if strategy==ex.BASELINE else ex.BASELINE
            with self.assertRaisesRegex(ValueError,'experiment_result_identity'):ex.score(DATA,PIN,results,other)
            mixed=copy.deepcopy(results);mixed[1]['audit_request_sha256']='0'*64
            with self.assertRaisesRegex(ValueError,'experiment_result_identity'):ex.score(DATA,PIN,mixed,strategy)

    def test_stop_raw_preserved_and_semantic_verdict_continues(self):
        first=json.dumps({'op_index':0,'verdict':'contradicted','explanation':'fixture'})
        for error in ('invalid',RuntimeError('fixture'),ResponseProtocolError('unexpected_tool_calls','raw text')):
            client=FakeClient([first,error]);journal=[]
            rows=asyncio.run(ex.run(DATA,PIN,CapturedTransport(client,fake=True),ex.CANDIDATE,on_result=journal.append))
            self.assertEqual(len(client.calls),2);self.assertEqual(rows,journal)
            self.assertEqual(rows[0]['engineering_status'],'ok')
            self.assertEqual(rows[2]['engineering_status'],'not_run_after_engineering_error')
            self.assertEqual(rows[2]['experiment_strategy'],ex.CANDIDATE)
            if isinstance(error,ResponseProtocolError):self.assertEqual(rows[1]['raw_response'],'raw text')

    def test_cli_export_fake_and_guarded_profile_mock(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);base=['experiment','--dataset',str(DATA),'--manifest-sha256',PIN,'--strategy',ex.CANDIDATE]
            with patch('sys.argv',base+['export','--out',str(root/'plan.json')]):ex.main()
            with patch('sys.argv',base+['fake','--out',str(root/'fake')]):ex.main()
            plan=json.loads((root/'plan.json').read_text(encoding='utf-8'))
            self.assertEqual(plan,json.loads((root/'fake/experiment-plan.json').read_text(encoding='utf-8')))
            received=[json.loads(line)['request'] for line in (root/'fake/requests.jsonl').read_text(encoding='utf-8').splitlines()]
            self.assertEqual(received,[{k:e['request'][k] for k in ('system','prompt','tools')} for e in plan['entries']])
            args=base+['run-profile','--profile','UNREAD_FAKE_PROFILE','--out',str(root/'mock')]
            with patch('sys.argv',args),patch.object(ex,'load_profile_client') as loader:
                with self.assertRaises(SystemExit):ex.main()
                loader.assert_not_called()
            with patch('sys.argv',args+['--execute-authorized-real-model']),patch.object(ex,'load_profile_client',return_value=FakeClient(['bad'])):
                with self.assertRaisesRegex(SystemExit,'stopped'):ex.main()
            self.assertTrue((root/'mock/results.json').exists())
