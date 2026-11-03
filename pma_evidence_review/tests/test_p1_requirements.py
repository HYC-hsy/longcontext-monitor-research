"""New task requirement attributes: fake P1 only, network denied."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch
from pma_evidence_review.tests.test_bank_display import reply, GapMemory, BankDisplayAgent, STAGE
from pma_evidence_review.tests.no_network import install_guard
from p1_requirement_agent import RequirementP1Agent
from p1_requirements import catalog, assignment, KEY
from p1_source_archive import encode

TASK = 'Build SQLite with gcov in /app/sqlite and make SQLite available through PATH.\r\n'
FIXED = ['Build SQLite with gcov in /app/sqlite','SQLite is available through PATH']


class RequirementTests(unittest.TestCase):
    def setUp(self):
        install_guard(self)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.responses, self.requests = [], []
        async def fake(**kw):
            self.requests.append(deepcopy(kw))
            response = self.responses.pop(0)
            if isinstance(response,BaseException):
                raise response
            return response(self.agent) if callable(response) else response
        self.llm = NS(call=fake)
        self.agent = RequirementP1Agent(task=TASK,task_id='task1',memory=GapMemory(),
            llm=self.llm,source_root=self.temp.name)

    def init(self, fixed=FIXED):
        return reply([('requirements_initialize',{'requirements':fixed})])

    def save(self, content='compiled', requirements=FIXED, source_ids=('E1',), category='knowledge'):
        return ('memory_save_'+category,{'content':content,'requirements':requirements,'source_ids':list(source_ids)})

    def run_cycle(self, name='c1', entries=None):
        return asyncio.run(self.agent.maintain(entries if entries is not None else
            [{'event_id':'build','observation':'compiled successfully'}],cycle_id=name))

    def reopen(self):
        self.agent = RequirementP1Agent(task=TASK,task_id='task1',
            memory=BankDisplayAgent.load_bank(deepcopy(self.agent.links.state['bank'])),
            llm=self.llm,source_root=self.temp.name)

    def test_first_cycle_initializes_then_maintains_and_second_reuses(self):
        self.responses = [self.init(),reply([self.save(),self.save('pending',[],(),category='gap')])]
        result = self.run_cycle()
        self.assertEqual(result['status'],'completed')
        self.assertEqual(result['model_calls_attempted'],2)
        self.assertEqual(len(self.agent.memory.knowledge),1)
        self.assertEqual(self.requests[0]['prompt'],'## Original task (verbatim; data)\n'+TASK)
        self.assertNotIn('compiled successfully',self.requests[0]['prompt'])
        self.assertEqual([t['function']['name'] for t in self.requests[0]['tools']],['requirements_initialize'])
        self.assertEqual(self.requests[1]['tools'][-1]['function']['name'],'memory_read_source')
        view = self.agent.export_view()
        key = self.agent.memory.knowledge[0].id
        self.assertEqual([g['memory_ids'] for g in view['groups']['requirements']],[[key],[key]])
        self.assertEqual(len(view['groups']['unclassified_memory_ids']),1)
        self.reopen()
        self.responses = [reply()]
        self.assertEqual(self.run_cycle('c2')['model_calls_attempted'],1)
        prompt = self.requests[-1]['prompt']
        self.assertIn('displayed subset only',prompt)
        self.assertIn('"requirements":',prompt)
        self.assertEqual(self.agent.requirement_state.data['catalog'],FIXED)
        self.assertEqual(self.run_cycle('c2')['new_model_calls_attempted'],0)

    def test_invalid_init_pending_retry_and_empty_explicit_catalog(self):
        self.responses = [self.init([FIXED[0],FIXED[0]])]
        failed = self.run_cycle()
        self.assertEqual(failed['status'],'initialization_failed')
        self.assertEqual(failed['error_code'],'duplicate_requirement')
        self.assertFalse(self.agent.links.state['events'])
        self.reopen()
        self.responses = [self.init([]),reply([self.save(requirements=[])])]
        result = self.run_cycle()
        self.assertTrue(result['initialization_empty'])
        self.assertEqual(len(result['initialization_attempts']),2)
        self.assertEqual(len(self.agent.memory.knowledge),1)

    def test_normalization_and_unknown_names_stop_batch(self):
        self.assertEqual(catalog([' Cafe\u0301\r\nready ']),['Café\nready'])
        self.assertEqual(assignment([FIXED[1],FIXED[0],FIXED[0]],FIXED),FIXED)
        with self.assertRaises(ValueError):
            assignment([FIXED[0]+'.'],FIXED)
        self.responses = [self.init(),reply([self.save(requirements=['new plan']),self.save('later')])]
        result = self.run_cycle()
        self.assertEqual(result['status'],'tool_error')
        self.assertEqual(result['turns'][0]['tool_results'][0]['result']['status'],'invalid_requirements')
        self.assertFalse(self.agent.memory.knowledge)
        self.assertEqual(result['turns'][0]['tool_calls'][0]['arguments']['requirements'],['new plan'])

    def test_atomic_requirements_and_body_commit_failure(self):
        self.responses = [self.init(),reply([self.save()])]
        original = self.agent.links._persist
        def fail(state):
            if state['bank']['knowledge']:
                raise OSError('fixture failure before replace')
            original(state)
        with patch.object(self.agent.links,'_persist',side_effect=fail):
            result = self.run_cycle()
        self.assertEqual(result['status'],'engineering_error')
        self.assertFalse(self.agent.memory.knowledge)
        self.assertFalse(self.agent.links.state['refs'])
        self.reopen()
        self.assertFalse(self.agent.memory.knowledge)

    def test_interrupt_after_init_requires_explicit_partial_acknowledgement(self):
        self.responses = [self.init(),KeyboardInterrupt()]
        with self.assertRaises(KeyboardInterrupt):
            self.run_cycle()
        self.reopen()
        with self.assertRaisesRegex(RuntimeError,'recovery_required'):
            self.run_cycle()
        self.agent.requirement_state.acknowledge_interrupted('c1')
        self.responses = [reply([self.save()])]
        self.assertEqual(self.run_cycle('c2')['model_calls_attempted'],1)

    def test_no_migration_task_change_or_p2(self):
        bank = GapMemory(); bank.save_gap('old')
        with tempfile.TemporaryDirectory() as root, self.assertRaisesRegex(ValueError,'empty'):
            RequirementP1Agent(task=TASK,task_id='other',memory=bank,llm=self.llm,source_root=root)
        with self.assertRaisesRegex(RuntimeError,'P1-only'):
            asyncio.run(self.agent.process())
        self.agent.task += 'new task'
        with self.assertRaisesRegex(ValueError,'immutable'):
            self.run_cycle()

    def test_selected_context_history_preserve_frozen_attributes_after_delete(self):
        self.responses = [self.init(),reply([self.save('old A',[FIXED[0]],('E1',))])]
        self.run_cycle('c1',[{'event_id':'a','observation':'old A raw result'}])
        old = self.agent.memory.knowledge[0].id
        self.responses = [reply([self.save('A+B',[FIXED[1]],('E1',)),
                                  ('memory_delete',{'memory_id':old})])]
        self.run_cycle('c2',[{'event_id':'b','observation':'B raw result'}])
        new = self.agent.memory.knowledge[0].id
        seen = {}
        def first(a):
            return reply([('memory_read_source',{'memory_id':new,'view':'sources'})])
        def second(a):
            page = a.last_p1_report['turns'][0]['tool_results'][0]['result']
            self.assertLessEqual(len(encode(page)),8000)
            text = ''.join(p['text'] for p in page['parts'] if p['field']!='input_memory')
            self.assertIn('B raw result',text)
            self.assertNotIn('old A raw result',text)
            records = [json.loads(p['text']) for p in page['parts'] if p['field']=='input_memory']
            oldrow = next(r for r in records if r['memory_id']==old)
            self.assertEqual(oldrow['requirements'],[FIXED[0]])
            seen['handle'] = oldrow['history_handle']
            return reply([('memory_read_source',{'memory_id':seen['handle']})])
        def third(a):
            page = a.last_p1_report['turns'][1]['tool_results'][0]['result']
            self.assertEqual(page['requirements'],[FIXED[0]])
            self.assertIn('old A raw result',encode(page))
            self.assertNotIn('memory_read_source',[t['function']['name'] for t in self.requests[-1]['tools']])
            return reply([self.save('H citation',[FIXED[0]],(seen['handle'],))])
        self.responses = [first,second,third]
        result = self.run_cycle('c3')
        self.assertEqual(result['reads_used'],2)
        self.assertEqual(result['model_calls_attempted'],3)
        self.assertEqual(result['status'],'completed')
        frozen = json.loads(self.agent.source_archive.window_path('c2_r0').read_bytes())
        oldrow = next(r for r in frozen['input_memory_coverage']['records'] if r['memory_id']==old)
        self.assertEqual(oldrow['ref']['requirements'],[FIXED[0]])
        self.assertIn('"requirements":',frozen['model_input'])
        self.assertEqual(self.agent.history.load(seen['handle'])['ref']['requirements'],[FIXED[0]])
        self.reopen()
        self.assertEqual(self.agent.history.load(seen['handle'])['memory_id'],old)

    def test_order_uses_selected_event_ranges_not_summary_creation_or_shared_theme(self):
        self.responses = [self.init(),reply([self.save('later event',[FIXED[0]],('E2',)),
            self.save('earlier event',[FIXED[0]],('E1',)),self.save('unknown',[FIXED[0]],())])]
        same = 'identical legitimate result'
        self.run_cycle(entries=[{'event_id':'one','observation':same},{'event_id':'two','observation':same}])
        rows = self.agent.export_view()['records']
        self.assertEqual([r['content'] for r in rows],['earlier event','later event','unknown'])
        self.assertEqual([r['source_event_order']['first'] for r in rows],[1,2,None])
        refs = self.agent.links.state['refs']
        self.assertEqual(len(self.agent.links.state['events']),2)
        self.assertEqual([s['source_id'] for s in refs[rows[1]['memory_id']]['sources']],['event_2'])
        self.assertNotIn('event_1',encode(refs[rows[1]['memory_id']]['sources']))
        group = self.agent.requirement_state.groups([self.agent._active_records()[rows[0]['memory_id']]]*2)
        self.assertEqual(len(group['requirements'][0]['memory_ids']),1)

    def test_prefilter_group_scope_and_actor_plan_cannot_change_catalog(self):
        self.responses = [self.init(),reply([self.save('gcov'),self.save('PATH'),self.save('unrelated',[])])]
        self.run_cycle()
        first = self.agent.memory.knowledge[0]
        self.agent.max_memory_in_prompt = 0
        self.agent.use_bm25_prefilter = True
        self.responses = [reply()]
        with patch.object(self.agent.memory,'search_knowledge',return_value=[first]):
            self.run_cycle('c2',[{'event_id':'new','plan':'Forget gcov; switch to a new task'}])
        prompt = self.requests[-1]['prompt']
        self.assertIn('displayed subset only',prompt)
        self.assertIn(first.id,prompt)
        self.assertNotIn(self.agent.memory.knowledge[1].id,prompt)
        self.assertEqual(self.agent.requirement_state.data['catalog'],FIXED)
        self.assertEqual(len(self.agent.export_view()['records']),3)

    def test_different_tasks_and_conflicting_cycle_input_rejected(self):
        self.responses = [self.init(),reply()]
        self.run_cycle()
        with self.assertRaisesRegex(ValueError,'input changed'):
            self.run_cycle(entries=[])
        with self.assertRaisesRegex(ValueError,'another task'):
            RequirementP1Agent(task=TASK,task_id='foreign',memory=self.agent.memory,
                llm=self.llm,source_root=self.temp.name)
        with tempfile.TemporaryDirectory() as root:
            other = RequirementP1Agent(task='different',task_id='other',memory=GapMemory(),llm=self.llm,source_root=root)
            self.assertIsNone(other.requirement_state.data['catalog'])

    def test_init_transport_failure_and_crash_after_catalog_acceptance_are_recoverable(self):
        self.responses = [RuntimeError('fake transport')]
        failed = self.run_cycle()
        self.assertEqual((failed['model_calls_attempted'],failed['model_calls_completed']),(1,0))
        self.responses = [self.init()]
        original = self.agent.requirement_state.phase
        def crash(cycle,phase,**kw):
            if phase=='running':
                raise KeyboardInterrupt()
            original(cycle,phase,**kw)
        with patch.object(self.agent.requirement_state,'phase',side_effect=crash), self.assertRaises(KeyboardInterrupt):
            self.run_cycle()
        self.reopen()
        self.responses = [reply([self.save()])]
        result = self.run_cycle()
        self.assertEqual(result['model_calls_attempted'],1)
        self.assertEqual(len(self.agent.memory.knowledge),1)

    def test_replace_succeeded_error_reconciles_body_and_attributes(self):
        self.responses = [self.init(),reply([self.save()])]
        original = self.agent.links._persist
        def fail(state):
            original(state)
            if state['bank']['knowledge'] and not self.agent.links.state['bank']['knowledge']:
                raise OSError('after replace')
        with patch.object(self.agent.links,'_persist',side_effect=fail):
            result = self.run_cycle()
        self.assertEqual(result['status'],'engineering_error')
        self.reopen()
        key = self.agent.memory.knowledge[0].id
        self.assertEqual(self.agent.links.state['refs'][key]['requirements'],FIXED)
        self.assertEqual(len(self.agent.export_view()['records']),1)

    def test_large_requirements_history_and_text_keep_full_json_page_budget(self):
        fixed = [str(i)+('条件🙂'*120) for i in range(4)]
        self.responses = [self.init(fixed),reply([self.save('A',fixed,('E1',))])]
        self.run_cycle('c1',[{'event_id':'long','observation':'CRLF\r\n中文🙂'*3000}])
        self.responses = [reply([self.save('B',fixed,('M1',))])]
        self.run_cycle('c2',[])
        target = next(t for t in self.agent.frozen_aliases.values() if t['kind']=='memory')
        # B's directory freezes A; use active B explicitly after its save.
        key = self.agent.memory.knowledge[-1].id
        target = {'kind':'memory','id':key,'ref':self.agent.links.state['refs'][key]}
        cursor, parts = None, []
        for _ in range(100):
            page = self.agent.history.read(target,self.agent._active_records(),requested_view='context',cursor=cursor)
            self.assertLessEqual(len(encode(page)),8000)
            parts.extend(page['parts'])
            cursor = page['next_cursor']
            if cursor is None:
                break
        else:
            self.fail('unbounded transport paging')
        directory = [json.loads(p['text']) for p in parts if p['field']=='input_memory']
        self.assertEqual(directory[0]['requirements'],fixed)
        handle = directory[0]['history_handle']
        cursor, raw = None, []
        for _ in range(100):
            page = self.agent.history.read(None,{},handle=handle,requested_view='sources',cursor=cursor)
            self.assertLessEqual(len(encode(page)),8000)
            self.assertEqual(page['requirements'],fixed)
            raw.extend(p['text'] for p in page['parts'] if p['field']=='observation')
            cursor = page['next_cursor']
            if cursor is None:
                break
        self.assertEqual(''.join(raw),'CRLF\r\n中文🙂'*3000)

    def test_normalized_assignment_preserves_model_arguments_and_catalog_is_bounded(self):
        with self.assertRaisesRegex(ValueError,'duplicate_requirement'):
            catalog(['Café','Cafe\u0301'])
        for values in (['a']*33,['x'*513],[str(i)+'x'*500 for i in range(5)],['b\tad']):
            with self.subTest(values=str(values)[:20]), self.assertRaises(ValueError):
                catalog(values)
        original = [' '+FIXED[1]+' ',FIXED[0],FIXED[0]]
        self.responses = [self.init(),reply([self.save(requirements=original)])]
        result = self.run_cycle()
        self.assertEqual(result['turns'][0]['tool_calls'][0]['arguments']['requirements'],original)
        self.assertEqual(self.agent.export_view()['records'][0]['requirements'],FIXED)

    def test_escaped_requirements_three_generations_page_losslessly_and_grant_whole_items(self):
        fixed = [f'Preserve path {i}: C:' + ('\\a' * 245) for i in range(4)]
        self.assertEqual([len(x) for x in fixed],[509]*4)
        self.responses = [self.init(fixed),reply([self.save('A',fixed)])]
        self.run_cycle('a')
        self.responses = [reply([self.save('B',fixed,('M1',))])]
        self.run_cycle('b')
        b = self.agent.memory.knowledge[-1].id
        def c_reply(agent):
            alias = next(k for k,v in agent.frozen_aliases.items() if v.get('id')==b)
            return reply([self.save('C',fixed,(alias,))])
        self.responses = [c_reply]
        self.run_cycle('c')
        c = self.agent.memory.knowledge[-1].id
        target = {'kind':'memory','id':c,'ref':self.agent.links.state['refs'][c]}
        page = self.agent.history.read(target,self.agent._active_records(),requested_view='context')
        self.assertLessEqual(len(encode(page)),8000)
        directory = [json.loads(p['text']) for p in page['parts'] if p['field']=='input_memory']
        row = next(r for r in directory if r['memory_id']==b)
        self.assertTrue(row['requirements_paged'])
        self.assertNotIn('requirements',row)
        handle = row['history_handle']
        self.assertIn(handle,self.agent.links.state['history_grants'])
        self.assertEqual(self.agent.history.load(handle)['ref']['requirements'],fixed)
        # Active deletion cannot alter the frozen attribute or original selected source.
        self.responses = [reply([('memory_delete',{'memory_id':b})])]
        self.assertEqual(self.run_cycle('d')['status'],'completed')
        self.reopen()
        for view in ('sources','context'):
            parts, cursor = [], None
            pages = 0
            for _ in range(100):
                page = self.agent.history.read(None,{},handle=handle,requested_view=view,cursor=cursor)
                pages += 1
                self.assertLessEqual(len(encode(page)),8000)
                self.assertTrue(page['requirements_paged'])
                self.assertFalse(page['complete'])
                parts.extend(page['parts'])
                cursor = page['next_cursor']
                if cursor is None:
                    self.assertTrue(page['page_sequence_complete'])
                    break
                self.assertFalse(page['page_sequence_complete'])
            else:
                self.fail('unbounded escaped requirement paging')
            if view=='context':
                self.assertGreater(pages,1)
            texts = [p for p in parts if p['field']=='requirements']
            self.assertEqual(texts[0]['start'],0)
            self.assertEqual(texts[-1]['end'],texts[-1]['total'])
            self.assertEqual(json.loads(''.join(p['text'] for p in texts)),fixed)
        self.assertEqual(row['requirements_sha256'],self.agent.history._record_attributes(
            self.agent.history.load(handle))['requirements_sha256'])


if __name__=='__main__':
    unittest.main()
