"""Offline source/format parity with the pinned reference checkout."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

from pma_baseline.runtime import PMABaseline, PhaseClient

ROOT = Path(__file__).resolve().parents[2]
UPSTREAM = ROOT / 'some_research/research_library/02_direct_methods/repositories/yifannnwu__proactive-memory-agent/src/memory_agent'
VENDORED = ROOT / 'GenericAgent-main/pma_baseline'


class ParityTests(unittest.TestCase):
    def test_three_core_files_match_upstream(self):
        for name in ('memory_agent.py', 'universal_memory.py', 'bm25_search.py'):
            with self.subTest(file=name):
                original = (UPSTREAM / 'memory' / name).read_text(encoding='utf-8-sig')
                copied = (VENDORED / name).read_text(encoding='utf-8-sig')
                self.assertEqual(original.rstrip(), copied.rstrip())

    def test_context_matches_original_functions(self):
        tree = ast.parse((UPSTREAM / 'memory_enabled_agent.py').read_text(encoding='utf-8'))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
        functions = [n for n in cls.body if isinstance(n, ast.FunctionDef)
                     and n.name in ('_get_memory_agent_context', '_format_step_entry')]
        scope = {}
        exec(compile(ast.Module(body=functions, type_ignores=[]), 'upstream_format_only', 'exec'), scope)
        for count in (0, 1, 11):
            ours = PMABaseline('root task', None)
            for n in range(count):
                ours.observe('intent' if n % 2 else '', list(range(7)), 'tool output', plan='optional plan')
            original = SimpleNamespace(_task_description='root task', _sliding_window_size=8,
                _accumulated_observations=[{'step': 1}] + list(ours.steps),
                _format_step_entry=scope['_format_step_entry'])
            self.assertEqual(ours.context(), scope['_get_memory_agent_context'](original))
            if count:
                self.assertEqual(ours.steps[-1]['step'], count + 1)

    def test_phase_calls_do_not_share_provider_history(self):
        import asyncio
        instances = []
        class Client:
            def __init__(self):
                self.messages = []
                instances.append(self)
            def complete(self, messages, tools):
                self.messages.extend(messages)
                return SimpleNamespace(content='<no_intervention/>', tool_calls=[])
            def drain_telemetry(self):
                return {}
        bridge = PhaseClient(Client)
        asyncio.run(bridge.call(prompt='first', system='phase1', tools=[]))
        asyncio.run(bridge.call(prompt='second', system='phase2'))
        self.assertEqual(len(instances), 2)
        self.assertEqual(instances[1].messages[-1]['content'], 'second')
        self.assertEqual(len(instances[1].messages), 2)


if __name__ == '__main__':
    unittest.main()
