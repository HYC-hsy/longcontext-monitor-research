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
            result = responses.pop(0)
            if isinstance(result,Exception):
                raise result
            return result(agent) if callable(result) else result
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
            trajectory=json.loads((episode.archive/'trajectory_memory.json').read_bytes())
            self.assertEqual(trajectory['summary']['total_operations'],1)
            self.assertEqual(len(trajectory['steps']),1)
            self.assertEqual(trajectory['steps'][0]['memory_snapshot']['gap_count'],0)
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

    def test_missing_tag_uses_upstream_fallback_with_visible_warning(self):
        responses=[reply(calls=[('requirements_initialize',{'requirements':[]})]),
            reply(),reply('<context_for_action>broken')]
        with tempfile.TemporaryDirectory() as tmp:
            episode,_=self.setup_run(Path(tmp),responses)
            result = asyncio.run(episode.handle(event('task_start',1,initial_user_content='Do A under C')))
            self.assertEqual(result['status'],'started')
            self.assertIsNone(episode._failure)
            row=json.loads((episode.archive/'requirement_cycles.jsonl').read_text().splitlines()[0])
            self.assertEqual(row['report']['status'],'no_intervention')
            self.assertIn('format_warning',row['report']['p2'])
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
            result = asyncio.run(episode.handle(event('task_start',1,initial_user_content='Do A under C')))
            self.assertEqual(result['memory_cycle_status'],'tool_error')
            self.assertIsNone(episode._failure)
            report=episode.agent._requirement_pipeline.p2.last_p2_report
            self.assertEqual(report['status'],'tool_error')
            self.assertIsNone(episode.agent._pending_injection)

    def test_initialization_failure_stops_before_p2(self):
        responses=[reply(content='not a requirements tool')]
        with tempfile.TemporaryDirectory() as tmp:
            episode,seen=self.setup_run(Path(tmp),responses)
            result = asyncio.run(episode.handle(event('task_start',1,initial_user_content='Do A under C')))
            self.assertEqual(result['memory_cycle_status'],'p1_incomplete')
            self.assertIsNone(episode._failure)
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

    def test_three_real_visible_outputs_survive_serial_adapter_and_original_delivery(self):
        fixture=json.loads((Path(__file__).parent/'fixtures/pma_p2_three_visible_outputs.json').read_bytes())
        for case in fixture['cases']:
            with self.subTest(member=case['source_member']), tempfile.TemporaryDirectory() as tmp:
                responses=[reply(calls=[('requirements_initialize',{'requirements':[]})]),reply(),reply(case['content'])]
                episode,_=self.setup_run(Path(tmp),responses)
                async def run():
                    result=await episode.handle(event('task_start',1,initial_user_content='Original task'))
                    self.assertEqual(result['status'],'started')
                    delivery=await episode.handle(event('before_actor_call',2,actor_attempt=1))
                    expected=episode.agent._requirement_pipeline.p2.last_p2_report['context_for_action']
                    self.assertEqual(delivery['status'],'reminder' if expected else 'silent')
                    if expected:
                        self.assertIn(expected,delivery['reminder'])
                    await episode.handle(event('task_end',3,terminal='synthetic; no Task run'))
                asyncio.run(run())
                trajectory=json.loads((episode.archive/'trajectory_memory.json').read_bytes())
                self.assertEqual(trajectory['summary']['total_triggers'],1)
                self.assertEqual(len(trajectory['steps']),1)
                self.assertEqual(trajectory['steps'][0]['raw_response_phase2'],case['content'])
                self.assertIsNone(episode._failure)

    def test_plain_model_conflict_records_error_but_next_serial_event_proceeds(self):
        raw='prefix <context_for_action>A</context_for_action><no_intervention/>'
        responses=[reply(calls=[('requirements_initialize',{'requirements':[]})]),reply(),reply(raw),
                   reply(),reply('<no_intervention/>')]
        with tempfile.TemporaryDirectory() as tmp:
            episode,_=self.setup_run(Path(tmp),responses)
            async def run():
                first=await episode.handle(event('task_start',1,initial_user_content='Original task'))
                self.assertEqual(first['memory_cycle_status'],'selection_error')
                self.assertEqual((await episode.handle(event('before_actor_call',2,actor_attempt=1)))['status'],'silent')
                after=await episode.handle(event('actor_step',3,actor_attempt=1,step_status='normal',
                    response='visible actor response',commands=['echo x'],observation='actual x receipt'))
                self.assertEqual(after['memory_cycle_status'],'no_intervention')
                await episode.handle(event('task_end',4,terminal='synthetic'))
            asyncio.run(run())
            rows=[json.loads(x)['report'] for x in (episode.archive/'requirement_cycles.jsonl').read_text().splitlines()]
            self.assertEqual(rows[0]['error_policy'],'continue_without_reminder')
            self.assertEqual(rows[0]['p2']['turns'][0]['assistant_text'],raw)
            self.assertEqual(episode.agent._requirement_memory_error_count,1)
            self.assertEqual(episode.agent._noop_count,1)  # Error is not counted as a normal no-op.
            self.assertIsNone(episode._failure)

    def test_optional_provider_failures_preserve_counts_and_committed_p1(self):
        for phase in ('maintenance','selection'):
            with self.subTest(phase=phase),tempfile.TemporaryDirectory() as tmp:
                p1=reply(calls=[('memory_save_knowledge',{'content':'saved','requirements':[],'source_ids':['TASK']})])
                responses=[reply(calls=[('requirements_initialize',{'requirements':[]})]),
                    RuntimeError('synthetic provider failure') if phase=='maintenance' else p1,
                    reply('prefix <no_intervention/>') if phase=='maintenance' else RuntimeError('synthetic provider failure')]
                episode,_=self.setup_run(Path(tmp),responses)
                result=asyncio.run(episode.handle(event('task_start',1,initial_user_content='Original task')))
                self.assertEqual(result['status'],'started')
                row=json.loads((episode.archive/'requirement_cycles.jsonl').read_text().splitlines()[0])['report']
                self.assertEqual((row['model_calls_attempted'],row['model_calls_completed']),(3,2))
                if phase=='maintenance':
                    self.assertEqual(row['p1']['failure_kind'],'transport')
                    self.assertEqual(row['p1_warning'],'memory_error')
                    self.assertEqual(episode.agent._memory_trajectory_steps[0]['memory_warning']['failure_kind'],'transport')
                    self.assertEqual(row['status'],'no_intervention')
                else:
                    self.assertEqual((row['status'],row['failure_kind']),('memory_error','transport'))
                    self.assertEqual([x.content for x in episode.agent._memory.knowledge],['saved'])
                    self.assertEqual(episode.agent._memory_operation_count,1)
                    self.assertIn('memory_error',episode.agent._memory_trajectory_steps[0])
                self.assertIsNone(episode._failure)

    def test_invalid_initialization_native_json_counts_return_and_retries_later(self):
        malformed=NS(content='visible invalid arguments',tool_calls=[NS(function=NS(name='requirements_initialize',arguments='{broken'))])
        responses=[malformed,reply(calls=[('requirements_initialize',{'requirements':[]})]),reply(),reply('<no_intervention/>')]
        with tempfile.TemporaryDirectory() as tmp:
            episode,_=self.setup_run(Path(tmp),responses)
            async def run():
                first=await episode.handle(event('task_start',1,initial_user_content='Original task'))
                self.assertEqual(first['memory_cycle_status'],'p1_incomplete')
                self.assertIsNone(episode.agent._memory_agent.requirement_state.data['catalog'])
                await episode.handle(event('before_actor_call',2,actor_attempt=1))
                await episode.handle(event('actor_step',3,actor_attempt=1,step_status='normal',response='visible actor response',observation='new receipt'))
            asyncio.run(run())
            rows=[json.loads(x)['report'] for x in (episode.archive/'requirement_cycles.jsonl').read_text().splitlines()]
            self.assertEqual((rows[0]['model_calls_attempted'],rows[0]['model_calls_completed']),(1,1))
            attempt=rows[0]['p1']['initialization_attempts'][0]
            self.assertEqual(attempt['assistant_text'],'visible invalid arguments')
            self.assertEqual(attempt['response_tool_calls'][0]['arguments'],'{broken')
            self.assertTrue(rows[0]['initialization_aborted_without_maintenance'])
            self.assertEqual(rows[1]['status'],'no_intervention')
            self.assertIsNone(episode._failure)

    def test_source_integrity_error_still_fail_stops_and_is_not_optional_noop(self):
        def corrupt(agent):
            p1=agent._memory_agent
            p1.source_archive.window_path('r_step_1_r0').write_bytes(b'corrupt window')
            return reply(calls=[('memory_read_source',{'entry':'M1','view':'context'})])
        responses=[reply(calls=[('requirements_initialize',{'requirements':[]})]),
            reply(calls=[('memory_save_knowledge',{'content':'saved','requirements':[],'source_ids':['TASK']})]),corrupt]
        with tempfile.TemporaryDirectory() as tmp:
            episode,_=self.setup_run(Path(tmp),responses)
            with self.assertRaises(EpisodeFault):
                asyncio.run(episode.handle(event('task_start',1,initial_user_content='Original task')))
            row=json.loads((episode.archive/'requirement_cycles.jsonl').read_text().splitlines()[0])['report']
            self.assertEqual((row['status'],row['failure_kind']),('tool_error','integrity'))
            self.assertNotIn('error_policy',row)
            self.assertIsNotNone(episode._failure)
            with self.assertRaises(EpisodeFault):
                asyncio.run(episode.handle(event('before_actor_call',2,actor_attempt=1)))


    def test_default_upstream_episode_keeps_original_two_calls_and_no_requirement_adapter(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            agent=construct_upstream(root/'upstream')
            calls=[]
            async def fake(**kw):
                calls.append(kw)
                return reply() if len(calls)==1 else reply('prefix <no_intervention/> explanation')
            agent._memory_llm.call=fake
            episode=PMAEpisode(agent,run_id='r',task_id='t',archive=root/'archive')
            result=asyncio.run(episode.handle(event('task_start',1,initial_user_content='Original task')))
            self.assertEqual(result['status'],'started')
            self.assertEqual(len(calls),2)
            from memory_agent.memory.memory_agent import PHASE1_SYSTEM, PHASE2_SYSTEM, BANK_TOOLS
            self.assertEqual(calls[0]['system'],PHASE1_SYSTEM)
            self.assertEqual(calls[0]['tools'],BANK_TOOLS)
            self.assertEqual(calls[1]['system'],PHASE2_SYSTEM)
            self.assertNotIn('tools',calls[1])
            self.assertFalse(hasattr(agent,'_requirement_pipeline'))
            self.assertEqual(agent._memory_trigger_count,1)
            self.assertEqual(len(agent._memory_trajectory_steps),1)
            self.assertFalse((episode.archive/'requirement_cycles.jsonl').exists())


    def test_initialization_transport_failure_retries_only_at_next_trigger(self):
        responses=[RuntimeError('synthetic initialization provider failure'),
            reply(calls=[('requirements_initialize',{'requirements':[]})]),reply(),reply('<no_intervention/>')]
        with tempfile.TemporaryDirectory() as tmp:
            episode,seen=self.setup_run(Path(tmp),responses)
            async def run():
                await episode.handle(event('task_start',1,initial_user_content='Original task'))
                self.assertEqual(len(seen),1)
                await episode.handle(event('before_actor_call',2,actor_attempt=1))
                await episode.handle(event('actor_step',3,actor_attempt=1,step_status='normal',
                    response='visible actor response',observation='new receipt'))
            asyncio.run(run())
            reports=[json.loads(x)['report'] for x in (episode.archive/'requirement_cycles.jsonl').read_text().splitlines()]
            self.assertEqual((reports[0]['model_calls_attempted'],reports[0]['model_calls_completed']),(1,0))
            self.assertEqual(reports[0]['p1']['failure_kind'],'transport')
            self.assertTrue(reports[0]['initialization_aborted_without_maintenance'])
            self.assertEqual(reports[1]['status'],'no_intervention')
            self.assertEqual(len(seen),4)
            self.assertIsNone(episode._failure)

    def test_malformed_native_json_in_each_phase_preserves_raw_and_does_not_fail_task(self):
        for phase in ('maintenance','selection'):
            bad=NS(content='visible malformed native arguments',tool_calls=[NS(function=NS(
                name='memory_save_knowledge' if phase=='maintenance' else 'memory_browse',arguments='{broken'))])
            responses=[reply(calls=[('requirements_initialize',{'requirements':[]})]),
                       bad if phase=='maintenance' else reply(),
                       reply('<no_intervention/>') if phase=='maintenance' else bad]
            with self.subTest(phase=phase),tempfile.TemporaryDirectory() as tmp:
                episode,_=self.setup_run(Path(tmp),responses)
                result=asyncio.run(episode.handle(event('task_start',1,initial_user_content='Original task')))
                self.assertEqual(result['status'],'started')
                report=json.loads((episode.archive/'requirement_cycles.jsonl').read_text().splitlines()[0])['report']
                record=report['p1' if phase=='maintenance' else 'p2']
                self.assertEqual(record['failure_kind'],'model_output')
                self.assertEqual(record['turns'][0]['response_tool_calls'][0]['arguments'],'{broken')
                self.assertEqual((report['model_calls_attempted'],report['model_calls_completed']),(3,3))
                self.assertEqual(episode.agent._memory.knowledge,[])
                self.assertIsNone(episode._failure)



if __name__=='__main__':
    unittest.main()
