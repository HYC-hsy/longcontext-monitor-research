"""Process-isolated runtime owned by Monitor Agent."""

from __future__ import annotations

import json
import multiprocessing as mp
import os
import queue
import hashlib
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .eis_v0 import append_index as append_eis_index


ASE_CONTROL_ACTIONS = frozenset({
    'wait', 'allow_complete', 'intervene', 'local_intervened', 'root_intervened',
    'root_reestimate',
})
TASK_MODEL_FEEDBACK_BOUNDARIES = frozenset({'post_model_pre_tool', 'task_control_handoff'})


def _remaining_root_turns(remaining, action):
    """Charge every internal subreview to the same root handoff ceiling."""
    used = (action.payload['prior_model_turns'] if action.kind == 'root_route' else
            action.payload['model_turns_used_in_this_subreview'])
    if type(used) is not int or used < 0:
        raise ValueError('Invalid root subreview model-turn count')
    return remaining - used


def _root_turn_ceiling(config, ordinary_limit):
    """Use the ordinary ceiling unless this run explicitly sets a root-only one."""
    root_limit = config.get('root_max_review_turns')
    if root_limit is None:
        return ordinary_limit
    if type(root_limit) is not int or root_limit < 1:
        raise ValueError('root_max_review_turns must be a positive integer')
    return root_limit


class ASEFeedbackBarrier:
    """An intervention cannot be followed by control before a newer Task model event."""

    def __init__(self, audit):
        self.audit = audit
        self.pending = None

    def start(self, *, task_turn, cursor, action_locator=None, submission_id=None):
        self.pending = {'submitted_task_turn': int(task_turn), 'submitted_cursor': int(cursor),
                        'intervention_locator': action_locator, 'submission_id': submission_id}
        self.audit('ase_feedback_barrier_started', **self.pending,
                   current_task_turn=int(task_turn), current_cursor=int(cursor))

    def permits(self, *, task_turn, cursor, model_feedback_turn, model_feedback_cursor):
        if self.pending is None:
            return True
        current = dict(current_task_turn=int(task_turn), current_cursor=int(cursor))
        if (int(model_feedback_turn) > self.pending['submitted_task_turn']
                and int(model_feedback_cursor) > self.pending['submitted_cursor']
                and int(task_turn) > self.pending['submitted_task_turn']
                and int(cursor) >= int(model_feedback_cursor)):
            self.audit('ase_feedback_barrier_satisfied', **self.pending, **current,
                       model_feedback_turn=int(model_feedback_turn),
                       model_feedback_cursor=int(model_feedback_cursor))
            self.pending = None
            return True
        self.audit('ase_feedback_barrier_blocked_wake', **self.pending, **current,
                   model_feedback_turn=int(model_feedback_turn),
                   model_feedback_cursor=int(model_feedback_cursor))
        return False


@dataclass(frozen=True)
class CompletionOutcome:
    allow: bool
    message: str = ""
    reason: str = ""
    incomplete: bool = False


def _append(path: Path, value: Mapping[str, Any]):
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(dict(value), ensure_ascii=False, default=str) + "\n")


