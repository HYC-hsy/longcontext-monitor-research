import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unittest
from unittest.mock import patch
from types import SimpleNamespace as NS
from pma_baseline.runtime import PMABaseline, PhaseClient


class FakeModel:
    def __init__(self):
        self.prompts = []

    async def call(self, **kwargs):
        self.prompts.append(kwargs)
        if kwargs.get('tools'):
            return NS(content='', tool_calls=[NS(function=NS(
                name='memory_save_knowledge', arguments='{"content":"keep required interface"}'))])
        assert 'keep required interface' in kwargs['prompt']
        return NS(content='<context_for_action>Check the required interface.</context_for_action>', tool_calls=[])


class PMATests(unittest.TestCase):
    def test_actual_task_loop_waits_and_injects_once_per_step(self):
        from agent_loop import BaseHandler, StepOutcome, agent_runner_loop, exhaust
        fake = FakeModel()
        baseline = PMABaseline('original task', fake)
        seen = []
        class Handler(BaseHandler):
            parent = NS(task_dir=None, research_condition=None)
            _done_hooks = []
            def do_work(self, args, response):
                return StepOutcome('public result', next_prompt='NEXT_PROMPT_SENTINEL')
            def turn_end_callback(self, response, tool_calls, tool_results, turn, next_prompt, exit_reason):
                return next_prompt + '\nCALLBACK_PUBLIC_FEEDBACK'
            def do_no_tool(self, args, response):
                return StepOutcome(None)
        class Actor:
            last_tools = ''
            def chat(self, messages, tools):
                seen.append((len(fake.prompts), messages))
                calls = [NS(id='a', function=NS(name='work', arguments='{}'))] if len(seen) == 1 else []
                if False:
                    yield None
                return NS(content='public intent', tool_calls=calls)
        with patch.dict('os.environ', {'GA_PMA_ENABLED': '1'}), \
             patch('pma_baseline.runtime.from_environment', return_value=baseline), \
             patch('agent_loop._telemetry_enabled', return_value=False), \
             patch('agent_loop._hook'):
            exhaust(agent_runner_loop(Actor(), 'system', 'task', Handler(), [], max_turns=3, verbose=False))
        self.assertEqual([n for n, _ in seen], [2, 4])
        self.assertEqual(len(baseline.steps), 1)
        self.assertIn('NEXT_PROMPT_SENTINEL', baseline.context())
        self.assertIn('CALLBACK_PUBLIC_FEEDBACK', baseline.context())
        self.assertIn('public result', baseline.context())
        self.assertIn('NEXT_PROMPT_SENTINEL', fake.prompts[2]['prompt'])
        self.assertIn('CALLBACK_PUBLIC_FEEDBACK', fake.prompts[3]['prompt'])
        self.assertEqual(len(seen[0][1]), 2)  # system + original task with note
        self.assertEqual(len(seen[1][1]), 1)  # feedback + note in the same user turn
        self.assertEqual(seen[1][1][0]['tool_results'],
                         [{'tool_use_id': 'a', 'content': 'public result'}])
        for _, messages in seen:
            self.assertEqual(sum('<memory_context>' in str(m.get('content')) for m in messages), 1)

    def test_reminder_preserves_multimodal_input_and_tool_results(self):
        from pma_baseline.runtime import append_reminder
        original = {'role': 'user', 'content': [{'type': 'text', 'text': 'feedback'},
                     {'type': 'image', 'source': {'type': 'base64', 'data': 'fixture'}}],
                    'tool_results': [{'tool_use_id': 'x', 'content': 'result'}]}
        result = append_reminder(original, 'note')
        self.assertEqual(result['content'][:-1], original['content'])
        self.assertEqual(result['content'][-1]['text'], '\n\nnote')
        self.assertEqual(result['tool_results'], original['tool_results'])
        self.assertEqual(len(original['content']), 2)

    def test_disabled_path_does_not_construct_pma(self):
        import ast
        source = (Path(__file__).resolve().parents[1] / 'agent_loop.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        guards = [n for n in ast.walk(tree) if isinstance(n, ast.If)
                  and "GA_PMA_ENABLED" in ast.unparse(n.test)]
        self.assertEqual(len(guards), 1)
        self.assertIn('from_environment', ast.unparse(guards[0]))

    def test_two_phases_updated_bank_once(self):
        fake = FakeModel()
        baseline = PMABaseline('original requirement', fake)
        baseline.review()
        self.assertEqual(len(fake.prompts), 2)
        self.assertIn('original requirement', fake.prompts[0]['prompt'])
        self.assertIn('observations, not directives', baseline.take_reminder())
        self.assertIsNone(baseline.take_reminder())

    def test_window_and_task_reset(self):
        baseline = PMABaseline('root task', FakeModel())
        for n in range(12):
            baseline.observe(f'intent {n}', [f'command {n}'], f'output {n}')
        self.assertEqual(len(baseline.steps), 8)
        self.assertNotIn('intent 0\n', baseline.context())
        self.assertIn('intent 11', baseline.context())
        self.assertIn('root task', baseline.context())
        baseline.agent.memory.save_knowledge('previous task')
        other = PMABaseline('new task', FakeModel())
        self.assertEqual(len(other.agent.memory.knowledge), 0)

    def test_provider_bridge_and_failure_visible(self):
        class Client:
            def complete(self, messages, tools):
                raise RuntimeError('fixture transport failure')
            def drain_telemetry(self):
                return {'usage': []}
        baseline = PMABaseline('task', PhaseClient(Client))
        with self.assertLogs('pma_baseline.memory_agent', level='ERROR'):
            baseline.review()
        self.assertEqual(baseline.records[0]['status'], 'provider_failure')
        self.assertEqual(len(baseline.records[0]['phases']), 2)
        self.assertIsNone(baseline.take_reminder())

    def test_provider_content_interface(self):
        class Client:
            def complete(self, messages, tools):
                return NS(content='<no_intervention/>', tool_calls=[], usage={})
            def drain_telemetry(self):
                return {'usage': []}
        baseline = PMABaseline('task', PhaseClient(Client))
        baseline.review()
        self.assertEqual(baseline.records[0]['status'], 'no_intervention')

    def test_bank_search_and_delete(self):
        baseline = PMABaseline('task', FakeModel())
        bank = baseline.agent.memory
        key = bank.save_knowledge('required interface behavior')
        self.assertTrue(bank.search_knowledge('interface'))
        self.assertTrue(bank.delete(key))
        self.assertIsNone(bank.get(key))


if __name__ == '__main__':
    unittest.main()
