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

    def test_prompts_keep_entire_original_system_and_only_feature_appendices(self):
        self.build()
        self.assertTrue(P1_SYSTEM.startswith(PHASE1_SYSTEM))
        self.assertTrue(self.p2.system.startswith(PHASE2_SYSTEM))
        self.assertIn('memory_save_gap',P1_SYSTEM)
        self.assertIn('requirements attribute',P1_SYSTEM)
        self.assertNotIn('Only the six memory tools',P1_SYSTEM)
        self.assertNotIn('Agent claims and self-printed success',P1_SYSTEM)
        self.assertLess(len(P1_SYSTEM),4000)

    def test_original_task_plus_eight_steps_is_query_and_raw_history_stays_visible(self):
        self.build()
        prefix = '\n### [WORKING MEMORY]\n<earlier_context>\nOLD RAW\n</earlier_context>\n<history>\nHISTORY RAW\n</history>\nCurrent turn: 9\n\n<key_info>CHECKPOINT RAW</key_info>'
        raw = json.dumps({'content':prefix,'tool_results':[{'content':'RECEIPT RAW'}]})
        entries = [{'step':i+2,'event_id':'new-'+str(i),'commands':['echo a']*6,
                    'observation':raw,'analysis':'visible actor analysis','plan':'visible plan'} for i in range(10)]
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
        self.assertEqual(len(self.agent.links.state['events']),10)  # two prior + eight new, no wrapper re-ingest.


if __name__=='__main__':
    unittest.main()
