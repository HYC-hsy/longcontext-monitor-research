"""Candidate-only Agent-time diagnostic contract; no model or Docker calls."""

import asyncio
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from .harbor_adapter import _UncappedAgentExecution
from .live_launcher import _derive_uncapped_task


class _Environment:
    def __init__(self):
        self.calls = []

    async def exec(self, command, *args, **kwargs):
        self.calls.append((command, args, kwargs))
        return object()


class StatefulAgentTimeTests(unittest.TestCase):
    def test_derived_task_changes_only_agent_timeout(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            task = root / 'public_task'
            task.mkdir()
            original = (b'[task]\nname="test"\n[verifier]\ntimeout_sec = 900.0\n'
                        b'[agent]\ntimeout_sec = 900.0\n[environment]\ncpus = 1\n')
            (task / 'task.toml').write_bytes(original)
            result = _derive_uncapped_task(root)
            derived = (task / 'task.toml').read_bytes()
            self.assertEqual(result['original_task_toml_sha256'],
                             hashlib.sha256(original).hexdigest())
            self.assertEqual(result['derived_task_toml_sha256'],
                             hashlib.sha256(derived).hexdigest())
            self.assertEqual(result['agent_timeout_sec'], None)
            self.assertIn(b'[agent]\n[environment]', derived)
            self.assertIn(b'[verifier]\ntimeout_sec = 900.0', derived)

    def test_uncapped_adapter_changes_only_long_exec(self):
        base = _Environment()
        overlay = _UncappedAgentExecution(base, 'run-1', 900)
        command = ('set +e\n# GA_WRAPPER_RUN_ID=run-1\n'
                   'timed_out=1\nfor i in $(seq 1 450); do\n'
                   '  sleep 2\ndone\n')
        asyncio.run(overlay.exec(command, timeout_sec=990, user='root'))
        actual, _, options = base.calls[0]
        self.assertIn('timed_out=0\nwhile :; do', actual)
        self.assertNotIn('seq 1 450', actual)
        self.assertIsNone(options['timeout_sec'])
        self.assertEqual(options['user'], 'root')
        with self.assertRaisesRegex(RuntimeError, 'repeated'):
            asyncio.run(overlay.exec(command, timeout_sec=990))
        self.assertEqual(len(base.calls), 1)

    def test_changed_base_template_refused(self):
        base = _Environment()
        overlay = _UncappedAgentExecution(base, 'run-1', 900)
        with self.assertRaisesRegex(RuntimeError, 'template changed'):
            asyncio.run(overlay.exec('# GA_WRAPPER_RUN_ID=run-1\n'
                                     'for i in $(seq 1 450); do', timeout_sec=990))
        self.assertEqual(base.calls, [])


if __name__ == '__main__':
    unittest.main()
