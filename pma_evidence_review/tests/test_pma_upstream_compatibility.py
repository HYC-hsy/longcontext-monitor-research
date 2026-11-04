"""Original PMA text extraction and task/window inputs; no real clients."""
import asyncio
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest
from pma_evidence_review.tests import test_p2_requirement_reminder as fixtures
from pma_evidence_review.tests.test_bank_display import reply
from memory_agent.memory.memory_agent import MemoryAgent, PHASE1_SYSTEM, PHASE2_SYSTEM
from memory_agent.memory_enabled_agent import MemoryEnabledTerminus2
from p1_requirement_agent import SYSTEM as P1_SYSTEM
from p1_requirements import upstream_observation


class UpstreamCompatibilityTests(unittest.TestCase):
    setUp = fixtures.ReminderTests.setUp
    init = fixtures.ReminderTests.init
    save = fixtures.ReminderTests.save
    run_cycle = fixtures.ReminderTests.run_cycle
    build = fixtures.ReminderTests.build
    run_reminder = fixtures.ReminderTests.run_reminder

    def test_three_archived_visible_outputs_match_original_pma_extraction(self):
        self.build()
        fixture = json.loads((Path(__file__).parent/'fixtures/pma_p2_three_visible_outputs.json').read_bytes())
        self.assertEqual(len(fixture['cases']),3)
        for case in fixture['cases']:
            with self.subTest(member=case['source_member']):
                raw = case['content']
                self.assertEqual(hashlib.sha256(raw.encode()).hexdigest(),case['visible_output_sha256'])
                self.p2_responses = [reply(content=raw)]
                result = self.run_reminder()
                expected = MemoryAgent._parse_phase2_response(self.p2,raw)
                self.assertEqual(result['delivery'],expected)
                self.assertEqual(result['status'],'intervention' if expected else 'no_intervention')
                self.assertEqual((result['model_calls_attempted'],result['reads_used']),(1,0))
                self.assertEqual(result['turns'][0]['assistant_text'],raw)
                self.assertEqual(result['raw_output'],raw)

    def test_conflicts_are_logged_before_classification_and_execute_no_tools(self):
        self.build()
        samples = [
            reply(content='<context_for_action>A</context_for_action><no_intervention/>'),
            reply(content='<context_for_action>A</context_for_action><context_for_action>B</context_for_action>'),
            reply([('memory_browse',{})],content='prefix <no_intervention/>'),
            reply(content='<tool_call><function=memory_browse></function></tool_call><no_intervention/>')]
        for response in samples:
            self.p2_responses = [response]
            result = self.run_reminder()
            self.assertEqual((result['status'],result['failure_kind']),('selection_error','model_output'))
            self.assertEqual(result['reads_used'],0)
            self.assertEqual(result['turns'][0]['assistant_text'],response.content)
            self.assertIn('parse_error',result['turns'][0])
            self.assertIsNone(result['delivery'])

    def test_prompts_preserve_p2_and_align_p1_to_approved_guidance(self):
        self.build()
        self.assertEqual(self.p2.system.split('## PROCESS:',1)[0], PHASE2_SYSTEM.split('## PROCESS:',1)[0])
        self.assertEqual(self.p2.system.split('## OUTPUT FORMAT:',1)[1].split('## GUIDELINES:',1)[0],
                         PHASE2_SYSTEM.split('## OUTPUT FORMAT:',1)[1].split('## GUIDELINES:',1)[0])
        self.assertIn('Memory is a fallible overview, not independent evidence.', self.p2.system)
        self.assertIn('Retrieval is optional.', self.p2.system)
        self.assertNotIn('Four shared reads', self.p2.system)
        self.assertNotIn('last turn has no tools', self.p2.system)
        for text in (
            'You are a Memory Bank Manager.',
            'The original task remains authoritative',
            'Include a cause or explanation only when supported',
            'A local or partial result does not by itself establish',
            'The action agent\'s statements and existing memory may be mistaken',
            'If the conflict is unresolved, preserve the uncertainty',
            'until the condition is satisfied, the question is answered',
            'they do not by themselves establish evidence or completion',
        ):
            self.assertIn(text, P1_SYSTEM)
        self.assertIn('Organize entries using the supplied topics', P1_SYSTEM)
        self.assertIn('When saving, choose one or more relevant topics', P1_SYSTEM)
        self.assertLess(P1_SYSTEM.index('Organize entries using the supplied topics'), P1_SYSTEM.index('## Your Tools'))
        self.assertEqual(P1_SYSTEM.count('Topic assignments and source links organize memory'), 1)
        self.assertNotIn('Additional memory support:', P1_SYSTEM)
        self.assertNotIn('save the replacement before deleting', P1_SYSTEM)
        self.assertLess(len(P1_SYSTEM), 4000)

    def test_p1_tool_contract_is_unchanged(self):
        self.build()
        tools = {row['function']['name']: row['function']
                 for row in self.agent.get_tools_schema()}
        self.assertEqual(set(tools), {
            'memory_save_knowledge', 'memory_save_procedural', 'memory_save_gap',
            'memory_update_status', 'memory_delete', 'memory_read_source'})
        for name in ('memory_save_knowledge', 'memory_save_procedural', 'memory_save_gap'):
            params = tools[name]['parameters']
            self.assertEqual(set(params['required']), {'content', 'requirements'})
            self.assertEqual(set(params['properties']), {'content', 'requirements', 'source_ids'})
            self.assertFalse(params['additionalProperties'])
        self.assertEqual(set(tools['memory_update_status']['parameters']['required']), {'content'})
        self.assertEqual(set(tools['memory_delete']['parameters']['required']), {'entry'})
        self.assertEqual(set(tools['memory_read_source']['parameters']['required']), {'entry'})
        self.assertIn('only when supported', tools['memory_save_procedural']['description'])
        self.assertIn('history handles are read-only', tools['memory_delete']['description'])
        self.assertIn('same entry and view', tools['memory_read_source']['description'])

    def test_original_task_plus_eight_steps_is_query_and_raw_history_stays_visible(self):
        self.build()
        prefix = '\n### [WORKING MEMORY]\n<earlier_context>\nOLD RAW\n</earlier_context>\n<history>\nHISTORY RAW\n</history>\nCurrent turn: 9\n\n<key_info>CHECKPOINT RAW</key_info>'
        raw = json.dumps({'content':prefix,'tool_results':[{'content':'RECEIPT RAW'}]})
        entries = [{'step':i+2,'event_id':'new-'+str(i),'commands':['echo a']*6,
                    'observation':raw,'analysis':'visible actor analysis','plan':'visible plan',
                    'evaluation_label':'DO NOT SEND EVALUATION METADATA'} for i in range(10)]
        original = deepcopy(entries)
        expected = upstream_observation(self.agent.task,entries)
        self.assertIn(self.agent.task,expected)
        self.assertIn('[Recent Trajectory (last 8 steps)]',expected)
        self.assertNotIn('[Step 2]',expected)
        self.assertIn('(+1 more)',expected)
        self.assertEqual(entries,original)
        with unittest.mock.patch.object(self.agent.memory,'search_knowledge',return_value=[]) as search:
            self.agent.max_memory_in_prompt=0
            self.agent.use_bm25_prefilter=True
            self.responses=[reply()]
            self.run_cycle('query',entries)
            search.assert_called_once_with(expected,top_k=20)
        prompt = self.requests[-1]['prompt']
        self.assertIn('HISTORY RAW',prompt)
        self.assertIn('CHECKPOINT RAW',prompt)
        self.assertIn('OLD RAW',prompt)
        self.assertIn('RECEIPT RAW',prompt)
        self.p2.max_memory_in_prompt=0
        with unittest.mock.patch.object(self.agent.memory.__class__,'search_knowledge',return_value=[]) as search:
            self.p2._prepare(expected,entries,12)
            search.assert_called_once_with(expected,top_k=20)
        p2prompt,_=self.p2._prepare(expected,entries,12)
        self.assertIn('HISTORY RAW',p2prompt)
        self.assertIn('CHECKPOINT RAW',p2prompt)
        self.assertNotIn('DO NOT SEND EVALUATION METADATA',p2prompt)
        self.assertEqual(len(self.agent.links.state['events']),10)  # two prior + eight new, no wrapper re-ingest.
        bad = reply([('memory_save_knowledge',{})])
        bad.tool_calls[0].function.arguments = '{broken'
        self.responses = [bad]
        report = self.run_cycle('bad_seen',[{'event_id':'after-error','observation':'already presented raw'}])
        self.assertEqual(report['failure_kind'],'model_output')
        accepted = self.agent.links.state['accepted']['after-error']
        self.assertIn(accepted,self.agent.links.state['presented'])


if __name__=='__main__':
    unittest.main()
