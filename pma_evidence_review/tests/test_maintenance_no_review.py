"""Scripted clients test engineering contracts, never summarization quality."""
import asyncio
import json
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import unittest

from pma_evidence_review.tests.no_network import install_guard
ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT / 'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013'
for path in (STAGE, STAGE / 'vendor/pma_89e5c0d/src'):
    sys.path.insert(0, str(path))
from maintenance_no_review_agent import MaintenanceNoReviewAgent, maintenance_system
from latest_evidence_gap_store import LatestEvidenceGapMemory
from latest_evidence_gap_agent import latest_phase1_system
from gap_evidence import sha256


def reply(calls=(), content='scripted'):
    return NS(content=content, tool_calls=[NS(function=NS(name=n, arguments=json.dumps(a)))
                                         for n, a in calls])


class MaintenanceNoReviewTests(unittest.TestCase):
    def setUp(self):
        install_guard(self)

    def agent(self, calls, selection='<no_intervention/>', bank=None):
        requests = []
        async def fake(**kwargs):
            requests.append((agent.transport_phase, kwargs))
            if agent.transport_phase == 'maintenance':
                return reply(calls)
            self.assertEqual(agent.transport_phase, 'selection')
            return reply(content=selection)
        bank = bank if bank is not None else LatestEvidenceGapMemory()
        agent = MaintenanceNoReviewAgent(task='Original task', memory=bank, llm=NS(call=fake))
        agent.prepare_visible_context('recent actions', [{'source_id': 'event-1',
            'role': 'tool_observation', 'order': 1, 'field_path': 'result',
            'text': 'query returned 7 rows', 'record_digest': sha256('query returned 7 rows'),
            'record_digest_kind': 'event'}])
        return agent, requests

    def test_optional_quotes_commit_latest_and_select_exact_text_without_review(self):
        calls = [('memory_save_knowledge', {'content': '  scoped result\r\n'}),
                 ('memory_save_procedural', {'content': 'tried query; 7 rows',
                    'evidence': [{'quote': 'query returned 7 rows'}]}),
                 ('memory_save_gap', {'content': 'Fresh session access unverified',
                    'evidence': [{'quote': 'absent quotation'}]}),
                 ('memory_update_status', {'content': 'Query returned rows; next export'})]
        agent, requests = self.agent(calls, '<intervene>M1,TASK</intervene>')
        result = asyncio.run(agent.process('recent actions', 1))
        self.assertTrue(all(op.success for op in result.operations))
        self.assertEqual([p for p, _ in requests], ['maintenance', 'selection'])
        self.assertEqual(json.loads(result.context_for_action)['blocks'][0]['content'], calls[0][1]['content'])
        self.assertTrue(agent.pending_refs_valid())
        self.assertEqual(len(agent.memory.manifests), 1)
        self.assertTrue(agent.memory.sources)
        self.assertFalse(hasattr(agent, 'review_transport'))
        self.assertEqual(agent.memory.binding(result.operations[0].memory_id).status, 'unbound')
        agent.memory.active_revisions[result.operations[0].memory_id] = 'new-revision'
        self.assertFalse(agent.pending_refs_valid())

    def test_update_delete_and_bad_target_are_independent(self):
        bank = LatestEvidenceGapMemory()
        key = bank.save_gap('old condition')
        agent, requests = self.agent([
            ('memory_save_gap', {'memory_id': key, 'content': 'remaining condition'}),
            ('memory_save_gap', {'memory_id': 'invented', 'content': 'bad'}),
            ('memory_save_gap', {'content': ''}),
            ('memory_delete', {'memory_id': key})], bank=bank)
        result = asyncio.run(agent.process('recent actions', 1))
        self.assertEqual([op.success for op in result.operations], [True, False, False, True])
        self.assertEqual(agent.memory.entries, [])
        self.assertEqual(result.operations[0].memory_id, key)
        self.assertEqual(len(agent.memory.tombstones), 1)
        self.assertEqual([p for p, _ in requests], ['maintenance', 'selection'])

    def test_prompt_and_tools_have_one_consistent_publication_contract(self):
        baseline = latest_phase1_system()
        text = maintenance_system()
        self.assertIn('Terminal output the agent just saw', baseline)
        self.assertNotIn('Terminal output the agent just saw', text)
        self.assertNotIn('why it failed', text)
        self.assertNotIn('exact_unique,', text)
        for rule in ('Maintain existing memory', 'specific unresolved condition',
                     'Unknown or unverified is not observed failure', 'including echo',
                     'Test-quality checks:', 'Every valid save becomes the latest'):
            self.assertIn(rule, text)
        agent, _ = self.agent([])
        for tool in agent.get_tools_schema():
            f = tool['function']
            self.assertNotIn('why', f['description'])
            self.assertNotIn('host commit receipt', f['description'])
            if f['name'] != 'memory_delete':
                self.assertEqual(f['parameters']['required'], ['content'])
        # Cross-domain synthetic observations are ordinary input, not expected verdicts.
        self.assertNotIn('sqlite', text.lower())
        self.assertEqual(latest_phase1_system(), baseline)
