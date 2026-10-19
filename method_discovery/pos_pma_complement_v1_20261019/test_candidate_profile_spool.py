"""No-model host PMA profile spool boundary checks."""
import asyncio
import importlib
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
PMA = ROOT / 'curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013'
POS = ROOT / 'pos_upstream_ga_v1_20261017'
for path in (str(POS), str(PMA)):
    if path not in sys.path:
        sys.path.insert(0, path)


class ProfileSpoolTests(unittest.TestCase):
    def test_complete_pma_request_budget_rejects_before_model(self):
        from candidate_transport_worker import TransportEpisode
        with tempfile.TemporaryDirectory() as directory:
            llm = SimpleNamespace(call=lambda **kwargs: None)
            episode = TransportEpisode(llm, run_id='r', task_id='t',
                archive=Path(directory))
            with self.assertRaisesRegex(ValueError, 'byte budget'):
                asyncio.run(episode.handle({'kind': 'candidate_pma_call',
                    'sequence': 1, 'event_id': 'event', 'role': 'pma_phase2',
                    'prompt': 'X' * 90000, 'system': 'original PMA system',
                    'tools': None}))
            self.assertEqual(episode.sequence, 0)

    def test_original_pma_profile_adapter_is_constructed_without_network(self):
        from episode import construct_upstream
        with tempfile.TemporaryDirectory() as directory:
            agent = construct_upstream(Path(directory) / 'logs', memory_profile={
                'provider': 'anthropic', 'api_mode': 'messages',
                'model': 'claude-opus-4-8', 'thinking_type': 'adaptive',
                'apibase': 'http://127.0.0.1:1/fake-only',
                'apikey': 'SYNTHETIC_TEST_ONLY', 'temperature': 1,
                'max_tokens': 8192, 'reasoning_effort': 'high',
                'read_timeout': 300})
            self.assertEqual(agent._memory_llm._model_name,
                             'anthropic/claude-opus-4-8')
            self.assertEqual(agent._memory_llm._reasoning_effort, 'high')
            captured = []
            async def last_hop(**kwargs):
                captured.append(kwargs)
                return {'choices': [{'message': {'content': '<no_intervention/>',
                    'tool_calls': None}, 'finish_reason': 'stop'}]}
            with patch('litellm.acompletion', side_effect=last_hop):
                reply = asyncio.run(agent._memory_llm.call(prompt='synthetic observation',
                    system='pinned PMA phase', tools=None))
            self.assertEqual(reply.content, '<no_intervention/>')
            self.assertEqual(len(captured), 1)
            self.assertEqual(captured[0]['model'], 'anthropic/claude-opus-4-8')
            self.assertEqual(captured[0]['temperature'], 1)
            self.assertEqual(captured[0]['max_tokens'], 8192)
            self.assertEqual(captured[0]['thinking'], {'type': 'adaptive'})
            self.assertEqual(captured[0]['timeout'], 300)

    def test_bound_two_phase_exchange_uses_one_host_transport(self):
        from event_spool import EventClient, EventDispatcher
        from candidate_transport_worker import TransportEpisode
        from worker import CandidatePMATransport

        class FakeLLM:
            def __init__(self):
                self.calls = []

            async def call(self, **kwargs):
                self.calls.append(kwargs)
                return SimpleNamespace(content='<no_intervention/>', tool_calls=[])

        class Log:
            def __init__(self): self.rows = []
            def log(self, event, **kwargs): self.rows.append((event, kwargs))

        async def scenario():
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                requests, responses, private = (root / name for name in
                    ('spool/requests', 'spool/responses', 'private'))
                (root / 'spool').mkdir()
                for path in (requests, responses, private): path.mkdir()
                llm = FakeLLM()
                episode = TransportEpisode(llm, run_id='run-1', task_id='task-1',
                                           archive=private)
                dispatcher = EventDispatcher(episode, requests, responses,
                    deadline_epoch=time.time() + 5)
                client = EventClient(requests, responses, 'run-1', 'task-1',
                    deadline_monotonic=time.monotonic() + 5)
                log = Log()
                transport = CandidatePMATransport(role_transport=SimpleNamespace(
                    mode='profile', archive=log), profile_client=client)
                async def send(tools):
                    task = asyncio.create_task(transport.call(prompt='original trajectory',
                        system='pinned PMA phase', tools=tools))
                    while not task.done():
                        await dispatcher.serve_once()
                        await asyncio.sleep(.01)
                    return await task
                first = await send([{'name': 'bank_only'}])
                second = await send(None)
                self.assertEqual(first.content, '<no_intervention/>')
                self.assertEqual(second.content, '<no_intervention/>')
                self.assertEqual(len(llm.calls), 2)
                self.assertEqual([call['tools'] is not None for call in llm.calls],
                                 [True, False])
                self.assertEqual(len((private / 'requests.jsonl').read_text().splitlines()), 2)
                self.assertEqual(len((private / 'responses.jsonl').read_text().splitlines()), 2)
                self.assertEqual([event for event, _ in log.rows],
                                 ['candidate_pma_request', 'candidate_pma_response'] * 2)

        asyncio.run(scenario())


if __name__ == '__main__':
    unittest.main()
