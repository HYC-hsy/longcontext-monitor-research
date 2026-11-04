"""Opt-in optional P2 tools, tested with visible scripted responses only."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch
from pma_evidence_review.tests import test_p1_requirements as fixtures
from pma_evidence_review.tests.test_bank_display import reply, BankDisplayAgent
from p2_requirement_agent import RequirementSelectionAgent, SYSTEM
from p2_requirement_view import RequirementSelectionView
from selection_context import render_selection
from p1_source_archive import encode
from p1_context_agent import SYSTEM as P1_SYSTEM


class SelectionTests(unittest.TestCase):
    setUp = fixtures.RequirementTests.setUp
    init = fixtures.RequirementTests.init
    save = fixtures.RequirementTests.save
    run_cycle = fixtures.RequirementTests.run_cycle

    def build(self):
        self.responses = [self.init(),reply([self.save('B later',[fixtures.FIXED[1]],('E2',)),
            self.save('A earlier',fixtures.FIXED,('E1',)),self.save('unclassified',[],())])]
        self.run_cycle(entries=[{'event_id':'a','observation':'A original raw'},
                                {'event_id':'b','observation':'B original raw'}])
        self.p2_responses,self.p2_requests = [],[]
        async def fake(**kw):
            self.p2_requests.append(deepcopy(kw))
            value = self.p2_responses.pop(0)
            return value(self.p2) if callable(value) else value
        self.p2 = RequirementSelectionAgent(p1=self.agent,llm=NS(call=fake))
        return self.p2

    def select(self):
        return asyncio.run(self.p2.select(observation='current observation',step_count=2))

    def files(self):
        return {str(p.relative_to(self.temp.name)):p.read_bytes() for p in Path(self.temp.name).rglob('*') if p.is_file()}

    def test_zero_tool_original_text_and_default_candidates_keep_guards(self):
        self.build()
        before = self.files()
        self.p2_responses = [reply(content='<intervene>TASK,M1</intervene>')]
        report = self.select()
        self.assertEqual(report['status'],'intervention')
        self.assertEqual(report['model_calls_attempted'],1)
        blocks = json.loads(report['delivery'])['blocks']
        self.assertEqual([r['content'] for r in blocks],[self.agent.task,'A earlier'])
        self.assertEqual(report['initial_scope'],'all_frozen_active_records')
        self.assertEqual(self.files(),before)
        with self.assertRaisesRegex(RuntimeError,'P2-only'):
            asyncio.run(self.p2.process())
        with self.assertRaisesRegex(RuntimeError,'P1-only'):
            asyncio.run(self.agent.process())

    def test_hidden_theme_and_general_reachable_with_stable_full_snapshot_aliases(self):
        self.build()
        self.p2.max_memory_in_prompt = 0
        self.p2.use_bm25_prefilter = True
        # Initial BM25 sees only B; full P2 aliases are A=M1, B=M2, unclassified=M3.
        self.p2_responses = [reply([('memory_browse',{'view':'requirement','requirement':fixtures.FIXED[0]}),
                                    ('memory_browse',{'view':'requirement','requirement':'General'})]),
            reply(content='<intervene>M3,M1</intervene>')]
        with patch('memory_agent.memory.universal_memory.UniversalMemory.search_knowledge',
                   return_value=[self.agent.memory.knowledge[0]]):
            report = self.select()
        self.assertEqual(report['status'],'intervention')
        self.assertEqual(report['initial_aliases'],['M2'])
        self.assertEqual(report['initial_scope'],'subset_of_frozen_active_records')
        self.assertEqual(report['model_calls_attempted'],2)
        self.assertEqual(report['reads_used'],2)
        self.assertEqual([b['content'] for b in json.loads(report['delivery'])['blocks']],['unclassified','A earlier'])
        self.assertIn('not only the initial BM25 subset',self.p2_requests[1]['prompt'])

    def test_unseen_or_partial_alias_cannot_be_selected(self):
        self.build()
        self.p2.max_memory_in_prompt = 0
        self.p2_responses = [reply(content='<intervene>M1</intervene>')]
        with patch('memory_agent.memory.universal_memory.UniversalMemory.search_knowledge',return_value=[]):
            report = self.select()
        self.assertEqual(report['status'],'selection_error')
        self.assertEqual(report['error'],'record_not_fully_shown')
        self.assertIsNone(report['delivery'])

    def test_source_then_history_then_original_selection_no_grant_files(self):
        self.build()
        # B's generation input had no old memories, so create one later generation.
        self.responses = [reply([self.save('A+B child',fixtures.FIXED,('E1',))])]
        self.run_cycle('child',[{'event_id':'child','observation':'C new raw'}])
        before = self.files()
        def first(p2):
            alias = next(a for a,r in p2.view.aliases.items() if r.content=='A+B child')
            return reply([('memory_read_source',{'memory_id':alias})])
        def second(p2):
            page = p2.last_p2_report['turns'][0]['tool_results'][0]['result']
            rows = [json.loads(p['text']) for p in page['parts'] if p['field']=='input_memory']
            token = next(r['history_handle'] for r in rows if r['content_preview']=='A earlier')
            return reply([('memory_read_source',{'memory_id':token})])
        def third(p2):
            self.assertNotIn('tools',self.p2_requests[-1])
            page = p2.last_p2_report['turns'][1]['tool_results'][0]['result']
            self.assertIn('A original raw',json.dumps(page))
            return reply(content='<intervene>M1</intervene>')
        self.p2_responses = [first,second,third]
        report = self.select()
        self.assertEqual((report['status'],report['reads_used'],report['model_calls_attempted']),('intervention',2,3))
        self.assertEqual(self.files(),before)

    def test_invalid_tool_stops_batch_and_ref_mutation_revokes_original_delivery(self):
        self.build()
        before = self.files()
        self.p2_responses = [reply([('memory_delete',{'memory_id':'M1'}),('memory_browse',{})])]
        report = self.select()
        self.assertEqual(report['status'],'tool_error')
        self.assertEqual(report['turns'][0]['tool_results'][1]['result']['status'],'not_executed_after_tool_failure')
        self.assertEqual(self.files(),before)
        def mutate(p2):
            key = p2.view.aliases['M1'].id
            self.agent.links.state['refs'][key]['association'] = 'changed'
            return reply(content='<intervene>M1</intervene>')
        self.p2_responses = [mutate]
        report = self.select()
        self.assertEqual(report['status'],'selection_error')
        self.assertEqual(report['error'],'p1_state_not_reconciled')

    def test_four_shared_reads_limit_and_final_turn_has_no_tools(self):
        self.build()
        self.p2_responses = [reply([('memory_browse',{})]*5),reply(content='<no_intervention/>')]
        report = self.select()
        self.assertEqual((report['status'],report['reads_used']),('no_intervention',4))
        self.assertEqual(report['turns'][0]['tool_results'][-1]['result']['status'],'budget_exhausted')
        self.assertNotIn('tools',self.p2_requests[1])

    def test_real_bm25_top20_does_not_limit_full_requirement_tool(self):
        self.build()
        self.responses = [reply([self.save('query repeated '+str(i),[fixtures.FIXED[0]]) for i in range(55)]+
                                [self.save('needle original body',[fixtures.FIXED[1]])])]
        self.run_cycle('large')
        # Old 3 + 56 records trigger the actual inherited prefilter (no BM25 mock).
        self.assertEqual(len(self.agent.memory.knowledge),59)
        chosen = {}
        def first(p2):
            alias = next(a for a,r in p2.view.aliases.items() if r.content=='needle original body')
            chosen['alias'] = alias
            self.assertEqual(len(p2.last_p2_report['initial_aliases']),20)
            self.assertNotIn(alias,p2.last_p2_report['initial_aliases'])
            return reply([('memory_browse',{'view':'requirement','requirement':fixtures.FIXED[1]})])
        def final(p2):
            self.assertIn(chosen['alias'],p2.view.seen)
            page = p2.last_p2_report['turns'][0]['tool_results'][0]['result']
            self.assertEqual(page['all_active_record_count'],59)
            return reply(content='<intervene>'+chosen['alias']+'</intervene>')
        self.p2_responses = [first,final]
        report = asyncio.run(self.p2.select(observation='query repeated',step_count=3))
        self.assertEqual(report['status'],'intervention')
        self.assertEqual(json.loads(report['delivery'])['blocks'][0]['content'],'needle original body')

    def test_partial_browse_result_does_not_authorize_final_selection(self):
        self.build()
        self.responses = [reply([self.save('long body🙂\r\n'*4000,fixtures.FIXED)])]
        self.run_cycle('long')
        self.p2.max_memory_in_prompt = 0
        chosen = {}
        def first(p2):
            chosen['alias'] = next(a for a,r in p2.view.aliases.items() if r.content.startswith('long body'))
            return reply([('memory_browse',{'view':'requirement','requirement':fixtures.FIXED[0]})])
        def final(p2):
            self.assertNotIn(chosen['alias'],p2.view.seen)
            return reply(content='<intervene>'+chosen['alias']+'</intervene>')
        self.p2_responses = [first,final]
        with patch('memory_agent.memory.universal_memory.UniversalMemory.search_knowledge',return_value=[]):
            report = self.select()
        self.assertEqual((report['status'],report['error']),('selection_error','record_not_fully_shown'))

    def test_theme_and_flat_browse_then_evidence_then_exact_original_selection(self):
        self.build()
        self.p2.max_memory_in_prompt = 0
        before = self.files()
        for browse in ({'view':'all'},{'view':'requirement','requirement':fixtures.FIXED[0]}):
            with self.subTest(browse=browse):
                self.p2_requests = []
                selected = {}
                def first(p2):
                    return reply([('memory_browse',browse)])
                def second(p2):
                    page = p2.last_p2_report['turns'][0]['tool_results'][0]['result']
                    rows = [json.loads(p['text']) for p in page['parts']]
                    row = next(r for r in rows if r['content']=='A earlier')
                    selected.update(row)
                    selected['memory_id'] = p2.view.aliases[row['alias']].id
                    return reply([('memory_read_source',{'memory_id':row['alias'],'view':'sources'})])
                def third(p2):
                    page = p2.last_p2_report['turns'][1]['tool_results'][0]['result']
                    self.assertEqual(page['target'],selected['memory_id'])
                    self.assertIn('A original raw',json.dumps(page))
                    self.assertNotIn('B original raw',json.dumps(page))
                    return reply(content='<intervene>'+selected['alias']+'</intervene>')
                self.p2_responses = [first,second,third]
                with patch('memory_agent.memory.universal_memory.UniversalMemory.search_knowledge',return_value=[]):
                    report = self.select()
                self.assertEqual((report['status'],report['reads_used'],report['model_calls_attempted']),('intervention',2,3))
                delivered = json.loads(report['delivery'])['blocks'][0]
                self.assertEqual((delivered['alias'],delivered['id'],delivered['content']),
                    (selected['alias'],selected['memory_id'],selected['content']))
                self.assertEqual(report['initial_aliases'],[])
                self.assertNotIn('tools',self.p2_requests[-1])
        self.assertEqual(self.files(),before)

    def test_transport_or_missing_final_output_is_not_no_intervention(self):
        self.build()
        self.p2_responses = [reply([('memory_browse',{})]),reply()]
        report = self.select()
        self.assertEqual(report['status'],'selection_error')
        self.assertIsNone(report['delivery'])

        async def fail(**kw):
            raise RuntimeError('fake transport failure')
        self.p2.llm = NS(call=fail)
        report = self.select()
        self.assertEqual(report['status'],'engineering_error')
        self.assertEqual((report['model_calls_attempted'],report['model_calls_completed']),(1,0))
        self.assertIsNone(report['delivery'])

    def test_pending_delivery_revalidation_rejects_later_delete(self):
        self.build()
        self.p2_responses = [reply(content='<intervene>M1</intervene>')]
        report = self.select()
        self.assertEqual(report['status'],'intervention')
        self.assertTrue(self.p2.pending_refs_valid())
        key = self.p2.view.aliases['M1'].id
        self.responses = [reply([('memory_delete',{'memory_id':key})])]
        self.assertEqual(self.run_cycle('later_delete')['status'],'completed')
        self.assertFalse(self.p2.pending_refs_valid())
        self.assertTrue(report['delivery_revoked'])

    def test_interrupted_p1_save_before_delete_blocks_new_and_delayed_p2(self):
        self.build()
        self.p2_responses = [reply(content='<intervene>M1</intervene>')]
        report = self.select()
        self.assertTrue(self.p2.pending_refs_valid())
        old = self.p2.view.aliases['M1'].id
        self.responses = [reply([self.save('replacement saved before interrupted delete'),
                                ('memory_delete',{'memory_id':old})])]
        original = self.agent._apply
        def interrupt(call,*args):
            if call['name']=='memory_delete':
                raise KeyboardInterrupt()
            return original(call,*args)
        with patch.object(self.agent,'_apply',side_effect=interrupt), self.assertRaises(KeyboardInterrupt):
            self.run_cycle('interrupted')
        self.assertFalse(self.agent._active or self.agent._requirement_active)
        self.assertIn(old,self.agent._active_records())
        self.assertTrue(any(r.content=='replacement saved before interrupted delete'
                            for r in self.agent._active_records().values()))
        self.assertFalse(self.p2.pending_refs_valid())
        self.assertEqual(report['delivery_error'],'unresolved_p1_maintenance_cycle')
        fixtures.RequirementTests.reopen(self)
        with self.assertRaisesRegex(RuntimeError,'unresolved_p1_maintenance_cycle'):
            RequirementSelectionView(self.agent)
        fresh = RequirementSelectionAgent(p1=self.agent,llm=self.p2.llm)
        rejected = asyncio.run(fresh.select())
        self.assertEqual((rejected['status'],rejected['model_calls_attempted']),('engineering_error',0))
        self.assertIsNone(rejected['delivery'])

    def test_compact_initial_prompt_preserves_bodies_membership_source_scope_and_task(self):
        fixed = [f'Requirement {i}: '+('x'*(512-len(f'Requirement {i}: '))) for i in range(4)]
        self.assertEqual(sum(map(len,fixed)),2048)
        self.responses = [self.init(fixed),reply([self.save(f'Entry {i}: body🙂\r\n',fixed) for i in range(40)])]
        self.run_cycle()
        p2 = RequirementSelectionAgent(p1=self.agent,llm=None)
        new,aliases = p2._prepare('benchmark observation',None,4)
        scope = 'all_frozen_active_records'
        old = render_selection([{'alias':'TASK','content':p2.view.task}]+[p2.view.record(a) for a in aliases],
            p2.memory.status,'benchmark observation',4,
            memory_note='Initial catalogue scope: '+scope+'; tools can browse the frozen full active bank.')
        old += ('\n## Fixed requirement choices\n'+encode(p2.view.catalog)+
            '\n## Groups of initially displayed records (scope: '+scope+')\n'+encode(p2.view.groups(aliases))+
            '\nP2 full snapshot active record count: '+str(len(p2.view.items))+'. Unclassified remains reachable.\n')
        rows = json.loads(new.split('## Selectable catalogue\n',1)[1].split('\n',1)[0])
        self.assertNotIn('## Fixed requirements and initial memberships',new)
        self.assertEqual(len(rows),41)
        self.assertEqual(rows[0]['content'],self.agent.task)
        for row in rows[1:]:
            alias = row['alias']
            original = p2.view.record(alias)
            self.assertEqual(row['content'],original['content'])
            self.assertEqual(row['requirements'],original['requirements'])
            self.assertEqual(row['source']['association'],original['source_association'])
            self.assertEqual(row['source']['count'],original['source_count'])
            order = original['source_event_order']
            self.assertEqual(row['source']['accepted_event_range'],[order['first'],order['last']])
        for requirement in fixed:
            self.assertEqual(new.count(encode(requirement)),len(aliases))
        # Topics intentionally repeat on each record; only metadata remains compact.
        self.assertLess(len(new),len(old))
        self.prompt_measurement = {'old_characters':len(old),'new_characters':len(new),
            'unit':'Python Unicode characters, not tokens','records':40,'requirement_characters':2048,
            'task_preserved':rows[0]['content']==self.agent.task}



if __name__=='__main__':
    unittest.main()
