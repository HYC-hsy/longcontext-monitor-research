"""Process-isolated runtime owned by Monitor Agent."""

from __future__ import annotations

import json
import multiprocessing as mp
import queue
import hashlib
import shutil
import tempfile
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
    from .probe import IndependentVerifier, ProbeConfig
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
        checkpoint_root = Path(config["private_root"]) / "audit" / "live_checkpoints"
        checkpoint_root.mkdir(parents=True, exist_ok=True)
        checkpoint_sequence = len(list(checkpoint_root.glob("checkpoint-*")))

        def capture_root_request(snapshot):
            """Persist one complete root-handoff request before transport."""
            nonlocal checkpoint_sequence
            checkpoint_sequence += 1
            final = checkpoint_root / f"checkpoint-{checkpoint_sequence:04d}"
            temporary = Path(tempfile.mkdtemp(prefix=".capture-", dir=checkpoint_root))
            try:
                events = workspace.evidence_root / "public_events.jsonl"
                lines = events.read_text(encoding="utf-8").splitlines() if events.exists() else []
                cutoff = int(config.get("completion_cursor").value)
                parsed = []
                for index, line in enumerate(lines):
                    row = json.loads(line)
                    event_cursor = row.get("archive_sequence", row.get("cursor"))
                    if type(event_cursor) is not int:
                        raise ValueError(f"event {index} has no valid cursor")
                    if event_cursor > cutoff:
                        raise ValueError("events advanced while capturing root boundary")
                    parsed.append(row)
                if not parsed or parsed[-1].get("archive_sequence", parsed[-1].get("cursor")) != cutoff:
                    raise ValueError("event prefix does not end at root boundary cursor")
                visible_events = temporary / "events" / "public_events.jsonl"
                visible_events.parent.mkdir(parents=True, exist_ok=True)
                visible_events.write_text("\n".join(
                    json.dumps(row, ensure_ascii=False) for row in parsed) + "\n", encoding="utf-8")
                synopsis = workspace.evidence_root / "synopsis.jsonl"
                if synopsis.exists():
                    shutil.copy2(synopsis, temporary / "events" / "synopsis.jsonl")
                request_path = temporary / "request.json"
                request_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
                workspace.refresh_snapshot()
                shutil.copytree(workspace.snapshot_root, temporary / "workspace")
                private_state = temporary / "private_state"
                private_state.mkdir()
                for child in Path(config["private_root"]).iterdir():
                    if child.name in {"audit", ".task_view"}:
                        continue
                    destination = private_state / child.name
                    shutil.copytree(child, destination) if child.is_dir() else shutil.copy2(child, destination)
                manifest = {}
                for root in (temporary / "events", temporary / "workspace", temporary / "private_state"):
                    for path in root.rglob("*"):
                        if path.is_file():
                            manifest[str(path.relative_to(temporary)).replace("\\", "/")] = hashlib.sha256(path.read_bytes()).hexdigest()
                (temporary / "identity.json").write_text(json.dumps({
                    "task_id": config.get("task_id"), "config_name": config.get("config_name"),
                    "review_id": snapshot.get("review_id"),
                    "request_sequence": snapshot.get("request_sequence"),
                    "cursor": cutoff, "task_turn": int(config.get("latest_task_turn").value),
                    "cursor_field": "archive_sequence" if parsed and "archive_sequence" in parsed[-1] else "cursor",
                    "captured_at": time.time(), "source": "live_request_before_transport",
                    "history_source_kind": "provider_snapshot",
                }, ensure_ascii=False, indent=2), encoding="utf-8")
                (temporary / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
                (temporary / "complete.json").write_text(json.dumps({
                    "status": "complete", "cursor": cutoff, "files": len(manifest),
                }, indent=2), encoding="utf-8")
                temporary.replace(final)
            except Exception as exc:
                shutil.rmtree(temporary, ignore_errors=True)
                client._progress("root_checkpoint_invalid", error_type=type(exc).__name__, error=str(exc))
                raise

        client.request_assembly_callback = capture_root_request
        history_path = Path(config["private_root"]) / "audit" / "provider_history.json"
        if history_path.is_file():
            client.restore_history(json.loads(history_path.read_text(encoding="utf-8")))
        probe_total = int(config.get("independent_probe_total_requests", 0) or 0)
        probe_per_call = int(config.get("independent_probe_max_requests", 3) or 3)
        probe_lock = threading.Lock()

        def independent_check(question, paths):
            nonlocal probe_total
            with probe_lock:
                if probe_total <= 0:
                    return {"status": "budget_exhausted", "outcome": None,
                            "conclusion": None, "limitation": "independent_probe_budget_exhausted",
                            "requests": 0}
                allowance = min(probe_per_call, probe_total)
            probe = IndependentVerifier.from_provider_config(
                config["config_name"], config["model_config"], workspace,
                ProbeConfig(mode="direct", source_paths=("task/original_task.txt",),
                            evidence_paths=tuple(paths), max_requests=allowance, max_turns=8),
                audit=lambda event, **fields: monitor_probe_audit(event, **fields),
            )
            # A child request must obey the same stop/deadline as its parent;
            # otherwise a failed or cancelled probe can outlive supervision.
            probe.client.recovery_deadline = getattr(client, "recovery_deadline", None)
            probe.client.recovery_stop = getattr(client, "recovery_stop", config["stop_event"])
            result = None
            telemetry = {}
            error = None
            try:
                result = probe.run(question)
            except Exception as exc:
                error = repr(exc)
            finally:
                telemetry = probe.client.drain_telemetry()
                used = int(probe.logical_calls)
                with probe_lock:
                    probe_total = max(0, probe_total - used)
                    remaining = probe_total
                refs = list(probe.evidence_refs)
                changed = []
                for ref in refs:
                    try:
                        current = workspace.read_text(ref["path"], 1, 1, max_chars=1)
                        if current.get("sha256") != ref.get("sha256"):
                            changed.append({"path": ref["path"],
                                            "before": ref.get("sha256"),
                                            "after": current.get("sha256")})
                    except Exception as exc:
                        changed.append({"path": ref.get("path"),
                                        "status": "unavailable", "error": type(exc).__name__})
                payload = {
                    "status": result.status if result is not None else "error",
                    "outcome": result.outcome if result is not None else None,
                    "conclusion": result.conclusion if result is not None else None,
                    "limitation": result.limitation if result is not None else error,
                    "requests": used, "remaining_requests": remaining,
                    "usage": telemetry.get("usage", []),
                    "evidence_refs": refs, "evidence_changed": changed,
                }
                monitor_probe_audit("independent_probe_finished", question=question,
                                    paths=list(paths), **payload)
            return payload

        def monitor_probe_audit(event, **fields):
            # Keep probe evidence in the same monitor audit stream, without
            # placing the child dialogue into the parent History.
            try:
                monitor._progress(event, **fields)
            except Exception:
                pass

        monitor = MonitorAgent(client, workspace, config["max_review_turns"],
                               stop_event=config['stop_event'],
                               independent_check=(independent_check if probe_total > 0 else None))
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

    def review(context, completion=False, request_id=None):
        nonlocal next_wake_turn, close_watch, receipt_offset
        submitted = False
        wake_receipts = config.get('wake_receipts')
        if not close_watch and not completion and wake_receipts is not None:
            identity = uuid.uuid4().hex
            outputs.put({'kind': 'review_wake', 'identity': identity})
            # The host installs the execution barrier before any review LLM.
            while not config['stop_event'].is_set():
                try:
                    receipt = wake_receipts.get(timeout=.1)
                except queue.Empty:
                    continue
                if receipt['identity'] == identity:
                    if not receipt['accepted']:
                        outputs.put({'kind': 'failure', 'error': 'Wake barrier failed'})
                        return False
                    break
            else:
                return False

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
            client.checkpoint_kind = "root_handoff" if completion else "ordinary"
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
            from .provider import failure_chain
            outputs.put({"kind": "failure", "error": repr(exc), "completion": completion and not submitted,
                         "request_id": request_id, "cause_chain": failure_chain(exc),
                         "failed_at": time.time()})
            # A terminal transport recovery must not silently restart via the
            # queued patrol/completion commands after the parent has failed it.
            return not isinstance(exc, ProviderRecoveryExhausted)
        finally:
            client.checkpoint_kind = None
        if action.kind == "wait":
            release_wake = close_watch or wake_receipts is not None
            close_watch = action.payload.get('mode', 'follow') == 'follow'
            # Silence starts now, not when this potentially long review began.
            # This clock conveys progress only; it does not mark evidence read.
            clock = config.get('latest_task_turn')
            current_turn = max(task_turn, clock.value) if clock is not None else task_turn
            next_wake_turn = current_turn + max(1, int(action.payload["after_turns"]))
            if release_wake:
                outputs.put({'kind': 'review_silent', 'from_turn': current_turn,
                             'next_wake_turn': next_wake_turn,
                             'mode': 'follow' if close_watch else 'patrol'})
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
        "code, diffs, and artifacts. "
        f"Task-side original requirements location: {config.get('task_original_path') or 'not supplied by the host'}. "
        "task/ paths are your virtual paths, not its filesystem paths. "
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
        if kind == "boundary" and task_turn >= next_wake_turn:
            if not review(
                f"Public task cursor advanced through {cursor}. Continue from your existing history, inspect "
                "new synopsis rows, and retrieve original evidence wherever it can change your decision."
            ):
                return
        elif kind == "completion" and completion_is_active(command):
            if not review(
                f"The host requested a root handoff review at cursor {cursor}. Read the Task Agent's actual "
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
                 correction_begin=None, correction_end=None, task_original_path=None, task_id,
                 independent_probe_total_requests=0, independent_probe_max_requests=3):
        if model_config.get('monitor_hybrid_control', False):
            raise ValueError('Model-requested hybrid pause is retired')
        self.artifact_dir = Path(artifact_dir).resolve()
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError('An explicit non-empty task_id is required')
        task_workspace = Path(task_workspace).resolve()
        if self.artifact_dir == task_workspace or task_workspace in self.artifact_dir.parents:
            raise ValueError("Monitor artifacts must be outside the supervised task workspace")
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        identity = {'task_id': task_id, 'workspace': str(task_workspace),
                    'task_sha256': hashlib.sha256(public_task.encode('utf-8')).hexdigest()}
        identity_path = self.artifact_dir / 'task_identity.json'
        if identity_path.exists():
            if json.loads(identity_path.read_text(encoding='utf-8')) != identity:
                raise ValueError('Monitor history belongs to a different task or workspace')
        else:
            if any(self.artifact_dir.iterdir()):
                raise ValueError('Existing monitor artifacts have no verified task identity')
            with identity_path.open('x', encoding='utf-8') as stream:
                json.dump(identity, stream)
        self.evidence_root = self.artifact_dir / "task_evidence"
        self.private_root = self.artifact_dir / "monitor_private"
        self.evidence_root.mkdir(parents=True, exist_ok=True)
        self.private_root.mkdir(parents=True, exist_ok=True)
        (self.evidence_root / "original_task.txt").write_text(public_task, encoding="utf-8")
        self.task_original_path = task_original_path
        self.synopsis_path = self.evidence_root / "synopsis.jsonl"
        self.events_path = self.evidence_root / "public_events.jsonl"
        self._archive_lock = threading.Lock()
        self._receipt_lock = threading.Lock()
        self._sequence = 0
        if self.events_path.exists():
            with self.events_path.open(encoding='utf-8') as stream:
                for line in stream:
                    self._sequence = max(self._sequence, int(json.loads(line)['archive_sequence']))
        self._interrupt_callback = interrupt_callback
        if (correction_begin is None) != (correction_end is None):
            raise ValueError('Correction lifecycle requires both host callbacks')
        self._correction_begin = correction_begin
        self._correction_end = correction_end
        self._correction_identity = None
        self._correction_deadline = 0.0
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
        self._wake_receipts = self._context.Queue() if correction_begin is not None else None
        self._pending = {}
        self._pending_lock = threading.Lock()
        self._completion_generation = 0
        self._active_completion = self._context.Value('q', 0)
        self._completion_cursor = self._context.Value('q', 0)
        self._latest_task_turn = self._context.Value('q', 0)
        self._closed = threading.Event()
        process = process_factory or self._context.Process
        self._process = process(target=worker_target or _worker, args=({
            "config_name": config_name, "model_config": dict(model_config), "task_id": task_id,
            "evidence_root": str(self.evidence_root), "private_root": str(self.private_root),
            "task_workspace": str(task_workspace), "max_review_turns": int(max_review_turns),
            "task_original_path": self.task_original_path,
            "active_completion": self._active_completion,
            "completion_cursor": self._completion_cursor,
            "latest_task_turn": self._latest_task_turn,
            "run_deadline_epoch": time.time() + max(0.0, self._run_deadline - time.monotonic()),
            "stop_event": self._stop_event,
            "independent_probe_total_requests": int(independent_probe_total_requests),
            "independent_probe_max_requests": int(independent_probe_max_requests),
            "completion_receipts": self._completion_receipts,
            "wake_receipts": self._wake_receipts,
        }, self._commands, self._outputs), daemon=True)
        try:
            if self._correction_begin:
                self._correction_identity = 'initialization'
                self._correction_deadline = time.monotonic() + 300
                self._correction_begin('initialization')
            self._process.start()
        except Exception:
            self._finish_correction()
            raise
        self._pump = threading.Thread(target=self._pump_outputs, daemon=True, name="monitor-output")
        self._pump.start()

    def _archive(self, packet):
        with self._archive_lock:
            self._sequence += 1
            sequence = self._sequence
            raw = dict(packet, archive_sequence=sequence, archived_at=time.time())
            _append(self.events_path, raw)
            with self._latest_task_turn.get_lock():
                self._latest_task_turn.value = max(
                    self._latest_task_turn.value, int(raw.get('task_turn') or 0))
            calls = raw.get("tool_calls") or []
            _append(self.synopsis_path, {
                "cursor": sequence, "task_turn": raw.get("task_turn"),
                "boundary": raw.get("boundary"), "intent": raw.get('synopsis', raw.get('text', '')),
                "tool_names": [str(call.get("name") or "") for call in calls],
                "outcome_available": bool(raw.get("tool_results")),
                "raw_event": f"public_events.jsonl#{sequence}",
            })
        return sequence

    def archive_boundary(self, packet):
        sequence = self._archive(packet)
        self._commands.put({
            "kind": "boundary", "cursor": sequence,
            "task_turn": int(packet.get("task_turn") or 0),
        })
        return True

    def _pump_outputs(self):
        while not self._closed.is_set():
            if (self._correction_identity is not None and
                    time.monotonic() >= self._correction_deadline):
                self._append_receipt({'kind': 'wake_review_timeout',
                                      'identity': self._correction_identity})
                self._finish_correction()
                self._stop_event.set()
            try: value = self._outputs.get(timeout=0.1)
            except queue.Empty:
                if not self._process.is_alive():
                    self._finish_correction()
                continue
            except (OSError, EOFError):
                if self._closed.is_set():
                    return
                raise
            kind = value.get("kind")
            if kind == 'review_wake':
                accepted = False
                try:
                    if self._correction_begin:
                        self._correction_identity = value['identity']
                        self._correction_deadline = time.monotonic() + 300
                        value = dict(value, receipt=self._correction_begin(value['identity']))
                    accepted = True
                except Exception as exc:
                    self._finish_correction()
                    value = dict(value, error=repr(exc))
                finally:
                    if self._wake_receipts is not None:
                        self._wake_receipts.put({'identity': value['identity'], 'accepted': accepted})
            elif kind == 'review_silent':
                self._finish_correction()
            elif kind == "intervention":
                try:
                    receipt = self._interrupt_callback(value["message"])
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
                finally:
                    self._finish_correction()
            elif kind == "completion" or (kind == "failure" and value.get("completion") is True):
                self._finish_correction()
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
                self._finish_correction()
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
                            "task_turn": int((public_event or {}).get("task_turn") or 0)})
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

    def _finish_correction(self, identity=None):
        if identity is None or identity == self._correction_identity:
            if self._correction_end:
                self._correction_end(identity)
            self._correction_identity = None

    def close(self):
        self._closed.set()
        self._finish_correction()
        self._stop_event.set()
        self._commands.put({"kind": "close"})
        self._process.join(timeout=3)
        if self._process.is_alive():
            self._process.terminate(); self._process.join(timeout=1)
        self._pump.join(timeout=1)
