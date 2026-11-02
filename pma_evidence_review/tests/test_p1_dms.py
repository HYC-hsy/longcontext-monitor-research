"""Offline DMS-inspired material selection; fake outputs are not semantic scores."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch
from pma_evidence_review.tests.test_bank_display import ROOT, GapMemory, reply
from pma_evidence_review.tests.no_network import install_guard
from pma_evidence_review.tools.run_p1_source_case import build_case,run_case,source_identity
from p1_dms_agent import DMSP1Agent,SYSTEM


class DMSTests(unittest.TestCase):
    def setUp(self):
        install_guard(self)
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)

    def agent(self,responses,bank=None,task='  task A\r\n\r\n task B\n\n'):
        requests=[]
        async def fake(**kw):
            requests.append(deepcopy(kw));return responses.pop(0)
        return DMSP1Agent(task=task,task_id='task',source_root=self.tmp.name,
                           memory=bank or GapMemory(),llm=NS(call=fake)),requests

    def test_task_paragraphs_and_two_equal_outputs_preserve_distinct_events(self):
        a,req=self.agent([reply([('memory_keep',{'category':'procedural','source_ids':['E2','T1','E1']})])])
        rows=[{'event_id':'a','commands':['workspace A/run'],'observation':'same'},
              {'event_id':'b','commands':['workspace B/run'],'observation':'same'}]
        r=asyncio.run(a.maintain(rows,cycle_id='c'))
        self.assertEqual(r['status'],'completed');self.assertEqual(req[0]['system'],SYSTEM)
        self.assertEqual([x['function']['name'] for x in req[0]['tools']],['memory_keep','memory_delete','memory_read_source'])
        self.assertEqual(''.join(x['text'] for x in a.links.state['task_segments'].values()),a.task)
        key=r['operations'][0]['memory_id'];ref=a.links.state['refs'][key]
        self.assertEqual([s['source_id'] for s in ref['sources']],['T1','event_1','event_2'])
        page=a.links.read({'kind':'memory','id':key},a._active_records())
        self.assertIn('workspace A/run',json.dumps(page));self.assertIn('workspace B/run',json.dumps(page))
        self.assertEqual(a.links.state['groups'][key]['outcome'],'unknown')
        self.assertEqual(a.memory.status,'')

    def test_legacy_A_B_group_survives_delete_without_nested_text_or_false_complete(self):
        bank=GapMemory();a_id=bank.save_knowledge('A=50');b_id=bank.save_knowledge('B=200')
        a,req=self.agent([reply([('memory_keep',{'category':'knowledge','source_ids':['M1','M2']}),
                                 ('memory_delete',{'memory_id':a_id}),('memory_delete',{'memory_id':b_id})])],bank)
        r=asyncio.run(a.maintain([],cycle_id='c'));self.assertEqual(r['status'],'completed')
        key=r['operations'][0]['memory_id'];page=a.links.read({'kind':'memory','id':key},a._active_records())
        self.assertIn('A=50',json.dumps(page));self.assertIn('B=200',json.dumps(page))
        self.assertFalse(page['complete']);self.assertTrue(page['page_sequence_complete'])
        self.assertNotIn('A=50',a._active_records()[key].content)
        self.assertEqual(a.links.read({'kind':'memory','id':a_id},a._active_records())['status'],'entry_not_found')
        reopened=DMSP1Agent(task=a.task,task_id='task',source_root=self.tmp.name,
            memory=GapMemory.from_dict(a.memory.to_dict()),llm=None)
        self.assertEqual(reopened.links.read({'kind':'memory','id':key},reopened._active_records()),page)

    def test_failed_keep_and_forbidden_prose_stop_delete_or_do_not_write_status(self):
        bank=GapMemory();key=bank.save_knowledge('old Correct fix claim')
        a,req=self.agent([reply([('memory_keep',{'category':'procedural','source_ids':['E99']}),
                                 ('memory_delete',{'memory_id':key})])],bank)
        r=asyncio.run(a.maintain([],cycle_id='c'));self.assertEqual(r['status'],'tool_error')
        self.assertIn(key,a._active_records())
        async def fake(**kw):return reply([('memory_update_status',{'content':'Task completed'})])
        a.llm=NS(call=fake);r=asyncio.run(a.maintain([],cycle_id='c2'))
        self.assertEqual(r['status'],'tool_error');self.assertEqual(a.memory.status,'')
        self.assertEqual(a.memory.knowledge[0].content,'old Correct fix claim')

    def test_commit_preparation_failure_retains_old_and_blocks_delete(self):
        bank=GapMemory();key=bank.save_knowledge('keep')
        a,req=self.agent([reply([('memory_keep',{'category':'gap','source_ids':['TASK']}),
                                 ('memory_delete',{'memory_id':key})])],bank)
        before=bank.to_dict()
        with patch.object(a.links,'bind_state',side_effect=OSError('injected')):
            r=asyncio.run(a.maintain([],cycle_id='c'))
        self.assertEqual(r['status'],'engineering_error');self.assertEqual(bank.to_dict(),before)
        self.assertFalse(r['operations'][0]['success'])

    def test_original_six_inputs_noop_and_legacy_window_paging(self):
        folder=ROOT/'pma_evidence_review/p1_source_read_delivery/cases'
        for row in json.loads((folder/'INDEX.json').read_text())['cases']:
            with self.subTest(case=row['file']),tempfile.TemporaryDirectory() as tmp:
                case=json.loads((folder/row['file']).read_text());requests=[]
                async def fake(**kw):requests.append(kw);return reply()
                r=asyncio.run(run_case(case,tmp,NS(call=fake),candidate='dms-inspired-v1'))
                self.assertEqual(r['status'],'completed',r);self.assertEqual(len(requests),1)
                self.assertEqual(json.loads((Path(tmp)/'bank_after.json').read_text()),case['initial_bank'])
                if case['entry_sources']:
                    a=build_case(case,Path(tmp)/'other',NS(call=fake),candidate='dms-inspired-v1')
                    a._input('',case['step_count'],a._public_events(case['entries']))
                    key=case['entry_sources'][0]['memory_id'];target=next(v for v in a.frozen_aliases.values() if v.get('id')==key)
                    parts=[];cursor=None
                    for _ in range(100):
                        page=a.links.read(target,a._active_records(),cursor=cursor)
                        parts.extend(page['parts']);cursor=page['next_cursor']
                        self.assertLessEqual(len(json.dumps(page,ensure_ascii=False,separators=(',',':'),sort_keys=True)),8000)
                        if cursor is None:break
                    self.assertTrue(any(p['field']=='legacy_generation_context_not_proof' for p in parts))
                    self.assertFalse(page['complete'])

    def test_checkpoint_representations_reuse_event_and_keep_single_failure(self):
        a,req=self.agent([reply(),reply([('memory_keep',{'category':'procedural','source_ids':['E1']})])])
        row={'event_id':'e','analysis':'Actor claims verified gcda','commands':['checkpoint'],
             'observation':'checkpoint saved, no compiler receipt'}
        asyncio.run(a.maintain([row],cycle_id='c1'));r=asyncio.run(a.maintain([row],cycle_id='c2'))
        self.assertEqual(len(a.links.state['events']),1)
        self.assertIn('previously_presented',req[1]['prompt'])
        page=a.links.read({'kind':'memory','id':r['operations'][0]['memory_id']},a._active_records())
        self.assertIn('Actor claims verified gcda',json.dumps(page))
        self.assertEqual(a.links.state['groups'][r['operations'][0]['memory_id']]['outcome'],'unknown')
        self.assertNotIn('memory_update_status',json.dumps(req[1]['tools']))

    def test_real_client_adapter_three_turn_keep_has_no_free_summary_interface(self):
        from unittest.mock import patch
        from litellm import ModelResponse
        from pma_evidence_review.tools.run_p1_source_case import profile_client
        from pma_evidence_review.tests.test_p1_source_client import simple_case
        case=simple_case();case['entries'][0]['observation']='🙂 raw\r\n  '*8000
        root=Path(self.tmp.name);captured=[]
        async def provider(**kw):
            captured.append(deepcopy(kw))
            if len(captured)==1:
                name,args='memory_read_source',{'memory_id':'E1'}
            elif len(captured)==2:
                rows=[json.loads(x) for x in (root/'source_archive/maintenance.jsonl').read_text().splitlines()]
                prior=[x for x in rows if x['kind']=='response_and_receipts'][-1]
                name,args='memory_read_source',{'memory_id':'E1','cursor':prior['tool_results'][0]['result']['next_cursor']}
            else:
                name,args='memory_keep',{'category':'procedural','source_ids':['E1','T1']}
            return ModelResponse(model='anthropic/claude-opus-4-8',choices=[{'index':0,'finish_reason':'tool_calls',
                'message':{'role':'assistant','content':'','tool_calls':[{'id':'p'+str(len(captured)),'type':'function',
                'function':{'name':name,'arguments':json.dumps(args)}}]}}])
        profile={'provider':'anthropic','api_mode':'messages','model':'claude-opus-4-8','thinking_type':'adaptive',
            'temperature':0.3,'reasoning_effort':'high','apibase':'https://example.invalid','apikey':'synthetic-not-a-secret','max_tokens':2048,'read_timeout':30}
        client=profile_client(profile,root/'client')
        with patch('litellm.acompletion',side_effect=provider):
            result=asyncio.run(run_case(case,root,client,candidate='dms-inspired-v1'))
        self.assertEqual(result['status'],'completed');self.assertEqual(len(captured),3)
        self.assertEqual([len(x['tools']) for x in captured],[3,3,2])
        self.assertEqual(result['reads_used'],2)
        for request in captured:
            self.assertNotIn('memory_update_status',json.dumps(request['tools']))
            self.assertNotIn('memory_save_knowledge',json.dumps(request['tools']))
        self.assertEqual(json.loads((root/'bank_after.json').read_text())['status'],case['initial_bank']['status'])

    def test_keep_after_replace_exception_is_reconciled_and_stops_later_delete(self):
        bank=GapMemory();old=bank.save_knowledge('preserve')
        a,req=self.agent([reply([('memory_keep',{'category':'procedural','source_ids':['TASK']}),
                                 ('memory_delete',{'memory_id':old})])],bank)
        commit=a.links.commit
        def fault(state):
            commit(state)
            if state['groups']:raise OSError('after replace')
        with patch.object(a.links,'commit',side_effect=fault):
            result=asyncio.run(a.maintain([],cycle_id='c'))
        self.assertEqual(result['status'],'engineering_error')
        self.assertEqual(result['operations'][0]['persistence_outcome'],'committed_reconciled_after_error')
        self.assertTrue(result['operations'][0]['success']);self.assertIn(old,a._active_records())
        self.assertEqual(a.links.state['bank'],bank.to_dict())
        self.assertEqual(len(source_identity(candidate='dms-inspired-v1',strict=False)['source_files']),62)

    def test_groups_above_threshold_keep_payload_only_keyword_visible(self):
        a,requests=self.agent([reply([('memory_keep',{'category':'knowledge','source_ids':['E1']}),
                                      ('memory_keep',{'category':'knowledge','source_ids':['E2']})]),reply()])
        a.max_memory_in_prompt=1
        rows=[{'event_id':'first','commands':['NEEDLE_PAYLOAD_ONLY'],'observation':'failure'},
              {'event_id':'second','commands':['unrelated'],'observation':'other'}]
        first=asyncio.run(a.maintain(rows,cycle_id='c1'))
        wanted=first['operations'][0]['memory_id']
        self.assertNotIn('NEEDLE_PAYLOAD_ONLY',a._active_records()[wanted].content)
        self.assertGreater(len(a.memory.knowledge),a.max_memory_in_prompt)
        self.assertFalse(a.use_bm25_prefilter)
        with patch.object(a.memory,'search_knowledge',side_effect=AssertionError('ID BM25 must not run')):
            result=asyncio.run(a.maintain([],observation='NEEDLE_PAYLOAD_ONLY',cycle_id='c2'))
        self.assertEqual(result['status'],'completed')
        self.assertIn('NEEDLE_PAYLOAD_ONLY',requests[1]['prompt'])
        self.assertIn(wanted,requests[1]['prompt'])
        self.assertTrue(any(x.get('id')==wanted for x in a.request_aliases.values()))
        from p1_linked_agent import LinkedSourceP1Agent
        with tempfile.TemporaryDirectory() as other:
            old=LinkedSourceP1Agent(task='old',task_id='old',source_root=other,memory=GapMemory(),
                                    llm=None,use_bm25_prefilter=True,max_memory_in_prompt=1)
            self.assertTrue(old.use_bm25_prefilter)

    def test_legacy_window_wrong_scope_rejected_even_with_matching_digest(self):
        from p1_source_archive import encode,digest
        for bad_field in ('task_id','cycle_id','binding_task','binding_cycle'):
            with self.subTest(field=bad_field),tempfile.TemporaryDirectory() as root:
                bank=GapMemory();key=bank.save_knowledge('legacy')
                async def fake(**kw):return reply([('memory_keep',{'category':'knowledge','source_ids':['M1']})])
                a=DMSP1Agent(task='task',task_id='task',source_root=root,memory=bank,llm=NS(call=fake))
                a.source_archive.capture('old_window','FOREIGN_SENTINEL',[])
                state=deepcopy(a.links.state)
                a.links.bind_state(state,key,'knowledge','legacy',
                    {'sources':[],'inherited_unassociated':[],'association':'legacy_unassociated'},'old_window')
                a.links.commit(state)
                r=asyncio.run(a.maintain([],cycle_id='c1'))
                group=r['operations'][0]['memory_id']
                state=deepcopy(a.links.state);ref=state['legacy_snapshots'][key]['old_source']
                path=a.source_archive.window_path('old_window');window=json.loads(path.read_text())
                if bad_field in ('task_id','cycle_id'):window[bad_field]='other'
                else:ref['task_id' if bad_field=='binding_task' else 'cycle_id']='other'
                raw=encode(window);path.write_text(raw,encoding='utf-8');ref['context_sha256']=digest(raw)
                a.links.commit(state)
                with self.assertRaisesRegex(ValueError,'scope mismatch'):
                    a.links.read({'kind':'memory','id':group},a._active_records())
                a.request_aliases={'M1':{'kind':'memory','id':group,'ref':deepcopy(a.links.state['refs'][group])}}
                report={'read_requests':0,'reads_used':0}
                with self.assertRaisesRegex(ValueError,'scope mismatch'):
                    a._apply({'name':'memory_read_source','arguments':{'memory_id':'M1'}},'unused',0,report)

    def test_forbidden_or_unknown_tool_stops_delete_but_keeps_prior_commit(self):
        bad_calls=[('memory_save_knowledge',{'content':'forbidden prose'}),
                   ('memory_update_status',{'content':'forbidden completion'}),
                   ('file_read',{'path':'not read'})]
        for bad in bad_calls:
            with self.subTest(tool=bad[0]),tempfile.TemporaryDirectory() as root:
                bank=GapMemory();old=bank.save_knowledge('preserve old')
                async def fake(**kw):return reply([('memory_keep',{'category':'knowledge','source_ids':['TASK']}),
                                                   bad,('memory_delete',{'memory_id':old})])
                a=DMSP1Agent(task='task',task_id='task',source_root=root,memory=bank,llm=NS(call=fake))
                result=asyncio.run(a.maintain([],cycle_id='c'))
                self.assertEqual(result['status'],'tool_error')
                self.assertEqual([x['result']['status'] for x in result['turns'][0]['tool_results']],
                                 ['applied','unknown_tool','not_executed_after_forbidden_tool'])
                self.assertIn(old,a._active_records());self.assertEqual(len(bank.knowledge),2)
                self.assertEqual(len(result['operations']),1);self.assertTrue(result['operations'][0]['success'])
                self.assertEqual(a.links.state['bank'],bank.to_dict())
                self.assertIn(bad[0],(Path(root)/'maintenance.jsonl').read_text())
        from p1_linked_agent import LinkedSourceP1Agent
        self.assertFalse(LinkedSourceP1Agent.stop_after_unknown_tool)
