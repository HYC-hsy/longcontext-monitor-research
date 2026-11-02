"""Window-local input coverage; no model/provider execution."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from pma_evidence_review.tests.test_bank_display import GapMemory
from pma_evidence_review.tests.no_network import install_guard
from p1_context_agent import ContextSourceP1Agent
from p1_context_history import InputMemoryHistory, HistoryError
from p1_source_archive import encode


class HistoryStoreTests(unittest.TestCase):
    def setUp(self):
        install_guard(self)
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        bank=GapMemory();self.old=bank.save_knowledge('known A')
        self.a=ContextSourceP1Agent(task='task',task_id='t',memory=bank,llm=None,source_root=self.temp.name)
        self.h=InputMemoryHistory(self.a.links,self.a.source_archive)
        self.a.source_archive.capture('origin','A original query\r\n🙂',[])
        state=deepcopy(self.a.links.state)
        self.a.links.bind_state(state,self.old,'knowledge','known A',{
            'sources':[],'inherited_unassociated':[],'association':'legacy_unassociated'},'origin')
        self.a.links.commit(state)

    def child(self, count=1):
        oldref=deepcopy(self.a.links.state['refs'][self.old])
        records=[self.h.record(self.old if i==0 else 'old_'+str(i),'knowledge',
            'known A' if i==0 else '长🙂\r\n'*100,None if i else oldref) for i in range(count)]
        self.a.source_archive.capture('child','A+B generation input',[],
            input_memory_coverage=self.h.coverage(records,[]))
        key=self.a.memory.save_knowledge('A+B summary')
        state=deepcopy(self.a.links.state)
        self.a.links.bind_state(state,key,'knowledge','A+B summary',{
            'sources':[],'inherited_unassociated':[],'association':'unassociated'},'child')
        state['bank']=self.a.memory.to_dict();self.a.links.commit(state)
        return {'kind':'memory','id':key,'ref':deepcopy(state['refs'][key])}

    def test_issued_snapshot_survives_delete_and_reopens(self):
        target=self.child()
        page=self.h.read(target,self.a._active_records())
        self.assertEqual((page['requested_view'],page['resolved_view']),('auto','context'))
        import json
        token=next(json.loads(p['text'])['history_handle'] for p in page['parts'] if p['field']=='input_memory')
        self.assertEqual(self.h.load(token)['memory_id'],self.old)
        self.a.memory.delete(self.old)
        state=deepcopy(self.a.links.state);state['refs'].pop(self.old);state['bank']=self.a.memory.to_dict()
        self.a.links.commit(state)
        read=self.h.read(None,{},handle=token)
        text=''.join(p['text'] for p in read['parts'] if p['field']=='model_input')
        self.assertEqual(text,'A original query\r\n🙂')
        self.assertFalse(read['complete'])
        reopened=ContextSourceP1Agent(task='task',task_id='t',memory=GapMemory.from_dict(self.a.memory.to_dict()),
            llm=None,source_root=self.temp.name)
        self.assertEqual(InputMemoryHistory(reopened.links,reopened.source_archive).load(token)['content'],'known A')
        with self.assertRaises(HistoryError):
            self.h.load(token+'x')

    def test_large_directory_atomic_paging_grants_only_returned_handles(self):
        target=self.child(100)
        fields,pending,_=self.h._directory(target['ref'])
        page=self.h.read(target,self.a._active_records(),requested_view='context')
        self.assertLessEqual(len(encode(page)),8000)
        grants=self.a.links.state['history_grants']
        self.assertLess(len(grants),len(pending))
        not_issued=next(h for h in pending if h not in grants)
        with self.assertRaises(HistoryError):
            self.h.load(not_issued)
        returned=[];cursor=None
        for _ in range(100):
            page=self.h.read(target,self.a._active_records(),requested_view='context',cursor=cursor)
            self.assertLessEqual(len(encode(page)),8000)
            for part in page['parts']:
                if part['field']=='input_memory':
                    self.assertEqual((part['start'],part['end']),(0,part['total']))
                    returned.append(part['source_id'])
            cursor=page['next_cursor']
            if cursor is None:break
        self.assertEqual(len(returned),100)
        self.assertEqual(len(set(returned)),100)
        self.assertEqual(len(self.a.links.state['history_grants']),100)
        self.a.source_archive.window_path('child').write_bytes(b'corrupt')
        with self.assertRaises(HistoryError):
            self.h.load(not_issued)


class HistoryAgentTests(unittest.TestCase):
    def setUp(self):
        import asyncio
        from types import SimpleNamespace as NS
        from pma_evidence_review.tests.test_bank_display import reply
        install_guard(self)
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.responses=[];self.requests=[]
        async def fake(**kwargs):
            self.requests.append(deepcopy(kwargs))
            value=self.responses.pop(0)
            return value() if callable(value) else value
        bank=GapMemory();self.old=bank.save_knowledge('known A')
        self.a=ContextSourceP1Agent(task='task',task_id='t',memory=bank,llm=NS(call=fake),source_root=self.temp.name)
        self.a.source_archive.capture('manual_origin','A original query receipt\r\n🙂',[])
        state=deepcopy(self.a.links.state)
        self.a.links.bind_state(state,self.old,'knowledge','known A',{
            'sources':[],'inherited_unassociated':[],'association':'legacy_unassociated'},'manual_origin')
        self.a.links.commit(state)
        self.reply=reply

    def maintain(self, cycle, entries=()):
        import asyncio
        result=asyncio.run(self.a.maintain(list(entries),cycle_id=cycle))
        self.assertNotEqual(result['status'],'engineering_error',result)
        return result

    def prime(self):
        self.a._input('',0,[])
        self.a.request_aliases=deepcopy(self.a.frozen_aliases)

    def read(self, value, **kwargs):
        return self.a._apply({'name':'memory_read_source','arguments':{'memory_id':value,**kwargs}},
            'unused',0,{'operations':[],'read_requests':0,'reads_used':0})

    def handle(self, receipt, memory_id):
        import json
        return next(json.loads(p['text'])['history_handle'] for p in receipt['parts']
                    if p['field']=='input_memory' and json.loads(p['text'])['memory_id']==memory_id)

    def make_summary(self):
        self.responses.append(self.reply([
            ('memory_save_knowledge',{'content':'A+B summary','source_ids':['E1']}),
            ('memory_delete',{'memory_id':'M1'})]))
        result=self.maintain('summarize',[{'event_id':'B','observation':'B receipt'}])
        self.assertEqual(result['status'],'completed')
        self.assertNotIn(self.old,self.a._active_records())
        return result['operations'][0]['memory_id']

    def test_auto_fallback_strict_views_and_integrity_are_distinct(self):
        self.prime()
        auto=self.read('M1');strict=self.read('M1',view='sources');context=self.read('M1',view='context')
        self.assertEqual((auto['requested_view'],auto['resolved_view']),('auto','context'))
        self.assertEqual(auto['fallback_reason'],'no_linked_sources')
        self.assertEqual(auto['status'],'context_complete')
        self.assertEqual(strict['status'],'source_unassociated')
        self.assertEqual(strict['parts'],[])
        self.assertEqual(context['resolved_view'],'context')
        self.assertFalse(auto['complete'])
        self.assertEqual(auto['input_memory_coverage'],'unrecorded')
        self.a.source_archive.window_path('manual_origin').write_bytes(b'corrupt')
        self.assertEqual(self.read('M1')['status'],'source_binding_error')

    def test_selected_b_keeps_deleted_a_source_and_accepts_handle_citation(self):
        summary=self.make_summary()
        token=None
        def read_history():
            nonlocal token
            page=self.a.last_p1_report['turns'][0]['tool_results'][0]['result']
            self.assertEqual(page['resolved_view'],'sources')
            self.assertEqual(page['source_count'],1)
            self.assertFalse(any(p['field']=='model_input' for p in page['parts']))
            self.assertTrue(any(p['field']=='observation' and p['text']=='B receipt' for p in page['parts']))
            token=self.handle(page,self.old)
            return self.reply([('memory_read_source',{'memory_id':token})])
        def cite_history():
            page=self.a.last_p1_report['turns'][1]['tool_results'][0]['result']
            self.assertEqual(page['historical_memory_id'],self.old)
            self.assertEqual(page['resolved_view'],'context')
            self.assertEqual(''.join(p['text'] for p in page['parts'] if p['field']=='model_input'),
                             'A original query receipt\r\n🙂')
            self.assertEqual(page['input_memory_coverage'],'unrecorded')
            return self.reply([('memory_save_gap',{'content':'condition remains','source_ids':[token]})])
        self.responses.extend([self.reply([('memory_read_source',{'memory_id':summary})]),read_history,cite_history])
        result=self.maintain('consume')
        self.assertEqual((result['status'],result['reads_used'],result['continuations_used']),('completed',2,2))
        self.assertEqual(len(result['turns']),3)
        self.assertEqual(len(self.requests[-1]['tools']),5)
        self.assertEqual(result['turns'][1]['tool_calls'][0]['arguments'],{'memory_id':token})
        gap=result['operations'][0]['memory_id']
        self.assertIn(self.old,self.a.links.state['refs'][gap]['inherited_unassociated'])
        import json
        window=json.loads(self.a.source_archive.window_path('consume_r2').read_bytes())
        self.assertIn(token,window['input_memory_coverage']['read_handles'])
        self.assertEqual(window['model_input'],self.requests[-1]['prompt'])

    def test_historical_snapshot_ignores_same_id_replacement_and_prefilter(self):
        from unittest.mock import patch
        summary=self.make_summary();self.prime()
        token=self.handle(self.read(summary),self.old)
        self.a.memory.save_knowledge('new A content');self.a.memory.knowledge[-1].id=self.old
        self.a.source_archive.capture('new_origin','new A receipt',[])
        state=deepcopy(self.a.links.state)
        self.a.links.bind_state(state,self.old,'knowledge','new A content',{
            'sources':[],'inherited_unassociated':[],'association':'unassociated'},'new_origin')
        state['bank']=self.a.memory.to_dict();self.a.links.commit(state)
        self.a.use_bm25_prefilter=True;self.a.max_memory_in_prompt=1
        shown=next(r for r in self.a.memory.knowledge if r.id==summary)
        with patch.object(type(self.a.memory),'search_knowledge',return_value=[shown]), \
                patch.object(type(self.a.memory),'search_procedural',return_value=[]):
            self.prime()
        self.assertEqual(self.read(self.old)['status'],'source_not_displayed')
        page=self.read(token)
        self.assertEqual(''.join(p['text'] for p in page['parts'] if p['field']=='model_input'),
                         'A original query receipt\r\n🙂')
        self.assertEqual(self.a._active_records()[self.old].content,'new A content')

    def test_handles_reject_foreign_tampered_unissued_collision_and_delete(self):
        summary=self.make_summary();self.prime();token=self.handle(self.read(summary),self.old)
        self.assertEqual(self.read(token+'x')['status'],'invalid_history_handle')
        before=deepcopy(self.a.memory.to_dict())
        invalid=self.a._apply({'name':'memory_save_knowledge','arguments':{
            'content':'must not save','source_ids':['H1.'+'0'*64]}},'unused',0,
            {'operations':[],'read_requests':0,'reads_used':0})
        self.assertEqual(invalid['status'],'invalid_source_ids')
        self.assertEqual(self.a.memory.to_dict(),before)
        from p1_context_history import InputMemoryHistory
        with tempfile.TemporaryDirectory() as root:
            other=ContextSourceP1Agent(task='other task',task_id='other',memory=GapMemory(),llm=None,source_root=root)
            other.links.state['history_grants']=deepcopy(self.a.links.state['history_grants'])
            other.links.state['secret']=self.a.links.state['secret']
            with self.assertRaises(HistoryError) as error:
                InputMemoryHistory(other.links,other.source_archive).load(token)
            self.assertEqual(error.exception.status,'invalid_history_handle')
        self.responses.append(self.reply([('memory_delete',{'memory_id':token}),
                                         ('memory_save_gap',{'content':'must not execute'})]))
        result=self.maintain('readonly')
        self.assertEqual(result['status'],'tool_error')
        self.assertEqual([r['result']['status'] for r in result['turns'][0]['tool_results']],
                         ['historical_read_only','not_executed_after_tool_failure'])
        self.assertEqual(len(self.a.gaps.entries),0)
        self.a.memory.knowledge[0].id=token;self.prime()
        self.assertEqual(self.read(token)['status'],'ambiguous_memory_id')
        rejected=self.a._apply({'name':'memory_delete','arguments':{'memory_id':token}},'unused',0,
            {'operations':[],'read_requests':0,'reads_used':0})
        self.assertEqual(rejected['status'],'ambiguous_memory_id')

    def test_claimed_missing_source_does_not_trigger_context_fallback(self):
        state=deepcopy(self.a.links.state)
        state['refs'][self.old]['sources']=[{'source_id':'missing_event','via':'selected'}]
        self.a.links.commit(state);self.prime()
        page=self.read('M1')
        self.assertEqual((page['status'],page['resolved_view']),('source_missing','sources'))
        self.assertIsNone(page['fallback_reason'])
        self.assertFalse(page['complete'])

    def test_history_and_active_reads_share_budget_and_final_write_turn(self):
        summary=self.make_summary();token=None
        def mixed_reads():
            nonlocal token
            page=self.a.last_p1_report['turns'][0]['tool_results'][0]['result']
            token=self.handle(page,self.old)
            return self.reply([('memory_read_source',{'memory_id':value})
                               for value in (token,summary,token,token)])
        def finish():
            return self.reply([('memory_save_gap',{'content':'still unanswered','source_ids':[token]})])
        self.responses.extend([self.reply([('memory_read_source',{'memory_id':summary})]),mixed_reads,finish])
        result=self.maintain('budget')
        self.assertEqual(result['status'],'budget_limited')
        self.assertEqual((result['reads_used'],result['read_requests'],result['continuations_used']),(4,5,2))
        self.assertEqual(result['turns'][1]['tool_results'][-1]['result']['status'],'budget_exhausted')
        self.assertEqual(len(self.requests[-1]['tools']),5)
        self.assertEqual(len(self.a.gaps.entries),1)

    def test_history_long_text_and_cursor_request_scope_are_lossless(self):
        original='\r\n🙂中文\t"\\'*6000
        self.a.source_archive.capture('long_origin',original,[])
        state=deepcopy(self.a.links.state)
        self.a.links.bind_state(state,self.old,'knowledge','known A',{
            'sources':[],'inherited_unassociated':[],'association':'legacy_unassociated'},'long_origin')
        self.a.links.commit(state)
        summary=self.make_summary();self.prime();token=self.handle(self.read(summary),self.old)
        helper=self.a.history
        first=helper.read(None,{},handle=token)
        self.assertIsNotNone(first['next_cursor'])
        wrong=helper.read(None,{},handle=token,requested_view='context',cursor=first['next_cursor'])
        self.assertEqual(wrong['status'],'invalid_cursor')
        target=self.a.request_aliases['M1']
        wrong=helper.read(target,self.a._active_records(),cursor=first['next_cursor'])
        self.assertEqual(wrong['status'],'invalid_cursor')
        text=[];cursor=None
        for _ in range(100):
            page=helper.read(None,{},handle=token,cursor=cursor)
            self.assertLessEqual(len(encode(page)),8000)
            text.extend(p['text'] for p in page['parts'] if p['field']=='model_input')
            self.assertFalse(page['semantic_verification_performed'])
            cursor=page['next_cursor']
            if cursor is None:
                self.assertTrue(page['page_sequence_complete']);break
        self.assertEqual(''.join(text),original)
        with self.assertRaises(HistoryError):
            helper.read(None,{},handle=token,requested_view='auto')
