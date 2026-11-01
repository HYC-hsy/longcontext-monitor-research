"""Offline plain-bank contracts. Scripted responses are not semantic evidence."""
import asyncio
from copy import deepcopy
import hashlib
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
from bank_display_agent import BankDisplayAgent, MAINTENANCE_SYSTEM, SELECTION_SYSTEM
from gap_memory_agent import GAP_TOOL
from gap_store import GapMemory
from memory_agent.memory.memory_agent import BANK_TOOLS
from memory_agent.memory.universal_memory import MemoryEntry


def reply(calls=(), content=''):
    return NS(content=content, tool_calls=[NS(function=NS(name=n, arguments=json.dumps(a)))
                                         for n, a in calls])


class BankDisplayTests(unittest.TestCase):
    def setUp(self):
        install_guard(self)

    def agent(self, calls=(), output='<no_intervention/>', bank=None):
        requests = []
        async def fake(**kwargs):
            requests.append(deepcopy(kwargs))
            return reply(calls) if len(requests) == 1 else reply(content=output)
        a = BankDisplayAgent(task='  entire task\r\n', memory=bank, llm=NS(call=fake))
        return a, requests

    def test_exact_original_schema_plain_store_and_load(self):
        a, _ = self.agent()
        self.assertIs(type(a.memory), GapMemory)
        self.assertEqual(a.get_tools_schema(), BANK_TOOLS + [GAP_TOOL])
        for f in a.get_tools_schema():
            if f['function']['name'] != 'memory_delete':
                self.assertEqual(set(f['function']['parameters']['properties']), {'content'})
        key = a.memory.save_knowledge('fact')
        a.memory.save_procedural('attempt')
        a.memory.save_gap('pending')
        a.memory.status = 'progress'
        data = a.memory.to_dict()
        self.assertEqual(set(data), {'status', 'knowledge', 'procedural', 'gaps'})
        self.assertEqual(BankDisplayAgent.load_bank(data).to_dict(), data)
        self.assertEqual(a._active_records()[key].revision, '')
        for forbidden in ('revisions', 'blobs', 'tombstones', 'manifests', 'sources'):
            self.assertFalse(hasattr(a.memory, forbidden))
            with self.assertRaises(ValueError):
                BankDisplayAgent.load_bank({**data, forbidden: {}})

    def test_two_calls_exact_systems_and_original_text(self):
        text = '  scoped fact\r\n\t'
        a, req = self.agent([('memory_save_knowledge', {'content': text})],
                            '<intervene>M1,TASK</intervene>')
        result = asyncio.run(a.process('raw observation', 1))
        self.assertEqual(len(req), 2)
        self.assertEqual([r['system'] for r in req], [MAINTENANCE_SYSTEM, SELECTION_SYSTEM])
        self.assertEqual((len(MAINTENANCE_SYSTEM), len(SELECTION_SYSTEM)), (2672, 2855))
        self.assertNotIn('tools', req[1])
        blocks = json.loads(result.context_for_action)['blocks']
        self.assertEqual([b['content'] for b in blocks], [text, a.task])
        self.assertTrue(a.pending_refs_valid())
        self.assertNotIn('binding', req[1]['prompt'])
        self.assertNotIn('alignment', req[1]['prompt'])
        self.assertIn('Stored memory is not an independent observation.', req[1]['prompt'])
        a.memory.knowledge[0].content = 'changed'
        self.assertFalse(a.pending_refs_valid())

    def test_projection_keeps_all_commands_and_long_receipt_both_phases(self):
        commands = [f'COMMAND_{i}' for i in range(6)]
        receipt = 'stdout BEGIN ' + 'long receipt ' * 1600 + ' END receipt'
        entry = {'step': 1, 'commands': commands, 'analysis': 'visible report',
                 'observation': json.dumps({'content': 'unknown wrapper <history>keep</history>',
                                            'tool_results': [{'tool_use_id': 'c6', 'content': receipt}]})}
        a, req = self.agent()
        a.prepare_selection_context('raw', [entry])
        result = asyncio.run(a.process('raw', 1))
        self.assertFalse(result.should_inject)
        self.assertEqual(a.last_selection_report['status'], 'no_intervention')
        for request in req:
            for command in commands:
                self.assertIn(command, request['prompt'])
            self.assertIn(receipt, request['prompt'])
            self.assertIn('<history>keep</history>', request['prompt'])
            self.assertIn(a.task.strip(), request['prompt'])

    def test_new_ids_delete_status_and_gap(self):
        a, _ = self.agent()
        ops = a._execute_tool_calls(reply([
            ('memory_save_knowledge', {'content': 'one'}),
            ('memory_save_knowledge', {'content': 'two'}),
            ('memory_update_status', {'content': 'first'}),
            ('memory_update_status', {'content': 'second'}),
            ('memory_save_gap', {'content': 'pending'})]))
        self.assertTrue(all(op.success for op in ops))
        self.assertNotEqual(ops[0].memory_id, ops[1].memory_id)
        self.assertEqual(a.memory.status, 'second')
        result = a._execute_tool_calls(reply([
            ('memory_delete', {'memory_id': ops[0].memory_id}),
            ('memory_delete', {'memory_id': ops[-1].memory_id})]))
        self.assertTrue(all(op.success for op in result))
        self.assertEqual(len(a.memory.knowledge), 1)
        self.assertEqual(a.memory.entries, [])

    def test_duplicate_ids_and_wrong_category_rejected(self):
        a, _ = self.agent()
        key = a.memory.save_knowledge('one')
        a.memory.procedural.append(MemoryEntry(id=key, content='ambiguous'))
        with self.assertRaises(ValueError):
            a._active_records()
        a.memory.procedural.clear()
        a.memory.knowledge[0].id = 'gap_wrong'
        with self.assertRaises(ValueError):
            a._active_records()
