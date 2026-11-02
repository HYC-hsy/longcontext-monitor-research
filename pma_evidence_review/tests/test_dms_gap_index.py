"""Engineering contracts only; scripted selections are not semantic validation."""
import asyncio
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch
from pma_evidence_review.tests.test_bank_display import ROOT, GapMemory, reply
from pma_evidence_review.tests.no_network import install_guard
from pma_evidence_review.tools.run_p1_source_case import candidate_config, run_case, source_identity
from p1_dms_agent import DMSP1Agent, SYSTEM as OLD_SYSTEM
from p1_dms_gap_agent import GapIndexP1Agent, SYSTEM, CANDIDATE, PENDING_MAX_CHARS


class GapIndexTests(unittest.TestCase):
    def setUp(self):
        install_guard(self)
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)

    def agent(self, calls, bank=None):
        requests=[]
        async def fake(**kw):
            requests.append(deepcopy(kw));return reply(calls)
        return GapIndexP1Agent(task='Preserve output requirements.',task_id='task',
            source_root=self.tmp.name,memory=bank or GapMemory(),llm=NS(call=fake)),requests

    def test_gap_required_short_pending_and_other_categories_forbid_it_stop_delete(self):
        invalid=[{'category':'gap','source_ids':['TASK']},
                 {'category':'gap','source_ids':['TASK'],'pending':''},
                 {'category':'gap','source_ids':['TASK'],'pending':' \t'},
                 {'category':'gap','source_ids':['TASK'],'pending':'x'*(PENDING_MAX_CHARS+1)},
                 {'category':[],'source_ids':['TASK']},
                 {'category':'knowledge','source_ids':['TASK'],'pending':'question'},
                 {'category':'procedural','source_ids':['TASK'],'pending':None},
                 {'category':'gap','source_ids':['TASK'],'pending':'question','content':'free body'}]
        for i,args in enumerate(invalid):
            with self.subTest(args=args),tempfile.TemporaryDirectory() as root:
                bank=GapMemory();old=bank.save_knowledge('old fact')
                async def fake(**kw):return reply([('memory_keep',args),('memory_delete',{'memory_id':'M1'})])
                a=GapIndexP1Agent(task='task',task_id='task',source_root=root,memory=bank,llm=NS(call=fake))
                r=asyncio.run(a.maintain([],cycle_id='c'))
                self.assertEqual(r['status'],'tool_error');self.assertIn(old,a._active_records())
                self.assertEqual(r['turns'][0]['tool_results'][0]['result']['status'],'invalid_tool_arguments')
                self.assertTrue(r['turns'][0]['tool_results'][1]['result']['status'].startswith('not_executed'))

    def test_pending_is_typed_in_bank_display_read_pages_and_persistence(self):
        pending='Whether the required output is available in the requested scope.'
        a,requests=self.agent([('memory_keep',{'category':'gap','source_ids':['TASK','E1'],'pending':pending})])
        raw=[{'event_id':'one','commands':['check --scope=local'],'observation':'literal partial result'}]
        r=asyncio.run(a.maintain(raw,cycle_id='c'));self.assertEqual(r['status'],'completed')
        key=r['operations'][0]['memory_id'];index=json.loads(a._active_records()[key].content)
        self.assertEqual(index['pending'],pending);self.assertEqual(index['index_kind'],'generated_unresolved_index_not_fact')
        page=a.links.read({'kind':'memory','id':key},a._active_records())
        self.assertEqual(page['parts'][0]['field'],'generated_unresolved_index_not_fact')
        self.assertEqual(page['parts'][0]['text'],pending)
        self.assertIn('literal partial result',json.dumps(page))
        self.assertLessEqual(len(json.dumps(page,ensure_ascii=False,separators=(',',':'),sort_keys=True)),8000)
        prompt=a._input('',2,[])[0]
        self.assertIn('generated_unresolved_index',prompt);self.assertIn(pending,prompt)
        reopened=GapIndexP1Agent(task=a.task,task_id='task',source_root=self.tmp.name,
            memory=GapMemory.from_dict(a.memory.to_dict()),llm=None)
        self.assertEqual(reopened.links.read({'kind':'memory','id':key},reopened._active_records()),page)
        self.assertEqual(a.memory.status,'');self.assertEqual(requests[0]['system'],SYSTEM)
        self.assertEqual(a.links.state['candidate'],CANDIDATE)
        self.assertTrue(a._valid_keep({'category':'knowledge','source_ids':['TASK']}))
        self.assertTrue(a._valid_keep({'category':'procedural','source_ids':['TASK']}))

    def test_real_tool_path_reads_generated_gap_then_deletes_same_frozen_alias(self):
        a,_=self.agent([('memory_keep',{'category':'gap','source_ids':['TASK'],'pending':'Required format still unconfirmed.'})])
        first=asyncio.run(a.maintain([],cycle_id='first'));key=first['operations'][0]['memory_id']
        responses=[reply([('memory_read_source',{'memory_id':'M1'})]),reply([('memory_delete',{'memory_id':'M1'})])]
        requests=[]
        async def fake(**kw):requests.append(deepcopy(kw));return responses.pop(0)
        a.llm=NS(call=fake);r=asyncio.run(a.maintain([],cycle_id='second'))
        self.assertEqual(r['status'],'completed');self.assertEqual(r['reads_used'],1)
        self.assertEqual(len(requests),2);self.assertIn('generated_unresolved_index_not_fact',requests[1]['prompt'])
        self.assertNotIn(key,a._active_records());self.assertEqual(r['operations'][0]['resolved_memory_id'],key)
        self.assertIn(key,a.links.state['groups']) # inactive index remains diagnostic history

    def test_gap_write_failure_or_invalid_sources_blocks_later_delete_and_reopens_consistently(self):
        bank=GapMemory();old=bank.save_knowledge('retain useful older experience')
        args={'category':'gap','source_ids':['TASK'],'pending':'Required condition unresolved.'}
        a,_=self.agent([('memory_keep',args),('memory_delete',{'memory_id':'M1'})],bank)
        before=bank.to_dict()
        with patch.object(a.links,'bind_state',side_effect=OSError('injected')):
            r=asyncio.run(a.maintain([],cycle_id='fault'))
        self.assertEqual(r['status'],'engineering_error');self.assertEqual(bank.to_dict(),before)
        reopened=GapIndexP1Agent(task=a.task,task_id='task',source_root=self.tmp.name,
            memory=GapMemory.from_dict(bank.to_dict()),llm=None)
        self.assertEqual(reopened.memory.to_dict(),before);self.assertIn(old,reopened._active_records())
        async def fake(**kw):return reply([('memory_keep',{**args,'source_ids':['E99']}),('memory_delete',{'memory_id':'M1'})])
        a.llm=NS(call=fake);r=asyncio.run(a.maintain([],cycle_id='badsource'))
        self.assertEqual(r['status'],'tool_error');self.assertIn(old,a._active_records())

    def test_old_protocol_prompt_and_candidate_storage_are_distinct(self):
        self.assertEqual(hashlib.sha256(OLD_SYSTEM.encode()).hexdigest(),'0450177055b29c30a03fc796466e3f820f5ab6c633e6384bcc49d328afedf826')
        a,_=self.agent([])
        self.assertNotIn('pending',DMSP1Agent.get_tools_schema(a)[0]['function']['parameters']['properties'])
        schema=a.get_tools_schema();self.assertEqual(len(schema),3)
        self.assertEqual(schema[0]['function']['parameters']['required'],['category','source_ids'])
        self.assertIn('pending',schema[0]['function']['parameters']['properties'])
        self.assertFalse(DMSP1Agent._valid_keep(a,{'category':'gap','source_ids':['TASK'],'pending':'question'}))
        self.assertTrue(DMSP1Agent._valid_keep(a,{'category':'gap','source_ids':['TASK']}))
        with self.assertRaises(ValueError):
            DMSP1Agent(task=a.task,task_id='task',source_root=self.tmp.name,memory=GapMemory(),llm=None)
        # Text contract, not a claim about model judgment.
        self.assertIn('its condition is met, its question is answered',SYSTEM)
        self.assertIn('clearly no longer applies',SYSTEM)
        self.assertIn('A failure result may answer what happened',SYSTEM)
        self.assertIs(candidate_config(CANDIDATE)[0],GapIndexP1Agent)
        self.assertEqual(len(source_identity(candidate=CANDIDATE,strict=False)['source_files']),65)

    def test_original_six_inputs_noop_actual_new_requests_and_p2_bytes_unchanged(self):
        folder=ROOT/'pma_evidence_review/p1_source_read_delivery/cases'
        for row in json.loads((folder/'INDEX.json').read_text())['cases']:
            path=folder/row['file'];before=path.read_bytes();case=json.loads(before);requests=[]
            async def fake(**kw):requests.append(deepcopy(kw));return reply()
            with self.subTest(case=row['file']),tempfile.TemporaryDirectory() as tmp:
                r=asyncio.run(run_case(case,tmp,NS(call=fake),candidate=CANDIDATE))
                self.assertEqual(r['status'],'completed');self.assertEqual(len(requests),1)
                self.assertEqual(requests[0]['system'],SYSTEM);self.assertIn(case['task'],requests[0]['prompt'])
                self.assertEqual(json.loads((Path(tmp)/'bank_after.json').read_text()),case['initial_bank'])
                self.assertIn('pending',requests[0]['tools'][0]['function']['parameters']['properties'])
                self.assertEqual(path.read_bytes(),before)
        p='method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/tag_selection_contract.py'
        self.assertEqual((ROOT/p).read_bytes(),subprocess.check_output(['git','show','8d36aca1d2aa5b95ca37e13b445ebdf688356b9c:'+p],cwd=ROOT))

    def test_short_multiline_pending_is_preserved_and_input_tail_has_gap_exception(self):
        text='Required condition\r\nremains unresolved.'
        a,requests=self.agent([('memory_keep',{'category':'gap','source_ids':['TASK'],'pending':text})])
        r=asyncio.run(a.maintain([],cycle_id='multiline'))
        self.assertEqual(r['status'],'completed')
        key=r['operations'][0]['memory_id']
        self.assertEqual(json.loads(a._active_records()[key].content)['pending'],text)
        page=a.links.read({'kind':'memory','id':key},a._active_records())
        self.assertEqual(page['parts'][0]['text'],text)
        self.assertIn('only gap may add a short pending index.',requests[0]['prompt'])
        self.assertNotIn('No new status or conclusions.',requests[0]['prompt'])
        self.assertEqual(DMSP1Agent.input_tail,'\nKeep useful original materials with the three tools. No new status or conclusions.\n')
