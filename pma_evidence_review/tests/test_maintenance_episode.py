"""Real factory, PMAEpisode and dispatcher; all completions are scripted offline."""
import asyncio
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pma_evidence_review.tests.test_maintenance_no_review import (
    MaintenanceNoReviewAgent, LatestEvidenceGapMemory, reply, STAGE)
from pma_evidence_review.tests.no_network import install_guard
from citation_gate_config import MAINTENANCE_POLICY
from episode import construct_upstream, PMAEpisode
from event_spool import EventDispatcher
from worker_main import install_transport_audit


class MaintenanceEpisodeTests(unittest.TestCase):
    def setUp(self):
        install_guard(self)

    def construct(self, root):
        actor = construct_upstream(root / 'upstream', research_candidate='pma_gap_evidence_v1',
            memory_maintenance_policy=MAINTENANCE_POLICY)
        self.assertIsInstance(actor._memory_agent, MaintenanceNoReviewAgent)
        self.assertNotIn('CitationGateMemoryAgent', [c.__name__ for c in type(actor._memory_agent).__mro__])
        return actor

    def test_full_factory_dispatcher_durable_logs_no_intervention_and_delivery(self):
        for intervene in (False, True):
            with self.subTest(intervene=intervene), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                actor = self.construct(root)
                agent = actor._memory_agent
                calls = []
                async def fake(**kw):
                    phase = agent.transport_phase
                    calls.append((phase, kw))
                    if phase == 'maintenance':
                        return reply([('memory_save_gap', {'content': '  unresolved export\r\n',
                            'evidence': [{'quote': 'not an exact match'}]}),
                            ('memory_update_status', {'content': 'Export pending'})])
                    self.assertEqual(phase, 'selection')
                    return reply(content='<intervene>M1,TASK</intervene>' if intervene else '<no_intervention/>')
                actor._memory_llm.call = fake
                episode = PMAEpisode(actor, run_id='offline', task_id='synthetic', archive=root / 'private')
                install_transport_audit(actor, episode.archive)
                requests, responses = root / 'spool/in', root / 'spool/out'
                requests.mkdir(parents=True)
                responses.mkdir()
                dispatcher = EventDispatcher(episode, requests, responses)
                task = '  Export the requested regional data.\r\n'
                events = [('task_start', {'initial_user_content': task}),
                    ('before_actor_call', {'actor_attempt': 1}),
                    ('actor_step', {'actor_attempt': 1, 'step_status': 'normal', 'response': 'Next export',
                        'commands': ['query --region west'],
                        'observation': json.dumps({'content': 'Next export', 'tool_results': [
                            {'tool_use_id': 'query', 'content': '7 regional rows'}]})}),
                    ('task_end', {'terminal': 'synthetic-stop'})]
                async def run():
                    for seq, (kind, fields) in enumerate(events, 1):
                        row = dict(schema='pma-ga-events-v1', kind=kind, sequence=seq,
                            event_id='e'+str(seq), run_id='offline', task_id='synthetic', **fields)
                        (requests / ('e'+str(seq)+'.json')).write_text(json.dumps(row))
                        self.assertEqual(await dispatcher.serve_once(), 1)
                asyncio.run(run())
                before = json.loads((responses / 'e2.json').read_text())['result']
                self.assertEqual(before['status'], 'reminder' if intervene else 'silent')
                if intervene:
                    wire = before['reminder']
                    blocks, _ = json.JSONDecoder().raw_decode(wire[wire.index('{"blocks":'):])
                    self.assertEqual([b['content'] for b in blocks['blocks']],
                        ['  unresolved export\r\n', task])
                self.assertEqual(agent.task, task)
                self.assertEqual([p for p, _ in calls], ['maintenance', 'selection'] * 2)
                self.assertFalse((root / 'upstream/citation_review').exists())
                self.assertTrue(episode.ended)
                restored = LatestEvidenceGapMemory.from_dict(json.loads((episode.archive / 'memory.json').read_text()))
                self.assertTrue(restored.manifests)
                for name in ('events.jsonl', 'gap_cycle.jsonl', 'memory_payload.jsonl',
                             'gap_visible_transport.jsonl', 'memory_transport.jsonl'):
                    rows = [json.loads(line) for line in (episode.archive / name).read_text().splitlines()]
                    self.assertTrue(rows, name)
                    if name == 'gap_cycle.jsonl':
                        self.assertTrue(all(r['memory_maintenance_policy'] == MAINTENANCE_POLICY for r in rows))
                        self.assertTrue(all('citation_gate_report' not in r for r in rows))
                self.assertIn('7 regional rows', calls[2][1]['prompt'])
                self.assertIn(task, calls[2][1]['prompt'])
                self.assertIsInstance(json.loads((episode.archive / 'trajectory_memory.json').read_text()), dict)

    def test_maintenance_and_selection_transport_failure_remain_distinct(self):
        for failing_phase in ('maintenance', 'selection'):
            with self.subTest(phase=failing_phase), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                actor = self.construct(root)
                agent = actor._memory_agent
                calls = []
                async def fake(**kw):
                    calls.append(agent.transport_phase)
                    if agent.transport_phase == failing_phase:
                        raise RuntimeError('synthetic transport failure')
                    return reply(content='<no_intervention/>')
                actor._memory_llm.call = fake
                episode = PMAEpisode(actor, run_id='r', task_id='t', archive=root / 'private')
                install_transport_audit(actor, episode.archive)
                asyncio.run(episode.handle(dict(kind='task_start', sequence=1, event_id='e1',
                    run_id='r', task_id='t', initial_user_content='Synthetic task')))
                self.assertIsNone(actor._pending_injection)
                self.assertEqual(calls, ['maintenance', 'selection'])
                self.assertIn(failing_phase, [e['phase'] for e in agent.last_gap_report['transport_errors']])
                rows = [json.loads(line) for line in (episode.archive / 'memory_transport.jsonl').read_text().splitlines()]
                self.assertEqual([r['phase'] for r in rows], calls)
                self.assertEqual(next(r for r in rows if r['phase'] == failing_phase)['status'], 'RuntimeError')

    def test_corrupt_source_cannot_be_committed_without_citations(self):
        from pma_evidence_review.tests.test_maintenance_no_review import MaintenanceNoReviewTests
        helper = MaintenanceNoReviewTests()
        agent, _ = helper.agent([('memory_save_gap', {'content': 'must reject'})])
        original = agent.llm.call
        async def corrupt(**kw):
            if agent.transport_phase == 'maintenance':
                key = next(iter(agent._parts.catalog))
                visible = agent._parts.catalog[key]
                blob = replace(visible.snapshot.blob, text='tampered source bytes')
                catalog = dict(agent._parts.catalog)
                catalog[key] = replace(visible, snapshot=replace(visible.snapshot, blob=blob))
                agent._parts = replace(agent._parts, catalog=catalog)
            return await original(**kw)
        agent.llm.call = corrupt
        result = asyncio.run(agent.process('recent actions', 1))
        self.assertFalse(result.operations[0].success)
        self.assertEqual(agent.memory.entries, [])

    def test_real_worker_fake_mode_keeps_policy_identity_and_tags(self):
        from types import SimpleNamespace as NS
        from worker_main import serve
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            requests, responses = root / 'spool/in', root / 'spool/out'
            requests.mkdir(parents=True)
            responses.mkdir()
            events = [('task_start', {'initial_user_content': 'Synthetic task'}),
                      ('before_actor_call', {'actor_attempt': 1}),
                      ('task_end', {'terminal': 'synthetic-stop'})]
            for seq, (kind, fields) in enumerate(events, 1):
                row = dict(schema='pma-ga-events-v1', kind=kind, sequence=seq, event_id='e'+str(seq),
                    run_id='offline', task_id='synthetic', **fields)
                (requests / ('e'+str(seq)+'.json')).write_text(json.dumps(row))
            args = NS(private_root=str(root / 'private'), requests=str(requests), responses=str(responses),
                run_id='offline', task_id='synthetic', fake_memory=True, deadline_epoch=None,
                research_candidate='pma_gap_evidence_v1', memory_maintenance_policy=MAINTENANCE_POLICY)
            asyncio.run(serve(args))
            ready = json.loads((root / 'private/worker_ready.json').read_text())
            self.assertEqual(ready['memory_maintenance_policy'], MAINTENANCE_POLICY)
            before = json.loads((responses / 'e2.json').read_text())['result']
            self.assertEqual(before['status'], 'reminder')
            self.assertIn('Synthetic task', before['reminder'])
            audit = root / 'private/archive'
            phases = [json.loads(line)['phase'] for line in (audit / 'memory_payload.jsonl').read_text().splitlines()]
            self.assertEqual(phases, ['maintenance', 'selection'])
