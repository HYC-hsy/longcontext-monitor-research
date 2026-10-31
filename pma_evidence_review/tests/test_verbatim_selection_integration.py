"""Focused host-adapter checks; scripted model outputs are not semantic evidence."""
import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest

from pma_evidence_review.tests.test_live_gate import LatestEvidenceGapMemory, reply, TEXT
from gap_evidence import sha256
from verbatim_selection_agent import VerbatimSelectionCitationGateAgent


class VerbatimSelectionIntegrationTests(unittest.TestCase):
    def _agent(self, selection, *, bank=None, task='  Original task\r\n'):
        bank = bank if bank is not None else LatestEvidenceGapMemory()
        holder, requests = {}, []

        async def fake(**kwargs):
            agent = holder['agent']
            requests.append((agent.transport_phase, kwargs))
            if agent.transport_phase == 'maintenance':
                return reply([])
            if agent.transport_phase == 'selection':
                return reply(content=selection(agent))
            raise AssertionError('unexpected model phase')

        agent = VerbatimSelectionCitationGateAgent(task=task, memory=bank,
            llm=NS(call=fake), review_strategy='claim-split-same-evidence-v4')
        holder['agent'] = agent
        return agent, requests

    @staticmethod
    def _raw(agent, refs, decision='intervene'):
        snapshot = agent._selection_snapshot
        return json.dumps({'cycle': snapshot.cycle,
            'task_version': snapshot.task_version, 'decision': decision,
            'references': refs})

    def test_task_only_through_process_and_pending_delivery(self):
        bank = LatestEvidenceGapMemory()
        bank.update_status('Private progress status')
        agent, requests = self._agent(lambda a: self._raw(a, [
            {'kind': 'task', 'version': a._selection_snapshot.task_version}]), bank=bank)
        agent.prepare_visible_context('visible', [])
        result = asyncio.run(agent.process('visible', 1))
        self.assertTrue(result.should_inject)
        self.assertEqual(json.loads(result.context_for_action)['blocks'][0]['text'], agent.task)
        self.assertTrue(agent.pending_refs_valid())
        self.assertEqual(agent.last_gap_report['selection']['status'], 'intervention')
        self.assertEqual([phase for phase, _ in requests], ['maintenance', 'selection'])
        self.assertNotIn('context_for_action', requests[-1][1]['system'])
        self.assertIn('Private progress status', requests[-1][1]['prompt'])
        self.assertNotIn('Private progress status', result.context_for_action)

    def test_invalid_output_is_error_not_deliberate_silence(self):
        agent, _ = self._agent(lambda a: self._raw(a, [
            {'kind': 'status'}]))
        agent.prepare_visible_context('visible', [])
        result = asyncio.run(agent.process('visible', 1))
        self.assertFalse(result.should_inject)
        self.assertEqual(agent.last_gap_report['selection_error']['error'],
                         'unselectable_reference_kind')
        self.assertNotIn('selection', agent.last_gap_report)

    def test_legacy_entry_is_visible_but_not_given_false_revision(self):
        bank = LatestEvidenceGapMemory()
        legacy = bank.save_gap('  Pending issue\n')
        agent, requests = self._agent(lambda a: self._raw(a, [
            {'kind': 'task', 'version': a._selection_snapshot.task_version}]), bank=bank)
        agent.prepare_visible_context('visible', [])
        asyncio.run(agent.process('visible', 1))
        self.assertIn(legacy, agent.last_selection_report['excluded_legacy_ids'])
        self.assertNotIn('"id": "' + legacy + '"', requests[-1][1]['prompt'].split(
            '## Selectable frozen candidates\n', 1)[1])

    def test_frozen_committed_entry_exact_revision_and_revocation(self):
        bank = LatestEvidenceGapMemory()
        key = bank.save_gap('Old gap')
        bank._revision(key, receipt_id='test-commit')
        revision = bank.active_revisions[key]
        agent, _ = self._agent(lambda a: self._raw(a, [
            {'kind': 'memory', 'id': key, 'revision': revision}]), bank=bank)
        agent.prepare_visible_context('visible', [])
        result = asyncio.run(agent.process('visible', 1))
        self.assertEqual(json.loads(result.context_for_action)['blocks'][0]['text'], 'Old gap')
        self.assertTrue(agent.pending_refs_valid())
        bank.active_revisions[key] = 'rev_replaced'
        self.assertFalse(agent.pending_refs_valid())
        self.assertEqual(agent.last_gap_report['delivery_error'], 'selection_revision_revoked')

    def test_real_episode_parser_result_and_pending_task_input(self):
        from episode import construct_upstream, PMAEpisode
        from harbor.llms.base import LLMResponse
        with TemporaryDirectory() as directory:
            root = Path(directory)
            wrapper = construct_upstream(root / 'upstream',
                research_candidate='pma_gap_evidence_v1',
                citation_review_gate='gate-one-repair',
                citation_review_strategy='claim-split-same-evidence-v4')
            agent = wrapper._memory_agent
            self.assertIsInstance(agent, VerbatimSelectionCitationGateAgent)

            async def fake(**kwargs):
                if agent.transport_phase == 'maintenance':
                    return LLMResponse(content='', tool_calls=[])
                if agent.transport_phase == 'selection':
                    snapshot = agent._selection_snapshot
                    raw = self._raw(agent, [{'kind': 'task',
                        'version': snapshot.task_version}])
                    return LLMResponse(content=raw)
                raise AssertionError('unexpected model phase')

            wrapper._memory_llm.call = fake
            episode = PMAEpisode(wrapper, run_id='r', task_id='t', archive=root / 'archive')
            start = {'kind': 'task_start', 'sequence': 1, 'event_id': 'e1',
                     'run_id': 'r', 'task_id': 't',
                     'initial_user_content': '  Keep this exact task.\n',
                     'source_record_sha256': 'source_sha_fixture'}
            asyncio.run(episode.handle(start))
            self.assertEqual(agent.task, start['initial_user_content'])
            self.assertIsNotNone(wrapper._pending_injection)
            delivery = asyncio.run(episode.handle({
                'kind': 'before_actor_call', 'sequence': 2, 'event_id': 'e2',
                'run_id': 'r', 'task_id': 't', 'actor_attempt': 1}))
            self.assertEqual(delivery['status'], 'reminder')
            start_json = delivery['reminder'].index('{"blocks":')
            decoded, _ = json.JSONDecoder().raw_decode(delivery['reminder'][start_json:])
            self.assertEqual(decoded['blocks'][0]['text'], start['initial_user_content'])
            self.assertNotIn('source_sha_fixture', delivery['reminder'])

    def test_phase1_gate_commits_only_approved_candidate_before_selection(self):
        bank = LatestEvidenceGapMemory()
        calls = [('memory_save_knowledge', {'content': 'First accepted.',
                  'evidence': [{'quote': TEXT}]}),
                 ('memory_save_knowledge', {'content': 'Rejected proposal.',
                  'evidence': [{'quote': 'not in visible source'}]})]
        review_count = 0
        holder = {}

        async def fake(**kwargs):
            nonlocal review_count
            agent = holder['agent']
            if agent.transport_phase == 'maintenance':
                return reply(calls)
            if agent.transport_phase == 'citation_review':
                review_count += 1
                if review_count == 1:
                    return reply(content=json.dumps(['First accepted.']))
                return reply(content=json.dumps({'overall': {'verdict': 'supported',
                    'reason': 'visible receipt'}, 'results': [
                    {'verdict': 'supported', 'reason': 'visible receipt'}]}))
            if agent.transport_phase == 'selection':
                snapshot = agent._selection_snapshot
                self.assertEqual([row.text for row in snapshot.items], ['First accepted.'])
                ref = snapshot.items[0]
                return reply(content=self._raw(agent, [{'kind': 'memory',
                    'id': ref.id, 'revision': ref.revision}]))
            raise AssertionError('unexpected model phase')

        agent = VerbatimSelectionCitationGateAgent(task='Task', memory=bank,
            llm=NS(call=fake), review_strategy='claim-split-same-evidence-v4')
        holder['agent'] = agent
        agent.prepare_visible_context('visible', [{'source_id': 'e1',
            'role': 'tool_observation', 'order': 1, 'field_path': 'result',
            'text': TEXT, 'record_digest': sha256(TEXT),
            'record_digest_kind': 'event'}])
        result = asyncio.run(agent.process('visible', 1))
        self.assertEqual(review_count, 2)
        self.assertEqual([op.success for op in result.operations], [True, False])
        self.assertEqual(json.loads(result.context_for_action)['blocks'][0]['text'],
                         'First accepted.')
        self.assertEqual(len(bank.knowledge), 1)
        self.assertEqual(bank.knowledge[0].content, 'First accepted.')


if __name__ == '__main__':
    unittest.main()
