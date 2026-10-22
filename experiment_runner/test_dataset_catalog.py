import subprocess
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from experiment_runner.dataset_catalog import catalog
from experiment_runner.methods import resolve, register, Method, validate_binding


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        for name, text in {'task.toml': '[agent]\ntimeout_sec=900\n[verifier]\ntimeout_sec=900',
                           'instruction.md': 'Public instruction',
                           'tests/test.sh': 'PRIVATE EVALUATOR',
                           'solution/solve.sh': 'PRIVATE SOLUTION',
                           'environment/Dockerfile': 'FROM example'}.items():
            path = self.root / 'sqlite-with-gcov' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        subprocess.run(['git', '-C', str(self.root), 'add', '.'], check=True)
        subprocess.run(['git', '-C', str(self.root), '-c', 'user.name=test',
                        '-c', 'user.email=test@example.org', 'commit', '-qm', 'fixture'], check=True)
        self.commit = subprocess.check_output(['git', '-C', str(self.root), 'rev-parse', 'HEAD']).decode().strip()
        self.dataset = {'source_git': str(self.root), 'commit': self.commit}

    def test_public_only_and_pinned(self):
        import experiment_runner.dataset_catalog as module
        calls = []
        original = module._git
        def record(source, *args):
            calls.append(args)
            return original(source, *args)
        with patch.object(module, '_git', record):
            result = catalog(self.dataset)
        self.assertEqual(result['tasks'][0]['agent_timeout_sec'], 900)
        self.assertEqual([x for x in calls if x[0] == 'show'],
                         [('show', f'{self.commit}:sqlite-with-gcov/task.toml')])
        self.assertNotIn('tests/test.sh', result['tasks'][0]['public_blobs'])

    def test_invalid_and_missing(self):
        for name in ('../bad', 'missing'):
            with self.assertRaises(ValueError):
                catalog(self.dataset, [name])
        with self.assertRaises(ValueError):
            catalog({**self.dataset, 'commit': 'HEAD'})

    def test_registry_cannot_invent_dispatch(self):
        with self.assertRaisesRegex(ValueError, 'no installed'):
            register(Method('invented', 'B', 'new-algorithm'))
        with self.assertRaises(ValueError):
            validate_binding('A', 'pma_stateful_memory_v1')
        self.assertTrue(validate_binding('B', 'pma_stateful_memory_v1'))

    def test_registry(self):
        self.assertEqual(resolve('pma-stateful').prepare_fields()['research_candidate'],
                         'pma_stateful_memory_v1')
        with self.assertRaises(ValueError):
            resolve('typo')


if __name__ == '__main__':
    unittest.main()
