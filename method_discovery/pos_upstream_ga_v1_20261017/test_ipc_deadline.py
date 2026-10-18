"""No-model PoS IPC deadline and diagnostic controls."""
import io
import json
import math
from pathlib import Path
import queue
import tempfile
import unittest
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'GenericAgent-main'))
import pos_bridge


class Clock:
    def __init__(self):
        self.value = 0.0

    def monotonic(self):
        return self.value


class Process:
    def __init__(self):
        self.stdin = io.StringIO()
        self.returncode = None
        self.exited = False

    def poll(self):
        return 1 if self.exited else None


class Replies:
    def __init__(self, clock, ready=None, raw=None, exit_at=None, process=None):
        self.clock, self.ready, self.raw = clock, ready, raw
        self.exit_at, self.process = exit_at, process
        self.waits = []

    def get(self, timeout):
        self.waits.append(timeout)
        self.clock.value += timeout
        if self.exit_at is not None and self.clock.value >= self.exit_at:
            self.process.exited = True
        if self.ready is not None and self.clock.value >= self.ready:
            return self.raw
        raise queue.Empty


class DeadlineTests(unittest.TestCase):
    def bridge(self, root, clock, *, deadline=10, ready=None, raw=None,
               exit_at=None):
        bridge = pos_bridge.PoSBridge.__new__(pos_bridge.PoSBridge)
        bridge.process = Process()
        bridge.replies = Replies(clock, ready, raw, exit_at, bridge.process)
        bridge._reader = type('Reader', (), {'is_alive': lambda self: False})()
        bridge.timeout = 1.0  # scaled per-request cap, not IPC limit
        bridge.deadline_epoch = 1000.0
        bridge.deadline_monotonic = deadline
        bridge.sent = 0
        bridge.closed = False
        bridge.close_status = None
        bridge.archive_path = Path(root) / 'events.jsonl'
        bridge.run_id = 'synthetic-run'
        bridge.task_id = 'synthetic-task'
        bridge.diagnostic_persist_error_type = None
        bridge.close = lambda: setattr(bridge, 'closed', True)
        return bridge

    def test_cumulative_wait_exceeds_provider_limit_without_resend(self):
        with tempfile.TemporaryDirectory() as root:
            clock = Clock()
            bridge = self.bridge(root, clock, ready=3.0,
                raw=json.dumps({'status':'ok','result':{'done':True}}))
            with patch.object(pos_bridge.time, 'monotonic', clock.monotonic):
                self.assertEqual(bridge.exchange('update')['done'], True)
            self.assertEqual(clock.value, 3.0)
            self.assertEqual(bridge.sent, 1)
            self.assertEqual(bridge.process.stdin.getvalue().count('"kind": "update"'), 1)
            events = [json.loads(x) for x in (Path(root)/'events.bridge.jsonl').read_text().splitlines()]
            self.assertEqual([x['event'] for x in events],
                             ['command_started','command_sent','command_finished'])
            self.assertEqual(events[-1]['outcome'], 'receipt_ok')

    def test_fixed_deadline_and_worker_exit(self):
        for mode in ('deadline','exit','eof','cancel'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as root:
                clock = Clock()
                bridge = self.bridge(root, clock, deadline=1.25,
                    exit_at=0.5 if mode=='exit' else None,
                    ready=0.5 if mode=='eof' else None,
                    raw=None)
                if mode == 'cancel':
                    original = bridge.replies.get
                    def cancel(timeout):
                        bridge.closed = True
                        return original(timeout)
                    bridge.replies.get = cancel
                with patch.object(pos_bridge.time, 'monotonic', clock.monotonic):
                    with self.assertRaises(pos_bridge.PoSBridgeError):
                        bridge.exchange('update')
                self.assertEqual(bridge.sent, 1)
                self.assertLessEqual(clock.value, 1.25)
                events = [json.loads(x) for x in
                    (Path(root)/'events.bridge.jsonl').read_text().splitlines()]
                self.assertEqual(events[-1]['event'], 'command_finished')
                self.assertTrue(events[-1]['result_unknown'])
                self.assertEqual(events[-1]['command_id'], 'cmd-000001')

    def test_profile_requires_finite_frozen_deadline_before_spawn(self):
        kwargs = dict(worker_script='unused',vendor='unused',episode_module='unused',
                      archive='unused',mode='profile')
        for deadline in (None, math.inf, math.nan, -1):
            with self.subTest(deadline=deadline):
                with self.assertRaises(pos_bridge.PoSBridgeError):
                    pos_bridge.PoSBridge(**kwargs, deadline_epoch=deadline)


if __name__ == '__main__':
    unittest.main(verbosity=2)
