"""Autonomous concurrent runtime for the persistent research monitor.

The task side only appends public boundaries to an archive. A separate monitor
process watches the archive, chooses what to retrieve, and returns only real
interventions; an empty intervention never enters the task Agent's critical path.
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


def _completion_recovery_decision(reason_code: str):
    """Keep the root task open when its dedicated monitor audit is unavailable."""
    from research_runtime import CompletionDecision

    return CompletionDecision(
        decision="CONTINUE",
        reason_codes=(reason_code,),
        next_prompt=(
            "The persistent monitor could not complete the root-task audit at this "
            "boundary. Continue concrete work from the original public task and do "
            "not treat this monitor failure as completion evidence. The monitor will "
            "reconstruct its audit at a later completion boundary."
        ),
    )


def _review_cursor_path(archive_path: Path) -> Path:
    return archive_path.with_name("adaptive_review_cursor.json")


def _load_review_cursor(archive_path: Path) -> int:
    path = _review_cursor_path(archive_path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return max(0, int(value.get("last_reviewed_sequence", 0)))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return 0


def _save_review_cursor(archive_path: Path, sequence: int) -> None:
    path = _review_cursor_path(archive_path)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps({
        "schema_version": "adaptive-monitor-review-cursor/1",
        "last_reviewed_sequence": int(sequence),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)


def _adaptive_review_reason(rows: list[Mapping[str, Any]], *, focused: bool,
                            review_after_turns: int = 20,
                            initial_calibration: bool = False) -> str | None:
    """Execute the monitor-authored patrol distance without semantic classification."""
    if not rows:
        return None
    latest_boundary = str(rows[-1].get("boundary", ""))
    settled = latest_boundary == "post_tool_pre_next_llm"
    # Focused attention matches the demonstrated human loop: remain online for
    # both the Agent's next stated intent and the resulting public action even
    # when the monitor has no new message. This does
    # not expand intent-level review to ordinary patrol operation.
    if focused:
        if latest_boundary == "post_model_pre_tool":
            return "focused_intent_followup"
        if latest_boundary == "post_tool_pre_next_llm":
            return "focused_result_followup"
        return None
    if not settled:
        return None
    turns = {int(row.get("internal_turn") or 0) for row in rows}
    # Turn-0 initialization has no evidence about task speed or artifact shape.
    # Give the same monitor one small real progress window, then let its own
    # observation plan govern every later patrol.  This is an activity clock,
    # not an outer semantic classifier.
    distance = min(int(review_after_turns), 3) if initial_calibration else int(
        review_after_turns
    )
    if len(turns) >= max(1, distance):
        return (
            "initial_monitor_calibration"
            if initial_calibration else "monitor_authored_semantic_patrol"
        )
    return None


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


def _max_archive_sequence(rows: list[Mapping[str, Any]]) -> int:
    sequences = []
    for row in rows:
        try:
            sequences.append(max(0, int(row.get("archive_sequence") or 0)))
        except (TypeError, ValueError):
            continue
    return max(sequences, default=0)


def _reconciled_review_cursor(archive_path: Path) -> tuple[int, int]:
    """Return a cursor valid for the current archive and its stored value."""
    stored = _load_review_cursor(archive_path)
    archived = _max_archive_sequence(_read_archive(archive_path))
    return (0 if stored > archived else stored), stored


def _resume_archive(path: Path) -> int:
    """Return the durable sequence and isolate any crash-truncated tail."""
    rows = _read_archive(path)
    sequence = _max_archive_sequence(rows)
    try:
        if path.stat().st_size:
            with path.open("rb+") as stream:
                stream.seek(-1, os.SEEK_END)
                if stream.read(1) != b"\n":
                    # Preserve the damaged bytes for audit, but ensure the next
                    # valid record begins on its own JSONL line.
                    stream.seek(0, os.SEEK_END)
                    stream.write(b"\n")
    except OSError:
        # The normal append below remains authoritative and will surface any
        # genuine filesystem failure; recovery inspection is best effort.
        pass
    return sequence


class _IncrementalArchiveReader:
    """Read newly appended complete JSONL records without semantic filtering."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.offset = 0
        self.identity: tuple[int, int] | None = None

    def read_new(self) -> tuple[list[dict[str, Any]], bool]:
        try:
            stat = self.path.stat()
        except OSError:
            return [], False
        identity = (int(stat.st_dev), int(stat.st_ino))
        reset = bool(
            (self.identity is not None and identity != self.identity)
            or stat.st_size < self.offset
        )
        if reset:
            self.offset = 0
        self.identity = identity
        rows: list[dict[str, Any]] = []
        try:
            with self.path.open("rb") as stream:
                stream.seek(self.offset)
                while True:
                    line_start = stream.tell()
                    line = stream.readline()
                    if not line:
                        break
                    # The task process may currently be appending the final
                    # record. Leave an incomplete line for the next patrol.
                    if not line.endswith(b"\n"):
                        self.offset = line_start
                        break
                    self.offset = stream.tell()
                    try:
                        value = json.loads(line.decode("utf-8", errors="replace"))
                    except json.JSONDecodeError:
                        continue
                    if isinstance(value, dict):
                        rows.append(value)
        except OSError:
            return [], reset
        return rows, reset


