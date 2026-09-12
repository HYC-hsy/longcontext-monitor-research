"""Process-isolated runtime owned by Monitor Agent."""

from __future__ import annotations

import json
import multiprocessing as mp
import queue
import re
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class CompletionOutcome:
    allow: bool
    message: str = ""
    reason: str = ""
    incomplete: bool = False


def _append(path: Path, value: Mapping[str, Any]):
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(dict(value), ensure_ascii=False, default=str) + "\n")


def _synopsis(packet):
    content = str(packet.get("response_content") or "")
    matches = re.findall(r"<summary[^>]*>(.*?)</summary>", content, re.I | re.S)
    return (matches[-1].strip() if matches else content.strip())[:600]


def _coalesce_wake_command(commands, first, completion_is_active=None):
    """Keep the newest patrol wake while preserving control-boundary priority."""
    selected = None
    candidate = first
    while True:
        kind = candidate.get("kind")
        if kind == "close":
            return candidate
        if kind == "completion":
            if completion_is_active is None or completion_is_active(candidate):
                selected = candidate
        elif kind == "boundary" and (selected is None or selected.get("kind") != "completion"):
            selected = candidate
        try:
            candidate = commands.get_nowait()
        except queue.Empty:
            return selected


def _worker(config, commands, outputs):
    from .agent import MonitorAgent
    from .provider import MonitorProviderClient, ProviderRecoveryExhausted
    from .workspace import MonitorWorkspace

    try:
        client = MonitorProviderClient(config["config_name"], config["model_config"])
        if 'run_deadline_epoch' in config:
            client.recovery_deadline = time.monotonic() + max(
                0.0, config['run_deadline_epoch'] - time.time())
            client.recovery_stop = config['stop_event']
        workspace = MonitorWorkspace(
            config["evidence_root"], config["private_root"],
            task_mounts={"workspace": config["task_workspace"]},
        )
        history_path = Path(config["private_root"]) / "audit" / "provider_history.json"
        if history_path.is_file():
            client.restore_history(json.loads(history_path.read_text(encoding="utf-8")))
        monitor = MonitorAgent(client, workspace, config["max_review_turns"])
    except Exception as exc:
        outputs.put({"kind": "failure", "error": repr(exc), "phase": "startup"})
        return

    next_wake_turn = 1
    close_watch = False
    cursor = 0
    task_turn = 0
    receipt_offset = 0

    def completion_is_active(command):
        active = config.get("active_completion")
        return active is None or active.value == command.get("generation")

    def current_completion():
        active = config["active_completion"]
        with active.get_lock():
            generation = active.value
            if not generation:
                return None
            return {"generation": generation, "request_id": f"completion-{generation}",
                    "cursor": config["completion_cursor"].value}

    monitor.completion_state = current_completion
    hybrid_control = bool(config['model_config'].get('monitor_hybrid_control', False))
    if hybrid_control:
        def task_control(operation, **arguments):
            outputs.put({'kind': 'task_control', 'operation': operation, **arguments})
            return {'status': 'queued', 'operation': operation,
                    'receipt_path': 'monitor/task_control.json',
                    'note': 'Requested, not proof the task has stopped. Lease expiry resumes execution.'}
        monitor.task_control_callback = task_control

    def review(context, completion=False, request_id=None):
        nonlocal next_wake_turn, close_watch, receipt_offset
        submitted = False

        def send_now(message):
            nonlocal submitted, close_watch, next_wake_turn
            delivery_id = uuid.uuid4().hex
            if completion and not submitted:
                delivery_id = request_id
                outputs.put({"kind": "completion", "decision": "continue", "cursor": cursor,
                             "request_id": request_id, "message": message})
            else:
                outputs.put({"kind": "intervention", "cursor": cursor,
                             "request_id": delivery_id, "message": message})
            submitted = True
            close_watch = True
            next_wake_turn = task_turn + 1
            return {"submission_id": delivery_id, "delivery": "queued"}

        if config["model_config"].get("monitor_live_intervention", True):
            monitor.intervention_callback = send_now
            # Only actual review-ending actions define compaction boundaries.
            client.CONTROL_ACTIONS = {"wait", "allow_complete"}
        try:
            next_receipt_offset = receipt_offset
            receipt_path = Path(config["private_root"]) / "delivery_feedback.jsonl"
            if receipt_path.exists():
                with receipt_path.open("rb") as stream:
                    stream.seek(receipt_offset)
                    feedback = stream.read()
                # The pump writes complete lines; retry a partial trailing line next wake.
                complete = feedback.rfind(b"\n") + 1
                if complete:
                    context += "\nRuntime feedback on prior actions (handoff is not proof of uptake):\n" + feedback[:complete].decode("utf-8")
                    next_receipt_offset += complete
            action = monitor.review(context, completion_pending=completion)
            receipt_offset = next_receipt_offset
        except Exception as exc:
            if hybrid_control:
                outputs.put({'kind': 'task_control', 'operation': 'resume', 'cause': 'review_failure'})
            outputs.put({"kind": "failure", "error": repr(exc), "completion": completion and not submitted,
                         "request_id": request_id})
            # A terminal transport recovery must not silently restart via the
            # queued patrol/completion commands after the parent has failed it.
            return not isinstance(exc, ProviderRecoveryExhausted)
        if action.kind == "wait":
            if hybrid_control:
                outputs.put({'kind': 'task_control', 'operation': 'resume', 'cause': 'monitor_wait'})
            close_watch = False
            next_wake_turn = task_turn + max(1, int(action.payload["after_turns"]))
        elif action.kind == "intervene":
            close_watch = True
            next_wake_turn = task_turn + 1
            if not completion:
                outputs.put({
                    "kind": "intervention", "message": action.payload["message"],
                    "cursor": cursor, "request_id": uuid.uuid4().hex,
                })
        elif action.kind == "allow_complete":
            approval_id = action.payload.get("request_id", request_id)
            outputs.put({"kind": "completion", "decision": "allow", "cursor": cursor,
                         "request_id": approval_id})
            # Delivery, not the model's proposal, determines whether this task ended.
            # Do not consume patrol backlog while the parent resolves this approval.
            while not config['stop_event'].is_set():
                try:
                    receipt = config['completion_receipts'].get(timeout=0.1)
                except queue.Empty:
                    continue
                if receipt['request_id'] != approval_id:
                    continue
                if not receipt['accepted']:
                    return True  # A stale approval must not disable a live monitor.
                # Stay alive until normal close so the completion waiter does not
                # mistake an immediately exited worker for an unavailable monitor.
                config['stop_event'].wait()
                return False
            return False
        if completion and not submitted and action.kind == "intervene":
            outputs.put({
                "kind": "completion", "decision": "continue", "cursor": cursor,
                "request_id": request_id,
                "message": action.payload["message"],
            })
        return True

    if not review(
        "Turn-zero initialization. Read task/original_task.txt. Use task/synopsis.jsonl for chronological "
        "navigation, task/public_events.jsonl for original public events, and task/workspace/ for live tests, "
        "code, diffs, and artifacts. The Task Agent can read its original task copy at "
        f"{config['task_original_path']}. task/ paths are your virtual paths, not its filesystem paths. "
        "Establish your task understanding, inspect available progress, and choose your next action. "
        "Initialization does not require silence if a material discrepancy is already supported."
    ):
        return
    outputs.put({"kind": "ready"})
    while True:
        command = _coalesce_wake_command(commands, commands.get(), completion_is_active)
        if command is None:
            continue
        kind = command.get("kind")
        if kind == "close": return
        cursor = int(command.get("cursor") or cursor)
        task_turn = int(command.get("task_turn") or task_turn)
        if kind == "boundary" and (close_watch or task_turn >= next_wake_turn):
            if not review(
                f"Public task cursor advanced through {cursor}. Continue from your existing history, inspect "
                "new synopsis rows, and retrieve original evidence wherever it can change your decision."
            ):
                return
        elif kind == "completion" and completion_is_active(command):
            if not review(
                f"The Task Agent yielded control without a tool call at cursor {cursor}. Read its actual "
                "message in the public evidence: it may claim completion, ask for clarification, or report "
                "a blocker. Judge its meaning yourself. Answer missing information or correct drift with "
                "intervene; use allow_complete only if the task is actually complete. A clarification "
                "request is not itself a false completion claim.", completion=True,
                request_id=command["request_id"],
            ):
                return


