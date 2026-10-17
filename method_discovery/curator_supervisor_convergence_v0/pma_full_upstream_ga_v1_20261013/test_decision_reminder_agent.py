"""No-provider checks for the U/V1/D1 Phase-2-only comparison."""

import asyncio
import copy
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from harbor.llms.base import LLMResponse
from memory_agent.memory.memory_agent import (BANK_TOOLS, PHASE1_SYSTEM,
                                              PHASE2_SYSTEM, MemoryAgent)
from memory_agent.memory.universal_memory import UniversalMemory

from decision_reminder_agent import (D1_SYSTEM, D1_TASK, DecisionReminderAgent,
                                     UPSTREAM_TASK, V1_SYSTEM_REPLACEMENTS,
                                     phase2_prompt, phase2_system)
from episode import construct_upstream
from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.six_task_plan import validate_plan


class DecisionReminderTest(unittest.TestCase):
    def test_candidate_binding_rejects_tampering(self):
        slot = {'order': 1, 'task': 'fixed-task', 'repeat': 1,
                'condition': 'B', 'research_candidate': 'D1'}
        manifest = {'schema': 'pma-ga-live-manifest-v5',
                    'execution_authorized': False, 'planned_order': [slot],
                    'assets': {'fixed-task': {}}, 'config_sha256': 'a' * 64,
                    'config': {'research_candidate': 'D1'}}
        with TemporaryDirectory() as temporary:
            bound = {**slot, 'run_id': 'one', 'run_root': str(Path(temporary) / 'one'),
                     'batch_id': 'batch', 'config_sha256': 'a' * 64}
            granted = {'execution_authorized': True, 'approved_arms': [slot],
                       'run_bindings': [bound], 'run_id': 'one',
                       'batch_id': 'batch', 'config_sha256': 'a' * 64,
                       'output_root': temporary}
            self.assertEqual(validate_plan(manifest, granted), [bound])
            for change in ({'research_candidate': 'V1'},
                           {'research_candidate': 'unknown'},
                           {'condition': 'A'}):
                altered = copy.deepcopy(manifest)
                altered['planned_order'][0].update(change)
                with self.assertRaises(RuntimeError):
                    validate_plan(altered, granted)
            legacy = copy.deepcopy(manifest)
            legacy['schema'] = 'pma-ga-live-manifest-v4'
            legacy['planned_order'][0].pop('research_candidate')
            legacy['config'].pop('research_candidate')
            old_grant = copy.deepcopy(granted)
            old_grant['approved_arms'][0].pop('research_candidate')
            old_grant['run_bindings'][0].pop('research_candidate')
            self.assertEqual(validate_plan(legacy, old_grant), old_grant['run_bindings'])

    def test_exact_phase2_contract(self):
        upstream = MemoryAgent(memory=UniversalMemory())
        original = upstream._build_phase2_prompt('visible trajectory', 7)
        self.assertTrue(original.endswith(UPSTREAM_TASK))
        d1 = phase2_prompt(original, 'D1')
        v1 = phase2_prompt(original, 'V1')
        self.assertEqual(d1[:-len('## Your Task\n' + D1_TASK + '\n')],
                         original[:-len(UPSTREAM_TASK)])
        self.assertEqual(v1.count('failing to apply'), 1)
        self.assertEqual(phase2_system('D1'), D1_SYSTEM)
        expected = PHASE2_SYSTEM
        for old, new in V1_SYSTEM_REPLACEMENTS:
            self.assertEqual(expected.count(old), 1)
            expected = expected.replace(old, new, 1)
        self.assertEqual(phase2_system('V1'), expected)
        self.assertEqual(PHASE2_SYSTEM.count('already visible in the recent trajectory'), 2)
        with self.assertRaises(RuntimeError):
            phase2_prompt(original + ' extra', 'D1')
        with self.assertRaises(RuntimeError):
            phase2_prompt(UPSTREAM_TASK + original, 'D1')

    def test_real_constructor_and_two_phase_requests(self):
        all_requests = {}
        banks = {}
        with TemporaryDirectory() as temporary:
            for index, variant in enumerate(('U', 'D1', 'V1', 'U')):
                agent = construct_upstream(Path(temporary) / str(index),
                                           research_candidate=variant)
                self.assertIs(agent._memory_agent.memory, agent._memory)
                self.assertIsInstance(agent._memory_agent,
                    MemoryAgent if variant == 'U' else DecisionReminderAgent)
                self.assertNotIn('SourceMemory', type(agent._memory).__name__)
                calls = []

                async def fake_call(*, prompt, system, tools=None):
                    calls.append({'prompt': prompt, 'system': system, 'tools': tools})
                    if tools:
                        tool = SimpleNamespace(function=SimpleNamespace(
                            name='memory_save_knowledge',
                            arguments={'content': 'Remember the public constraint.'}))
                        return LLMResponse(content='', tool_calls=[tool])
                    return LLMResponse(content='<context_for_action>Check the public constraint.</context_for_action>')

                agent._memory_llm.call = fake_call
                with patch.object(agent._memory, '_generate_id', return_value='same-id'):
                    result = asyncio.run(agent._memory_agent.process('public task and trace', 2))
                self.assertTrue(result.should_inject)
                self.assertEqual(len(calls), 2)
                self.assertEqual(calls[0]['system'], PHASE1_SYSTEM)
                self.assertEqual(calls[0]['tools'], BANK_TOOLS)
                self.assertIsNone(calls[1]['tools'])
                self.assertIn('[same-id] Remember the public constraint.', calls[1]['prompt'])
                self.assertEqual(calls[1]['system'],
                    PHASE2_SYSTEM if variant == 'U' else phase2_system(variant))
                all_requests[f'{index}-{variant}'] = calls
                banks[f'{index}-{variant}'] = agent._memory.to_dict()
        self.assertEqual(all_requests['0-U'], all_requests['3-U'])
        self.assertEqual(all_requests['0-U'][0], all_requests['1-D1'][0])
        self.assertEqual(all_requests['0-U'][0], all_requests['2-V1'][0])
        self.assertEqual(banks['0-U']['knowledge'][0]['content'],
                         banks['1-D1']['knowledge'][0]['content'])
        self.assertEqual(all_requests['1-D1'][1]['prompt'],
                         phase2_prompt(all_requests['0-U'][1]['prompt'], 'D1'))
        self.assertEqual(all_requests['2-V1'][1]['prompt'],
                         phase2_prompt(all_requests['0-U'][1]['prompt'], 'V1'))


if __name__ == '__main__':
    unittest.main()
