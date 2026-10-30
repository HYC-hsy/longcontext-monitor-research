"""Keep the host scan and its enclosing finish wait in sync."""

import asyncio
import json
import subprocess
import unittest
from unittest.mock import AsyncMock, patch

from . import control_processes
from .pma_harbor_hooks import NativeSharedTrialHooks


class ScanTimeoutTests(unittest.TestCase):
    def test_scan_allows_bounded_slow_docker_exec(self):
        response = subprocess.CompletedProcess([], 0, json.dumps({
            'pid_namespace': 'pid:[1]', 'processes': []}), '')
        with patch.object(control_processes.subprocess, 'run', return_value=response) as run:
            self.assertEqual(control_processes.scan('container', 'python', 'run')['processes'], [])
        self.assertEqual(run.call_args.kwargs['timeout'], 120)


class FinishTimeoutTests(unittest.IsolatedAsyncioTestCase):
    async def test_finish_wait_exceeds_single_scan_timeout(self):
        hooks = object.__new__(NativeSharedTrialHooks)
        hooks._control_watch_stop = asyncio.Event()
        hooks._control_watch_task = object()
        with patch('asyncio.wait_for', new_callable=AsyncMock) as wait:
            await hooks._finish_control_watch()
        self.assertTrue(hooks._control_watch_stop.is_set())
        self.assertEqual(wait.call_args.kwargs['timeout'], 130)


if __name__ == '__main__':
    unittest.main()
