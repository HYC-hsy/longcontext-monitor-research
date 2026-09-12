import asyncio
from pathlib import Path
from types import SimpleNamespace as NS
import tempfile
import unittest
from pma_native_trial import execute_trial
from harbor.models.task.config import EnvironmentConfig


class LifecycleTests(unittest.TestCase):
    def run_fixture(self, evaluation_fails=False):
        events = []
        class Env:
            def __init__(self, **kwargs):
                assert not kwargs['task_env_config'].allow_internet
            async def start(self, **kwargs): events.append('start')
            async def exec(self, *args, **kwargs): return NS(return_code=0)
            async def stop(self, **kwargs): events.append('stop')
        class Agent:
            async def setup(self, env): events.append('setup')
            async def run(self, *args): events.append('agent_finished')
            def save_memory(self, path): events.append('archive')
        class Verifier:
            def __init__(self, **kwargs): pass
            async def verify(self):
                assert 'agent_finished' in events
                events.append('hidden_tests')
                if evaluation_fails: raise FileNotFoundError('missing reward')
                return NS(model_dump=lambda **kwargs: {'rewards': {'reward': 1.0}})
        with tempfile.TemporaryDirectory() as directory:
            task = NS(name='fixture',instruction='public task',
                      paths=NS(environment_dir=Path(directory)),
                      config=NS(environment=EnvironmentConfig(docker_image='fixture'),
                                verifier=NS(timeout_sec=1)))
            report = asyncio.run(execute_trial(task, None, Path(directory)/'run', 1,
                approved=True, environment_factory=Env, agent_factory=lambda *args: Agent(),
                verifier_factory=Verifier))
        self.assertEqual(events[-1], 'stop')
        return report

    def test_verifier_only_after_agent(self):
        self.assertEqual(self.run_fixture()['reward'], {'reward': 1.0})

    def test_missing_evaluation_is_not_zero_score(self):
        report = self.run_fixture(True)
        self.assertIsNone(report['reward'])
        self.assertEqual(report['evaluation_status'], 'failed')

    def test_start_requires_separate_approval(self):
        with self.assertRaises(PermissionError):
            asyncio.run(execute_trial(None,None,None,1))


if __name__ == '__main__':unittest.main()
