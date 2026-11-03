"""Strict fake-client checks of the opt-in Task adapter, never model semantics."""
import asyncio
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
import sys

from pma_evidence_review.tests.no_network import install_guard
from pma_evidence_review.tests import test_bank_display as _stage_import
from episode import construct_upstream, PMAEpisode
from citation_gate_config import REQUIREMENT_REMINDER_POLICY
from pma_evidence_review.private_faults import EpisodeFault
from worker_main import install_transport_audit


def reply(content='', calls=()):
    return NS(content=content,tool_calls=[NS(function=NS(name=name,
        arguments=json.dumps(args,ensure_ascii=False))) for name,args in calls])


def event(kind,seq,**fields):
    return dict(schema='pma-ga-events-v1',run_id='r',task_id='t',kind=kind,
                sequence=seq,event_id='e'+str(seq),**fields)


class RequirementTaskEntryTests(unittest.TestCase):
    def setUp(self):
        install_guard(self)

    def setup_run(self,root,responses):
        agent=construct_upstream(root/'upstream',research_candidate='pma_gap_memory_v0',
            memory_maintenance_policy=REQUIREMENT_REMINDER_POLICY)
        seen=[]
        async def fake(**kw):
            seen.append((agent._memory_agent.transport_phase,kw))
            return responses.pop(0)
        agent._memory_llm.call=fake
        episode=PMAEpisode(agent,run_id='r',task_id='t',archive=root/'archive')
        install_transport_audit(agent,episode.archive)
        return episode,seen

    def test_initialization_direct_silence_and_durable_logs(self):
        responses=[reply(calls=[('requirements_initialize',{'requirements':['Do A under C']})]),
            reply(calls=[('memory_save_knowledge',{'content':'Do A under C',
                'source_ids':['TASK'],'requirements':['Do A under C']})]),
            reply('<no_intervention/>')]
        with tempfile.TemporaryDirectory() as tmp:
            episode,seen=self.setup_run(Path(tmp),responses)
            async def run():
                self.assertEqual((await episode.handle(event('task_start',1,
                    initial_user_content='Do A under C')))['status'],'started')
                self.assertEqual((await episode.handle(event('before_actor_call',2,
                    actor_attempt=1)))['status'],'silent')
                self.assertEqual((await episode.handle(event('task_end',3,
                    terminal='synthetic')))['status'],'saved')
            asyncio.run(run())
            self.assertEqual([phase for phase,_ in seen],
                ['requirement_initialization','maintenance','selection'])
            self.assertEqual(episode.agent._memory_agent.source_archive.task,'Do A under C')
            self.assertEqual([x.content for x in episode.agent._memory.knowledge],['Do A under C'])
            self.assertTrue((episode.archive/'requirement_cycles.jsonl').is_file())
            self.assertEqual(len((episode.archive/'memory_payload.jsonl').read_text().splitlines()),3)

    def test_reminder_is_returned_then_only_counted_after_actor_request(self):
        responses=[reply(calls=[('requirements_initialize',{'requirements':[]})]),
            reply(),reply('<context_for_action>Remember C.</context_for_action>')]
        with tempfile.TemporaryDirectory() as tmp:
            episode,_=self.setup_run(Path(tmp),responses)
            async def run():
                await episode.handle(event('task_start',1,initial_user_content='Do A under C'))
                self.assertEqual(episode.agent._pending_injection,'Remember C.')
                result=await episode.handle(event('before_actor_call',2,actor_attempt=1))
                self.assertEqual(result['status'],'reminder',str(episode.agent._requirement_pipeline.p2.last_p2_report))
                self.assertIn('Remember C.',result['reminder'])
                self.assertEqual(result['delivery'],'returned_not_confirmed_in_ga_request')
                ga_root=Path(__file__).resolve().parents[2]/'GenericAgent-main'
                sys.path.insert(0,str(ga_root))
                try:
                    from pma_upstream_bridge import append_reminder
                    next_request={'messages':[{'role':'user','content':'Visible current Task input'}]}
                    next_request['messages'][-1]=append_reminder(next_request['messages'][-1],result['reminder'])
                    self.assertIn('Remember C.',next_request['messages'][-1]['content'])
                finally:
                    sys.path.remove(str(ga_root))
            asyncio.run(run())

    def test_p2_optional_browse_and_source_read(self):
        responses=[reply(calls=[('requirements_initialize',{'requirements':[]})]),
            reply(),reply(calls=[('memory_browse',{'view':'all'})]),
            reply(calls=[('memory_read_source',{'entry':'TASK'})]),
            reply('<no_intervention/>')]
        with tempfile.TemporaryDirectory() as tmp:
            episode,seen=self.setup_run(Path(tmp),responses)
            asyncio.run(episode.handle(event('task_start',1,initial_user_content='Do A under C')))
            self.assertEqual(len(seen),5)
            report=episode.agent._requirement_pipeline.p2.last_p2_report
            self.assertEqual(report['tool_requests'],2)
            self.assertEqual(report['status'],'no_intervention')

    def test_bad_output_is_engineering_error_not_silence(self):
        responses=[reply(calls=[('requirements_initialize',{'requirements':[]})]),
            reply(),reply('<context_for_action>broken')]
        with tempfile.TemporaryDirectory() as tmp:
            episode,_=self.setup_run(Path(tmp),responses)
            with self.assertRaises(EpisodeFault):
                asyncio.run(episode.handle(event('task_start',1,initial_user_content='Do A under C')))
            self.assertIsNotNone(episode._failure)
            row=json.loads((episode.archive/'requirement_cycles.jsonl').read_text().splitlines()[0])
            self.assertEqual(row['report']['status'],'selection_error')
            self.assertIsNone(episode.agent._pending_injection)

    def test_next_event_keeps_real_event_id_and_new_cycle_uses_actual_result(self):
        responses=[reply(calls=[('requirements_initialize',{'requirements':[]})]),
            reply(),reply('<no_intervention/>'),reply(),reply('<no_intervention/>')]
        with tempfile.TemporaryDirectory() as tmp:
            episode,seen=self.setup_run(Path(tmp),responses)
            async def run():
                await episode.handle(event('task_start',1,initial_user_content='Do A under C'))
                await episode.handle(event('before_actor_call',2,actor_attempt=1))
                await episode.handle(event('actor_step',3,actor_attempt=1,step_status='normal',
                    response='Visible actor response',commands=['tool id=call-1'],
                    observation='Observed result from call-1'))
                await episode.handle(event('task_end',4,terminal='synthetic'))
            asyncio.run(run())
            self.assertEqual([x[0] for x in seen],
                ['requirement_initialization','maintenance','selection','maintenance','selection'])
            self.assertIn('Observed result from call-1',seen[3][1]['prompt'])
            rows=[json.loads(line) for line in (episode.archive/'requirement_cycles.jsonl').read_text().splitlines()]
            self.assertEqual(rows[1]['entries'][0]['event_id'],'e3')
            self.assertEqual(rows[1]['entries'][0]['commands'],['tool id=call-1'])

    def test_changed_bank_rejects_pending_delivery(self):
        responses=[reply(calls=[('requirements_initialize',{'requirements':[]})]),
            reply(),reply('<context_for_action>Remember C.</context_for_action>')]
        with tempfile.TemporaryDirectory() as tmp:
            episode,_=self.setup_run(Path(tmp),responses)
            async def run():
                await episode.handle(event('task_start',1,initial_user_content='Do A under C'))
                episode.agent._memory.update_status('changed after reminder')
                with self.assertRaises(EpisodeFault):
                    await episode.handle(event('before_actor_call',2,actor_attempt=1))
            asyncio.run(run())
            self.assertIsNotNone(episode._failure)

    def test_p2_tool_error_is_not_normal_no_intervention(self):
        responses=[reply(calls=[('requirements_initialize',{'requirements':[]})]),
            reply(),reply(calls=[('memory_read_source',{'entry':'UNKNOWN'})])]
        with tempfile.TemporaryDirectory() as tmp:
            episode,_=self.setup_run(Path(tmp),responses)
            with self.assertRaises(EpisodeFault):
                asyncio.run(episode.handle(event('task_start',1,initial_user_content='Do A under C')))
            report=episode.agent._requirement_pipeline.p2.last_p2_report
            self.assertEqual(report['status'],'tool_error')
            self.assertIsNone(episode.agent._pending_injection)

    def test_initialization_failure_stops_before_p2(self):
        responses=[reply(content='not a requirements tool')]
        with tempfile.TemporaryDirectory() as tmp:
            episode,seen=self.setup_run(Path(tmp),responses)
            with self.assertRaises(EpisodeFault):
                asyncio.run(episode.handle(event('task_start',1,initial_user_content='Do A under C')))
            self.assertEqual(len(seen),1)
            rows=[json.loads(line) for line in (episode.archive/'requirement_cycles.jsonl').read_text().splitlines()]
            self.assertEqual(rows[0]['report']['p1']['status'],'initialization_failed')
            self.assertIsNone(rows[0]['report']['p2'])

    def test_cycle_log_write_failure_never_reports_started(self):
        responses=[reply(calls=[('requirements_initialize',{'requirements':[]})]),
            reply(),reply('<no_intervention/>')]
        with tempfile.TemporaryDirectory() as tmp:
            episode,_=self.setup_run(Path(tmp),responses)
            (episode.archive/'requirement_cycles.jsonl').mkdir()
            with self.assertRaises(EpisodeFault):
                asyncio.run(episode.handle(event('task_start',1,initial_user_content='Do A under C')))
            self.assertIsNotNone(episode._failure)
            self.assertFalse((episode.archive/'events.jsonl').exists())


if __name__=='__main__':
    unittest.main()
