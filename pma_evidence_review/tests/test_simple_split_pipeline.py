"""Bounded pipeline fixtures; no model, network, Task, or effect claims."""
import asyncio
import json
import unittest
from types import SimpleNamespace as NS

from pma_evidence_review import claim_split_simple as cs
from pma_evidence_review.tests import test_live_gate as host
from pma_evidence_review.tests.no_network import install_guard


class SimplePipelineTests(unittest.TestCase):
    def setUp(self):
        install_guard(self)

    async def run_cycle(self, calls, *, bank=None, hook=None, repair_limit=0):
        bank = bank if bank is not None else host.LatestEvidenceGapMemory()
        events = []
        async def fake(**kw):
            phase = agent.transport_phase
            if phase == 'maintenance':
                return host.reply(calls)
            if phase == 'selection':
                events.append(('selection', len(bank.knowledge)))
                return host.reply(content='<no_intervention/>')
            if phase == 'citation_repair':
                events.append(('repair', 0))
                value = {'decision': 'replace', 'content': 'repaired',
                         'evidence': [{'quote': host.TEXT}]}
                if hook:
                    override = await hook('repair', 0, bank, events)
                    if override is not None:
                        value = override
                return host.reply(content=json.dumps(value))
            first = kw['prompt'].split('\n', 1)[1]
            material = json.loads(first.split('\nSUBMITTED EVIDENCE ONLY')[0])
            index = material['original_operation']['op_index']
            kind = 'split' if kw['prompt'].startswith('CLOSED MATERIAL') else 'review'
            events.append((kind, index))
            override = await hook(kind, index, bank, events) if hook else None
            if isinstance(override, BaseException):
                raise override
            value = ([material['original_operation']['content']] if kind == 'split' else
                     {'overall': {'verdict': 'supported', 'reason': 'fixture'},
                      'results': [{'verdict': 'supported', 'reason': 'fixture'}]})
            return host.reply(content=json.dumps(value if override is None else override))
        agent = host.CitationGateMemoryAgent(task='synthetic', memory=bank, llm=NS(call=fake),
                    review_strategy=cs.STRATEGY, repair_limit=repair_limit)
        self.agent = agent
        agent.prepare_visible_context('UNQUOTED SECRET', [{'source_id': 'e1',
            'role': 'tool_observation', 'order': 1, 'field_path': 'result', 'text': host.TEXT,
            'record_digest': host.sha256(host.TEXT), 'record_digest_kind': 'event'}])
        result = await agent.process('UNQUOTED SECRET', 1)
        return agent, result, events

    def test_overlap_keeps_both_commits_and_exact_candidate_identity(self):
        async def scenario():
            second_split = asyncio.Event()
            async def hook(kind, index, bank, events):
                if (kind, index) == ('split', 1):
                    second_split.set()
                if (kind, index) == ('review', 0):
                    await asyncio.wait_for(second_split.wait(), 2)
                    self.assertEqual(bank.knowledge, [])
            agent, result, events = await self.run_cycle([host.write('one'), host.write('two')], hook=hook)
            self.assertEqual([o.success for o in result.operations], [True, True], agent.last_citation_gate_report)
            self.assertEqual([e.content for e in agent.memory.knowledge], ['one', 'two'])
            for row in agent.last_citation_gate_report['operations']:
                original = row['attempts'][0]['input']['operation']
                self.assertEqual(original['revision_id'], row['candidate']['revision_id'])
                self.assertEqual(agent.memory.active_revisions[original['memory_id']], original['revision_id'])
            self.assertEqual(events[-1], ('selection', 2))
        asyncio.run(scenario())

    def test_same_target_waits_and_keeps_revision_chain(self):
        async def scenario():
            bank = host.LatestEvidenceGapMemory()
            key = bank.save_knowledge('old')
            async def hook(kind, index, bank, events):
                if (kind, index) == ('split', 1):
                    self.assertEqual(bank.knowledge[0].content, 'one')
            agent, result, _ = await self.run_cycle([host.write('one', key), host.write('two', key)], bank=bank, hook=hook)
            self.assertTrue(all(o.success for o in result.operations), agent.last_citation_gate_report)
            first, second = agent.last_citation_gate_report['operations']
            self.assertEqual(bank.revisions[second['candidate']['revision_id']].previous_revision_id,
                             first['candidate']['revision_id'])
        asyncio.run(scenario())

    def test_independent_review_advances_during_repair_but_cannot_commit_first(self):
        async def scenario():
            second_review = asyncio.Event()
            first_rejected = False
            async def hook(kind, index, bank, events):
                nonlocal first_rejected
                if (kind, index) == ('review', 1):
                    second_review.set()
                    self.assertEqual(bank.knowledge, [])
                if (kind, index) == ('review', 0) and not first_rejected:
                    first_rejected = True
                    return {'overall': {'verdict': 'insufficient', 'reason': 'fixture'},
                            'results': [{'verdict': 'insufficient', 'reason': 'fixture'}]}
                if kind == 'repair':
                    await asyncio.wait_for(second_review.wait(), 2)
            agent, result, _ = await self.run_cycle([host.write('one'), host.write('two')], hook=hook, repair_limit=1)
            self.assertTrue(all(o.success for o in result.operations), agent.last_citation_gate_report)
            self.assertEqual([e.content for e in agent.memory.knowledge], ['repaired', 'two'])
            self.assertEqual(agent.last_citation_gate_report['repair_calls'], 1)
        asyncio.run(scenario())

    def test_cancellation_drains_without_publication(self):
        async def scenario():
            reached = asyncio.Event()
            async def hook(kind, index, bank, events):
                if kind == 'review':
                    reached.set()
                    await asyncio.Event().wait()
            task = asyncio.create_task(self.run_cycle([host.write('one'), host.write('two')], hook=hook))
            await asyncio.wait_for(reached.wait(), 2)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertEqual(self.agent.memory.knowledge, [])
            self.assertTrue(all(t.done() for t in self.agent._pipeline_tasks))
        asyncio.run(scenario())

    def test_local_invalid_operation_does_not_drop_later_valid_operation(self):
        async def scenario():
            agent, result, _ = await self.run_cycle([('bad_tool', {}), host.write('valid')])
            self.assertEqual([o.success for o in result.operations], [False, True], agent.last_citation_gate_report)
        asyncio.run(scenario())

    def test_independent_legacy_targets_preserve_precycle_normalization(self):
        async def scenario():
            bank = host.LatestEvidenceGapMemory()
            first = bank.save_knowledge('old first')
            second = bank.save_knowledge('old second')
            agent, result, _ = await self.run_cycle(
                [host.write('new first', first), host.write('new second', second)], bank=bank)
            self.assertEqual([o.success for o in result.operations], [True, True], agent.last_citation_gate_report)
            self.assertEqual([e.content for e in bank.knowledge], ['new first', 'new second'])
            bank.validate_bank()
        asyncio.run(scenario())

    def test_transport_failure_cancels_speculation_and_blocks_publication(self):
        async def scenario():
            second_started = asyncio.Event()
            async def hook(kind, index, bank, events):
                if (kind, index) == ('split', 1):
                    second_started.set()
                    await asyncio.Event().wait()
                if (kind, index) == ('review', 0):
                    await asyncio.wait_for(second_started.wait(), 2)
                    return RuntimeError('transport fixture')
            agent, result, _ = await self.run_cycle([host.write('one'), host.write('two')], hook=hook)
            self.assertEqual([o.success for o in result.operations], [False, False])
            self.assertEqual(agent.memory.knowledge, [])
            self.assertTrue(all(t.done() for t in agent._pipeline_tasks))
            self.assertEqual(agent.pending_receipt['operations'][1]['outcome'], 'not_run')
            second = agent.last_citation_gate_report['operations'][1]
            self.assertEqual(len(second['attempts']), 1)
            self.assertEqual(second['attempts'][0]['engineering_status'], 'cancelled')
        asyncio.run(scenario())

    def test_external_target_change_is_not_rebased_or_overwritten(self):
        async def scenario():
            bank = host.LatestEvidenceGapMemory()
            key = bank.save_knowledge('old')
            async def hook(kind, index, bank, events):
                if (kind, index) == ('review', 1):
                    bank.clear()
            agent, result, _ = await self.run_cycle([host.write('one'), host.write('two', key)], bank=bank, hook=hook)
            self.assertFalse(result.operations[1].success)
            self.assertEqual(bank.knowledge, [])
        asyncio.run(scenario())

    def test_malformed_item_is_local(self):
        from unittest.mock import patch
        def parse(agent, item):
            if item[0] == 'broken':
                raise ValueError('malformed arguments')
            return host.write('valid')
        async def scenario():
            with patch.object(host.CitationGateMemoryAgent, '_parse_item', parse), \
                 patch.object(host.CitationGateMemoryAgent, '_tool_items',
                              return_value=[('broken', ''), ('valid', '')]):
                agent, result, _ = await self.run_cycle([])
                self.assertEqual([o.success for o in result.operations], [False, True], agent.last_citation_gate_report)
        asyncio.run(scenario())

    def test_failed_target_after_independent_operation_is_not_prefetched(self):
        async def scenario():
            bank = host.LatestEvidenceGapMemory()
            key = bank.save_knowledge('old')
            async def hook(kind, index, bank, events):
                if (kind, index) == ('review', 0):
                    return {'overall': {'verdict': 'insufficient', 'reason': 'fixture'},
                            'results': [{'verdict': 'insufficient', 'reason': 'fixture'}]}
            agent, result, events = await self.run_cycle(
                [host.write('failed', key), host.write('independent'), host.write('dependent', key)],
                bank=bank, hook=hook)
            self.assertEqual([o.success for o in result.operations], [False, True, False])
            self.assertNotIn(('split', 2), events)
            self.assertNotIn(('review', 2), events)
            self.assertEqual(agent.last_citation_gate_report['operations'][2]['error_code'],
                             'not_run_failed_target_dependency')
        asyncio.run(scenario())
