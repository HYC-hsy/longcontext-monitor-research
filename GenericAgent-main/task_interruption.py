"""Thread-safe resumable interruption mailbox for a running Task Agent."""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class InterruptionRequest:
    sequence: int
    message: str
    source: str
    created_at: float


class ResumableInterruption:
    """Cancel the current action without terminating the surrounding task."""

    def __init__(self):
        self._lock = threading.Lock()
        self._requested = threading.Event()
        self._pending: deque[InterruptionRequest] = deque()
        self._sequence = 0

    def request(self, message: str, source: str = "monitor") -> InterruptionRequest:
        message = str(message or "").strip()
        if not message:
            raise ValueError("Interruption message must not be empty")
        with self._lock:
            self._sequence += 1
            request = InterruptionRequest(self._sequence, message, source, time.time())
            self._pending.append(request)
            self._requested.set()
            return request

    def is_requested(self) -> bool:
        return self._requested.is_set()

    def consume(self) -> list[dict]:
        with self._lock:
            values = [asdict(value) for value in self._pending]
            self._pending.clear()
            self._requested.clear()
            return values
