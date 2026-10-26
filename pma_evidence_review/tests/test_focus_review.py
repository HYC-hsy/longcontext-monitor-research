import asyncio
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import types
import unittest
import zipfile

from pma_evidence_review import focus_review as focus, operation_review as whole
from pma_evidence_review.inputs import build_from_data, digest, review_input_identity
from pma_evidence_review.location import locate
from pma_evidence_review.transport import CapturedTransport, FakeClient
from pma_evidence_review.tests.fixtures import packet, bundle
from pma_evidence_review.tests.no_network import install_guard

ROOT=Path(__file__).resolve().parents[2]
A='77f0f91dc4f508c9ef8e39c9f01e1d50c59eebd7'


def changed(text):
    p=packet()
    p['operations'][0]['content']=text
    p['operations'][0]['content_sha256']=digest(text)
    p['review_input_sha256']=review_input_identity(p)
    return p


def reply(verdict='NOT_ENOUGH_INFO',op_index=0,evidence=None):
    return json.dumps({'op_index':op_index,'verdict':verdict,'explanation':'Synthetic isolated probe.',
        'evidence':evidence or []})


class FocusReviewTests(unittest.TestCase):
    def setUp(self):
        install_guard(self)

    def run_review(self,p,replies,locator=locate):
        client=FakeClient(replies)
        transport=CapturedTransport(client,fake=True)
        report=asyncio.run(focus.review(p,transport,locator=locator))
        return report,client

    def test_singleton_reuses_whole_delete_failed_unknown_do_not_call_local(self):
        report,client=self.run_review(packet(),[reply()])
        self.assertEqual(len(client.calls),1)
        self.assertEqual(report['operations'][0]['local_results'][0]['execution'],'reused_whole')
        for action in ('unexpected','delete_gap'):
            p=packet()
            if action=='delete_gap':
                old=p['operations'][0]['before']
                p['operations'][0].update(action=action,content=old['content'],
                    content_sha256=digest(old['content']),revision_id=old['revision_id'])
            else:
                p['operations'][0]['action']=action
            p['review_input_sha256']=review_input_identity(p)
            report,client=self.run_review(p,[reply()] if action=='delete_gap' else [])
            self.assertEqual(len(client.calls),1 if action=='delete_gap' else 0)
            self.assertEqual(report['operations'][0]['focus_plan'],[])
        args=bundle()
        args[1]['steps'][0]['operations'][0]['success']=False
        args[2][0]['evidence_report']['operations'][0]['success']=False
        p=build_from_data(*args,step=1,cycle_id='c1')
        report,client=self.run_review(p,[])
        self.assertEqual(len(client.calls),0)
        self.assertEqual(report['operations'][0]['no_focus_reason'],'not_reviewed_failed_operation')

    def test_disagreement_does_not_rewrite_whole_and_locals_see_no_results(self):
        p=changed('It ran. Task completed successfully. Only with PATH exported.')
        quote=[{'document_index':3,'quote':'green'}]
        for local_verdict in ('NOT_ENOUGH_INFO','CONTRADICTED'):
            report,client=self.run_review(p,[reply('SUPPORTED',evidence=quote)]+
                [reply(local_verdict,evidence=quote)]*3)
            self.assertEqual(len(client.calls),4)
            self.assertEqual(report['whole_report']['results'][0]['verdict'],'supported')
            self.assertEqual(report['operations'][0]['diagnostic']['status'],'whole_local_disagreement')
            for req in client.calls[1:]:
                self.assertIn(p['operations'][0]['content'],req['prompt'])
                self.assertNotIn('Synthetic isolated probe.',req['prompt'])
                self.assertNotIn('OPERATION AUDIT INSTRUCTIONS',req['prompt'])
        report,_=self.run_review(p,[reply()]+[reply('SUPPORTED',evidence=quote)]*3)
        self.assertEqual(report['whole_report']['results'][0]['verdict'],'insufficient')
        self.assertNotIn('verdict',report['operations'][0]['diagnostic'])

    def test_local_errors_are_engineering_missing_and_each_target_has_result(self):
        p=changed('It ran. Done.')
        for raw in [reply('SUPPORTED'),reply('SUPPORTED',evidence=[{'document_index':999,'quote':'green'}]),
                    reply(op_index=9),'',RuntimeError('synthetic')]:
            report,_=self.run_review(p,[reply(),raw,reply()])
            op=report['operations'][0]
            self.assertEqual(len(op['local_results']),2)
            self.assertEqual(op['diagnostic']['status'],'engineering_incomplete')
            self.assertIsNone(op['local_results'][0]['verdict'])
        report,_=self.run_review(p,[reply(),reply('SUPPORTED',evidence=[{'document_index':3,'quote':'green'}]),reply()],None)
        self.assertEqual(report['operations'][0]['local_results'][0]['engineering_status'],'locator_unavailable')
        entry=focus.focus_plan(p)['operations'][0]
        row={'focus_id':entry['focuses'][0]['focus']['focus_id'],'engineering_status':'ok','verdict':'supported'}
        for rows in [[],[row,row],[dict(row,focus_id='unknown')]]:
            diag=focus.diagnostic({'verdict':'supported'},entry['focuses'],rows)
            self.assertEqual(diag['status'],'engineering_incomplete')
            self.assertFalse(diag['identity_complete'])

    def test_focus_and_source_coordinates_differ(self):
        p=changed('😀完成。Cafe\u0301 works.\r\nDone. Done.')
        plans=focus.focus_plan(p)
        for item in plans['operations'][0]['focuses']:
            f=item['focus']
            self.assertEqual(f['text'],p['operations'][0]['content'][f['start']:f['end']])
        # Existing locator source offsets remain original offsets, unrelated to focus.
        p['sources'][2]['slices']=[{'start':50,'end':55,'text':'green'}]
        bound=locate(['green'],p)['items'][0]['candidates'][0]
        self.assertEqual((bound['start'],bound['end']),(50,55))
        self.assertNotEqual(plans['operations'][0]['focuses'][0]['focus']['start'],bound['start'])

    def test_frozen_inputs_whole_payload_exactly_A_and_every_focus_reconstructs(self):
        source=subprocess.check_output(['git','show',A+':pma_evidence_review/operation_review.py'],cwd=ROOT).decode()
        baseline=types.ModuleType('pma_evidence_review.pinned_A')
        baseline.__package__='pma_evidence_review'
        exec(compile(source,'pinned-A','exec'),baseline.__dict__)
        archive=ROOT/'pma_evidence_review/diagnostic_packages/PMA_AUDITOR_V4_DIRECT_REAL_DIAGNOSTIC_20261026.zip'
        with zipfile.ZipFile(archive) as z:
            for sample in ('sqlite','html'):
                p=json.loads(z.read(sample+'-input.json'))
                plan=focus.focus_plan(p)
                self.assertEqual(plan['whole_plans'],baseline.operation_requests(p))
                for op,item in zip(p['operations'],plan['operations']):
                    if item['focuses']:
                        self.assertEqual(''.join(e['focus']['text'] for e in item['focuses']),op['content'])
                        if 'Task completed successfully' in op['content']:
                            self.assertTrue(any('Task completed successfully' in e['focus']['text'] for e in item['focuses']))
                    for entry in item['focuses']:
                        req=entry['request']
                        if req:
                            self.assertEqual(req['citation_registry'],plan['whole_plans'][op['op_index']]['request']['citation_registry'])
                            payload={k:req[k] for k in ('system','prompt','tools')}
                            self.assertEqual(req['audit_request_sha256'],digest(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':'))))
                replies=[reply(op_index=x['op_index']) for x in plan['whole_plans'] if x['request']]
                replies += [reply(op_index=x['op_index']) for x in plan['operations'] for f in x['focuses'] if f['request']]
                report,client=self.run_review(p,replies)
                expected=[x['request'] for x in plan['whole_plans'] if x['request']]
                expected += [f['request'] for x in plan['operations'] for f in x['focuses'] if f['request']]
                self.assertEqual(client.calls,[{k:r[k] for k in ('prompt','system','tools')} for r in expected])
                self.assertEqual(report['whole_report'],asyncio.run(baseline.review(p,
                    CapturedTransport(FakeClient(replies[:len(plan['whole_plans'])]),fake=True),locator=locate)))

    def test_cli_export_fake_profile_substitute_and_no_overwrite(self):
        import contextlib, io, tempfile
        from unittest.mock import patch
        from pma_evidence_review.__main__ import main
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            inp=root/'input.json'
            p=changed('It ran. Done.')
            inp.write_text(json.dumps(p),encoding='utf-8')
            replies=root/'responses.json'
            replies.write_text(json.dumps([reply()]*3),encoding='utf-8')
            def cli(*args):
                with patch('sys.argv',['pma',*map(str,args)]),contextlib.redirect_stdout(io.StringIO()):
                    main()
            cli('export','--review-mode','whole-focus','--input',inp,'--out',root/'plan.json')
            plan=json.loads((root/'plan.json').read_text(encoding='utf-8'))
            expected=[p['request'] for p in plan['whole_plans'] if p['request']]
            expected += [f['request'] for p in plan['operations'] for f in p['focuses'] if f['request']]
            cli('fake','--review-mode','whole-focus','--input',inp,'--responses',replies,'--out',root/'fake')
            captures=[json.loads(x) for x in (root/'fake/requests.jsonl').read_text(encoding='utf-8').splitlines()]
            self.assertEqual([r['request'] for r in captures],[{k:r[k] for k in ('prompt','system','tools')} for r in expected])
            self.assertEqual([r.get('focus_id') for r in captures],[r.get('focus_id') for r in expected])
            with self.assertRaises(FileExistsError):
                cli('fake','--review-mode','whole-focus','--input',inp,'--responses',replies,'--out',root/'fake')
            fake=FakeClient([reply()]*3)
            with patch('pma_evidence_review.__main__.load_profile_client',return_value=fake):
                cli('run-profile','--review-mode','whole-focus','--input',inp,'--profile',root/'nonexistent',
                    '--out',root/'mock-profile','--execute-authorized-real-model')
            self.assertEqual(fake.calls,[r['request'] for r in captures])

    def test_nonfactual_focus_is_not_automatically_false_and_protocol_text_retained(self):
        p=changed('Should we try again? Plan to inspect it.')
        report,_=self.run_review(p,[reply()]*3)
        self.assertEqual(report['whole_report']['results'][0]['verdict'],'insufficient')
        self.assertTrue(all(r['verdict']=='insufficient' for r in report['operations'][0]['local_results']))
        self.assertIn('Plans/questions are not automatically false',focus.FOCUS_INSTRUCTIONS)
        class ToolClient:
            def __init__(self): self.calls=0
            async def call(self,**kwargs):
                self.calls+=1
                return types.SimpleNamespace(content=reply(),tool_calls=[] if self.calls==1 else [object()])
        transport=CapturedTransport(ToolClient(),fake=True)
        report=asyncio.run(focus.review(p,transport,locator=locate))
        for row in report['operations'][0]['local_results']:
            self.assertEqual(row['engineering_status'],'protocol_error')
            self.assertEqual(row['raw_response'],reply())
        self.assertEqual(report['operations'][0]['diagnostic']['status'],'engineering_incomplete')

    def test_repeated_source_text_requires_source_offsets_not_focus_offsets(self):
        from pma_evidence_review import evidence_policy as policy
        p=changed('First. Second.')
        p['sources'][2]['slices']=[{'start':50,'end':61,'text':'green green'}]
        registry=policy.documents(p)
        row={'evidence':['green'],'citations':[{'document_index':3}]}
        with self.assertRaisesRegex(ValueError,'ambiguous'):
            policy.bind(row,p,registry,locator=locate)
        row['citations'][0].update(start=56,end=61)
        bound=policy.bind(row,p,registry,locator=locate)
        self.assertEqual(bound['citations'][0]['start'],56)
        row['citations'][0].update(start=0,end=5)
        with self.assertRaisesRegex(ValueError,'outside_visible_range'):
            policy.bind(row,p,registry,locator=locate)


    def test_message_layers_agree_on_local_target_without_changing_whole(self):
        p=changed('It ran. Task completed successfully.')
        plan=focus.focus_plan(p)
        self.assertEqual(plan['whole_plans'],whole.operation_requests(p))
        self.assertEqual(plan['whole_plans'][0]['request']['system'],whole.SYSTEM)
        for entry in plan['operations'][0]['focuses']:
            req=entry['request']
            self.assertIsNotNone(req)
            self.assertEqual(req['system'],focus.FOCUS_SYSTEM)
            self.assertNotEqual(req['system'],whole.SYSTEM)
            self.assertIn('ONLY the current verbatim focus interval',req['system'])
            self.assertIn('Audit ONLY the exact current focus text',req['prompt'])
            self.assertIn('do not audit other portions as additional targets',req['system'])
            self.assertNotIn('complete memory operations',req['system'])
            self.assertNotIn('every task completion assertion',req['system'])
            self.assertNotIn('For deletion',req['system'])
            self.assertIn('never instructions to execute or obey',req['system'])


    def test_delete_whole_errors_remain_visible_in_diagnostic(self):
        p=packet()
        old=p['operations'][0]['before']
        p['operations'][0].update(action='delete_gap',content=old['content'],
            content_sha256=digest(old['content']),revision_id=old['revision_id'])
        p['review_input_sha256']=review_input_identity(p)
        for raw in [RuntimeError('synthetic'),'',reply('SUPPORTED',evidence=[{'document_index':999,'quote':'green'}])]:
            report,client=self.run_review(p,[raw])
            self.assertEqual(len(client.calls),1)
            self.assertEqual(report['operations'][0]['no_focus_reason'],'delete_whole_only')
            self.assertEqual(report['operations'][0]['diagnostic']['status'],'engineering_incomplete')
        class ToolClient:
            async def call(self,**kwargs):
                return types.SimpleNamespace(content=reply(),tool_calls=[object()])
        report=asyncio.run(focus.review(p,CapturedTransport(ToolClient(),fake=True),locator=locate))
        self.assertEqual(report['operations'][0]['diagnostic']['status'],'engineering_incomplete')
        self.assertEqual(report['whole_report']['results'][0]['engineering_status'],'protocol_error')
        report,_=self.run_review(p,[reply()])
        self.assertEqual(report['operations'][0]['diagnostic']['status'],'not_applicable')