def _review_with_one_freshness_pass(monitor, archive_path: Path,
                                    wake_packet: Mapping[str, Any],
                                    reviewed_sequence: int, *,
                                    archive_reader: _IncrementalArchiveReader | None = None,
                                    pending_rows: list[dict[str, Any]] | None = None,
                                    ) -> tuple[str, int, int, bool]:
    """Recheck one nonempty correction against activity that arrived during review."""
    message = str(monitor.review(wake_packet) or "").strip()
    reviewed_turn = int(wake_packet.get("internal_turn") or 0)
    if not message:
        return "", int(reviewed_sequence), reviewed_turn, False
    if archive_reader is None:
        rows = _read_archive(archive_path)
    else:
        rows, _reset = archive_reader.read_new()
        # Reading advances the byte cursor. Register fresh rows in the worker's
        # retry buffer before asking the model, so an exception during the
        # freshness judgment cannot make those public events disappear until a
        # process restart. The caller removes them only after cursor commit.
        if pending_rows is not None:
            pending_rows.extend(rows)
    fresh = [row for row in rows
             if int(row.get("archive_sequence") or 0) > int(reviewed_sequence)]
    if not fresh:
        return message, int(reviewed_sequence), reviewed_turn, False
    monitor.observe_archived_boundaries(fresh)
    latest_sequence = int(fresh[-1].get("archive_sequence") or reviewed_sequence)
    latest_turn = max(int(row.get("internal_turn") or 0) for row in fresh)
    packet = {
        "archive_wake_only": True,
        "boundary": "autonomous_archive_observation",
        "internal_turn": latest_turn,
        "archive_delta": {
            "new_boundaries": len(fresh),
            "first_sequence": fresh[0].get("archive_sequence"),
            "last_sequence": fresh[-1].get("archive_sequence"),
            "boundary_types": sorted({str(row.get("boundary", "")) for row in fresh}),
            "review_trigger": "prepublish_intervention_freshness",
        },
        "baseline_observation": monitor.baseline_observation(len(fresh)),
        "prior_observation_plan": monitor.observation_plan or {},
        "response_content": "", "tool_calls": [], "tool_results": [],
    }
    emit("async_monitor_intervention_freshness_started", {
        "candidate_evidence_through_sequence": reviewed_sequence,
        "fresh_first_sequence": fresh[0].get("archive_sequence"),
        "fresh_last_sequence": fresh[-1].get("archive_sequence"),
        "task_execution_blocked": False,
    })
    revised = str(monitor.review(packet) or "").strip()
    emit("async_monitor_intervention_freshness_completed", {
        "reviewed_through_sequence": latest_sequence,
        "candidate_withdrawn": not bool(revised),
        "candidate_replaced": bool(revised and revised != message),
        "task_execution_blocked": False,
    })
    return revised, latest_sequence, latest_turn, True


