"""P1-only scripted protocol tests. Preset edits do not establish semantic gains."""
import asyncio
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace as NS
import unittest

from pma_evidence_review.tests.test_bank_display import STAGE, reply, GapMemory
from pma_evidence_review.tests.no_network import install_guard
from p1_source_agent import SourceReadP1Agent, READ_TOOL
from p1_source_archive import encode
from gap_memory_agent import GAP_TOOL
from memory_agent.memory.memory_agent import BANK_TOOLS


class P1SourceAgentTests(unittest.TestCase):
    def setUp(self):
        install_guard(self)

    def agent(self, root, responses, bank=None):
        requests=[]
        async def fake(**kw):
            requests.append(deepcopy(kw))
            if not responses:
                raise AssertionError('extra model/P2 call')
            value=responses.pop(0)
            if isinstance(value,Exception):
                raise value
            return value
        a=SourceReadP1Agent(source_root=root,task_id='t1',task='Original full task',
            memory=bank, llm=NS(call=fake))
        return a,requests

    def test_unchanged_tools_plus_only_one_read_tool_and_no_p2_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,_=self.agent(tmp,[])
            self.assertEqual(a.get_tools_schema(),BANK_TOOLS+[GAP_TOOL,READ_TOOL])
            with self.assertRaises(RuntimeError):
                asyncio.run(a.process('no P2'))
            root=STAGE.parents[2]
            for name in ('bank_display_agent.py','tag_selection_contract.py','verbatim_selection_mixin.py','selection_context.py'):
                path=(STAGE/name).relative_to(root).as_posix()
                self.assertEqual((root/path).read_bytes(),subprocess.check_output(
                    ['git','show','bf96f6442032594c56308bf5cb477d0b03e64b33:'+path],cwd=root))

    def test_noop_is_one_p1_call_zero_writes_and_window_saved(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,req=self.agent(tmp,[reply()])
            before=a.memory.to_dict()
            result=asyncio.run(a.maintain([{'event_id':'e1','commands':['run --x 1'],'observation':'receipt'}],cycle_id='c1'))
            self.assertEqual(result['status'],'completed');self.assertEqual(len(req),1)
            self.assertEqual(result['operations'],[]);self.assertEqual(before,a.memory.to_dict())
            self.assertEqual(len(list((Path(tmp)/'windows').glob('*.json'))),1)
            self.assertIn('new_event',req[0]['prompt'])
            self.assertNotIn('Task-relevant gaps in visible checks',req[0]['system'])

    def test_read_then_new_id_replace_has_faithful_receipt_and_continuation_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            bank=GapMemory();old=bank.save_knowledge('old scoped fact')
            first=reply([('memory_read_source',{'memory_id':old})]);first.tool_calls[0].id='provider-call-7'
            a,req=self.agent(tmp,[first,reply([('memory_save_knowledge',{'content':'corrected fact'}),
                                             ('memory_delete',{'memory_id':old})])],bank)
            a.source_archive.capture('original','RAW ACTION --scope local; RAW RECEIPT',[])
            a.source_archive.bind(old,'knowledge','old scoped fact','original')
            result=asyncio.run(a.maintain([{'event_id':'e2','observation':'new visible result'}],cycle_id='c1'))
            self.assertEqual(result['status'],'completed');self.assertEqual(len(req),2)
            self.assertEqual(result['reads_used'],1);self.assertEqual(result['continuations_used'],1)
            self.assertEqual(req[1]['tools'],BANK_TOOLS+[GAP_TOOL])
            self.assertIn('provider-call-7',req[1]['prompt']);self.assertIn('RAW ACTION --scope local',req[1]['prompt'])
            self.assertEqual([r.content for r in bank.knowledge],['corrected fact'])
            new=bank.knowledge[0].id;self.assertNotEqual(old,new)
            self.assertEqual(a.source_archive.refs[new]['cycle_id'],'c1_r1')
            source=json.loads(a.source_archive.read(new,a._active_records()))
            self.assertIn('Previous maintenance turn',source['source_text'])
            self.assertEqual(json.loads(a.source_archive.read(old,a._active_records()))['status'],'entry_not_found')
            self.assertTrue(a.source_archive.window_path('original').exists())

    def test_two_reads_then_budget_receipt_one_continuation_no_semantic_veto(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,req=self.agent(tmp,[reply([('memory_read_source',{'memory_id':'absent'})]*3),
                reply([('memory_update_status',{'content':'Next step remains a plan'})])])
            result=asyncio.run(a.maintain([],cycle_id='c1'))
            statuses=[x['result']['status'] for x in result['turns'][0]['tool_results']]
            self.assertEqual(statuses,['entry_not_found','entry_not_found','budget_exhausted'])
            self.assertEqual((len(req),result['reads_used'],result['read_requests']), (2,2,3))
            self.assertEqual(result['status'],'budget_limited')
            self.assertEqual(a.memory.status,'Next step remains a plan')

    def test_unadvertised_second_turn_read_has_no_third_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,req=self.agent(tmp,[reply([('memory_read_source',{'memory_id':'absent'})]),
                reply([('memory_read_source',{'memory_id':'absent'})])])
            result=asyncio.run(a.maintain([],cycle_id='c1'))
            self.assertEqual(len(req),2)
            self.assertEqual(result['turns'][1]['tool_results'][0]['result']['status'],'continuation_unavailable')
            self.assertEqual(result['status'],'budget_limited')

    def test_repeat_marker_different_execution_same_output_and_raw_pairing(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,req=self.agent(tmp,[reply(),reply()])
            rows=[{'event_id':'e1','commands':['run --x 1'],'observation':'same output'}]
            asyncio.run(a.maintain(rows,cycle_id='c1'))
            rows += [{'event_id':'e2','commands':['run --x 2'],'observation':'same output'}]
            asyncio.run(a.maintain(rows,cycle_id='c2'))
            self.assertIn('previously_presented',req[1]['prompt']);self.assertIn('new_event',req[1]['prompt'])
            self.assertIn('run --x 1',req[1]['prompt']);self.assertIn('run --x 2',req[1]['prompt'])
            self.assertEqual(req[1]['prompt'].count('same output'),2)

    def test_legacy_without_source_is_not_false_and_reads_do_not_mutate_bank(self):
        with tempfile.TemporaryDirectory() as tmp:
            bank=GapMemory();key=bank.save_gap('unverified condition')
            a,req=self.agent(tmp,[reply([('memory_read_source',{'memory_id':key})]),reply()],bank)
            before=bank.to_dict();result=asyncio.run(a.maintain([],cycle_id='c1'))
            self.assertEqual(result['turns'][0]['tool_results'][0]['result']['status'],'source_unrecorded')
            self.assertEqual(result['status'],'completed');self.assertEqual(bank.to_dict(),before)

    def test_engineering_error_and_task_mismatch_are_not_semantic_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,req=self.agent(tmp,[RuntimeError('transport stopped')])
            result=asyncio.run(a.maintain([],cycle_id='c1'))
            self.assertEqual(result['status'],'engineering_error');self.assertEqual(len(req),1)
            self.assertEqual(result['operations'],[])
            a.task='other'
            with self.assertRaises(ValueError):
                asyncio.run(a.maintain([],cycle_id='c2'))
