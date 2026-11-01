"""Plain-bank factory, dispatcher, source inventory and policy contracts."""
import asyncio
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pma_evidence_review.tests.test_bank_display import (
    BankDisplayAgent, GapMemory, reply, MAINTENANCE_SYSTEM, SELECTION_SYSTEM)
from pma_evidence_review.tests.no_network import install_guard
from pma_evidence_review.tests.test_selection_deployment import source_contract, REL
from citation_gate_config import BANK_DISPLAY_POLICY, validate_maintenance, worker_flags
from episode import construct_upstream, PMAEpisode
from event_spool import EventDispatcher
from worker_main import install_transport_audit


class BankDisplayHostTests(unittest.TestCase):
    def setUp(self):
        install_guard(self)

    def construct(self, root):
        actor = construct_upstream(root / 'upstream', research_candidate='pma_gap_memory_v0',
            memory_maintenance_policy=BANK_DISPLAY_POLICY)
        self.assertIs(type(actor._memory), GapMemory)
        self.assertIs(type(actor._memory_agent), BankDisplayAgent)
        self.assertIs(actor._memory, actor._memory_agent.gaps)
        return actor

    def test_explicit_policy_and_old_default_routes(self):
        self.assertEqual(worker_flags(None, 'pma_gap_memory_v0', None, BANK_DISPLAY_POLICY),
                         ['--memory-maintenance-policy', BANK_DISPLAY_POLICY])
        for carrier, gate, strategy, condition in (
            ('pma_gap_evidence_v1', None, None, 'B'), ('U', None, None, 'B'),
            ('pma_gap_memory_v0', 'gate-only', None, 'B'),
            ('pma_gap_memory_v0', None, 'claim-split-same-evidence-v4', 'B'),
            ('pma_gap_memory_v0', None, None, 'A')):
            with self.assertRaises(ValueError):
                validate_maintenance(BANK_DISPLAY_POLICY, carrier, gate, strategy, condition)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            from gap_memory_agent import GapMemoryAgent
            from latest_evidence_gap_agent import LatestEvidenceGapMemoryAgent
            self.assertIs(type(construct_upstream(root/'old', research_candidate='pma_gap_memory_v0')._memory_agent), GapMemoryAgent)
            self.assertIs(type(construct_upstream(root/'evidence', research_candidate='pma_gap_evidence_v1')._memory_agent), LatestEvidenceGapMemoryAgent)

    def test_dispatcher_two_phases_original_delivery_and_durable_plain_logs(self):
        for output in ('<intervene>M1,TASK</intervene>', '<no_intervention/>'):
            with self.subTest(output=output), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                actor = self.construct(root)
                agent, calls = actor._memory_agent, []
                async def fake(**kw):
                    calls.append((agent.transport_phase, kw))
                    if agent.transport_phase == 'maintenance':
                        return reply([('memory_save_gap', {'content': '  pending\r\n'}),
                                      ('memory_update_status', {'content': 'current status'})])
                    return reply(content=output)
                actor._memory_llm.call = fake
                episode = PMAEpisode(actor, run_id='offline', task_id='t', archive=root/'private')
                install_transport_audit(actor, episode.archive)
                requests, responses = root/'spool/in', root/'spool/out'
                requests.mkdir(parents=True); responses.mkdir(parents=True)
                dispatcher = EventDispatcher(episode, requests, responses)
                task = '  original task\r\n'
                commands = [f'command_{i}' for i in range(6)]
                receipt = 'tool stdout ' + 'long receipt ' * 1200 + ' END'
                events = [('task_start', {'initial_user_content': task}),
                    ('before_actor_call', {'actor_attempt': 1}),
                    ('actor_step', {'actor_attempt': 1, 'step_status': 'normal', 'response': 'visible response',
                        'commands': commands, 'observation': json.dumps({'content': 'visible response',
                        'tool_results': [{'tool_use_id': 'c6', 'content': receipt}]})}),
                    ('task_end', {'terminal': 'synthetic-stop'})]
                async def run():
                    for seq, (kind, fields) in enumerate(events, 1):
                        row = dict(schema='pma-ga-events-v1', kind=kind, sequence=seq,
                            event_id=f'e{seq}', run_id='offline', task_id='t', **fields)
                        (requests/f'e{seq}.json').write_text(json.dumps(row))
                        self.assertEqual(await dispatcher.serve_once(), 1)
                asyncio.run(run())
                result = json.loads((responses/'e2.json').read_text())['result']
                self.assertEqual(result['status'], 'reminder' if output.startswith('<intervene>') else 'silent')
                if result['status'] == 'reminder':
                    wire = result['reminder']
                    payload, _ = json.JSONDecoder().raw_decode(wire[wire.index('{"blocks":'):])
                    self.assertEqual([b['content'] for b in payload['blocks']], ['  pending\r\n', task])
                self.assertEqual([phase for phase, _ in calls], ['maintenance','selection']*2)
                self.assertEqual([kw['system'] for _, kw in calls], [MAINTENANCE_SYSTEM,SELECTION_SYSTEM]*2)
                for _, kw in calls[2:]:
                    self.assertIn(receipt, kw['prompt'])
                    for command in commands:
                        self.assertIn(command, kw['prompt'])
                data = json.loads((episode.archive/'memory.json').read_text())
                self.assertEqual(BankDisplayAgent.load_bank(data).to_dict(), data)
                for name in ('events.jsonl','gap_cycle.jsonl','memory_payload.jsonl',
                             'gap_visible_transport.jsonl','memory_transport.jsonl'):
                    rows = [json.loads(line) for line in (episode.archive/name).read_text().splitlines()]
                    self.assertTrue(rows, name)
                self.assertIsInstance(json.loads((episode.archive/'trajectory_memory.json').read_text()), dict)
                self.assertFalse((root/'upstream/citation_review').exists())

    def test_source_inventory_and_modified_missing_sources_rejected(self):
        import citation_gate_config as config
        files = source_contract()['GAP_SOURCE_FILES']
        self.assertEqual(set(config.maintenance_source_paths(BANK_DISPLAY_POLICY)), set(files))
        for name in ('bank_display_agent.py','gap_store.py','gap_memory_agent.py',
                     'selection_context.py','tag_selection_contract.py','verbatim_selection_mixin.py',
                     'citation_gate_config.py','episode.py','worker_main.py','live_launcher.py'):
            self.assertEqual(files.count((REL/name).as_posix()), 1)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in files:
                path = root/name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'# synthetic source\r\n')
            hashes = {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in files}
            frozen = {'research_candidate':'pma_gap_memory_v0', 'memory_maintenance_policy':BANK_DISPLAY_POLICY,
                      'maintenance_source_sha256':hashes}
            with patch.object(config, '__file__', str(root/REL/'citation_gate_config.py')):
                config.verify_gate_sources(frozen)
                target = root/REL/'bank_display_agent.py'
                target.write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError, 'identity differs'):
                    config.verify_gate_sources(frozen)
                target.unlink()
                with self.assertRaises(FileNotFoundError):
                    config.verify_gate_sources(frozen)
