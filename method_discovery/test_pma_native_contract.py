"""Exercise installed upstream orchestration, never a remote model or a task."""
import asyncio
import os
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch
import tempfile
import unittest

os.environ['LITELLM_LOCAL_MODEL_COST_MAP'] = 'True'
from memory_agent.config import load_config
from memory_agent.runner import create_agent
from harbor.models.agent.context import AgentContext

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / 'some_research/research_library/02_direct_methods/repositories/yifannnwu__proactive-memory-agent'


class FakeLLM:
    def __init__(self, **kwargs):
        self.config = kwargs
        self.calls = []
        self._model_name = kwargs['model_name']

    async def call(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get('tools'):
            return NS(content='', tool_calls=[NS(function=NS(name='memory_save_knowledge',
                      arguments='{"content":"fixture requirement"}'))])
        assert 'fixture requirement' in kwargs['prompt']
        return NS(content='<context_for_action>Retain fixture requirement.</context_for_action>',
                  tool_calls=[])


class NativeContract(unittest.TestCase):
    def test_published_factory_and_full_memory_loop(self):
        config = load_config(REFERENCE / 'configs/memory_terminalbench.yaml')
        with tempfile.TemporaryDirectory() as directory, \
             patch('memory_agent.memory_enabled_agent.LiteLLM', FakeLLM), \
             patch('harbor.agents.terminus_2.terminus_2.LiteLLM', FakeLLM):
            agent = create_agent(config, Path(directory))
            self.assertEqual(agent._llm.config['temperature'], .7)
            self.assertEqual(agent._memory_llm.config['temperature'], .3)
            self.assertEqual(agent._max_episodes, 50)
            self.assertEqual(agent._injection_method, 'user_turn')
            self.assertTrue(agent._enable_summarize)
            agent._context = AgentContext()
            agent._session = NS(is_session_alive=AsyncMock(return_value=True))
            # Only environment/model boundary operations are mocked. The author's
            # _run_agent_loop, trigger, bank update, prompt and injection execute.
            agent._execute_commands = AsyncMock(return_value=(False, 'fixture tool observation'))
            agent._setup_episode_logging = lambda *args: {}
            agent._record_step_full = lambda *args, **kwargs: None
            agent._record_asciinema_marker = lambda *args: None
            agent._dump_trajectory = lambda: None
            received = []
            async def chat_call(prompt, **kwargs):
                received.append(prompt)
            chat = NS(chat=chat_call, total_input_tokens=0, total_output_tokens=0,
                      total_cache_tokens=0, total_cost=0)
            async def interact(chat, prompt, *args):
                await chat.chat(prompt)
                # Ordinary work, first completion proposal, confirmed completion.
                done = len(received) >= 2
                return [], done, '', 'fixture analysis', 'fixture plan', NS(content='fixture answer')
            agent._handle_llm_interaction = interact
            turns = asyncio.run(agent._run_agent_loop('original fixture task', chat))
            self.assertEqual(turns, 3)
            self.assertEqual(len(agent._memory_llm.calls), 4)
            self.assertEqual(len(agent._accumulated_observations), 2)
            self.assertIn('<memory_context>', received[0])
            self.assertIn('<memory_context>', received[1])
            self.assertNotIn('<memory_context>', received[2])
            self.assertIn('fixture tool observation', agent._memory_llm.calls[2]['prompt'])
            self.assertEqual(agent._memory_llm.calls[2]['prompt'].count('[Step 2]'), 1)
            agent.save_memory(str(Path(directory) / 'memory.json'))
            self.assertTrue((Path(directory) / 'trajectory_memory.json').is_file())

    def test_published_baseline_factory(self):
        config = load_config(REFERENCE / 'configs/baseline_terminalbench.yaml')
        with tempfile.TemporaryDirectory() as directory, \
             patch('harbor.agents.terminus_2.terminus_2.LiteLLM', FakeLLM):
            agent = create_agent(config, Path(directory))
            self.assertFalse(hasattr(agent, '_memory_agent'))
            self.assertEqual(agent._max_episodes, 50)


if __name__ == '__main__':
    unittest.main()