def _monitor_worker(monitor_kwargs: dict[str, Any], requests, responses, wake_event) -> None:
    from m0_deliberative_monitor import M0DeliberativeMonitor
    from research_runtime import JsonlEventSink, research_context

    values = dict(monitor_kwargs)
    event_path = values.pop("_runtime_event_path", None)
    identity = values.pop("_runtime_identity", {})
    archive_path = Path(values.pop("_runtime_boundary_archive"))
    adaptive_observation = bool(values.pop("_runtime_adaptive_observation", False))
    values["adaptive_review_planning_enabled"] = adaptive_observation
    monitor = M0DeliberativeMonitor(**values)
    archive_reader = _IncrementalArchiveReader(archive_path)
    reviewed_sequence, stored_reviewed_sequence = (
        _reconciled_review_cursor(archive_path)
        if adaptive_observation else (0, 0)
    )
    archived_sequence = _max_archive_sequence(_read_archive(archive_path))
    if stored_reviewed_sequence > archived_sequence:
        emit("adaptive_monitor_review_cursor_reset", {
            "stored_reviewed_sequence": stored_reviewed_sequence,
            "archive_max_sequence": archived_sequence,
            "reason": "cursor_ahead_of_current_archive",
            "task_execution_blocked": False,
        })
        reviewed_sequence = 0
        _save_review_cursor(archive_path, 0)
    pending_rows: list[dict[str, Any]] = []
    sink = JsonlEventSink(event_path) if event_path else None
    with research_context(identity, sink):
        if adaptive_observation and getattr(monitor, "m35_continuity_enabled", False):
            emit("m35_monitor_bootstrap_started", {
                "task_execution_blocked": False,
                "trajectory_events_in_bootstrap": 0,
            })
            try:
                result = monitor.bootstrap_task_state()
                emit("m35_monitor_bootstrap_ready", result)
            except BaseException as error:
                # Exit cleanly so the parent watchdog can restart a fresh
                # monitor. Task execution remains independent and all public
                # boundaries stay in the append-only archive.
                emit("m35_monitor_bootstrap_failed", {
                    "error_type": type(error).__name__,
                    "error": str(error)[:1000],
                    "traceback": traceback.format_exc()[-4000:],
                    "task_execution_blocked": False,
                })
                return
        last_deferred_signature = None
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

            appended, archive_reset = archive_reader.read_new()
            if archive_reset:
                pending_rows.clear()
                reviewed_sequence = 0
                if adaptive_observation:
                    _save_review_cursor(archive_path, 0)
            unseen = [row for row in appended
                      if str(row.get("archive_event_id", "")) not in monitor._observed_archive_ids]
            if unseen:
                monitor.observe_archived_boundaries(unseen)
            if adaptive_observation:
                pending_rows.extend(
                    row for row in appended
                    if int(row.get("archive_sequence") or 0) > reviewed_sequence
                )
                pending = pending_rows
            else:
                pending = unseen
            if not pending:
                wake_event.wait(0.5)
                wake_event.clear()
                continue

            plan = monitor.observation_plan or {}
            reason = (_adaptive_review_reason(
                pending, focused=monitor.attention_mode == "focused",
                review_after_turns=int(plan.get("review_after_turns", 20)),
                initial_calibration=not bool(monitor.decisions),
            ) if adaptive_observation else "legacy_any_delta")
            if reason is None:
                signature = (len(pending), pending[-1].get("archive_sequence"))
                if signature != last_deferred_signature:
                    emit("adaptive_monitor_review_deferred", {
                        "pending_boundaries": len(pending),
                        "latest_sequence": pending[-1].get("archive_sequence"),
                        "attention_mode": monitor.attention_mode,
                        "observation_plan": plan,
                    })
                    last_deferred_signature = signature
                wake_event.wait(0.5)
                wake_event.clear()
                continue
            last_deferred_signature = None

            # Archive ingestion and the first-look sensor are deterministic. The
            # task side still pushes no semantic packet; inside the autonomous
            # monitor process, unseen public boundaries become the same kind of
            # low-friction recent view a human gets before deciding whether to
            # investigate files, tests, diffs, or older history.
            baseline_observation = monitor.baseline_observation(len(pending))
            request_id = new_id("monitor_observation")
            latest_turn = max(int(row.get("internal_turn") or 0) for row in pending)
            wake_packet = {
                "archive_wake_only": True,
                "boundary": "autonomous_archive_observation",
                "internal_turn": latest_turn,
                "archive_delta": {
                    "new_boundaries": len(pending),
                    "first_sequence": pending[0].get("archive_sequence"),
                    "last_sequence": pending[-1].get("archive_sequence"),
                    "boundary_types": sorted({str(row.get("boundary", "")) for row in pending}),
                    "review_trigger": reason,
                },
                "baseline_observation": baseline_observation,
                "prior_observation_plan": plan,
                "response_content": "", "tool_calls": [], "tool_results": [],
            }
            responses.put({"kind": "started", "request_id": request_id,
                           "started_at": time.monotonic()})
            try:
                reviewed_through_sequence = int(
                    pending[-1].get("archive_sequence") or 0
                )
                (message, reviewed_through_sequence, reviewed_through_turn,
                 freshness_rechecked) = (
                    _review_with_one_freshness_pass(
                        monitor, archive_path, wake_packet,
                        reviewed_through_sequence,
                        archive_reader=archive_reader,
                        pending_rows=pending_rows,
                    )
                )
                # Publish before advancing the durable review cursor. A crash
                # between these operations may cause one safe re-review after
                # restart, but can never mark an undelivered correction as
                # consumed. Episode revisions deduplicate the at-least-once
                # delivery path in the parent runtime.
                responses.put({"kind": "boundary_result", "request_id": request_id,
                               "message": message, "internal_turn": reviewed_through_turn,
                               "reviewed_through_sequence": reviewed_through_sequence,
                               "freshness_rechecked": freshness_rechecked,
                               "delivery": dict(
                                   getattr(monitor, "last_intervention_delivery", None)
                                   or {}
                               )})
                if adaptive_observation:
                    reviewed_sequence = reviewed_through_sequence
                    pending_rows = [
                        row for row in pending_rows
                        if int(row.get("archive_sequence") or 0) > reviewed_sequence
                    ]
                    _save_review_cursor(
                        archive_path, reviewed_through_sequence
                    )
                    emit("adaptive_monitor_review_scheduled", {
                        "reviewed_through_sequence": reviewed_through_sequence,
                        "observation_plan": monitor.observation_plan,
                        "attention_mode": monitor.attention_mode,
                    })
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
        self._archive_sequence = _resume_archive(self.boundary_archive)
        self.process = None
        self.requests = None
        self.responses = None
        self.active: dict[str, Any] | None = None
        self.pending: dict[str, dict[str, Any]] = {}
        self.interventions: deque[dict[str, Any]] = deque()
        # Coalesce only candidates that carry no evidence newer than the last
        # delivered correction.  One task turn can expose both an intent and a
        # later tool result, so internal_turn alone is not a sufficient cursor.
        self.delivered_episode_turns: dict[str, int] = {}
        self.delivered_episode_sequences: dict[str, int] = {}
        self.completion_results: dict[str, dict[str, Any]] = {}
        self.retired_processes: deque[tuple[Any, float]] = deque()
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

    def _stop_worker(self, reason: str, *, wait: bool = True) -> None:
        process = self.process
        if process is not None and process.is_alive():
            process.terminate()
            if wait:
                process.join(timeout=3)
                if process.is_alive() and hasattr(process, "kill"):
                    process.kill()
                    process.join(timeout=2)
            else:
                self.retired_processes.append((process, time.monotonic()))
        emit("async_monitor_worker_stopped", {
            "generation": self.generation, "reason": reason,
            "exitcode": None if process is None else process.exitcode,
            "waited_for_exit": wait,
        })

    def _reap_retired_workers(self, *, force: bool = False) -> None:
        """Reap replaced workers without delaying ordinary task boundaries."""
        kept: deque[tuple[Any, float]] = deque()
        now = time.monotonic()
        for process, retired_at in self.retired_processes:
            process.join(timeout=0)
            if process.is_alive() and (force or now - retired_at > 3):
                if hasattr(process, "kill"):
                    process.kill()
                if force:
                    process.join(timeout=2)
                else:
                    process.join(timeout=0)
            if process.is_alive():
                kept.append((process, retired_at))
            elif hasattr(process, "close"):
                process.close()
        self.retired_processes = kept

    def _restart(self, reason: str) -> None:
        abandoned = list(self.pending)
        # Ordinary monitor recovery must not place process teardown on the task
        # Agent's synchronous boundary. Termination is requested immediately;
        # later watchdog polls reap the retired process without waiting.
        self._stop_worker(reason, wait=False)
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
            pending_item = self.pending.pop(request_id, None)
            if self.active and self.active.get("request_id") == request_id:
                self.active = None
            if result["kind"] == "boundary_result":
                message = str(result.get("message") or "").strip()
                if message:
                    delivery = result.get("delivery") or {}
                    candidate = {
                        "request_id": request_id, "message": message,
                        "internal_turn": result.get("internal_turn"),
                        "reviewed_through_sequence": result.get(
                            "reviewed_through_sequence"
                        ),
                        "freshness_rechecked": bool(result.get("freshness_rechecked")),
                        "episode_id": delivery.get("episode_id"),
                        "episode_revision": delivery.get("episode_revision"),
                        "intervention_signature": delivery.get(
                            "intervention_signature"
                        ),
                    }
                    if not self._enqueue_intervention(candidate):
                        continue
                    emit("async_monitor_intervention_ready", {
                        "request_id": request_id, "internal_turn": result.get("internal_turn"),
                        "message_characters": len(message),
                        "reviewed_through_sequence": result.get(
                            "reviewed_through_sequence"
                        ),
                        "freshness_rechecked": bool(result.get("freshness_rechecked")),
                        "episode_id": delivery.get("episode_id"),
                        "episode_revision": delivery.get("episode_revision"),
                    })
            elif result["kind"] == "error":
                emit("async_monitor_request_failed", result)
                if pending_item and pending_item.get("kind") == "completion":
                    self.completion_results[request_id] = {
                        "kind": "completion_result",
                        "decision": _completion_recovery_decision(
                            "MONITOR_COMPLETION_ERROR"
                        ).as_payload(),
                    }
            else:
                self.completion_results[request_id] = result

    def _enqueue_intervention(self, candidate: Mapping[str, Any]) -> bool:
        """Keep only the newest undelivered revision of one repair episode."""
        episode_id = str(candidate.get("episode_id") or "").strip()
        if not episode_id:
            self.interventions.append(dict(candidate))
            return True
        try:
            revision = int(candidate.get("episode_revision") or 0)
        except (TypeError, ValueError):
            revision = 0
        try:
            candidate_turn = int(candidate.get("internal_turn") or 0)
        except (TypeError, ValueError):
            candidate_turn = 0
        try:
            candidate_sequence = int(candidate.get("reviewed_through_sequence") or 0)
        except (TypeError, ValueError):
            candidate_sequence = 0
        delivered_turns = getattr(self, "delivered_episode_turns", {})
        delivered_turn = delivered_turns.get(episode_id)
        delivered_sequences = getattr(self, "delivered_episode_sequences", {})
        delivered_sequence = delivered_sequences.get(episode_id, 0)
        no_new_evidence = bool(
            delivered_turn is not None
            and (
                candidate_turn < delivered_turn
                or (
                    candidate_turn == delivered_turn
                    and candidate_sequence <= delivered_sequence
                )
            )
        )
        if no_new_evidence:
            emit("async_monitor_intervention_pre_uptake_coalesced", {
                "episode_id": episode_id,
                "candidate_revision": revision,
                "candidate_turn": candidate_turn,
                "last_delivered_turn": delivered_turn,
                "candidate_reviewed_through_sequence": candidate_sequence,
                "last_delivered_reviewed_through_sequence": delivered_sequence,
                "candidate_request_id": candidate.get("request_id"),
            })
            return False
        queued_values = list(self.interventions)
        newer = []
        for queued in queued_values:
            if str(queued.get("episode_id") or "") != episode_id:
                continue
            try:
                queued_revision = int(queued.get("episode_revision") or 0)
            except (TypeError, ValueError):
                queued_revision = 0
            if queued_revision > revision:
                newer.append(queued_revision)
        if newer:
            emit("async_monitor_intervention_stale_discarded", {
                "episode_id": episode_id,
                "candidate_revision": revision,
                "queued_revision": max(newer),
                "candidate_request_id": candidate.get("request_id"),
            })
            return False
        kept = deque()
        superseded = []
        for queued in queued_values:
            if str(queued.get("episode_id") or "") != episode_id:
                kept.append(queued)
                continue
            try:
                queued_revision = int(queued.get("episode_revision") or 0)
            except (TypeError, ValueError):
                queued_revision = 0
            superseded.append({
                "request_id": queued.get("request_id"),
                "episode_revision": queued_revision,
            })
        self.interventions = kept
        self.interventions.append(dict(candidate))
        if superseded:
            emit("async_monitor_interventions_superseded", {
                "episode_id": episode_id,
                "replacement_request_id": candidate.get("request_id"),
                "replacement_revision": revision,
                "superseded": superseded,
            })
        return True

    def _watchdog(self) -> None:
        self._reap_retired_workers()
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
            # Runtime identity is authoritative even if a compatibility caller
            # accidentally supplies similarly named packet fields.
            row = {**dict(packet), "archive_event_id": archive_id,
                   "archive_sequence": self._archive_sequence}
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
        if not hasattr(self, "delivered_episode_turns"):
            self.delivered_episode_turns = {}
        if not hasattr(self, "delivered_episode_sequences"):
            self.delivered_episode_sequences = {}
        for value in values:
            episode_id = str(value.get("episode_id") or "").strip()
            if not episode_id:
                continue
            try:
                turn = int(value.get("internal_turn") or 0)
            except (TypeError, ValueError):
                turn = 0
            self.delivered_episode_turns[episode_id] = max(
                turn, self.delivered_episode_turns.get(episode_id, 0)
            )
            try:
                sequence = int(value.get("reviewed_through_sequence") or 0)
            except (TypeError, ValueError):
                sequence = 0
            self.delivered_episode_sequences[episode_id] = max(
                sequence, self.delivered_episode_sequences.get(episode_id, 0)
            )
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
            emit("async_monitor_completion_recovery", {
                "request_id": request_id, "reason": "queue_full",
            })
            return _completion_recovery_decision("MONITOR_QUEUE_FULL")
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
        emit("async_monitor_completion_recovery", {
            "request_id": request_id, "reason": "bounded_wait_expired",
            "timeout_seconds": self.request_timeout,
        })
        return _completion_recovery_decision("MONITOR_TIMEOUT")

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
        self._reap_retired_workers(force=True)
