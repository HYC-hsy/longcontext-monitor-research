"""Framework-neutral finite pause, composed with the host's existing abort.

A lease gates the next model call, not a filesystem transaction. It cannot
undo tools already executed. No monitor LLM is called from this gate.
"""
import threading
import time


class PauseLease:
    def __init__(self):
        self._condition = threading.Condition()
        self._deadline = 0.0
        self._reason = ''

    def request(self, reason, seconds=120):
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError('A concrete pause reason is required')
        if type(seconds) not in (int, float) or not 1 <= seconds <= 300:
            raise ValueError('Pause duration must be between 1 and 300 seconds')
        with self._condition:
            self._reason = reason.strip()
            self._deadline = time.monotonic() + seconds
            self._condition.notify_all()
            return {'status': 'pause_requested', 'seconds': seconds, 'reason': self._reason,
                    'scope': 'next model call; running action cancellation is host-dependent'}

    def release(self):
        with self._condition:
            active = self._deadline > time.monotonic()
            self._deadline = 0.0
            self._condition.notify_all()
            return {'status': 'released', 'was_active': active}

    def wait(self, stopped=lambda: False):
        with self._condition:
            while self._deadline > time.monotonic():
                if stopped():
                    return False
                self._condition.wait(min(0.1, self._deadline - time.monotonic()))
        return not stopped()
