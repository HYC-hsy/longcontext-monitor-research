"""Autonomous concurrent runtime for the persistent research monitor.

The task side only appends public boundaries to an archive. A separate monitor
process watches the archive, chooses what to retrieve, and returns only real
interventions; SILENT decisions never enter the task Agent's critical path.
"""
from __future__ import annotations

import multiprocessing as mp
import json
import os
import queue
import threading
import time
import traceback
from collections import deque
from dataclasses import asdict
from typing import Any, Mapping
from pathlib import Path

from research_runtime import emit, new_id


def _read_archive(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _monitor_worker(monitor_kwargs: dict[str, Any], requests, responses, wake_event) -> None:
    from m0_deliberative_monitor import M0DeliberativeMonitor
    from research_runtime import JsonlEventSink, research_context

    values = dict(monitor_kwargs)
    event_path = values.pop("_runtime_event_path", None)
    identity = values.pop("_runtime_identity", {})
    archive_path = Path(values.pop("_runtime_boundary_archive"))
    monitor = M0DeliberativeMonitor(**values)
    sink = JsonlEventSink(event_path) if event_path else None
    with research_context(identity, sink):
        while True:
            try:
                item = requests.get_nowait()
            except queue.Empty:
                item = None
            if item is not None:
                if item.get("kind") == "stop":
                    return
                request_id = item["request_id"]
                responses.put({"kind": "started", "request_id": request_id,
                               "started_at": time.monotonic()})
                try:
                    proposal = item["proposal"]
                    decision = monitor.review_completion(
                        type("Proposal", (), proposal)(), item["turn"],
                        item.get("provider_link"), item.get("response_content", ""),
                    )
                    responses.put({"kind": "completion_result", "request_id": request_id,
                                   "decision": asdict(decision)})
                except BaseException as error:
                    responses.put({"kind": "error", "request_id": request_id,
                                   "error_type": type(error).__name__, "error": str(error)[:1000],
                                   "traceback": traceback.format_exc()[-4000:]})
                continue

            rows = _read_archive(archive_path)
            unseen = [row for row in rows
                      if str(row.get("archive_event_id", "")) not in monitor._observed_archive_ids]
            if not unseen:
                wake_event.wait(0.5)
                wake_event.clear()
                continue

            # Archive ingestion is deterministic indexing, not semantic review.
            # The model sees only this cursor notification and must actively use
            # trajectory/workspace tools to reconstruct any content it needs.
            monitor.observe_archived_boundaries(unseen)
            request_id = new_id("monitor_observation")
            latest_turn = max(int(row.get("internal_turn") or 0) for row in unseen)
            wake_packet = {
                "archive_wake_only": True,
                "boundary": "autonomous_archive_observation",
                "internal_turn": latest_turn,
                "archive_delta": {
                    "new_boundaries": len(unseen),
                    "first_sequence": unseen[0].get("archive_sequence"),
                    "last_sequence": unseen[-1].get("archive_sequence"),
                    "boundary_types": sorted({str(row.get("boundary", "")) for row in unseen}),
                },
                "response_content": "", "tool_calls": [], "tool_results": [],
            }
            responses.put({"kind": "started", "request_id": request_id,
                           "started_at": time.monotonic()})
            try:
                message = monitor.review(wake_packet)
                responses.put({"kind": "boundary_result", "request_id": request_id,
                               "message": message, "internal_turn": latest_turn})
            except BaseException as error:
                responses.put({"kind": "error", "request_id": request_id,
                               "error_type": type(error).__name__, "error": str(error)[:1000],
                               "traceback": traceback.format_exc()[-4000:]})


class AsyncMonitorRuntime:
    """Non-blocking event publisher plus bounded completion-boundary control."""

    def __init__(self, monitor_kwargs: Mapping[str, Any], *, request_timeout: float = 300.0,
                 queue_capacity: int = 256, mp_context: str | None = None,
                 worker_target=None):
        self.monitor_kwargs = dict(monitor_kwargs)
        self.request_timeout = max(1.0, float(request_timeout))
        self.queue_capacity = max(8, int(queue_capacity))
        # GenericAgent runs its task loop in a thread. Forking a multithreaded
        # Python process can inherit locked runtime state, so production always
        # uses a clean spawned interpreter.
        method = mp_context or "spawn"
        self.context = mp.get_context(method)
        self.worker_target = worker_target or _monitor_worker
        artifact_dir = self.monitor_kwargs.get("artifact_dir")
        default_archive = Path(artifact_dir or os.getcwd()) / "async_public_boundaries.jsonl"
        self.boundary_archive = Path(
            self.monitor_kwargs.setdefault("_runtime_boundary_archive", str(default_archive))
        )
        self.boundary_archive.parent.mkdir(parents=True, exist_ok=True)
        self._archive_lock = threading.Lock()
        self._archive_sequence = len(_read_archive(self.boundary_archive))
        self.process = None
        self.requests = None
        self.responses = None
        self.active: dict[str, Any] | None = None
        self.pending: dict[str, dict[str, Any]] = {}
        self.interventions: deque[dict[str, Any]] = deque()
        self.completion_results: dict[str, dict[str, Any]] = {}
        self.generation = 0
        self._start_worker("initial")

    def _start_worker(self, reason: str) -> None:
        self.requests = self.context.Queue(self.queue_capacity)
        self.responses = self.context.Queue(self.queue_capacity)
        self.wake_event = self.context.Event()
        worker_args = (self.monitor_kwargs, self.requests, self.responses, self.wake_event)
        self.process = self.context.Process(
            target=self.worker_target, args=worker_args,
            name="ga-persistent-monitor", daemon=True,
        )
        self.process.start()
        self.generation += 1
        self.active = None
        emit("async_monitor_worker_started", {
            "generation": self.generation, "pid": self.process.pid, "reason": reason,
        })

    def _stop_worker(self, reason: str) -> None:
        process = self.process
        if process is not None and process.is_alive():
            process.terminate()
            process.join(timeout=3)
            if process.is_alive() and hasattr(process, "kill"):
                process.kill()
                process.join(timeout=2)
        emit("async_monitor_worker_stopped", {
            "generation": self.generation, "reason": reason,
            "exitcode": None if process is None else process.exitcode,
        })

    def _restart(self, reason: str) -> None:
        abandoned = list(self.pending)
        self._stop_worker(reason)
        self.pending.clear()
        self.active = None
        emit("async_monitor_requests_abandoned", {
            "reason": reason, "request_ids": abandoned,
        })
        self._start_worker(reason)

    def _drain(self) -> None:
        while True:
            try:
                result = self.responses.get_nowait()
            except queue.Empty:
                break
            request_id = result.get("request_id")
            if result["kind"] == "started":
                self.active = {"request_id": request_id,
                               "started_at": result.get("started_at", time.monotonic())}
                continue
            self.pending.pop(request_id, None)
            if self.active and self.active.get("request_id") == request_id:
                self.active = None
            if result["kind"] == "boundary_result":
                message = str(result.get("message") or "").strip()
                if message:
                    self.interventions.append({
                        "request_id": request_id, "message": message,
                        "internal_turn": result.get("internal_turn"),
                    })
                    emit("async_monitor_intervention_ready", {
                        "request_id": request_id, "internal_turn": result.get("internal_turn"),
                        "message_characters": len(message),
                    })
            elif result["kind"] == "error":
                emit("async_monitor_request_failed", result)
            else:
                self.completion_results[request_id] = result

    def _watchdog(self) -> None:
        self._drain()
        if self.process is None or not self.process.is_alive():
            self._restart("worker_exit")
            return
        if self.active and time.monotonic() - self.active["started_at"] > self.request_timeout:
            emit("async_monitor_request_timeout", {
                "request_id": self.active["request_id"],
                "timeout_seconds": self.request_timeout,
            })
            self._restart("request_timeout")

    def archive_boundary(self, packet: Mapping[str, Any]) -> bool:
        """Archive one public boundary and wake the autonomous observer."""
        self._watchdog()
        with self._archive_lock:
            self._archive_sequence += 1
            archive_id = new_id("public_boundary")
            row = {"archive_event_id": archive_id,
                   "archive_sequence": self._archive_sequence, **dict(packet)}
            with self.boundary_archive.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
        self.wake_event.set()
        emit("async_monitor_boundary_archived", {
            "archive_event_id": archive_id, "archive_sequence": self._archive_sequence,
            "internal_turn": packet.get("internal_turn"),
            "boundary": packet.get("boundary"),
        })
        return True

    # Compatibility for non-M0 fixtures. Production M0 call sites use the
    # explicit archive_boundary name to avoid implying semantic packet push.
    publish = archive_boundary

    def consume_interventions(self) -> list[dict[str, Any]]:
        self._watchdog()
        values = list(self.interventions)
        self.interventions.clear()
        return values

    def review_completion(self, proposal, turn: int, provider_link=None,
                          response_content: str = ""):
        """Bound only the explicit root-completion transition, never ordinary turns."""
        from research_runtime import CompletionDecision

        self._watchdog()
        # Root completion is the one intentionally controlled transition. Do
        # not wait behind stale ordinary boundaries: durable archives and the
        # checkpoint let a fresh worker reconstruct the current completion view.
        if self.active or self.pending:
            self._restart("completion_priority_reconstruction")
        request_id = new_id("monitor_completion")
        item = {
            "kind": "completion", "request_id": request_id,
            "proposal": proposal.as_payload(), "turn": turn,
            "provider_link": dict(provider_link or {}),
            "response_content": response_content,
        }
        try:
            self.requests.put_nowait(item)
            self.wake_event.set()
        except queue.Full:
            emit("async_monitor_completion_fail_open", {
                "request_id": request_id, "reason": "queue_full",
            })
            return CompletionDecision(
                decision="ERROR_FAIL_OPEN", reason_codes=("MONITOR_QUEUE_FULL",),
            )
        self.pending[request_id] = item
        deadline = time.monotonic() + self.request_timeout
        while time.monotonic() < deadline:
            self._watchdog()
            result = self.completion_results.pop(request_id, None)
            if result is not None:
                value = result["decision"]
                return CompletionDecision(
                    decision=value["decision"],
                    reason_codes=tuple(value.get("reason_codes") or ()),
                    next_prompt=value.get("next_prompt"),
                    target_obligation_ids=tuple(value.get("target_obligation_ids") or ()),
                    checker_ids=tuple(value.get("checker_ids") or ()),
                )
            if request_id not in self.pending:
                break
            time.sleep(0.05)
        self.pending.pop(request_id, None)
        emit("async_monitor_completion_fail_open", {
            "request_id": request_id, "reason": "bounded_wait_expired",
            "timeout_seconds": self.request_timeout,
        })
        return CompletionDecision(
            decision="ERROR_FAIL_OPEN", reason_codes=("MONITOR_TIMEOUT",),
        )

    def close(self) -> None:
        if self.process is not None and self.process.is_alive():
            try:
                self.requests.put_nowait({"kind": "stop"})
                self.wake_event.set()
            except queue.Full:
                pass
            self.process.join(timeout=2)
        if self.process is not None and self.process.is_alive():
            self._stop_worker("close")
