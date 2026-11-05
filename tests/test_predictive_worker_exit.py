"""Uncapped supervisor must not wait forever on a dead PMA worker."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.live_launcher import (
    _require_worker_until_task_end,
)


class WorkerExitTests(unittest.TestCase):
    def test_live_worker_can_continue(self):
        with tempfile.TemporaryDirectory() as directory:
            _require_worker_until_task_end(Path(directory), SimpleNamespace(poll=lambda: None), 'run')

    def test_early_or_unverified_exit_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            private = root / 'host_private'
            private.mkdir()
            dead = SimpleNamespace(poll=lambda: 2)
            with self.assertRaisesRegex(RuntimeError, 'before a verified task_end'):
                _require_worker_until_task_end(root, dead, 'run')
            for receipt in ({'run_id': 'run', 'task_end_saved': False},
                            {'run_id': 'other', 'task_end_saved': True}):
                (private / 'worker_exit.json').write_text(json.dumps(receipt), encoding='utf-8')
                with self.assertRaisesRegex(RuntimeError, 'before a verified task_end'):
                    _require_worker_until_task_end(root, dead, 'run')

    def test_verified_end_allows_native_evaluation_to_finish(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            private = root / 'host_private'
            private.mkdir()
            (private / 'worker_exit.json').write_text(json.dumps({
                'run_id': 'run', 'task_end_saved': True}), encoding='utf-8')
            _require_worker_until_task_end(root, SimpleNamespace(poll=lambda: 0), 'run')


if __name__ == '__main__':
    unittest.main()