class MonitorRuntime:
    def __init__(self, *, public_task, task_workspace, artifact_dir, config_name,
                 model_config, interrupt_callback, max_review_turns=20,
                 completion_timeout=300, process_factory=None, worker_target=None,
                 interrupt_pending=None, run_timeout_seconds=10000, run_deadline_epoch=None,
                 pause_callback=None, resume_callback=None):
        self._hybrid_control = model_config.get('monitor_hybrid_control', False)
        if type(self._hybrid_control) is not bool:
            raise ValueError('monitor_hybrid_control must be boolean')
        if self._hybrid_control and (pause_callback is None or resume_callback is None):
            raise ValueError('Hybrid control requires host pause and resume callbacks')
        self._pause_callback, self._resume_callback = pause_callback, resume_callback
        self.artifact_dir = Path(artifact_dir).resolve()
        task_workspace = Path(task_workspace).resolve()
        if self.artifact_dir == task_workspace or task_workspace in self.artifact_dir.parents:
            raise ValueError("Monitor artifacts must be outside the supervised task workspace")
        self.evidence_root = self.artifact_dir / "task_evidence"
        self.private_root = self.artifact_dir / "monitor_private"
        self.evidence_root.mkdir(parents=True, exist_ok=True)
        self.private_root.mkdir(parents=True, exist_ok=True)
        (self.evidence_root / "original_task.txt").write_text(public_task, encoding="utf-8")
        self.task_original_path = task_workspace / f".monitor_original_task_{uuid.uuid4().hex}.txt"
        with self.task_original_path.open("x", encoding="utf-8") as stream:
            stream.write(public_task)
        self.synopsis_path = self.evidence_root / "synopsis.jsonl"
        self.events_path = self.evidence_root / "public_events.jsonl"
        self._archive_lock = threading.Lock()
        self._receipt_lock = threading.Lock()
        self._sequence = 0
        self._interrupt_callback = interrupt_callback
        self._interrupt_pending = interrupt_pending or (lambda: False)
        self._completion_timeout = max(1.0, float(completion_timeout))
        remaining = (float(run_deadline_epoch) - time.time() if run_deadline_epoch is not None
                     else float(run_timeout_seconds))
        self._run_deadline = time.monotonic() + max(0.0, remaining)
        self._context = mp.get_context("spawn")
        self._stop_event = self._context.Event()
        self._commands = self._context.Queue()
        self._outputs = self._context.Queue()
        self._completion_receipts = self._context.Queue()
        self._pending = {}
        self._pending_lock = threading.Lock()
        self._completion_generation = 0
        self._active_completion = self._context.Value('q', 0)
        self._completion_cursor = self._context.Value('q', 0)
        self._closed = threading.Event()
        process = process_factory or self._context.Process
        self._process = process(target=worker_target or _worker, args=({
            "config_name": config_name, "model_config": dict(model_config),
            "evidence_root": str(self.evidence_root), "private_root": str(self.private_root),
            "task_workspace": str(task_workspace), "max_review_turns": int(max_review_turns),
            "task_original_path": str(self.task_original_path),
            "active_completion": self._active_completion,
            "completion_cursor": self._completion_cursor,
            "run_deadline_epoch": time.time() + max(0.0, self._run_deadline - time.monotonic()),
            "stop_event": self._stop_event,
            "completion_receipts": self._completion_receipts,
        }, self._commands, self._outputs), daemon=True)
        self._process.start()
        self._pump = threading.Thread(target=self._pump_outputs, daemon=True, name="monitor-output")
        self._pump.start()

    def _archive(self, packet):
        with self._archive_lock:
            self._sequence += 1
            sequence = self._sequence
            raw = dict(packet, archive_sequence=sequence)
            _append(self.events_path, raw)
            calls = raw.get("tool_calls") or []
            _append(self.synopsis_path, {
                "cursor": sequence, "task_turn": raw.get("internal_turn"),
                "boundary": raw.get("boundary"), "intent": _synopsis(raw),
                "tool_names": [str(call.get("tool_name") or "") for call in calls],
                "outcome_available": bool(raw.get("tool_results")),
                "raw_event": f"public_events.jsonl#{sequence}",
            })
        return sequence

    def archive_boundary(self, packet):
        sequence = self._archive(packet)
        self._commands.put({
            "kind": "boundary", "cursor": sequence,
            "task_turn": int(packet.get("internal_turn") or 0),
        })
        return True

    def _pump_outputs(self):
        while not self._closed.is_set():
            try: value = self._outputs.get(timeout=0.1)
            except queue.Empty: continue
            except (OSError, EOFError):
                if self._closed.is_set():
                    return
                raise
            kind = value.get("kind")
            if kind == 'task_control':
                try:
                    if not self._hybrid_control:
                        raise ValueError('Hybrid control is disabled')
                    if value.get('operation') == 'pause':
                        receipt = self._pause_callback(value['reason'], value.get('seconds', 120))
                    elif value.get('operation') == 'resume':
                        receipt = self._resume_callback()
                    else:
                        raise ValueError('Unknown control operation')
                    value = dict(value, receipt=receipt, delivery='handed_to_host', timestamp=time.time())
                except Exception as exc:
                    value = dict(value, delivery='failed', error=repr(exc), timestamp=time.time())
                _append(self.private_root / 'delivery_feedback.jsonl', value)
                target = self.private_root / 'task_control.json'
                temporary = target.with_suffix('.pending')
                temporary.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
                temporary.replace(target)
            elif kind == "intervention":
                try:
                    receipt = self._interrupt_callback(value["message"])
                    if self._hybrid_control:
                        self._resume_callback()
                    value = dict(value, delivery="handed_to_task_interrupt_interface", receipt=str(receipt))
                    # The correction has one owner: the Task Agent's interrupt mailbox.
                    # Wake any completion wait, but do not inject the message a second time.
                    with self._pending_lock:
                        resumed = list(self._pending)
                        for request_id in resumed:
                            pending = self._pending.pop(request_id)
                            pending.put({"decision": "continue", "reason": "interrupted",
                                         "message": "Continue with the pending monitor correction."})
                        if resumed:
                            self._active_completion.value = 0
                        value = dict(value, resumed_completion_requests=resumed)
                except Exception as exc:
                    value = dict(value, delivery="failed", error=repr(exc))
            elif kind == "completion" or (kind == "failure" and value.get("completion") is True):
                if self._hybrid_control:
                    self._resume_callback()
                with self._pending_lock:
                    pending = self._pending.pop(value.get("request_id"), None)
                    if pending is not None:
                        self._active_completion.value = 0
                        pending.put(value)
                        value = dict(value, delivery="handed_to_completion_boundary")
                    else:
                        value = dict(value, delivery="archived_late_or_unmatched")
                if kind == 'completion' and value.get('decision') == 'allow':
                    self._completion_receipts.put({
                        'request_id': value.get('request_id'),
                        'accepted': pending is not None,
                    })
            elif kind == "failure":
                if self._hybrid_control:
                    self._resume_callback()
                # An ordinary review may fail while a root handoff is waiting.
                with self._pending_lock:
                    for pending in self._pending.values():
                        pending.put(value)
                    if self._pending:
                        self._pending.clear()
                        self._active_completion.value = 0
            self._append_receipt(value)
            if kind in {"intervention", "completion"}:
                _append(self.private_root / "delivery_feedback.jsonl", value)

    def request_completion(self, public_event=None) -> CompletionOutcome:
        if not self._process.is_alive():
            return self._incomplete("unavailable")
        cursor = self._archive(public_event) if public_event else self._sequence
        pending = queue.Queue()
        with self._pending_lock:
            # Covers an interrupt delivered immediately before registration as well
            # as the in-flight wait case handled by the output pump.
            if self._interrupt_pending():
                return CompletionOutcome(False, "Continue with the pending monitor correction.", "interrupted")
            if self._pending:
                raise RuntimeError("Only one Task Agent completion may be pending")
            self._completion_generation += 1
            generation = self._completion_generation
            request_id = f"completion-{generation}"
            with self._active_completion.get_lock():
                self._completion_cursor.value = cursor
                self._active_completion.value = generation
            self._pending[request_id] = pending
        self._commands.put({"kind": "completion", "cursor": cursor, "request_id": request_id,
                            "generation": generation,
                            "task_turn": int((public_event or {}).get("internal_turn") or 0)})
        delayed = False
        warning_at = time.monotonic() + self._completion_timeout
        try:
            while True:
                remaining = self._run_deadline - time.monotonic()
                if remaining <= 0:
                    return self._incomplete("run_budget_exhausted", request_id)
                if self._closed.is_set() or not self._process.is_alive():
                    return self._incomplete("unavailable", request_id)
                try:
                    value = pending.get(timeout=min(0.2, remaining))
                    break
                except queue.Empty:
                    if not delayed and time.monotonic() >= warning_at:
                        self._append_receipt({
                            "kind": "completion_delayed", "request_id": request_id,
                            "timestamp": time.time(), "action": "keep_same_review_pending"})
                        delayed = True
        finally:
            with self._pending_lock:
                self._pending.pop(request_id, None)
                if self._active_completion.value == generation:
                    self._active_completion.value = 0
        if value.get("decision") == "allow": return CompletionOutcome(True, reason="monitor_allowed")
        if value.get("decision") == "continue" and value.get("message"):
            return CompletionOutcome(False, value["message"],
                                     value.get("reason") or "monitor_correction")
        return self._incomplete("review_failed", request_id)

    def _incomplete(self, reason, request_id=None):
        record = {
            "kind": "completion_incomplete", "reason": reason,
            "request_id": request_id, "timestamp": time.time()}
        self._append_receipt(record)
        marker = self.artifact_dir / "completion_incomplete.json"
        temporary = marker.with_suffix('.pending')
        temporary.write_text(json.dumps(record), encoding='utf-8')
        temporary.replace(marker)
        return CompletionOutcome(False, "Completion review unfinished: " + reason,
                                 reason, incomplete=True)

    def _append_receipt(self, record):
        # Pump and completion waiter share this file, not the task event writer.
        with self._receipt_lock:
            _append(self.artifact_dir / 'runtime_receipts.jsonl', record)

    def close(self):
        self._closed.set()
        if self._hybrid_control:
            self._resume_callback()
        self._stop_event.set()
        self._commands.put({"kind": "close"})
        self._process.join(timeout=3)
        if self._process.is_alive():
            self._process.terminate(); self._process.join(timeout=1)
        self._pump.join(timeout=1)
        if self._hybrid_control:
            self._resume_callback()
