"""Generated PMA reminder protocol and explicit P1→P2 fake-only composition."""
import asyncio
from copy import deepcopy
import json
import unittest
from unittest.mock import patch
from pma_evidence_review.tests import test_p2_requirement_agent as fixtures
from pma_evidence_review.tests.test_bank_display import reply
from p2_requirement_reminder import RequirementReminderAgent, RequirementReminderPipeline, SYSTEM
from memory_agent.memory.memory_agent import PHASE2_SYSTEM


class ReminderTests(unittest.TestCase):
    setUp = fixtures.SelectionTests.setUp
    init = fixtures.SelectionTests.init
    save = fixtures.SelectionTests.save
    run_cycle = fixtures.SelectionTests.run_cycle

    def build(self):
        fixtures.SelectionTests.build(self)
        self.p2 = RequirementReminderAgent(p1=self.agent,llm=self.p2.llm)

    def run_reminder(self):
        return asyncio.run(self.p2.remind(observation='current trajectory',step_count=2))

    def test_original_pma_prompt_and_zero_tool_generated_note_delivery(self):
        self.build()
        note = 'A earlier and B later cover different observations; this reminder combines them for the current approach.'
        self.p2_responses = [reply(content='<context_for_action>\n'+note+'\n</context_for_action>')]
        result = self.run_reminder()
        self.assertTrue(SYSTEM.startswith(PHASE2_SYSTEM))
        self.assertEqual((result['status'],result['should_inject'],result['delivery']),('intervention',True,note))
        self.assertEqual(result['context_for_action'],note)
        self.assertEqual((result['model_calls_attempted'],result['reads_used']),(1,0))
        self.assertTrue(self.p2.pending_refs_valid())
        prompt = self.p2_requests[0]['prompt']
        rows = json.loads(prompt.split('## Original task and shown memory (data)\n',1)[1].split('\n',1)[0])
        self.assertEqual(rows[0]['content'],self.agent.task)
        self.assertEqual({r['content'] for r in rows[1:]},{r.content for r in self.agent._active_records().values()})
        self.assertNotIn('Only TASK and the listed M aliases may be selected',prompt)
        self.assertNotIn('<intervene>',prompt)
        self.assertEqual(self.p2_requests[0]['system'],SYSTEM)
        self.assertNotIn('select its stable M alias',self.p2_requests[0]['tools'][0]['function']['description'])

    def test_explicit_and_upstream_default_no_intervention_are_distinguished(self):
        self.build()
        self.p2_responses = [reply(content='<no_intervention/>')]
        result = self.run_reminder()
        self.assertEqual((result['status'],result['should_inject'],result['context_for_action']),('no_intervention',False,None))
        for raw in ('','untagged reminder','<intervene>M1</intervene>',
                    '<context_for_action> </context_for_action>','<context_for_action>broken'):
            with self.subTest(raw=raw):
                self.p2_responses = [reply(content=raw)]
                result = self.run_reminder()
                self.assertEqual(result['status'],'no_intervention')
                self.assertEqual(result['parse_status'],'upstream_default_no_intervention')
                self.assertIn('format_warning',result)
                self.assertIsNone(result['delivery'])
        self.p2_responses = [reply(content='<context_for_action>x</context_for_action><no_intervention/>')]
        self.assertEqual(self.run_reminder()['failure_kind'],'model_output')

    def test_explicit_tags_accept_surrounding_prose_like_upstream(self):
        self.build()
        from memory_agent.memory.memory_agent import MemoryAgent
        for raw in ('prefix <no_intervention/> explanation with <ordinary> markup',
                    '<context_for_action>note</context_for_action> explanation',
                    'explanation <context_for_action>note</context_for_action>',
                    '```xml\n<context_for_action>note</context_for_action>\n```',
                    '<no_intervention/>\n\nThe agent is proceeding with the visible requirements.'):
            self.p2_responses = [reply(content=raw)]
            result = self.run_reminder()
            self.assertEqual(result['context_for_action'],MemoryAgent._parse_phase2_response(self.p2,raw))
            self.assertEqual(result['raw_output'],raw)
            self.assertNotIn(result['status'],('selection_error','engineering_error'))

    def test_theme_and_flat_then_evidence_then_synthesized_reminder(self):
        self.build()
        self.p2.max_memory_in_prompt = 0
        for browse in ({'view':'all'},{'view':'requirement','requirement':fixtures.fixtures.FIXED[0]}):
            with self.subTest(browse=browse):
                self.p2_requests = []
                def after_browse(p2):
                    page = p2.last_p2_report['turns'][0]['tool_results'][0]['result']
                    row = next(json.loads(p['text']) for p in page['parts'] if json.loads(p['text'])['content']=='A earlier')
                    return reply([('memory_read_source',{'memory_id':row['alias'],'view':'sources'})])
                def final(p2):
                    page = p2.last_p2_report['turns'][1]['tool_results'][0]['result']
                    self.assertIn('A original raw',json.dumps(page))
                    self.assertNotIn('B original raw',json.dumps(page))
                    self.assertNotIn('tools',self.p2_requests[-1])
                    self.assertNotIn('original TASK/M selection protocol',self.p2_requests[-1]['prompt'])
                    return reply(content='<context_for_action>The earlier receipt concerns A; its scope should be kept when comparing the current approach.</context_for_action>')
                self.p2_responses = [reply([('memory_browse',browse)]),after_browse,final]
                with patch('memory_agent.memory.universal_memory.UniversalMemory.search_knowledge',return_value=[]):
                    result = self.run_reminder()
                self.assertEqual((result['status'],result['model_calls_attempted'],result['reads_used']),('intervention',3,2))
                self.assertTrue(result['delivery'].startswith('The earlier receipt'))

    def test_missing_evidence_can_be_reported_in_generated_note_without_fake_success(self):
        self.build()
        self.responses = [reply([self.save('unassociated summary',[],())])]
        self.run_cycle('missing')
        self.agent.source_archive.window_path('missing_r0').unlink()
        def first(p2):
            alias = next(a for a,r in p2.view.aliases.items() if r.content=='unassociated summary')
            return reply([('memory_read_source',{'memory_id':alias})])
        def final(p2):
            receipt = p2.last_p2_report['turns'][0]['tool_results'][0]['result']
            self.assertEqual(receipt['status'],'context_missing')
            self.assertFalse(receipt['complete'])
            return reply(content='<context_for_action>The old summary lacks an available original receipt; its claimed outcome remains unverified.</context_for_action>')
        self.p2_responses = [first,final]
        result = self.run_reminder()
        self.assertEqual(result['status'],'intervention')
        self.assertIn('unverified',result['delivery'])
        self.assertIn('Missing evidence does not establish success or failure',SYSTEM)

    def test_whole_bank_change_revokes_generated_note_without_invented_used_aliases(self):
        self.build()
        self.p2_responses = [reply(content='<context_for_action>A focused reminder.</context_for_action>')]
        result = self.run_reminder()
        self.assertTrue(self.p2.pending_refs_valid())
        self.assertNotIn('selected_aliases',result)
        self.responses = [reply([self.save('new fact not in the old snapshot')])]
        self.run_cycle('new_fact')
        self.assertFalse(self.p2.pending_refs_valid())
        self.assertEqual(result['delivery_error'],'frozen_reminder_version_changed')

    def test_explicit_pipeline_uses_same_client_and_real_generated_delivery(self):
        note = 'The PATH requirement remains distinct from the build observation.'
        self.responses = [self.init(),reply([self.save('build observation')]),
                          reply(content='<context_for_action>'+note+'</context_for_action>')]
        pipeline = RequirementReminderPipeline(self.agent)
        result = asyncio.run(pipeline.run([{'event_id':'build','observation':'built'}],cycle_id='combined'))
        self.assertEqual((result['status'],result['delivery'],result['should_inject']),('intervention',note,True))
        self.assertEqual((result['model_calls_attempted'],result['model_calls_completed']),(3,3))
        self.assertIs(pipeline.p2.llm,self.agent.llm)
        self.assertEqual(len(self.requests),3)
        self.assertFalse(result['task_enabled'])
        with self.assertRaisesRegex(RuntimeError,'P1-only'):
            asyncio.run(self.agent.process())
        with self.assertRaisesRegex(RuntimeError,'reminder-only'):
            asyncio.run(pipeline.p2.process())

    def test_pipeline_ordinary_p1_tool_failure_preserves_error_and_runs_p2(self):
        self.responses = [self.init(),reply([self.save(requirements=['unknown'])]),reply(content='<no_intervention/>')]
        result = asyncio.run(RequirementReminderPipeline(self.agent).run([],cycle_id='bad'))
        self.assertEqual(result['status'],'no_intervention')
        self.assertEqual(result['p1']['status'],'tool_error')
        self.assertEqual(result['p1_warning'],'tool_error')
        self.assertEqual(len(self.requests),3)
        self.assertEqual(self.agent.memory.knowledge,[])
        self.assertFalse(result['should_inject'])

    def test_optional_theme_gap_counts_and_fallible_overview_prompt(self):
        self.build()
        requirement = fixtures.fixtures.FIXED[1]
        self.responses = [reply([self.save('PATH outcome remains unverified',[requirement],category='gap')])]
        self.run_cycle('gap_record')
        def final(p2):
            page = p2.last_p2_report['turns'][0]['tool_results'][0]['result']
            self.assertEqual(page['matching_record_count'],1)
            self.assertEqual(page['matching_category_counts'],{'knowledge':0,'procedural':0,'gap':1})
            self.assertIn('not verified completion',page['gap_scope'])
            self.assertEqual(json.loads(page['parts'][0]['text'])['content'],'PATH outcome remains unverified')
            return reply(content='<context_for_action>The bank records an unverified PATH outcome; it is a reminder of uncertainty, not proof that PATH is broken.</context_for_action>')
        self.p2_responses = [reply([('memory_browse',{'view':'requirement','requirement':requirement,'category':'gap'})]),final]
        result = self.run_reminder()
        self.assertEqual(result['status'],'intervention')
        self.assertIn('fallible overview',SYSTEM)
        self.assertIn('No retrieval or audit is mandatory',SYSTEM)
        self.assertIn('No retrieval or audit is mandatory',SYSTEM)

    def test_pending_and_initializing_durable_cycles_reject_even_no_intervention(self):
        self.build()
        original = deepcopy(self.agent.links.state)
        for phase in ('pending','initializing','running','unknown'):
            with self.subTest(phase=phase):
                state = deepcopy(original)
                state['requirement_attributes_v1']['cycles']['unsettled'] = {'phase':phase}
                self.agent.links.commit(state)
                self.p2_responses = [reply(content='<no_intervention/>')]
                result = self.run_reminder()
                self.assertEqual((result['status'],result['model_calls_attempted']),('engineering_error',0))
                self.assertFalse(result['should_inject'])
        self.agent.links.commit(original)

    def test_uncommitted_live_body_status_or_addition_blocks_freeze_finish_and_delayed_delivery(self):
        self.build()
        note = '<context_for_action>The old snapshot is relevant.</context_for_action>'
        for change in ('body','status','addition'):
            with self.subTest(change=change):
                def mutate():
                    if change=='body':
                        self.agent.memory.knowledge[0].content = 'NEW UNCOMMITTED BODY'
                    elif change=='status':
                        self.agent.memory.status = 'NEW UNCOMMITTED STATUS'
                    else:
                        self.agent.memory.save_knowledge('NEW UNCOMMITTED ADDITION')
                self.p2_responses = [reply(content=note)]
                self.assertEqual(self.run_reminder()['status'],'intervention')
                mutate()
                self.assertFalse(self.p2.pending_refs_valid())
                self.assertEqual(self.p2.last_p2_report['delivery_error'],'p1_live_bank_not_committed')
                rejected = self.run_reminder()
                self.assertEqual((rejected['status'],rejected['model_calls_attempted']),('engineering_error',0))
                self.agent._restore_committed_bank()
                def mutate_while_waiting(p2):
                    mutate()
                    return reply(content=note)
                self.p2_responses = [mutate_while_waiting]
                result = self.run_reminder()
                self.assertEqual((result['status'],result['error']),('selection_error','p1_live_bank_not_committed'))
                self.assertFalse(result['should_inject'])
                self.assertIsNone(result['delivery'])
                self.agent._restore_committed_bank()

    def test_complete_reminder_with_literal_legacy_tool_examples_is_never_executed(self):
        self.build()
        for name in ('memory_browse','memory_read_source','memory_delete'):
            with self.subTest(name=name):
                note = 'The literal sample <tool_call><function='+name+'></function></tool_call> is historical data.'
                self.p2_responses = [reply(content='<context_for_action>'+note+'</context_for_action>')]
                result = self.run_reminder()
                self.assertEqual((result['status'],result['delivery']),('intervention',note))
                self.assertEqual((result['model_calls_attempted'],result['reads_used']),(1,0))
                self.assertEqual(result['turns'][0]['tool_calls'],[])

    def test_legacy_tool_fallback_still_works_and_mixed_final_tags_fail_without_tools(self):
        self.build()
        xml = '<tool_call><function=memory_browse></function></tool_call>'
        self.p2_responses = [reply(content=xml),reply(content='<no_intervention/>')]
        result = self.run_reminder()
        self.assertEqual((result['status'],result['model_calls_attempted'],result['reads_used']),('no_intervention',2,1))
        for text in ('<no_intervention/>'+xml,xml+'<context_for_action>note</context_for_action>',
                     '<context_for_action>note</context_for_action><no_intervention/>'):
            with self.subTest(text=text):
                self.p2_responses = [reply(content=text)]
                result = self.run_reminder()
                self.assertEqual((result['status'],result['reads_used']),('selection_error',0))
                self.assertIsNone(result['delivery'])
        self.p2_responses = [reply([('memory_browse',{})],content='<context_for_action>note</context_for_action>')]
        result = self.run_reminder()
        self.assertEqual(result['error'],'mixed_native_tools_and_final_output')
        self.assertEqual(result['reads_used'],0)

    def test_internal_id_source_call_and_generation_receipts_are_consistent(self):
        self.build()
        def first(p2):
            key = next(r.id for r in p2.view.aliases.values() if r.content=='A earlier')
            return reply([('memory_read_source',{'memory_id':key})])
        def final(p2):
            page = p2.last_p2_report['turns'][0]['tool_results'][0]['result']
            self.assertIn('A original raw',json.dumps(page))
            return reply(content='<context_for_action>The original A receipt concerns the earlier observation.</context_for_action>')
        self.p2_responses = [first,final]
        result = self.run_reminder()
        self.assertEqual((result['status'],result['reads_used']),('intervention',1))
        props = self.p2_requests[0]['tools'][1]['function']['parameters']['properties']
        self.assertIn('entry',props)
        self.assertNotIn('memory_id',props)

    def test_continuations_receive_only_visible_calls_receipts_and_text_not_diagnostics(self):
        self.build()
        response = reply([('memory_browse',{'view':'all'})],content='Browse the recorded overview.')
        response.usage = type('Usage',(),{'prompt_tokens':123456,'completion_tokens':789,'cost_usd':0.125})()
        def second(p2):
            prompt = self.p2_requests[1]['prompt']
            history = json.loads(prompt.split('## Visible P2 calls and receipts (historical data)\n',1)[1])
            self.assertEqual(set(history[0]),{'assistant_text','tool_calls','tool_results'})
            receipt = history[0]['tool_results'][0]['result']
            self.assertIn('record_scope',receipt)
            self.assertNotIn('selection_rule',receipt)
            self.assertNotIn('may be selected',json.dumps(receipt))
            return reply([('memory_read_source',{'memory_id':'M1'})])
        def final(p2):
            prompt = self.p2_requests[2]['prompt'].split('\nTools closed.',1)[0]
            history = json.loads(prompt.split('## Visible P2 calls and receipts (historical data)\n',1)[1])
            self.assertEqual(len(history),2)
            for turn in history:
                self.assertEqual(set(turn),{'assistant_text','tool_calls','tool_results'})
            return reply(content='<context_for_action>A scoped generated reminder.</context_for_action>')
        self.p2_responses = [response,second,final]
        result = self.run_reminder()
        self.assertEqual(result['status'],'intervention')
        logged = result['turns'][0]
        self.assertEqual(logged['usage']['prompt_tokens'],123456)
        self.assertIn('prompt_sha256',logged)

    def test_model_entry_labels_flat_theme_history_and_host_traceability(self):
        self.build()
        self.responses = [reply([self.save('child',fixtures.fixtures.FIXED)])]
        self.assertEqual(self.run_cycle('child')['status'],'completed')
        for browse in ({'view':'all'},{'view':'requirement','requirement':fixtures.fixtures.FIXED[0]}):
            self.p2_requests = []
            self.p2.max_memory_in_prompt = 0
            chosen = {}
            def after_browse(p2):
                page = p2.last_p2_report['turns'][0]['tool_results'][0]['result']
                rows = [json.loads(p['text']) for p in page['parts']]
                self.assertTrue(all('memory_id' not in r for r in rows))
                chosen['alias'] = next(r['alias'] for r in rows if r['content']=='child')
                return reply([('memory_read_source',{'entry':chosen['alias']})])
            def final(p2):
                history = json.loads(self.p2_requests[-1]['prompt'].split('## Visible P2 calls and receipts (historical data)\n')[1].split('\nTools closed.')[0])
                page = history[1]['tool_results'][0]['result']
                self.assertEqual(page['target'],chosen['alias'])
                directory = [json.loads(p['text']) for p in page['parts'] if p['field']=='input_memory']
                self.assertTrue(directory)
                self.assertTrue(all('memory_id' not in r and r['history_handle'].startswith('P2H.') for r in directory))
                chosen['handle'] = directory[0]['history_handle']
                return reply(content='<context_for_action>A scoped note.</context_for_action>')
            self.p2_responses = [reply([('memory_browse',browse)]),after_browse,final]
            result = self.run_reminder()
            self.assertEqual(result['status'],'intervention')
            raw = result['turns'][1]['tool_results'][0]['result']
            self.assertEqual(raw['target'],result['entry_id_map'][chosen['alias']])
            directory = [json.loads(p['text']) for p in raw['parts'] if p['field']=='input_memory']
            self.assertTrue(all('memory_id' in r for r in directory))
        # An independent source→history request chain uses the returned handle, never an old M label.
        self.p2.max_memory_in_prompt = 100
        def first(p2):
            alias = next(a for a,r in p2.view.aliases.items() if r.content=='child')
            return reply([('memory_read_source',{'entry':alias})])
        def follow(p2):
            raw = p2.last_p2_report['turns'][0]['tool_results'][0]['result']
            handle = next(json.loads(p['text'])['history_handle'] for p in raw['parts'] if p['field']=='input_memory')
            return reply([('memory_read_source',{'entry':handle})])
        def finish(p2):
            prompt = self.p2_requests[-1]['prompt']
            history = json.loads(prompt.split('## Visible P2 calls and receipts (historical data)\n')[1].split('\nTools closed.')[0])
            self.assertNotIn('historical_memory_id',history[1]['tool_results'][0]['result'])
            self.assertIn('historical_memory_id',p2.last_p2_report['turns'][1]['tool_results'][0]['result'])
            rows = json.loads(self.p2_requests[-3]['prompt'].split('## Original task and shown memory (data)\n')[1].split('\n')[0])
            self.assertTrue(all('memory_id' not in row for row in rows))
            return reply(content='<context_for_action>Evidence remains scoped to its original observation.</context_for_action>')
        self.p2_responses = [first,follow,finish]
        self.assertEqual(self.run_reminder()['status'],'intervention')



if __name__=='__main__':
    unittest.main()