class WorkspaceTransitionSampler:
    """Compare regular-file metadata at successive Supervisor review boundaries.

    This is a path observation, not a judgment about any ground or task behavior.
    An incomplete scan leaves the last complete sample intact.
    """

    PATH_CAP = 64

    def __init__(self):
        self._previous = None
        self._previous_cursor = None
        self._sequence = 0

    @staticmethod
    def _scan(root):
        files = {}
        errors = []

        def visit(directory):
            try:
                with os.scandir(directory) as entries:
                    for entry in entries:
                        if entry.name == ".git":
                            continue
                        relative = Path(entry.path).relative_to(root).as_posix()
                        try:
                            if entry.is_symlink():
                                continue
                            if entry.is_dir(follow_symlinks=False):
                                visit(entry.path)
                            elif entry.is_file(follow_symlinks=False):
                                info = entry.stat(follow_symlinks=False)
                                files[relative] = (info.st_size, info.st_mtime_ns, info.st_ctime_ns)
                        except OSError as exc:
                            errors.append({"path": relative, "error_type": type(exc).__name__})
            except OSError as exc:
                relative = Path(directory).relative_to(root).as_posix()
                errors.append({"path": relative, "error_type": type(exc).__name__})

        visit(root)
        return files, errors

    def sample(self, root, *, cursor, task_turn):
        started = time.monotonic()
        root = Path(root)  # MonitorWorkspace already resolved the supervised mount.
        files, errors = self._scan(root)
        initial = self._previous is None
        complete = not errors
        from_cursor = self._previous_cursor
        added, modified, deleted = [], [], []
        if complete:
            if not initial:
                before = self._previous
                added = sorted(set(files) - set(before))
                deleted = sorted(set(before) - set(files))
                modified = sorted(path for path in files.keys() & before.keys()
                                  if files[path] != before[path])
            self._previous = files
            self._previous_cursor = cursor
        self._sequence += 1

        def virtual(paths):
            return [f"task/workspace/{path}" for path in paths]

        changed = {"added": virtual(added), "modified": virtual(modified),
                   "deleted": virtual(deleted)}
        total = sum(len(paths) for paths in changed.values())
        visible = []
        for kind in ("added", "modified", "deleted"):
            visible.extend((kind, path) for path in changed[kind])
        truncated = len(visible) > self.PATH_CAP
        if not complete:
            kinds = ", ".join(sorted({error["error_type"] for error in errors}))
            view = ("Workspace transition sample incomplete "
                    f"at task cursor {cursor} ({kinds}); path delta unavailable. "
                    "Do not infer that the workspace was unchanged.")
        elif initial:
            view = (f"Workspace transition baseline established at task cursor {cursor}; "
                    "there is no previous Supervisor sample for comparison.")
        else:
            prefix = ("Workspace transition since the previous Supervisor sample "
                      f"(task cursor {from_cursor} -> {cursor}):")
            if not total:
                view = prefix + " no path-level changes detected."
            else:
                lines = [prefix]
                for kind in ("added", "modified", "deleted"):
                    paths = [path for item_kind, path in visible[:self.PATH_CAP]
                             if item_kind == kind]
                    if paths:
                        lines.append(f"{kind}:")
                        lines.extend(f"- {path}" for path in paths)
                if truncated:
                    lines.append(f"view truncated: showing {self.PATH_CAP} of {total} changed paths; "
                                 "undisplayed paths are not implied unchanged.")
                view = "\n".join(lines)
            view += ("\nMechanical path-transition facts only. Changed paths alone do not "
                     "decide a prior ground's applicability; unchanged direct source does not "
                     "establish its semantic basis.")

        audit = {"event": "workspace_transition_sample", "sample_sequence": self._sequence,
                 "from_cursor": from_cursor, "to_cursor": cursor, "task_turn": task_turn,
                 "initial_baseline": initial, "sample_complete": complete,
                 **changed, "total_changed": total, "model_visible_truncated": truncated,
                 "sampling_duration_ms": round((time.monotonic() - started) * 1000, 3),
                 "errors": errors, "error_types": sorted({e["error_type"] for e in errors})}
        return view, audit


def _coalesce_wake_command(commands, first, completion_is_active=None):
    """Keep the newest patrol wake while preserving control-boundary priority."""
    selected = None
    candidate = first
    while True:
        kind = candidate.get("kind")
        if kind == "close":
            return candidate
        if kind == "verification_boundary":
            if selected is not None:
                commands.put(selected)
            return candidate
        if kind == 'delivery_receipt':
            if selected is not None:
                commands.put(selected)
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


def _verification_boundary_valid(state, generation):
    if state is None:
        return False
    with state.get_lock():
        return int(state[0]) == generation and time.monotonic() < state[1]


