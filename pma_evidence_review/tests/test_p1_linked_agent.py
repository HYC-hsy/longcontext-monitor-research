"""Fake-client P1 lifecycle; no claims about semantic selection quality."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch
from pma_evidence_review.tests.test_bank_display import reply, GapMemory
from pma_evidence_review.tests.no_network import install_guard
from p1_linked_agent import LinkedSourceP1Agent, READ_LIMIT, CONTINUATION_LIMIT
from p1_source_links import SourceLinks


class LinkedAgentTests(unittest.TestCase):
    def setUp(self):
        install_guard(self)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def agent(self, responses, bank=None):
        calls=[]
        async def fake(**kwargs):
            calls.append(deepcopy(kwargs))
            result=responses.pop(0)
            return result() if callable(result) else result
        a=LinkedSourceP1Agent(task='task',task_id='task1',source_root=self.temp.name,
                              memory=bank or GapMemory(),llm=NS(call=fake))
        return a,calls

    def test_source_save_status_delete_and_frozen_aliases(self):
        bank=GapMemory(); old=bank.save_knowledge('old')
        a,req=self.agent([reply([('memory_save_knowledge',{'content':'first','source_ids':['E1','TASK']}),
            ('memory_save_procedural',{'content':'inherited legacy','source_ids':['M1']}),
            ('memory_delete',{'memory_id':old}),
            ('memory_save_gap',{'content':'still legacy','source_ids':['M1']}),
            ('memory_update_status',{'content':'progress','source_ids':['E1']})])],bank)
        r=asyncio.run(a.maintain([{'event_id':'e','commands':['run'],'observation':'done'}],cycle_id='c'))
        self.assertEqual(r['status'],'completed')
        self.assertEqual(len(req),1)
        self.assertNotIn(old,a._active_records())
        refs=a.links.state['refs']
        self.assertEqual(refs['STATUS']['sources'][0]['source_id'],'event_1')
        gaps=[v for v in refs.values() if v['category']=='gap']
        self.assertEqual(gaps[0]['inherited_unassociated'],[old])
        self.assertEqual(len(a.links.state['events']),1)
        window=json.loads(a.source_archive.window_path('c_r0').read_text())
        self.assertEqual(set(window['visible_events'][0]),{'event_id','presentation'})
        self.assertEqual(window['raw_generation_context']['events'][0]['commands'],['run'])
        self.assertEqual(a.links.state['bank'],bank.to_dict())
        self.assertEqual(a.frozen_aliases['M1']['id'],old)
        a.llm=NS(call=lambda **kw:None)
        a._input('',2,[])
        self.assertNotEqual(a.frozen_aliases['M1']['id'],old)
        reopened=LinkedSourceP1Agent(task='task',task_id='task1',source_root=self.temp.name,
            memory=GapMemory.from_dict(bank.to_dict()),llm=None)
        self.assertEqual(reopened.links.state,a.links.state)

    def test_three_turn_cursor_continuation_and_final_write_only(self):
        a=None
        def second():
            page=a.last_p1_report['turns'][0]['tool_results'][0]['result']
            self.assertFalse(page['complete'])
            return reply([('memory_read_source',{'memory_id':'E1','cursor':page['next_cursor']})])
        a,req=self.agent([reply([('memory_read_source',{'memory_id':'E1'})]),second,
                         reply([('memory_save_gap',{'content':'partial remains','source_ids':['E1']})])])
        r=asyncio.run(a.maintain([{'event_id':'e','commands':['long'],'observation':'\t🙂 x\n'*9000}],cycle_id='c'))
        self.assertEqual(r['status'],'completed')
        self.assertEqual((len(req),r['reads_used'],r['continuations_used']),(3,2,2))
        self.assertEqual([len(x['tools']) for x in req],[6,6,5])
        self.assertIn('Final turn',req[2]['prompt'])
        self.assertEqual((READ_LIMIT,CONTINUATION_LIMIT),(4,2))
        self.assertEqual(len(a.gaps.entries),1)
        log=[json.loads(x) for x in (Path(self.temp.name)/'maintenance.jsonl').read_text().splitlines()]
        aliases=[x['source_aliases'] for x in log if x['kind']=='request']
        self.assertEqual(aliases[0],aliases[1]);self.assertEqual(aliases[1],aliases[2])

    def test_four_read_budget_is_reported_not_semantic_rejection(self):
        a,req=self.agent([reply([('memory_read_source',{'memory_id':'TASK'})]*5),reply()])
        r=asyncio.run(a.maintain([],cycle_id='c'))
        self.assertEqual((r['reads_used'],r['read_requests'],len(req)),(4,5,2))
        self.assertEqual(r['status'],'budget_limited')
        self.assertEqual(len(req[1]['tools']),5)
        self.assertTrue(r['turns'][0]['tool_results'][-1]['result']['unread_remainder'])

    def test_failure_before_and_after_atomic_replace_never_leaves_ghost_binding(self):
        for after in (False,True):
            with self.subTest(after=after),tempfile.TemporaryDirectory() as root:
                bank=GapMemory(); old=bank.save_knowledge('keep')
                async def fake(**kw):
                    return reply([('memory_save_knowledge',{'content':'new','source_ids':['TASK']}),
                                  ('memory_delete',{'memory_id':old})])
                a=LinkedSourceP1Agent(task='task',task_id='task1',source_root=root,memory=bank,llm=NS(call=fake))
                original=a.links.commit
                def fault(state):
                    if len(state['bank']['knowledge'])>1:
                        if after: original(state)
                        raise OSError('injected write error')
                    original(state)
                with patch.object(a.links,'commit',side_effect=fault):
                    r=asyncio.run(a.maintain([],cycle_id='c'))
                self.assertEqual(r['status'],'engineering_error')
                self.assertIn(old,a._active_records())
                outcome='committed_reconciled_after_error' if after else 'not_committed_reconciled'
                self.assertEqual(r['operations'][0]['persistence_outcome'],outcome)
                self.assertEqual(r['operations'][0]['success'],after)
                self.assertEqual(r['turns'][0]['tool_results'][-1]['result']['status'],'not_executed_after_engineering_failure')
                reopened=SourceLinks(root,task_id='task1',task='task',bank=bank.to_dict())
                self.assertEqual(reopened.state['bank'],bank.to_dict())
                self.assertEqual(set(reopened.state['refs']),set(a._active_records())-{old})

    def test_unknown_future_sources_no_write_and_unknown_tool_no_retry(self):
        a,req=self.agent([reply([('memory_save_gap',{'content':'bad','source_ids':['E99']}),
                                ('file_read',{'path':'secret'})])])
        r=asyncio.run(a.maintain([],cycle_id='c'))
        self.assertEqual(r['status'],'tool_error')
        self.assertEqual([x['result']['status'] for x in r['turns'][0]['tool_results']],['invalid_source_ids','not_executed_after_invalid_source_ids'])
        self.assertEqual(len(req),1);self.assertEqual(r['operations'],[])
        self.assertEqual(a.memory.to_dict(),a.links.state['bank'])

    def test_inherited_events_survive_old_delete_read_is_readonly_and_new_ids_not_sources(self):
        a,req=self.agent([reply([('memory_save_knowledge',{'content':'old','source_ids':['E1']})])])
        asyncio.run(a.maintain([{'event_id':'e','commands':['run'],'observation':'receipt'}],cycle_id='c1'))
        old=a.memory.knowledge[0].id
        a.llm=NS(call=None)
        responses=[reply([('memory_save_knowledge',{'content':'replacement','source_ids':['M1','E1']}),
                          ('memory_delete',{'memory_id':old})])]
        async def second(**kwargs):
            return responses.pop(0)
        a.llm=NS(call=second)
        asyncio.run(a.maintain([{'event_id':'e','commands':['run'],'observation':'receipt'}],cycle_id='c2'))
        new=a.memory.knowledge[0].id
        self.assertNotEqual(old,new)
        ref=a.links.state['refs'][new]
        self.assertEqual(len(ref['sources']),1)
        self.assertEqual(ref['sources'][0]['inherited_from'],[old])
        before=deepcopy(a.links.state)
        page=a.links.read({'kind':'memory','id':new},a._active_records())
        self.assertTrue(page['complete'])
        self.assertIn('receipt',json.dumps(page))
        self.assertEqual(a.links.state,before)
        self.assertEqual(a.links.read({'kind':'memory','id':old},a._active_records())['status'],'entry_not_found')
        self.assertEqual(len(a.links.state['events']),1)
        self.assertNotIn(new,a.request_aliases)

    def test_legacy_and_empty_sources_are_explicit_and_state_truncation_bound_to_actual_text(self):
        bank=GapMemory();key=bank.save_knowledge('legacy')
        a,req=self.agent([reply([('memory_read_source',{'memory_id':'M1'})]),reply()],bank)
        r=asyncio.run(a.maintain([],cycle_id='c1'))
        page=r['turns'][0]['tool_results'][0]['result']
        self.assertEqual(page['association'],'legacy_unassociated')
        self.assertEqual(page['source_count'],0)
        self.assertEqual(page['status'],'source_unrecorded')
        self.assertFalse(page['complete'])
        self.assertEqual(bank.knowledge[0].id,key)
        async def write(**kw):
            return reply([('memory_update_status',{'content':'x'*5000,'source_ids':[]})])
        a.llm=NS(call=write)
        asyncio.run(a.maintain([],cycle_id='c2'))
        from p1_source_archive import digest
        self.assertEqual(a.links.state['refs']['STATUS']['content_sha256'],digest(a.memory.status))
        self.assertEqual(a.links.state['refs']['STATUS']['association'],'unassociated')

    def test_continuation_cannot_treat_new_save_as_previously_shown_M_alias(self):
        a,req=self.agent([reply([('memory_save_knowledge',{'content':'new','source_ids':['TASK']}),
                                 ('memory_read_source',{'memory_id':'TASK'})]),
                         reply([('memory_save_procedural',{'content':'bad reference','source_ids':['M1']})])])
        r=asyncio.run(a.maintain([],cycle_id='c'))
        self.assertEqual(len(req),2)
        self.assertNotIn('M1',a.request_aliases)
        self.assertEqual(r['turns'][1]['tool_results'][0]['result']['status'],'invalid_source_ids')
        self.assertEqual(len(a.memory.knowledge),1)
        self.assertEqual(len(a.memory.procedural),0)

    def test_invalid_source_save_stops_following_delete_of_old_knowledge(self):
        bank=GapMemory();old=bank.save_knowledge('preserve old')
        a,req=self.agent([reply([('memory_save_knowledge',{'content':'replacement','source_ids':['E99']}),
                                ('memory_delete',{'memory_id':old})])],bank)
        r=asyncio.run(a.maintain([],cycle_id='c'))
        self.assertEqual(r['status'],'tool_error')
        self.assertEqual(r['operations'],[])
        self.assertIn(old,a._active_records())
        self.assertEqual(r['turns'][0]['tool_results'][1]['result']['status'],'not_executed_after_invalid_source_ids')
        self.assertEqual(a.links.state['bank'],bank.to_dict())

    def test_unknown_tool_alone_is_rejected_without_extra_call(self):
        a,req=self.agent([reply([('file_read',{'path':'not opened'})])])
        r=asyncio.run(a.maintain([],cycle_id='c'))
        self.assertEqual(r['status'],'tool_error')
        self.assertEqual(r['turns'][0]['tool_results'][0]['result']['status'],'unknown_tool')
        self.assertEqual(len(req),1)

    def test_status_changed_in_same_request_is_not_silently_read_as_new_source(self):
        a,req=self.agent([reply([('memory_update_status',{'content':'new','source_ids':['TASK']}),
                                 ('memory_read_source',{'memory_id':'STATUS'})]),reply()])
        r=asyncio.run(a.maintain([],cycle_id='c'))
        page=r['turns'][0]['tool_results'][1]['result']
        self.assertEqual(page['status'],'source_changed')
        self.assertTrue(page['refresh_required'])
        self.assertNotIn('parts',page)

    def test_status_write_failure_is_reconciled_with_prior_binding(self):
        a,req=self.agent([reply([('memory_update_status',{'content':'prior','source_ids':['TASK']})])])
        asyncio.run(a.maintain([],cycle_id='c1'))
        before=deepcopy(a.links.state)
        async def fake(**kwargs):
            return reply([('memory_update_status',{'content':'replacement','source_ids':[]})])
        a.llm=NS(call=fake)
        commit=a.links.commit
        def fail(state):
            if state['bank']['status']=='replacement':
                raise OSError('status fail')
            commit(state)
        with patch.object(a.links,'commit',side_effect=fail):
            r=asyncio.run(a.maintain([],cycle_id='c2'))
        self.assertEqual(r['status'],'engineering_error')
        self.assertEqual(a.memory.status,'prior')
        self.assertEqual(a.links.state['refs']['STATUS'],before['refs']['STATUS'])

    def test_replacement_argument_and_underlying_failures_stop_later_delete(self):
        methods={'memory_save_knowledge':'save_knowledge','memory_save_procedural':'save_procedural',
                 'memory_save_gap':'save_gap','memory_update_status':'update_status'}
        for tool,method in methods.items():
            for cause in ('arguments','operation'):
                with self.subTest(tool=tool,cause=cause),tempfile.TemporaryDirectory() as root:
                    bank=GapMemory();old=bank.save_knowledge('preserve')
                    async def fake(**kwargs):
                        args={'content':42} if cause=='arguments' else {'content':'replacement','source_ids':['TASK']}
                        return reply([(tool,args),('memory_delete',{'memory_id':old})])
                    a=LinkedSourceP1Agent(task='task',task_id='task1',source_root=root,memory=bank,llm=NS(call=fake))
                    before=bank.to_dict()
                    if cause=='operation':
                        with patch.object(bank,method,side_effect=ValueError('injected write failure')):
                            result=asyncio.run(a.maintain([],cycle_id='c'))
                    else:
                        result=asyncio.run(a.maintain([],cycle_id='c'))
                    self.assertEqual(result['status'],'tool_error')
                    self.assertEqual(bank.to_dict(),before)
                    self.assertEqual(a.links.state['bank'],before)
                    self.assertIn(old,a._active_records())
                    self.assertEqual(result['turns'][0]['tool_results'][1]['result']['status'],'not_executed_after_failed_write')

    def test_binding_preparation_failure_is_not_reported_as_committed(self):
        bank=GapMemory();old=bank.save_knowledge('keep old')
        a,req=self.agent([reply([('memory_save_knowledge',{'content':'new','source_ids':['TASK']}),
                                ('memory_delete',{'memory_id':old})])],bank)
        before=bank.to_dict()
        with patch.object(a.links,'bind_state',side_effect=OSError('window read failed before binding')):
            result=asyncio.run(a.maintain([],cycle_id='c'))
        self.assertEqual(result['status'],'engineering_error')
        self.assertEqual(result['operations'][0]['persistence_outcome'],'not_committed_reconciled')
        self.assertFalse(result['operations'][0]['success'])
        self.assertEqual(bank.to_dict(),before)
        self.assertEqual(a.links.state['bank'],before)
        self.assertEqual(a.links.state['refs'],{})
        self.assertEqual(result['turns'][0]['tool_results'][1]['result']['status'],'not_executed_after_engineering_failure')
