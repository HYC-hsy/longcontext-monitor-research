import asyncio
import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

from pma_evidence_review import citation_inputs as ci, citation_review as cr
from pma_evidence_review.citation_cli import main
from pma_evidence_review.inputs import build_from_data,digest
from pma_evidence_review.tests.fixtures import bundle
from pma_evidence_review.tests.test_citation_inputs import aligned
from pma_evidence_review.tests.no_network import install_guard
from pma_evidence_review.transport import CapturedTransport,FakeClient


def response(**changes):
    return json.dumps({'op_index':0,'verdict':'insufficient','explanation':'Synthetic closed-evidence probe.',**changes})


def synthetic():
    return ci.build_from_parent(*aligned())


class CitationReviewTests(unittest.TestCase):
    def setUp(self): install_guard(self)

    def test_actual_seven_operations_only_two_requests_and_no_context_leak(self):
        for name,count in [('sqlite',3),('html',4)]:
            p=ci.build('.',name);plans=cr.requests(p)
            client=FakeClient([response()]);transport=CapturedTransport(client,fake=True)
            report=asyncio.run(cr.review(p,transport))
            self.assertEqual(len(report['results']),count)
            self.assertEqual(len(client.calls),1)
            self.assertEqual([r['op_index'] for r in plans if r['request']],[0])
            payload=client.calls[0]
            self.assertEqual(payload,{k:plans[0]['request'][k] for k in ('prompt','system','tools')})
            material=json.loads(payload['prompt'].split('PACKAGE:\n')[1].split('\nOUTPUT EXAMPLE')[0])
            self.assertEqual(set(material),{'original_operation','submitted_evidence','normative_requirements_context'})
            self.assertEqual(material['normative_requirements_context'],'')
            self.assertIn('missing necessary context as insufficient',payload['system'])
            self.assertEqual(set(material['original_operation']),{'op_index','action','memory_id','revision_id','content','content_sha256'})
            for forbidden in ('maintenance_prompt','memory_before','raw_response_phase','candidate_details','evidence_scope'):
                self.assertNotIn(forbidden,payload['prompt'])
            if name=='html':
                self.assertEqual(material['submitted_evidence'][0]['role'],'tool_command')
                self.assertEqual(material['submitted_evidence'][0]['field_path'],'commands/0/args/content')
            self.assertTrue(all(r['verdict'] is None for r in report['results'][1:]))

    def test_added_unquoted_visible_source_cannot_change_prompt(self):
        p,align=aligned();before=ci.build_from_parent(p,align)
        args=bundle();payload,_,_,bank=args
        sid=json.dumps(['ns','public','extra','observation/stdout'],separators=(',',':'))
        text='UNQUOTED_SUPPORT_SENTINEL'
        payload[0]['prompt']+='\n[s%s tool_observation event_order=4 field=observation/stdout]\n%s'%(digest(sid)[:12],text)
        manifest=bank['gap_evidence']['manifests']['c1']
        manifest['ordered_source_refs'].append(sid);manifest['visible_spans'].append([[0,len(text)]])
        manifest['request_sha256']=digest(payload[0]['prompt'])
        manifest['visibility_refs']=[digest(json.dumps(['c1',manifest['request_sha256'],s,r],separators=(',',':')))
            for s,r in zip(manifest['ordered_source_refs'],manifest['visible_spans'])]
        parent=build_from_data(*args,step=1,cycle_id='c1')
        after=ci.build_from_parent(*aligned(parent))
        self.assertNotEqual(before['host_provenance_sha256'],after['host_provenance_sha256'])
        self.assertNotEqual(before['citation_input_sha256'],after['citation_input_sha256'])
        self.assertEqual(cr.requests(before)[0]['request'],cr.requests(after)[0]['request'])
        self.assertNotIn(text,cr.requests(after)[0]['request']['prompt'])

    def test_other_operation_citation_changes_do_not_affect_ready_prompt(self):
        p=ci.build('.','html');modified=copy.deepcopy(p)
        alignment=modified['operations'][2]['recovered_alignment']
        raw=json.loads(alignment['alignment_json']);raw['items'][0]['quote']='OTHER_OPERATION_SENTINEL'
        alignment['alignment_json']=json.dumps(raw)
        modified['operations'][2]['preparation']=ci.prepare(modified['operations'][2]['operation'],alignment,modified['host_provenance'],modified['source_records'])
        modified['citation_input_sha256']=ci.identity({k:v for k,v in modified.items() if k!='citation_input_sha256'})
        self.assertEqual(cr.requests(p)[0]['request'],cr.requests(modified)[0]['request'])

    def test_raw_schema_unknown_op_and_protocol_error(self):
        for raw in [response(op_index=9),response(evidence=[]),response(verdict='unsupported'),'',
            response().replace('"op_index": 0','"op_index": 0, "op_index": 0')]:
            result=asyncio.run(cr.review(synthetic(),CapturedTransport(FakeClient([raw]),fake=True)))['results'][0]
            self.assertEqual(result['raw_response'],raw)
            self.assertEqual(result['engineering_status'],'parse_failure')
            self.assertIsNone(result['verdict'])
        class Client:
            async def call(self,**kwargs): return types.SimpleNamespace(content=response(verdict='supported'),tool_calls=[object()])
        result=asyncio.run(cr.review(synthetic(),CapturedTransport(Client(),fake=True)))['results'][0]
        self.assertEqual(result['engineering_status'],'protocol_error')
        self.assertEqual(result['model_verdict'],'supported')
        self.assertEqual(result['raw_response'],response(verdict='supported'))
        self.assertIsNone(result['verdict'])
        result=asyncio.run(cr.review(synthetic(),CapturedTransport(FakeClient([RuntimeError('synthetic')]),fake=True)))['results'][0]
        self.assertEqual(result['engineering_status'],'call_error')

    def test_ready_set_bound_before_model_and_core_has_no_archive_dependency(self):
        p=synthetic()
        with patch('pma_evidence_review.inputs.build',side_effect=AssertionError('no archive')):
            for verdict in ('supported','contradicted','insufficient'):
                report=asyncio.run(cr.review(p,CapturedTransport(FakeClient([response(verdict=verdict)]),fake=True)))
                self.assertEqual(report['results'][0]['verdict'],verdict)
                self.assertEqual(report['results'][0]['submitted_evidence'][0]['submitted_quote'],'green')
        p['operations'][0]['recovered_alignment']=None
        p['operations'][0]['preparation']=ci.prepare(p['operations'][0]['operation'],None,p['host_provenance'])
        p['citation_input_sha256']=ci.identity({k:v for k,v in p.items() if k!='citation_input_sha256'})
        client=FakeClient([]);report=asyncio.run(cr.review(p,CapturedTransport(client,fake=True)))
        self.assertEqual(client.calls,[])
        self.assertIsNone(report['results'][0]['verdict'])

    def test_cli_paths_export_fake_profile_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);inp=root/'input.json';inp.write_text(json.dumps(synthetic()),encoding='utf-8')
            replies=root/'responses.json';replies.write_text(json.dumps([response()]),encoding='utf-8')
            def cli(*args):
                with patch('sys.argv',['citation',*map(str,args)]),contextlib.redirect_stdout(io.StringIO()): main()
            cli('export','--input',inp,'--out',root/'plan.json')
            cli('fake','--input',inp,'--responses',replies,'--out',root/'fake')
            plan=json.loads((root/'plan.json').read_text(encoding='utf-8'))
            captured=json.loads((root/'fake/requests.jsonl').read_text(encoding='utf-8'))
            self.assertEqual(captured['request'],{k:plan[0]['request'][k] for k in ('prompt','system','tools')})
            fake=FakeClient([response()])
            with patch('pma_evidence_review.citation_cli.load_profile_client',return_value=fake):
                cli('run-profile','--input',inp,'--out',root/'profile','--profile',root/'absent','--execute-authorized-real-model')
            self.assertEqual(fake.calls,[captured['request']])
            for command in [('export','--input',inp,'--out',root/'plan.json'),('fake','--input',inp,'--responses',replies,'--out',root/'fake')]:
                with self.assertRaises(FileExistsError): cli(*command)
            with patch('pma_evidence_review.citation_cli.load_profile_client') as loader:
                with self.assertRaises(SystemExit),contextlib.redirect_stderr(io.StringIO()):
                    cli('run-profile','--input',inp,'--out',root/'blocked','--profile',root/'absent')
                loader.assert_not_called()
