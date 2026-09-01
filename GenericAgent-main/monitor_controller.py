"""Semantic-free, nonblocking controller shell for the clean Monitor Agent."""

from __future__ import annotations

import queue
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Callable

from monitor_agent import MonitorAction


@dataclass(frozen=True)
class WakeRequest:
    request_id: str
    cursor: int
    context: str
    completion_pending: bool = False


@dataclass(frozen=True)
class ActionReceipt:
    request_id: str
    cursor: int
    action: dict
    created_at: float


class MonitorController:
    """Schedule reviews without placing them on the Task Agent critical path.

    This shell understands cursors and lifecycle only.  It neither constructs a
    semantic packet nor judges whether a task event is correct.
    """

    def __init__(
        self,
        review: Callable[[str, bool], MonitorAction],
        *,
        on_intervention: Callable[[str], None] | None = None,
    ):
        self._review = review
        self._on_intervention = on_intervention
        self._requests: queue.Queue[WakeRequest | None] = queue.Queue()
        self._receipts: queue.Queue[ActionReceipt] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._latest_cursor = 0
        self._latest_context = ""
        self._next_wake_cursor = 0
        self._review_inflight = False
        self._close_watch = False
        self._pending_completion: tuple[int, str] | None = None
        self._stopping = False
        self.failures: list[dict] = []

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stopping = False
        self._thread = threading.Thread(target=self._worker, name="monitor-agent", daemon=True)
        self._thread.start()

    def initialize(self, context: str) -> bool:
        """Request turn-zero orientation without blocking Task Agent startup."""
        return self._schedule(0, context, completion_pending=False, force=True)

    def publish_cursor(self, cursor: int, context: str) -> bool:
        """Publish a content-free wake signal plus caller-owned navigation text."""
        with self._lock:
            if cursor <= self._latest_cursor:
                return False
            self._latest_cursor = cursor
            self._latest_context = context
            due = self._close_watch or cursor >= self._next_wake_cursor
        return self._schedule(cursor, context, completion_pending=False) if due else False

    def propose_completion(self, cursor: int, context: str) -> bool:
        with self._lock:
            self._latest_cursor = max(self._latest_cursor, cursor)
            self._latest_context = context
            if self._review_inflight:
                self._pending_completion = (cursor, context)
                return False
        return self._schedule(cursor, context, completion_pending=True, force=True)

    def _schedule(self, cursor: int, context: str, *, completion_pending: bool, force: bool = False) -> bool:
        with self._lock:
            if self._stopping or self._review_inflight:
                return False
            if not force and not self._close_watch and cursor < self._next_wake_cursor:
                return False
            self._review_inflight = True
        self._requests.put(WakeRequest(uuid.uuid4().hex, cursor, context, completion_pending))
        return True

    def _worker(self) -> None:
        while True:
            request = self._requests.get()
            if request is None:
                return
            try:
                action = self._review(request.context, request.completion_pending)
                self._apply_action(request, action)
            except Exception as exc:
                self.failures.append({
                    "request_id": request.request_id,
                    "cursor": request.cursor,
                    "error": repr(exc),
                    "created_at": time.time(),
                })
            finally:
                with self._lock:
                    self._review_inflight = False
                    pending_completion = self._pending_completion
                    self._pending_completion = None
                    catch_up = (
                        pending_completion is None
                        and
                        not self._stopping
                        and self._latest_cursor > request.cursor
                        and (self._close_watch or self._latest_cursor >= self._next_wake_cursor)
                    )
                    cursor = self._latest_cursor
                    context = self._latest_context
                if pending_completion is not None and not self._stopping:
                    self._schedule(
                        pending_completion[0], pending_completion[1],
                        completion_pending=True, force=True,
                    )
                elif catch_up:
                    self._schedule(cursor, context, completion_pending=False)

    def _apply_action(self, request: WakeRequest, action: MonitorAction) -> None:
        with self._lock:
            if action.kind == "wait":
                self._close_watch = False
                self._next_wake_cursor = request.cursor + max(1, int(action.payload["after_turns"]))
            elif action.kind == "intervene":
                self._close_watch = True
                self._next_wake_cursor = request.cursor + 1
            elif action.kind != "allow_complete":
                raise ValueError(f"Unknown monitor action: {action.kind}")
        if action.kind == "intervene" and self._on_intervention:
            self._on_intervention(action.payload["message"])
        self._receipts.put(ActionReceipt(
            request.request_id, request.cursor, asdict(action), time.time()
        ))

    def get_receipt(self, timeout: float | None = None) -> ActionReceipt:
        return self._receipts.get(timeout=timeout)

    def stop(self, timeout: float = 2.0) -> None:
        with self._lock:
            self._stopping = True
        self._requests.put(None)
        if self._thread:
            self._thread.join(timeout=timeout)

    @property
    def review_inflight(self) -> bool:
        with self._lock:
            return self._review_inflight

    @property
    def close_watch(self) -> bool:
        with self._lock:
            return self._close_watch