def _worker(config, commands, outputs):
    from .agent import MonitorAgent
    from .checkpoint import capture_live_root_checkpoint
    from .provider import MonitorProviderClient, ProviderRecoveryExhausted
    from .probe import IndependentVerifier, ProbeConfig
    from .workspace import MonitorWorkspace

    try:
        client = MonitorProviderClient(config["config_name"], config["model_config"])
        client.verification_due_turn = config.get('verification_due_turn')
        client.verification_accepted_generation = config.get('verification_accepted_generation')
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
        def capture_root_request(snapshot):
            """Persist one complete root-handoff request before transport."""
            handoff = snapshot.get("root_handoff") or {}
            try:
                identity = {
                    "task_id": config.get("task_id"), "run_id": config.get("run_id"),
                    "config_name": config.get("config_name"),
                    "review_id": snapshot.get("review_id"),
                    "request_sequence": snapshot.get("request_sequence"),
                    "task_turn": int(config.get("latest_task_turn").value),
                }
                final = capture_live_root_checkpoint(
                    workspace=workspace, checkpoint_root=checkpoint_root,
                    snapshot=snapshot, identity=identity,
                    current_handoff=current_completion)
                client._progress("root_checkpoint_created", path=str(final),
                                 request_id=handoff["request_id"], cursor=handoff["cursor"])
                return True
            except Exception as exc:
                client._progress("root_checkpoint_invalid", error_type=type(exc).__name__, error=str(exc))
                if config.get("root_checkpoint_required"):
                    raise
                return False

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
        root_turn_ceiling = _root_turn_ceiling(config, config['max_review_turns'])
        used_turns = config.get('task_budget_turns_used')
        max_turns = config.get('task_max_turns')
        monitor.task_budget_state = lambda: (
            used_turns.value if used_turns is not None else None, max_turns)
        workspace_sampler = (WorkspaceTransitionSampler()
                             if monitor.dcec_enabled and not getattr(monitor, 'cfs_v0', False) else None)
    except Exception as exc:
        outputs.put({"kind": "failure", "error": repr(exc), "phase": "startup"})
        return

    next_wake_turn = 1
    close_watch = False
    cursor = 0
    task_turn = 0
    receipt_offset = 0
    feedback_barrier = (ASEFeedbackBarrier(lambda event, **fields: monitor._progress(event, **fields))
                        if getattr(monitor, 'ase_v0', False) else None)

    def current_public_identity():
        public_cursor = config.get('latest_public_cursor')
        clock = config.get('latest_task_turn')
        return (max(task_turn, clock.value if clock is not None else task_turn),
                 max(cursor, public_cursor.value if public_cursor is not None else cursor))

    def sync_intervention_receipts(*, wait_for_receipt=False):
        receipts = config.get('intervention_receipts')
        echo_state = getattr(monitor, 'control_echo', None)
        if receipts is None or echo_state is None:
            return
        while True:
            try:
                receipt = (receipts.get(timeout=.1) if wait_for_receipt else receipts.get_nowait())
            except queue.Empty:
                if wait_for_receipt and not config['stop_event'].is_set():
                    continue
                return
            wait_for_receipt = False
            outcome = echo_state.reconcile_receipt(receipt)
            if outcome == 'delivered' and feedback_barrier is not None:
                echo = echo_state.active_echo
                feedback_barrier.start(task_turn=echo['delivered_task_turn'],
                                       cursor=echo['delivered_cursor'],
                                       action_locator=echo['action_locator'],
                                       submission_id=echo['submission_id'])

    def feedback_permits():
        sync_intervention_receipts()
        echo_state = getattr(monitor, 'control_echo', None)
        if echo_state is not None and echo_state.pending_submission is not None:
            monitor._progress('curator_delivery_pending_wake_blocked',
                              submission_id=echo_state.pending_submission['submission_id'],
                              current_task_turn=task_turn, current_cursor=cursor)
            return False
        if feedback_barrier is None or feedback_barrier.pending is None:
            return True
        identity = config.get('latest_model_feedback')
        with identity.get_lock():
            model_turn, model_cursor = int(identity[0]), int(identity[1])
        return feedback_barrier.permits(
            task_turn=task_turn, cursor=cursor,
            model_feedback_turn=model_turn if model_cursor <= cursor else 0,
            model_feedback_cursor=model_cursor if model_cursor <= cursor else 0)

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
            delivery_id = request_id if completion and not submitted else uuid.uuid4().hex
            submitted_turn, submitted_cursor = current_public_identity()
            if completion and not submitted:
                outputs.put({"kind": "completion", "decision": "continue", "cursor": cursor,
                             "request_id": request_id, "message": message,
                             "control_submission": True, "submission_id": delivery_id})
            else:
                outputs.put({"kind": "intervention", "cursor": cursor,
                             "request_id": delivery_id, "message": message,
                             "control_submission": True, "submission_id": delivery_id})
            submitted = True
            close_watch = True
            next_wake_turn = task_turn + 1
            return {"submission_id": delivery_id, "delivery": "queued",
                    "submitted_task_turn": submitted_turn,
                    "submitted_cursor": submitted_cursor}

        if config["model_config"].get("monitor_live_intervention", True):
            monitor.intervention_callback = send_now
            # Only actual review-ending actions define compaction boundaries.
            client.CONTROL_ACTIONS = (ASE_CONTROL_ACTIONS
                                      if monitor.ase_v0 else {"wait", "allow_complete"})
        try:
            transition_view = None
            if workspace_sampler is not None:
                clock = config.get('latest_task_turn')
                sampled_turn = max(task_turn, clock.value) if clock is not None else task_turn
                transition_view, transition_audit = workspace_sampler.sample(
                    workspace.task_mounts["workspace"], cursor=cursor, task_turn=sampled_turn)
                audit_path = Path(config["private_root"]) / "audit" / "workspace_transitions.jsonl"
                audit_path.parent.mkdir(parents=True, exist_ok=True)
                _append(audit_path, transition_audit)
                context += "\n" + transition_view
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
            root = current_completion() if monitor.root_routed else None
            if root is not None:
                completion, request_id = True, root['request_id']
            initial_review_kwargs = {
                'completion_pending': completion,
                'root_handoff': root,
                'root_transition_view': transition_view,
            }
            if root is not None and config.get('root_max_review_turns') is not None:
                initial_review_kwargs['max_turns_override'] = root_turn_ceiling
            action = monitor.review(context, **initial_review_kwargs)
            remaining_turns = root_turn_ceiling
            while action.kind in {'root_route', 'root_reestimate'}:
                prior = action.kind
                remaining_turns = _remaining_root_turns(remaining_turns, action)
                next_root = current_completion()
                if next_root is None or (prior == 'root_reestimate' and next_root != root):
                    if prior == 'root_reestimate':
                        monitor.crs.abandon('stale_handoff')
                        monitor.restore_rer_parent('stale_handoff')
                    outputs.put({'kind': 'root_route_superseded', 'reason': 'handoff_no_longer_pending'})
                    from .actions import MonitorAction
                    action = MonitorAction('wait', {'after_turns': 1, 'mode': 'follow'})
                    break
                root = next_root
                if remaining_turns <= 0:
                    if prior == 'root_reestimate':
                        monitor.crs.abandon('root_turn_budget_exhausted')
                        monitor.restore_rer_parent('root_turn_budget_exhausted')
                    outputs.put({'kind': 'failure', 'error': 'Root review turn budget exhausted',
                                 'completion': True, 'request_id': root['request_id']})
                    return False
                if prior == 'root_reestimate':
                    monitor.enter_root_reestimate(root, action)
                completion, request_id = True, root['request_id']
                root_transition_view = None
                if workspace_sampler is not None and prior == 'root_route':
                    clock = config.get('latest_task_turn')
                    sampled_turn = max(task_turn, clock.value) if clock is not None else task_turn
                    root_transition_view, root_transition_audit = workspace_sampler.sample(
                        workspace.task_mounts['workspace'], cursor=root['cursor'],
                        task_turn=sampled_turn)
                    _append(Path(config['private_root']) / 'audit' /
                            'workspace_transitions.jsonl', root_transition_audit)
                action = monitor.review(
                    context, completion_pending=True, root_handoff=root,
                    max_turns_override=remaining_turns,
                    root_transition_view=root_transition_view)
            receipt_offset = next_receipt_offset
        except Exception as exc:
            if getattr(monitor, 'rer_v0', False):
                monitor.crs.abandon('runtime_error')
                monitor.restore_rer_parent('runtime_error')
            from .provider import failure_chain
            outputs.put({"kind": "failure", "error": repr(exc), "completion": completion and not submitted,
                         "request_id": request_id, "cause_chain": failure_chain(exc),
                         "failed_at": time.time()})
            # A terminal transport recovery must not silently restart via the
            # queued patrol/completion commands after the parent has failed it.
            return not isinstance(exc, ProviderRecoveryExhausted)
        if action.kind == "wait":
            release_wake = close_watch or wake_receipts is not None
            close_watch = action.payload.get('mode', 'follow') == 'follow'
            # Silence starts now, not when this potentially long review began.
            # This clock conveys progress only; it does not mark evidence read.
            clock = config.get('latest_task_turn')
            current_turn = max(task_turn, clock.value) if clock is not None else task_turn
            next_wake_turn = current_turn + max(1, int(action.payload["after_turns"]))
            if monitor.verification is not None and close_watch:
                budget_used = config.get('task_budget_turns_used')
                if budget_used is not None:
                    monitor.verification.arm_follow(budget_used.value, action.payload['after_turns'])
            if release_wake:
                outputs.put({'kind': 'review_silent', 'from_turn': current_turn,
                             'next_wake_turn': next_wake_turn,
                             'mode': 'follow' if close_watch else 'patrol'})
        elif action.kind == "intervene":
            close_watch = True
            next_wake_turn = task_turn + 1
            delivery_id = request_id if completion else uuid.uuid4().hex
            if feedback_barrier is not None:
                raise RuntimeError('ASE intervention must use the delivery-acknowledged callback')
            if not completion:
                outputs.put({
                    "kind": "intervention", "message": action.payload["message"],
                    "cursor": cursor, "request_id": delivery_id,
                })
        elif action.kind == 'root_intervened':
            close_watch = True
            next_wake_turn = task_turn + 1
        elif action.kind == 'local_intervened':
            # The callback already queued the input and set the next wake.
            # This is only the review boundary, never a second submission.
            close_watch = True
        elif action.kind == 'incomplete_delivery':
            outputs.put({'kind': 'completion', 'decision': 'incomplete', 'cursor': cursor,
                         'request_id': action.payload.get('request_id', request_id),
                         'message': action.payload['reason']})
        elif action.kind == "allow_complete":
            approval_id = action.payload.get("request_id", request_id)
            current = current_completion()
            if monitor.root_routed and (
                    current is None or current['request_id'] != approval_id
                    or current['generation'] != action.payload.get('root_frame_generation')):
                outputs.put({'kind': 'root_approval_superseded', 'request_id': approval_id})
                return True
            key = ((current or {}).get("generation"), (current or {}).get("request_id"))
            if config.get("root_checkpoint_required") and key not in client.captured_root_handoffs:
                outputs.put({"kind": "failure", "error": "Required root checkpoint was not captured",
                             "completion": True, "request_id": approval_id})
                return False
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
        if kind == 'delivery_receipt':
            sync_intervention_receipts(wait_for_receipt=True)
            active = current_completion()
            if active is not None:
                kind = 'completion'
                command = dict(command, request_id=active['request_id'],
                               generation=active['generation'], cursor=active['cursor'])
            else:
                kind = 'boundary'
        if kind == 'verification_boundary':
            state = config.get('verification_boundary_state')
            generation = command['generation']
            def boundary_valid():
                return _verification_boundary_valid(state, generation)
            try:
                result = (monitor.verification.run_due(
                    int(command['task_turn']), boundary_valid=boundary_valid,
                    boundary_generation=generation)
                    if monitor.verification is not None and boundary_valid()
                    else {'status': 'boundary_expired'})
                outputs.put({'kind': 'verification_boundary_release', 'ticket': command['ticket'],
                             'generation': generation, 'result': result})
            except Exception as exc:
                due = config.get('verification_due_turn')
                if due is not None:
                    due.value = -1
                monitor._progress('verification_execution_error', error_type=type(exc).__name__)
                outputs.put({'kind': 'verification_boundary_release', 'ticket': command['ticket'],
                             'generation': generation, 'error': repr(exc)})
            continue
        cursor = int(command.get("cursor") or cursor)
        task_turn = int(command.get("task_turn") or task_turn)
        if kind == "boundary" and task_turn >= next_wake_turn:
            if not feedback_permits():
                continue
            if not review(
                f"Public task cursor advanced through {cursor}. Continue from your existing history, inspect "
                "new synopsis rows, and retrieve original evidence wherever it can change your decision."
            ):
                return
        elif kind == "completion" and completion_is_active(command):
            if not feedback_permits():
                outputs.put({'kind': 'completion', 'decision': 'continue', 'cursor': cursor,
                             'request_id': command['request_id'],
                             'message': 'Continue with the pending monitor correction.'})
                continue
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
                 root_max_review_turns=None,
                 completion_timeout=300, process_factory=None, worker_target=None,
                 interrupt_pending=None, run_timeout_seconds=10000, run_deadline_epoch=None,
                 correction_begin=None, correction_end=None, task_original_path=None, task_id,
                 independent_probe_total_requests=0, independent_probe_max_requests=3,
                 root_checkpoint_required=False, run_id=None, task_max_turns=None):
        if model_config.get('monitor_hybrid_control', False):
            raise ValueError('Model-requested hybrid pause is retired')
        _root_turn_ceiling({'root_max_review_turns': root_max_review_turns}, max_review_turns)
        self.artifact_dir = Path(artifact_dir).resolve()
        if type(root_checkpoint_required) is not bool:
            raise ValueError("root_checkpoint_required must be boolean")
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
        self._eis_enabled = model_config.get("monitor_executable_interpretation_surface", False)
        if type(self._eis_enabled) is not bool:
            raise ValueError("monitor_executable_interpretation_surface must be a boolean")
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
        self._intervention_receipts = (self._context.Queue()
                                       if model_config.get('monitor_adaptive_supervisory_environment') is True
                                       else None)
        self._wake_receipts = self._context.Queue() if correction_begin is not None else None
        self._pending = {}
        self._pending_lock = threading.Lock()
        self._completion_generation = 0
        self._active_completion = self._context.Value('q', 0)
        self._completion_cursor = self._context.Value('q', 0)
        self._latest_task_turn = self._context.Value('q', 0)
        self._latest_public_cursor = self._context.Value('q', self._sequence)
        self._latest_model_feedback = self._context.Array('q', [0, 0])
        self._task_budget_turns_used = self._context.Value('q', 0)
        self._task_max_turns = task_max_turns
        managed_check = (model_config.get('monitor_verification_loop_v0') is True and
                         model_config.get('monitor_verification_runtime_managed', True) is True)
        self._verification_due_turn = self._context.Value('q', -1) if managed_check else None
        self._verification_receipts = self._context.Queue() if managed_check else None
        self._verification_boundary_state = self._context.Array('d', [0, 0]) if managed_check else None
        self._verification_accepted_generation = self._context.Value('q', 0) if managed_check else None
        self._closed = threading.Event()
        process = process_factory or self._context.Process
        self._process = process(target=worker_target or _worker, args=({
            "config_name": config_name, "model_config": dict(model_config), "task_id": task_id,
            "evidence_root": str(self.evidence_root), "private_root": str(self.private_root),
            "task_workspace": str(task_workspace), "max_review_turns": int(max_review_turns),
            "root_max_review_turns": root_max_review_turns,
            "task_original_path": self.task_original_path,
            "active_completion": self._active_completion,
            "completion_cursor": self._completion_cursor,
            "root_checkpoint_required": root_checkpoint_required,
            "run_id": run_id,
            "latest_task_turn": self._latest_task_turn,
            "latest_public_cursor": self._latest_public_cursor,
            "latest_model_feedback": self._latest_model_feedback,
            "task_budget_turns_used": self._task_budget_turns_used,
            "task_max_turns": self._task_max_turns,
            "verification_due_turn": self._verification_due_turn,
            "verification_boundary_state": self._verification_boundary_state,
            "verification_accepted_generation": self._verification_accepted_generation,
            "run_deadline_epoch": time.time() + max(0.0, self._run_deadline - time.monotonic()),
            "stop_event": self._stop_event,
            "independent_probe_total_requests": int(independent_probe_total_requests),
            "independent_probe_max_requests": int(independent_probe_max_requests),
            "completion_receipts": self._completion_receipts,
            "intervention_receipts": self._intervention_receipts,
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
            with self._latest_public_cursor.get_lock():
                self._latest_public_cursor.value = sequence
            if raw.get('boundary') in TASK_MODEL_FEEDBACK_BOUNDARIES:
                with self._latest_model_feedback.get_lock():
                    self._latest_model_feedback[0] = int(raw.get('task_turn') or 0)
                    self._latest_model_feedback[1] = sequence
            if self._eis_enabled:
                try:
                    append_eis_index(self.evidence_root, raw)
                except OSError as exc:
                    # EIS is navigation over the authoritative public archive.
                    # An index failure must not recast or suppress that archive.
                    try:
                        _append(self.private_root / "eis_index_errors.jsonl", {
                            "archive_sequence": sequence, "error_type": type(exc).__name__})
                    except OSError:
                        pass
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

    def note_task_turn(self, local_turn):
        """Publish the loop counter that is bounded by agent_runner_loop.max_turns."""
        with self._task_budget_turns_used.get_lock():
            self._task_budget_turns_used.value = max(
                self._task_budget_turns_used.value, int(local_turn))

    def verification_boundary(self, local_turn):
        """Wait only at a completed Task-tool boundary; never cancel that tool."""
        due = self._verification_due_turn
        if due is None or due.value < 0 or local_turn < due.value:
            return None
        ticket = uuid.uuid4().hex
        deadline = min(self._run_deadline, time.monotonic() + 305)
        state = self._verification_boundary_state
        with state.get_lock():
            state[0] += 1
            generation = int(state[0])
            state[1] = deadline
        self._commands.put({'kind': 'verification_boundary', 'ticket': ticket,
                            'generation': generation, 'task_turn': int(local_turn)})
        while not self._closed.is_set() and time.monotonic() < deadline:
            if not self._process.is_alive():
                break
            try:
                receipt = self._verification_receipts.get(timeout=0.1)
            except queue.Empty:
                continue
            if receipt.get('ticket') == ticket:
                with state.get_lock():
                    valid = int(state[0]) == generation and time.monotonic() < state[1]
                    state[1] = 0
                if valid and receipt.get('result', {}).get('status') == 'observed':
                    self._verification_accepted_generation.value = generation
                else:
                    receipt = dict(receipt, error='verification_boundary_expired')
                return receipt
        with state.get_lock():
            if int(state[0]) == generation:
                state[1] = 0
        due.value = -1
        receipt = {'kind': 'verification_boundary_release', 'ticket': ticket,
                   'error': 'monitor_unavailable_or_boundary_timeout'}
        self._append_receipt(receipt)
        return receipt

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
            elif kind == 'verification_boundary_release':
                if self._verification_receipts is not None:
                    self._verification_receipts.put(value)
            elif kind == "intervention":
                try:
                    receipt = self._interrupt_callback(value["message"])
                    value = dict(value, delivery="handed_to_task_interrupt_interface", receipt=str(receipt),
                                 delivery_task_turn=self._latest_task_turn.value,
                                 delivery_cursor=self._latest_public_cursor.value)
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
                    value = dict(value, delivery="failed", error=repr(exc),
                                 error_type=type(exc).__name__)
                finally:
                    self._finish_correction()
            elif kind == "completion" or (kind == "failure" and value.get("completion") is True):
                self._finish_correction()
                with self._pending_lock:
                    pending = self._pending.pop(value.get("request_id"), None)
                    if pending is not None:
                        if value.get('control_submission'):
                            value = dict(value, delivery_task_turn=self._latest_task_turn.value,
                                         delivery_cursor=self._latest_public_cursor.value)
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
            if self._intervention_receipts is not None and value.get('control_submission'):
                delivered = value.get('delivery') in {
                    'handed_to_task_interrupt_interface', 'handed_to_completion_boundary'}
                receipt = {'submission_id': value['submission_id'], 'delivered': delivered,
                           'delivery_kind': value.get('delivery'),
                           'error_type': value.get('error_type'),
                           'delivery_task_turn': value.get('delivery_task_turn', self._latest_task_turn.value),
                           'delivery_cursor': value.get('delivery_cursor', self._latest_public_cursor.value)}
                self._intervention_receipts.put(receipt)
                # A boundary may have arrived while delivery was unresolved.
                # Recheck it after the receipt without creating a new model stage.
                self._commands.put({'kind': 'delivery_receipt',
                                    'task_turn': self._latest_task_turn.value,
                                    'cursor': self._latest_public_cursor.value})

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
        if value.get("decision") == "incomplete":
            return CompletionOutcome(False, value.get('message') or 'Verification limited.',
                                     'verification_limited', True)
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
