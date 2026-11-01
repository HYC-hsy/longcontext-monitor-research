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
            self.assertIn('Previous maintenance turn',json.loads(a.source_archive.window_path('c1_r1').read_text())['model_input'])
            self.assertTrue(source['presented_source_receipts'])
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

    def test_private_reasoning_and_signature_fields_are_never_read_or_logged(self):
        class VisibleReply:
            content='visible text'
            tool_calls=[]
            @property
            def reasoning_content(self):
                raise AssertionError('hidden reasoning was accessed')
            @property
            def signature(self):
                raise AssertionError('signature was accessed')
        with tempfile.TemporaryDirectory() as tmp:
            a,_=self.agent(tmp,[VisibleReply()])
            result=asyncio.run(a.maintain([],cycle_id='c1'))
            self.assertEqual(result['status'],'completed')
            self.assertEqual(result['turns'][0]['assistant_text'],'visible text')
            self.assertNotIn('reasoning_content',(Path(tmp)/'maintenance.jsonl').read_text())

    def test_structured_read_delete_ids_win_over_body_tool_tags(self):
        with tempfile.TemporaryDirectory() as tmp:
            bank=GapMemory();key=bank.save_knowledge('old fact')
            first=reply([('memory_read_source',{'memory_id':key}),('memory_delete',{'memory_id':key})],
                '<tool_call><name>memory_save_knowledge</name><content>BODY MUST NOT EXECUTE</content></tool_call>')
            first.tool_calls[0].id='provider-read';first.tool_calls[1].id='provider-delete'
            a,req=self.agent(tmp,[first,reply()],bank)
            result=asyncio.run(a.maintain([],cycle_id='c1'))
            self.assertEqual(result['status'],'completed')
            calls=result['turns'][0]['tool_calls']
            self.assertEqual([c['tool_call_id'] for c in calls],['provider-read','provider-delete'])
            self.assertEqual([c['name'] for c in calls],['memory_read_source','memory_delete'])
            self.assertEqual(bank.knowledge,[])
            self.assertNotIn('BODY MUST NOT EXECUTE',str(result['operations']))

    def test_association_failure_restores_save_and_stops_later_delete(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            bank=GapMemory(max_status_length=3000);key=bank.save_knowledge('keep original')
            bank.status='s'*2500
            before=bank.to_dict()
            a,req=self.agent(tmp,[reply([('memory_save_knowledge',{'content':'replacement'}),
                ('memory_delete',{'memory_id':key})])],bank)
            with patch.object(a.source_archive,'bind',side_effect=OSError('disk unavailable')):
                result=asyncio.run(a.maintain([],cycle_id='c1'))
            self.assertEqual(result['status'],'engineering_error')
            self.assertIs(a.memory,bank);self.assertEqual(bank.to_dict(),before)
            self.assertEqual(bank._max_status_length,3000)
            receipts=result['turns'][0]['tool_results']
            self.assertTrue(receipts[0]['result']['save_rolled_back'])
            self.assertEqual(receipts[1]['result']['status'],'not_executed_after_engineering_failure')
            self.assertFalse(result['operations'][0]['success'])
            self.assertEqual(len(req),1)

    def test_continuation_source_keeps_already_returned_read_without_following_old_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            bank=GapMemory();old=bank.save_knowledge('old scoped fact')
            a,_=self.agent(tmp,[reply([('memory_read_source',{'memory_id':old})]),
                reply([('memory_save_knowledge',{'content':'new scoped fact'})])],bank)
            old_events=[{'event_id':'old-event','presentation':'historical_visible_event',
                'commands':['query --old-scope A'], 'observation':json.dumps({'content':'Actor claim',
                'tool_results':[{'tool_use_id':'old-tool','content':'OLD RAW RECEIPT A=50'}]})}]
            a.source_archive.capture('origin','Original scoped input',old_events)
            a.source_archive.bind(old,'knowledge','old scoped fact','origin')
            result=asyncio.run(a.maintain([{'event_id':'current','commands':['other command'],
                'observation':'long current context '*2000}],cycle_id='c1'))
            self.assertEqual(result['status'],'completed')
            new=bank.knowledge[-1].id
            captured=json.loads(a.source_archive.window_path('c1_r1').read_text())
            expected=result['turns'][0]['tool_results'][0]['result']
            self.assertEqual(captured['presented_source_receipts'][0]['receipt'],expected)
            a.source_archive.window_path('origin').unlink()
            source=json.loads(a.source_archive.read(new,a._active_records()))
            self.assertIn('OLD RAW RECEIPT A=50',json.dumps(source))
            self.assertTrue(source['presented_source_receipts'])
            self.assertIn('not_new_observation',source['presented_source_receipts'][0]['role'])
