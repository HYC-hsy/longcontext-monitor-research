"""Zero-model checks for the isolated f838 predictive PMA adapter."""
import asyncio
import ast
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / 'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013'
VENDOR = STAGE / 'vendor/pma_89e5c0d/src/memory_agent'
sys.path.insert(0, str(VENDOR.parent))
from memory_agent.memory.predictive_memory_agent import (
    BANK_TOOLS, MemoryAgent as PredictiveMemoryAgent, PHASE1_SYSTEM, PHASE2_SYSTEM)
from memory_agent.memory.memory_agent import MemoryAgent as OriginalMemoryAgent
from memory_agent.memory.universal_memory import UniversalMemory


def class_from(path, name, namespace):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    klass = next(row for row in tree.body if isinstance(row, ast.ClassDef) and row.name == name)
    body = [ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), klass]
    exec(compile(ast.fix_missing_locations(ast.Module(body=body, type_ignores=[])),
                 str(path), 'exec'), namespace)
    return namespace[name]


class FakeLLM:
    def __init__(self):
        self.calls = []

    async def call(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get('tools'):
            call = types.SimpleNamespace(function=types.SimpleNamespace(
                name='memory_add', arguments={'content': 'keep exact scope'}))
            return types.SimpleNamespace(content='', tool_calls=[call])
        return types.SimpleNamespace(content='<no_intervention/>')


class PredictiveTests(unittest.IsolatedAsyncioTestCase):
    async def test_uncapped_turn_predicate_ignores_plan_mode_100_and_old_300(self):
        parsed = ast.parse((ROOT / 'GenericAgent-main/agent_loop.py').read_text(encoding='utf-8'))
        function = next(node for node in ast.walk(parsed)
                        if isinstance(node, ast.FunctionDef) and node.name == 'within_turn_limit')
        namespace = {'explicit_turn_policy': True, 'max_turns': None,
                     'local_turn': 301, 'handler': types.SimpleNamespace(max_turns=100),
                     'os': os, 'stateful_enabled': False, 'stateful_mode': None}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])),
                     '<actual-GA-turn-policy>', 'exec'), namespace)
        self.assertTrue(namespace['within_turn_limit']())
        namespace['max_turns'] = 7
        namespace['local_turn'] = 7
        self.assertFalse(namespace['within_turn_limit']())

    async def test_isolated_prompts_tool_and_flat_bank(self):
        self.assertEqual([x['function']['name'] for x in BANK_TOOLS], ['memory_add'])
        self.assertEqual(PHASE1_SYSTEM, (STAGE / 'vendor/pma_89e5c0d/src/memory_agent/memory/'
            'predictive_memory_agent.py').read_text(encoding='utf-8').split('PHASE1_SYSTEM = """', 1)[1].split('"""', 1)[0])
        self.assertNotEqual(PHASE1_SYSTEM, __import__(
            'memory_agent.memory.memory_agent', fromlist=['PHASE1_SYSTEM']).PHASE1_SYSTEM)
        self.assertNotEqual(PHASE2_SYSTEM, __import__(
            'memory_agent.memory.memory_agent', fromlist=['PHASE2_SYSTEM']).PHASE2_SYSTEM)
        bank = UniversalMemory()
        for i in range(60):
            bank.save_knowledge(f'entry-{i}')
        llm = FakeLLM()
        result = await PredictiveMemoryAgent(llm=llm, memory=bank).process('trajectory', 8)
        self.assertEqual(len(llm.calls), 2)
        self.assertIn('entry-0', llm.calls[0]['prompt'])
        self.assertIn('entry-59', llm.calls[0]['prompt'])
        self.assertEqual(bank.knowledge[-1].content, 'keep exact scope')
        self.assertFalse(result.should_inject)
        self.assertNotEqual(OriginalMemoryAgent._format_memory_bank,
                            PredictiveMemoryAgent._format_memory_bank)

    async def test_initial_then_nonoverlapping_eight_step_batches(self):
        Episode = class_from(STAGE / 'episode.py', 'PMAEpisode', {
            'Any': object, 'Path': Path, 'asyncio': asyncio, 'json': json,
            'hashlib': hashlib, 'os': os, 'stable_initial_text': lambda x: x})

        class Agent:
            _research_candidate = 'pma_predictive_f838_v1'
            _reset_status_on_episode = False
            _reset_knowledge_on_episode = False
            _reset_procedural_on_episode = False
            def __init__(self):
                self._trigger = types.SimpleNamespace(reset=lambda: None)
                self._memory = types.SimpleNamespace(knowledge=[], procedural=[])
                self._memory_agent = types.SimpleNamespace()
                self._accumulated_observations = []
                self.calls = []
            def _accumulate_step(self, *, step, observation):
                self._accumulated_observations.append({'step': step, 'observation': observation})
            async def _trigger_memory_agent(self, *, step_count):
                self.calls.append(step_count)

        with tempfile.TemporaryDirectory() as directory:
            agent = Agent()
            episode = Episode(agent, run_id='r', task_id='t', archive=Path(directory) / 'archive')
            started = await episode._task_start({'initial_user_content': 'task'})
            self.assertEqual(started['trigger_reason'], 'task_start')
            for attempt in range(1, 19):
                episode.last_attempt = attempt
                status = 'parse_error' if attempt == 4 else 'normal'
                result = await episode._actor_step({'actor_attempt': attempt,
                    'step_status': status, 'public_input': [{'type': 'text', 'text': 'in'}],
                    'public_blocks': [{'type': 'text', 'text': str(attempt)}],
                    'public_results': []})
                self.assertEqual(result['triggered'], attempt in (8, 16))
            self.assertEqual(agent.calls, [1, 8, 16])
            self.assertEqual(episode.batch_steps, 2)
            agent.save_memory = lambda _: None
            archive = Path(directory) / 'archive'
            (archive / 'memory.json').write_text('{}', encoding='utf-8')
            (archive / 'trajectory_memory.json').write_text('{}', encoding='utf-8')
            final = episode._task_end({'terminal': 'completed'})
            self.assertEqual(final['unprocessed_tail_steps'], 2)
            self.assertEqual(final['unprocessed_tail_attempts'], [17, 18])


if __name__ == '__main__':
    unittest.main()
