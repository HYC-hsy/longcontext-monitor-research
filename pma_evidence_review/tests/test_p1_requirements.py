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
from p1_context_agent import ContextSourceP1Agent

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
        general = self.agent.memory.entries[0].id
        self.assertEqual([g['requirement'] for g in view['groups']['requirements']], FIXED+['General'])
        self.assertEqual([g['memory_ids'] for g in view['groups']['requirements']],[[key],[key],[general]])
        self.assertEqual(view['groups']['unclassified_memory_ids'],[])
        self.assertEqual(self.agent.links.state['refs'][general]['requirements'],['General'])
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
        self.assertIn('gcov',prompt)
        self.assertNotIn('"content":"PATH"',prompt)
        self.assertNotIn('memory_id',prompt)
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

    def test_candidate_schema_forbids_extra_fields_and_keeps_all_save_enums(self):
        self.responses = [self.init(),reply([self.save()])]
        self.run_cycle()
        tools = self.agent.get_tools_schema()
        for tool in tools:
            schema = tool['function']['parameters']
            self.assertIs(schema['additionalProperties'],False)
            if tool['function']['name'].startswith('memory_save_'):
                self.assertEqual(schema['properties']['requirements']['items']['enum'],FIXED)
        self.responses = [reply([('memory_update_status',{'content':'bad extra','unexpected':True}),self.save('later')])]
        result = self.run_cycle('bad_fields')
        self.assertEqual(result['status'],'tool_error')
        self.assertEqual(len(self.agent.memory.knowledge),1)
        self.assertEqual(self.agent.memory.status,'')

    def test_model_receipts_separate_transport_from_semantics_and_keep_raw_logs(self):
        self.responses = [self.init(),reply([self.save()])]
        self.run_cycle('seed')
        response = reply([('memory_read_source',{'memory_id':'M1'})])
        response.usage = NS(prompt_tokens=333,completion_tokens=7)
        def next_turn(agent):
            prompt = self.requests[-1]['prompt']
            history = json.loads(prompt.split('## Previous P1 calls and receipts (historical data)\n',1)[1].split('\nContinue from exact receipts;',1)[0])
            self.assertEqual(set(history[0]),{'assistant_text','tool_calls','tool_results'})
            receipt = history[0]['tool_results'][0]['result']
            self.assertTrue(receipt['page_sequence_complete'])
            self.assertEqual(receipt['status'],'source_complete')
            self.assertNotIn('complete',receipt)
            self.assertFalse(receipt['semantic_verification_performed'])
            return reply()
        self.responses = [response,next_turn]
        result = self.run_cycle('read')
        logged = result['turns'][0]
        self.assertIs(logged['tool_results'][0]['result']['complete'],False)
        self.assertEqual(logged['usage']['prompt_tokens'],333)

    def test_new_saved_id_is_not_readable_or_deletable_until_next_cycle(self):
        self.responses = [self.init(),reply([self.save('starting')])]
        self.run_cycle('seed')
        saved_ids = []
        for index,operation in enumerate(('memory_read_source','memory_delete')):
            def attempt_new_target(agent):
                saved_ids.append(agent.memory.knowledge[-1].id)
                return reply([(operation,{'memory_id':saved_ids[-1]})])
            self.responses = [reply([self.save('new this cycle '+str(index)),
                ('memory_read_source',{'memory_id':'M1'})]),attempt_new_target]
            result = self.run_cycle('new_target_'+str(index))
            self.assertEqual(result['turns'][1]['tool_results'][0]['result']['status'],'source_not_displayed')
            self.assertIn(saved_ids[-1],self.agent._active_records())
        self.responses = [reply([('memory_delete',{'memory_id':key}) for key in saved_ids])]
        self.assertEqual(self.run_cycle('next_cycle')['status'],'completed')
        self.assertTrue(all(key not in self.agent._active_records() for key in saved_ids))

    def test_final_turn_has_exactly_save_delete_status_tools(self):
        self.responses = [self.init(),reply([self.save()])]
        self.run_cycle('seed')
        def final(agent):
            names = {t['function']['name'] for t in self.requests[-1]['tools']}
            self.assertEqual(names,{'memory_save_knowledge','memory_save_procedural','memory_save_gap',
                                    'memory_delete','memory_update_status'})
            self.assertIn('save knowledge/procedural/gap, delete, update status',self.requests[-1]['prompt'])
            return reply()
        self.responses = [reply([('memory_read_source',{'memory_id':'M1'})]),
                          reply([('memory_read_source',{'memory_id':'M1'})]),final]
        self.assertEqual(self.run_cycle('final_tools')['status'],'completed')

    def test_compact_p1_input_preserves_requirements_body_task_and_enum_protection(self):
        fixed = [f'Requirement {i}: '+('x'*(512-len(f'Requirement {i}: '))) for i in range(4)]
        self.responses = [self.init(fixed),reply([self.save(f'Entry {i}: body🙂\r\n',fixed) for i in range(40)])]
        self.run_cycle()
        with patch.object(self.agent,'_memory_attributes',side_effect=self.agent.requirement_state.attributes), \
                patch.object(self.agent,'_model_memory_row',side_effect=lambda row:row):
            old = ContextSourceP1Agent._input(self.agent,'benchmark observation',4,[])[0]
        selected = [self.agent._active_records()[t['id']] for t in self.agent.frozen_aliases.values() if t['kind']=='memory']
        old += ('\n## Fixed requirement choices (text attributes, not completion states)\n'+encode(fixed)+
            '\n## Requirement view (IDs reference flat records above; displayed subset only)\n'+
            encode(self.agent.requirement_state.groups(selected))+
            '\nUnclassified records remain in the flat view. Retrieval can omit active records; '
            'an empty displayed group does not mean its whole task history is empty.\n')
        new = self.agent._input('benchmark observation',4,[])[0]
        rows = json.loads(new.split('## Stored summaries',1)[1].split('\n',1)[1].split('\n',1)[0])
        groups = json.loads(new.split('## Fixed requirements and displayed memberships\n',1)[1].split('\n',1)[0])
        for row in rows:
            self.assertNotIn('memory_id',row)
            original = self.agent._active_records()[self.agent.frozen_aliases[row['alias']]['id']]
            self.assertEqual(row['content'],original.content)
            self.assertEqual([g['requirement'] for g in groups['requirements'] if row['alias'] in g['aliases']],fixed)
        self.assertIn(self.agent.task,new)
        for text in fixed:self.assertEqual(new.count(encode(text)),1)
        self.assertEqual(sum(t['function']['parameters']['properties'].get('requirements',{}).get('items',{}).get('enum')==fixed
                             for t in self.agent.get_tools_schema()),3)
        self.assertLess(len(new),len(old)*0.3)
        self.p1_character_measurement = {'old_user_characters':len(old),'new_user_characters':len(new),
            'unit':'Unicode characters, not tokens','records':40,'requirement_characters':2048,
            'three_schema_enums_retained':True,'task_body_memberships_preserved':True}

    def test_typed_entry_alias_collision_read_delete_and_model_projection(self):
        self.responses = [self.init(),reply([self.save('first'),self.save('second')])]
        self.run_cycle()
        first,second = self.agent.memory.knowledge
        old,other = first.id,second.id
        first.id,second.id = 'M2','X'
        state = deepcopy(self.agent.links.state)
        state['refs']['M2'] = state['refs'].pop(old)
        state['refs']['X'] = state['refs'].pop(other)
        state['bank'] = self.agent.memory.to_dict()
        self.agent.links.commit(state)
        def read(agent):
            self.assertEqual(agent.frozen_aliases['M1']['id'],'M2')
            self.assertNotIn('memory_id',self.requests[-1]['prompt'])
            return reply([('memory_read_source',{'entry':'M1'})])
        def remove(agent):
            return reply([('memory_delete',{'entry':'M1'})])
        self.responses = [read,remove]
        result = self.run_cycle('typed')
        self.assertEqual(result['status'],'completed')
        self.assertEqual(result['turns'][0]['tool_results'][0]['result']['target'],'M2')
        self.assertEqual(result['turns'][1]['tool_results'][0]['result']['target_resolution']['resolved_memory_id'],'M2')
        self.assertEqual([r.id for r in self.agent.memory.knowledge],['X'])
        for tool in self.agent.get_tools_schema():
            if tool['function']['name'] in ('memory_delete','memory_read_source'):
                self.assertIn('entry',tool['function']['parameters']['properties'])
                self.assertNotIn('memory_id',tool['function']['parameters']['properties'])

    def test_model_projection_preserves_evidence_and_entry_history_coverage(self):
        from p1_requirements import model_turn
        self.responses = [self.init(),reply([self.save('old')])]
        self.run_cycle('old')
        self.responses = [reply([self.save('child')])]
        self.run_cycle('child')
        child = self.agent.memory.knowledge[-1]
        target = {'kind':'memory','id':child.id,'ref':self.agent.links.state['refs'][child.id]}
        page = self.agent.history.read(target,self.agent._active_records())
        directory = [json.loads(p['text']) for p in page['parts'] if p['field']=='input_memory']
        handle = directory[0]['history_handle']
        coverage = self.agent.history.coverage([], [{'call':{'arguments':{'entry':handle}}}])
        self.assertEqual(coverage['read_handles'],[handle])
        raw = {'assistant_text':'literal memory_id is evidence text','tool_calls':[],
            'tool_results':[{'result':page}]}
        visible = model_turn(raw)
        for part in visible['tool_results'][0]['result']['parts']:
            if part['field']=='input_memory':self.assertNotIn('memory_id',json.loads(part['text']))
        self.assertTrue(all('memory_id' in x for x in directory))
        self.assertEqual(visible['assistant_text'],raw['assistant_text'])
        self.assertNotIn('complete',visible['tool_results'][0]['result'])
        self.assertIn('complete',page)



if __name__=='__main__':
    unittest.main()
