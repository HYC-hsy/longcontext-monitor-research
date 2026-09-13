"""Host-owned stop while an announced correction is being delivered.

No model-facing pause action. Normal observation never acquires this barrier.
"""
import threading
import time


class CorrectionBarrier:
    def __init__(self):
        self._condition = threading.Condition()
        self._active = None
        self._deadline = 0.0

    def begin(self, identity, timeout=300):
        with self._condition:
            self._active = identity
            self._deadline = time.monotonic() + timeout
            self._condition.notify_all()

    def end(self, identity=None):
        with self._condition:
            if identity is None or self._active == identity:
                self._active = None
                self._condition.notify_all()

    def is_active(self):
        with self._condition:
            return self._active is not None

    def wait(self, stopped=lambda: False):
        with self._condition:
            while self._active is not None:
                if stopped():
                    return False
                if time.monotonic() >= self._deadline:
                    self._active = None
                    return True
                self._condition.wait(.05)
        return not stopped()
