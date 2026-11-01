"""Characterize original non-atomic operations and retained selection checks."""
import asyncio
import json
from types import SimpleNamespace as NS
import unittest

from pma_evidence_review.tests import test_bank_display as fixtures
from pma_evidence_review.tests.test_bank_display import reply
from pma_evidence_review.tests.no_network import install_guard


class BankDisplayBoundaryTests(unittest.TestCase):
    def setUp(self):
        install_guard(self)

    def agent(self, *args, **kwargs):
        return fixtures.BankDisplayTests().agent(*args, **kwargs)

    def test_each_application_failure_keeps_independent_successes(self):
        a, _ = self.agent()
        old = a.memory.save_gap('old')
        ops = a._execute_tool_calls(reply([
            ('memory_save_gap', {'content': ''}),
            ('memory_delete', {'memory_id': old}),
            ('memory_save_knowledge', {'content': 'later success'}),
            ('memory_delete', {'memory_id': 'missing'}),
            ('memory_save_gap', {'content': 'new pending'})]))
        self.assertEqual([op.success for op in ops], [False,True,True,False,True])
        self.assertEqual([e.content for e in a.memory.entries], ['new pending'])
        self.assertEqual([e.content for e in a.memory.knowledge], ['later success'])
        # Save-first ordering is not a conditional replacement or rollback.
        self.assertNotIn(old, a._active_records())

    def test_delete_then_failed_save_and_success_then_failed_delete(self):
        a, _ = self.agent()
        key = a.memory.save_gap('old')
        ops = a._execute_tool_calls(reply([
            ('memory_delete', {'memory_id': key}), ('memory_save_gap', {'content': ''})]))
        self.assertEqual([op.success for op in ops], [True,False])
        self.assertEqual(a.memory.entries, [])
        key = a.memory.save_gap('retained')
        ops = a._execute_tool_calls(reply([
            ('memory_save_gap', {'content': 'new'}),
            ('memory_delete', {'memory_id': 'gap_missing'})]))
        self.assertEqual([op.success for op in ops], [True,False])
        self.assertEqual(len(a.memory.entries), 2)
        self.assertIn(key, a._active_records())

    def test_vendor_extra_parameters_do_not_update_existing_id(self):
        a, _ = self.agent()
        key = a.memory.save_knowledge('original')
        ops = a._execute_tool_calls(reply([('memory_save_knowledge', {
            'content': 'new', 'memory_id': key, 'evidence': [{'quote':'ignored by vendor'}]})]))
        self.assertTrue(ops[0].success)
        self.assertNotEqual(ops[0].memory_id, key)
        self.assertEqual([e.content for e in a.memory.knowledge], ['original','new'])
        # Existing GAP_TOOL is stricter than the original four executors.
        ops = a._execute_tool_calls(reply([('memory_save_gap', {'content':'gap','evidence':[]})]))
        self.assertFalse(ops[0].success)

    def test_json_preflight_can_abort_batch_before_writes_phase2_still_runs(self):
        a, req = self.agent(output='<intervene>TASK</intervene>')
        broken = reply([('memory_save_knowledge', {'content':'would save'})])
        broken.tool_calls.append(NS(function=NS(name='memory_save_gap', arguments='{broken')))
        with self.assertRaises(json.JSONDecodeError):
            a._execute_tool_calls(broken)
        self.assertEqual(a.memory.knowledge, [])
        original = a.llm.call
        async def fake(**kw):
            if a.transport_phase == 'maintenance':
                req.append(kw)
                return broken
            return await original(**kw)
        a.llm.call = fake
        result = asyncio.run(a.process('raw', 1))
        self.assertTrue(result.should_inject)
        self.assertEqual(len(req), 2)
        self.assertEqual(a.memory.knowledge, [])

    def test_invalid_output_is_not_silent_and_all_snapshot_bindings_checked(self):
        for output in ('<intervene>M9</intervene>', '<intervene>M1,M1</intervene>',
                       '{"decision":"intervene"}', '<context_for_action>x</context_for_action>'):
            a, _ = self.agent([('memory_save_knowledge', {'content':'fact'})], output)
            result = asyncio.run(a.process('raw', 1))
            self.assertFalse(result.should_inject)
            self.assertEqual(a.last_selection_report['status'], 'selection_error')
        for changed in ('call','cycle','task','delete','content'):
            a, _ = self.agent([('memory_save_knowledge', {'content':'fact'})], '<intervene>M1</intervene>')
            asyncio.run(a.process('raw', 1))
            if changed == 'call':
                a._completion_call_id = 'wrong-call'
            elif changed == 'cycle':
                a._active_selection_cycle = 'wrong-cycle'
            elif changed == 'task':
                a.task = 'changed task'
            elif changed == 'delete':
                a.memory.delete(a.memory.knowledge[0].id)
            else:
                a.memory.knowledge[0].content = 'changed content'
            self.assertIsNone(a._parse_phase2_response('<intervene>M1</intervene>'), changed)
            self.assertEqual(a.last_selection_report['status'], 'selection_error', changed)

    def test_evidence_instances_rejected_before_any_conversion(self):
        from latest_evidence_gap_store import LatestEvidenceGapMemory
        from aligned_evidence_gap_store import AlignedEvidenceGapMemory
        from bank_display_agent import BankDisplayAgent
        for bank in (LatestEvidenceGapMemory(), AlignedEvidenceGapMemory()):
            with self.assertRaises(TypeError):
                BankDisplayAgent(task='task', memory=bank, llm=None)

    def test_actual_before_actor_call_drops_mutated_pending_content(self):
        import tempfile
        from pathlib import Path
        from episode import construct_upstream, PMAEpisode
        from citation_gate_config import BANK_DISPLAY_POLICY
        for mutation in ('delete', 'content', 'task', 'cycle'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                actor = construct_upstream(root/'upstream', research_candidate='pma_gap_memory_v0',
                    memory_maintenance_policy=BANK_DISPLAY_POLICY)
                agent = actor._memory_agent
                async def fake(**kw):
                    if agent.transport_phase == 'maintenance':
                        return reply([('memory_save_knowledge', {'content':'original fact'})])
                    return reply(content='<intervene>M1</intervene>')
                actor._memory_llm.call = fake
                episode = PMAEpisode(actor, run_id='r', task_id='t', archive=root/'archive')
                asyncio.run(episode.handle(dict(kind='task_start', sequence=1, event_id='e1',
                    run_id='r', task_id='t', initial_user_content='task')))
                self.assertIsNotNone(actor._pending_injection)
                if mutation == 'delete':
                    actor._memory.delete(actor._memory.knowledge[0].id)
                elif mutation == 'content':
                    actor._memory.knowledge[0].content = 'changed'
                elif mutation == 'task':
                    agent.task = 'changed task'
                else:
                    agent._active_selection_cycle = 'changed cycle'
                result = asyncio.run(episode.handle(dict(kind='before_actor_call', sequence=2,
                    event_id='e2', run_id='r', task_id='t', actor_attempt=1)))
                self.assertEqual(result['status'], 'silent')
                self.assertIsNone(actor._pending_injection)
                self.assertIn('delivery_error', agent.last_gap_report)

    def test_real_episode_keeps_exact_latest_eight_steps_for_both_phases(self):
        import tempfile
        from pathlib import Path
        from episode import construct_upstream, PMAEpisode
        from citation_gate_config import BANK_DISPLAY_POLICY
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            actor = construct_upstream(root/'upstream', research_candidate='pma_gap_memory_v0',
                memory_maintenance_policy=BANK_DISPLAY_POLICY)
            agent, requests = actor._memory_agent, []
            async def fake(**kw):
                requests.append(kw)
                return reply(content='<no_intervention/>')
            actor._memory_llm.call = fake
            episode = PMAEpisode(actor, run_id='r', task_id='t', archive=root/'archive')
            async def run():
                seq = 0
                async def emit(kind, **fields):
                    nonlocal seq
                    seq += 1
                    return await episode.handle(dict(kind=kind, sequence=seq, event_id=f'e{seq}',
                        run_id='r', task_id='t', **fields))
                await emit('task_start', initial_user_content='Original whole task')
                for turn in range(1,10):
                    await emit('before_actor_call', actor_attempt=turn)
                    await emit('actor_step', actor_attempt=turn, step_status='normal',
                        response=f'report {turn}', commands=[f'UNIQUE_COMMAND_{turn}_END'],
                        observation=json.dumps({'content':f'report {turn}', 'tool_results':[
                            {'tool_use_id':str(turn), 'content':f'UNIQUE_RECEIPT_{turn}_END'}]}))
            asyncio.run(run())
            for kw in requests[-2:]:
                self.assertIn('Original whole task', kw['prompt'])
                for turn in range(2,10):
                    self.assertIn(f'UNIQUE_COMMAND_{turn}_END', kw['prompt'])
                    self.assertIn(f'UNIQUE_RECEIPT_{turn}_END', kw['prompt'])
                self.assertNotIn('UNIQUE_COMMAND_1_END', kw['prompt'])
                self.assertNotIn('UNIQUE_RECEIPT_1_END', kw['prompt'])
