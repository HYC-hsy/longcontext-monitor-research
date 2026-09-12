import asyncio
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest

os.environ['LITELLM_LOCAL_MODEL_COST_MAP'] = 'True'
from pma_native_support import original_config, gateway_config, attach_usage

REFERENCE = Path(__file__).resolve().parents[1] / 'some_research/research_library/02_direct_methods/repositories/yifannnwu__proactive-memory-agent'


class SupportTests(unittest.TestCase):
    def test_only_declared_transport_and_parallelism_change(self):
        from memory_agent.config import load_config
        config = original_config(REFERENCE)
        published = load_config(REFERENCE / 'configs/memory_terminalbench.yaml')
        for actor in ('model', 'memory'):
            left = getattr(config, actor).model_dump()
            right = getattr(published, actor).model_dump()
            for field in ('model_name', 'api_base', 'api_key'):
                left.pop(field)
                right.pop(field)
            self.assertEqual(left, right)
        self.assertEqual(config.model.max_turns, 50)
        self.assertEqual(config.memory.injection_method, 'user_turn')

    def test_routes_match_anthropic_request_models(self):
        routes = gateway_config('https://example.invalid', 'fixture-secret')
        config = original_config(REFERENCE)
        for side in (config.model, config.memory):
            name = side.model_name.removeprefix('anthropic/')
            self.assertEqual(routes['models'][name]['paths'], ['/v1/messages'])
        with self.assertRaises(ValueError):
            gateway_config('http://example.invalid', 'fixture')

    def test_meter_preserves_call_result_and_exception(self):
        class Client:
            async def call(self, prompt):
                if prompt == 'fail':
                    raise ValueError('fixture failure')
                return response
        response = NS(usage=NS(model_dump=lambda **kw: {'input_tokens': 11}))
        with tempfile.TemporaryDirectory() as directory:
            agent = NS(_llm=Client(), _memory_llm=Client())
            attach_usage(agent, directory)
            self.assertIs(asyncio.run(agent._llm.call('task')), response)
            self.assertIs(asyncio.run(agent._memory_llm.call('memory')), response)
            with self.assertRaises(ValueError):
                asyncio.run(agent._memory_llm.call('fail'))
            rows = [json.loads(line) for line in
                    (Path(directory) / 'model_calls.jsonl').read_text().splitlines()]
            self.assertEqual([r['actor'] for r in rows], ['task', 'memory', 'memory'])
            self.assertEqual(rows[0]['usage']['input_tokens'], 11)
            self.assertIsNone(rows[2]['usage'])
            self.assertEqual(rows[2]['status'], 'failed')


if __name__ == '__main__':
    unittest.main()
