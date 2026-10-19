"""Finite offline calls through pinned PMA bank/CRUD/phase-2 parser."""
import asyncio
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / 'curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/vendor/pma_89e5c0d/src'
sys.path.insert(0, str(VENDOR))
if 'shortuuid' not in sys.modules:
    shim = ModuleType('shortuuid')
    ids = iter(range(1000))
    shim.uuid = lambda: f'{next(ids):08d}'
    sys.modules['shortuuid'] = shim
from memory_agent.memory.memory_agent import MemoryAgent
from memory_agent.memory.universal_memory import UniversalMemory
from .memory_adapter import ComplementMemoryAgent


def call(name, arguments):
    return SimpleNamespace(function=SimpleNamespace(name=name, arguments=arguments))


class Fake:
    def __init__(self, replies):
        self.replies, self.requests = list(replies), []

    async def call(self, **kwargs):
        self.requests.append(kwargs)
        item = self.replies.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


class Tests(unittest.TestCase):
    def test_phase_separation_status_and_crud(self):
        transport = Fake([
            SimpleNamespace(content='', tool_calls=[
                call('memory_update_status', {'content': 'must not persist'}),
                call('memory_save_knowledge', {'content': 'actual observation'})]),
            SimpleNamespace(content='<context_for_action>Tentative alternative</context_for_action>', tool_calls=[]),
        ])
        bank = UniversalMemory()
        agent = ComplementMemoryAgent(llm=transport, memory=bank)
        result = asyncio.run(agent.process('Raw Task observation', 2,
            advisory_context='PoS interpretation, not observed fact'))
        self.assertEqual([op.action for op in result.operations], ['save_knowledge'])
        self.assertEqual(bank.status, '')
        self.assertEqual(bank.knowledge[0].content, 'actual observation')
        self.assertNotIn('PoS interpretation', transport.requests[0]['prompt'])
        self.assertIn('PoS interpretation', transport.requests[1]['prompt'])
        self.assertNotIn('<status>', result.user_prompt_phase1)
        self.assertNotIn('<status>', result.user_prompt_phase2)
        self.assertNotIn('memory_update_status', [x['function']['name']
            for x in transport.requests[0]['tools']])
        self.assertEqual(result.context_for_action, 'Tentative alternative')
        self.assertEqual(len(agent.rendered_entry_ids), 2)
        self.assertEqual(agent.rendered_entry_ids[1]['knowledge'], [bank.knowledge[0].id])

    def test_fallback_status_not_dispatched(self):
        transport = Fake([
            SimpleNamespace(content='<tool_call><function=memory_update_status>'
                '<parameter=content>leak</parameter></function></tool_call>', tool_calls=[]),
            SimpleNamespace(content='<no_intervention/>', tool_calls=[]),
        ])
        bank = UniversalMemory()
        result = asyncio.run(ComplementMemoryAgent(llm=transport, memory=bank)
            .process('Raw', 1))
        self.assertEqual(result.operations, [])
        self.assertEqual(bank.status, '')
        self.assertFalse(result.should_inject)

    def test_stage_failure_does_not_call_phase2(self):
        transport = Fake([RuntimeError('phase1 failed')])
        agent = ComplementMemoryAgent(llm=transport, memory=UniversalMemory())
        with self.assertRaisesRegex(RuntimeError, 'phase1 failed'):
            asyncio.run(agent.process('Raw', 1, advisory_context='derived'))
        self.assertEqual(len(transport.requests), 1)

    def test_original_is_unchanged(self):
        bank = UniversalMemory()
        transport = Fake([
            SimpleNamespace(content='', tool_calls=[call('memory_update_status',
                {'content': 'U status'})]),
            SimpleNamespace(content='<no_intervention/>', tool_calls=[]),
        ])
        result = asyncio.run(MemoryAgent(llm=transport, memory=bank).process('Raw', 1))
        self.assertEqual(bank.status, 'U status')
        self.assertEqual(result.operations[0].action, 'update_status')


if __name__ == '__main__':
    unittest.main(verbosity=2)
