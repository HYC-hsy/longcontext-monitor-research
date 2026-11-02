"""Window-local input coverage; no model/provider execution."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from pma_evidence_review.tests.test_bank_display import GapMemory
from pma_evidence_review.tests.no_network import install_guard
from p1_dms_gap_agent import GapIndexP1Agent
from p1_context_history import InputMemoryHistory, HistoryError
from p1_source_archive import encode


class HistoryStoreTests(unittest.TestCase):
    def setUp(self):
        install_guard(self)
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        bank=GapMemory();self.old=bank.save_knowledge('known A')
        self.a=GapIndexP1Agent(task='task',task_id='t',memory=bank,llm=None,source_root=self.temp.name)
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
        reopened=GapIndexP1Agent(task='task',task_id='t',memory=GapMemory.from_dict(self.a.memory.to_dict()),
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


class DMSHistoryAgentTests(unittest.TestCase):
    def setUp(self):
        import asyncio
        from types import SimpleNamespace as NS
        from pma_evidence_review.tests.test_bank_display import reply
        install_guard(self)
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.responses=[];self.requests=[];self.reply=reply
        async def fake(**kwargs):
            self.requests.append(deepcopy(kwargs));value=self.responses.pop(0)
            return value() if callable(value) else value
        bank=GapMemory();self.old=bank.save_knowledge('known A, earlier failed attempt')
        self.a=GapIndexP1Agent(task='task',task_id='t',memory=bank,llm=NS(call=fake),source_root=self.temp.name)
        self.a.source_archive.capture('origin','A original query receipt\r\n🙂',[])
        state=deepcopy(self.a.links.state)
        self.a.links.bind_state(state,self.old,'knowledge',bank.knowledge[0].content,
            {'sources':[],'inherited_unassociated':[],'association':'legacy_unassociated'},'origin')
        self.a.links.commit(state)

    def maintain(self, cycle, rows=()):
        import asyncio
        return asyncio.run(self.a.maintain(list(rows),cycle_id=cycle))

    def prime(self):
        self.a._input('',0,[]);self.a.request_aliases=deepcopy(self.a.frozen_aliases)

    def read(self, token, cursor=None):
        return self.a._apply({'name':'memory_read_source','arguments':{'memory_id':token,**({'cursor':cursor} if cursor else {})}},
            'unused',0,{'operations':[],'read_requests':0,'reads_used':0})

    def handle(self, page, memory_id):
        import json
        return next(json.loads(p['text'])['history_handle'] for p in page['parts']
                    if p['field']=='input_memory' and json.loads(p['text'])['memory_id']==memory_id)

    def make_group(self):
        self.responses.append(self.reply([('memory_keep',{'category':'procedural','source_ids':['E1']}),
                                          ('memory_delete',{'memory_id':'M1'})]))
        result=self.maintain('group',[{'event_id':'B','commands':['run B'], 'observation':'B receipt '+'x'*30000}])
        self.assertEqual(result['status'],'completed',result)
        self.assertNotIn(self.old,self.a._active_records())
        return result['operations'][0]['memory_id']

    def test_unselected_deleted_record_directory_precedes_long_sources_and_reopens(self):
        import json
        group=self.make_group();self.prime()
        page=self.read(group);token=self.handle(page,self.old)
        self.assertEqual(page['source_count'],1)
        self.assertFalse(page['complete']);self.assertIn('not claim support',page['input_memory_scope'])
        self.assertEqual(page['parts'][0]['field'],'input_memory')
        self.assertLessEqual(len(encode(page)),8000)
        window=json.loads(self.a.source_archive.window_path('group_r0').read_bytes())
        self.assertEqual([r['memory_id'] for r in window['input_memory_coverage']['records']],[self.old])
        self.assertEqual(window['model_input'],self.requests[0]['prompt'])
        history=self.read(token)
        self.assertTrue(history['historical']);self.assertEqual(history['historical_memory_id'],self.old)
        self.assertIn('known A, earlier failed attempt',encode(history))
        self.assertEqual(''.join(p['text'] for p in history['parts'] if p['field']=='legacy_generation_context_not_proof'),
                         'A original query receipt\r\n🙂')
        reopened=GapIndexP1Agent(task='task',task_id='t',memory=GapMemory.from_dict(self.a.memory.to_dict()),
            llm=None,source_root=self.temp.name)
        self.assertEqual(reopened.history.load(token)['memory_id'],self.old)
        self.assertEqual(reopened.history.read(None,{},handle=token),self.a.history.read(None,{},handle=token))
        self.assertEqual([s['source_id'] for s in self.a.links.state['refs'][group]['sources']],['event_1'])

    def test_three_turn_real_protocol_carries_read_handle_coverage_not_support(self):
        import json
        group=self.make_group();token=None
        def read_old():
            nonlocal token
            page=self.a.last_p1_report['turns'][0]['tool_results'][0]['result']
            token=self.handle(page,self.old)
            return self.reply([('memory_read_source',{'memory_id':token})])
        def keep_pending():
            page=self.a.last_p1_report['turns'][1]['tool_results'][0]['result']
            self.assertEqual(page['historical_memory_id'],self.old)
            return self.reply([('memory_keep',{'category':'gap','source_ids':['TASK',token],'pending':'Required condition remains open.'})])
        self.responses.extend([self.reply([('memory_read_source',{'memory_id':group})]),read_old,keep_pending])
        result=self.maintain('consume')
        self.assertEqual((result['status'],result['reads_used'],result['continuations_used']),('completed',2,2))
        self.assertEqual(len(self.requests[-1]['tools']),2)
        window=json.loads(self.a.source_archive.window_path('consume_r2').read_bytes())
        self.assertEqual(window['input_memory_coverage']['read_handles'],[token])
        key=result['operations'][0]['memory_id']
        self.assertEqual([s['source_id'] for s in self.a.links.state['refs'][key]['sources']],['TASK','legacy:'+self.old])
        self.assertIn(self.old,self.a.links.state['refs'][key]['inherited_unassociated'])
        self.assertIn('H1 handles may be read or cited',self.requests[-1]['system'])

    def test_deleted_gap_read_retains_typed_pending_and_legacy_material(self):
        self.responses.append(self.reply([('memory_keep',{'category':'gap','source_ids':['M1','TASK'],
            'pending':'Output availability\r\nstill unconfirmed.'})]))
        first=self.maintain('gap');gap=first['operations'][0]['memory_id']
        self.responses.append(self.reply([('memory_keep',{'category':'knowledge','source_ids':['E1']}),
                                          ('memory_delete',{'memory_id':gap})]))
        result=self.maintain('new',[{'event_id':'next','observation':'new result'}]);self.assertEqual(result['status'],'completed')
        current=result['operations'][0]['memory_id'];self.prime()
        token=self.handle(self.read(current),gap)
        self.a.links.state['groups'][gap]['pending']='Changed current metadata must not rewrite history.'
        page=self.read(token)
        pending=[p for p in page['parts'] if p['field']=='generated_unresolved_index_not_fact']
        self.assertEqual(pending[0]['text'],'Output availability\r\nstill unconfirmed.')
        self.assertIn('known A, earlier failed attempt',encode(page))
        self.assertNotIn(gap,self.a._active_records())
        self.responses.append(self.reply([('memory_keep',{'category':'knowledge','source_ids':[token]})]))
        kept=self.maintain('cite-old-gap');self.assertEqual(kept['status'],'completed')
        key=kept['operations'][0]['memory_id']
        inherited=self.a.links.state['refs'][key]['inherited_pending_indices']
        self.assertEqual(inherited[0]['pending'],'Output availability\r\nstill unconfirmed.')
        self.assertEqual(inherited[0]['kind'],'generated_unresolved_index_not_fact')
        direct=self.a.links.read({'kind':'memory','id':key},self.a._active_records())
        self.assertTrue(any(p['field']=='inherited_generated_unresolved_index_not_fact' for p in direct['parts']))

    def test_history_errors_stop_later_changes_and_do_not_allow_selection_or_delete(self):
        group=self.make_group();self.prime();token=self.handle(self.read(group),self.old)
        from p1_context_history import HistoryError
        for name,args in [('memory_delete',{'memory_id':token}),
                          ('memory_read_source',{'memory_id':token+'x'}),
                          ('memory_keep',{'category':'knowledge','source_ids':[token+'x']})]:
            with self.subTest(name=name):
                before=self.a.memory.to_dict()
                self.responses.append(self.reply([(name,args),('memory_delete',{'memory_id':group})]))
                result=self.maintain(name)
                self.assertEqual(result['status'],'tool_error')
                self.assertEqual(self.a.memory.to_dict(),before)
                self.assertTrue(result['turns'][0]['tool_results'][1]['result']['status'].startswith('not_executed'))
        with tempfile.TemporaryDirectory() as root:
            other=GapIndexP1Agent(task='different',task_id='foreign',memory=GapMemory(),llm=None,source_root=root)
            other.links.state['history_grants']=deepcopy(self.a.links.state['history_grants'])
            other.links.state['secret']=self.a.links.state['secret']
            with self.assertRaises(HistoryError):other.history.load(token)
        self.a.source_archive.window_path('group_r0').write_bytes(b'corrupted')
        self.responses.append(self.reply([('memory_read_source',{'memory_id':token}),('memory_delete',{'memory_id':group})]))
        result=self.maintain('corrupt')
        self.assertEqual(result['status'],'engineering_error');self.assertIn(group,self.a._active_records())

    def test_unlinked_historical_status_is_typed_and_failed_save_leaves_no_snapshot(self):
        from unittest.mock import patch
        self.a.memory.status='Actor claimed completion, not independent verification.'
        group=self.make_group();self.prime();token=self.handle(self.read(group),'STATUS')
        before=self.a.memory.to_dict();snapshots=deepcopy(self.a.links.state['legacy_snapshots'])
        self.responses.append(self.reply([('memory_keep',{'category':'knowledge','source_ids':[token]}),
                                          ('memory_delete',{'memory_id':group})]))
        with patch.object(self.a.links,'bind_state',side_effect=OSError('injected snapshot bind failure')):
            result=self.maintain('failed-history-keep')
        self.assertEqual(result['status'],'engineering_error');self.assertEqual(self.a.memory.to_dict(),before)
        self.assertEqual(self.a.links.state['legacy_snapshots'],snapshots)
        self.responses.append(self.reply([('memory_keep',{'category':'knowledge','source_ids':[token]})]))
        result=self.maintain('typed-status');self.assertEqual(result['status'],'completed')
        key=result['operations'][0]['memory_id'];ref=self.a.links.state['refs'][key]
        self.assertIn('STATUS',ref['inherited_unassociated'])
        page=self.a.links.read({'kind':'memory','id':key},self.a._active_records())
        self.assertTrue(any(p['field']=='historical_derived_status_not_fact' for p in page['parts']))
        self.assertFalse(page['complete'])
