"""Offline IPC timeout reproduction; no worker, provider, Task, or evaluator."""
import importlib.util
import io
from pathlib import Path
import queue
import time

SOURCE = Path(__file__).resolve().parents[3] / "GenericAgent-main" / "pos_bridge.py"
spec = importlib.util.spec_from_file_location("sampler_pos_bridge", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Process:
    def __init__(self):
        self.stdin = io.StringIO()

    def poll(self):
        return None


class NoReceipt:
    def __init__(self):
        self.timeout = None

    def get(self, timeout):
        self.timeout = timeout
        raise queue.Empty


bridge = module.PoSBridge.__new__(module.PoSBridge)
bridge.process = Process()
bridge.replies = NoReceipt()
bridge.timeout = 180.0
bridge.deadline_epoch = time.time() + 1000
bridge.sent = 0
bridge.closed = False
bridge.close = lambda: setattr(bridge, "closed", True)
try:
    bridge.exchange("update", step=88)
except module.PoSBridgeError as exc:
    assert str(exc) == "PoS command result unknown; never resend"
else:
    raise AssertionError("missing receipt was accepted")
assert bridge.replies.timeout == 180.0
assert bridge.sent == 1 and bridge.closed
assert bridge.process.stdin.getvalue().count('"kind": "update"') == 1
print("PASS: one update waits 180s for one receipt; queue.Empty closes IPC and forbids resend")
