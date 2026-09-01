"""High-capability, no-checker monitor used as an M0 teacher policy.

The monitor independently observes an append-only public archive, reconstructs
detail with read-only tools, and emits only justified user-like corrections.
Ordinary task execution never waits for a monitor judgment.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Mapping

from llmcore import resolve_session
from m0_monitor_checkpoint import MonitorCheckpointStore
from monitor_semantic_files import MonitorSemanticFiles
from research_runtime import CompletionDecision, emit


ATTENTION_MODES = {"patrol", "focused"}
INSPECTION_RESULT_ARCHIVE_THRESHOLD = 24000
INSPECTION_RESULT_PAGE_CHARACTERS = 12000
INSPECTIONS = {
    "read_file", "list_files", "search_text", "git_diff", "git_status",
    "list_changed_tests", "read_test_change", "search_test_contract",
}
TRAJECTORY_INSPECTIONS = {
    "read_public_trajectory", "search_public_trajectory",
    "read_monitor_decisions", "search_monitor_decisions",
    "read_repair_episode", "read_recent_delta", "read_original_task",
    "read_inspection_result", "list_monitor_history_archives",
    "read_monitor_history_archive",
}


def _json_object(raw: str) -> dict[str, Any]:
    text = raw.strip().lstrip("\ufeff\u200b")
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, re.I | re.S)
    if fenced:
        text = fenced.group(1)
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        if start < 0:
            raise
        value, _ = json.JSONDecoder().raw_decode(text[start:])
    if not isinstance(value, dict):
        raise ValueError("monitor decision must be a JSON object")
    return value


def _clip(value: Any, limit: int = 30000) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    if len(text) <= limit:
        return text
    half = limit // 2
    return text[:half] + "\n...[MONITOR VIEW CLIPPED]...\n" + text[-half:]


class PublicWorkspaceInspector:
    """Small read-only inspection surface rooted in the public task workspace."""

    def __init__(self, root: str | os.PathLike[str] | None):
        self.root = Path(root or ".").resolve()

    def _path(self, value: str) -> Path:
        path = (self.root / value).resolve()
        try:
            path.relative_to(self.root)
        except ValueError as error:
            raise ValueError("inspection path escapes public workspace") from error
        return path

    def execute(self, request: Mapping[str, Any]) -> dict[str, Any]:
        operation = str(request.get("operation", ""))
        if operation not in INSPECTIONS:
            return {"ok": False, "error": f"unsupported inspection: {operation}"}
        try:
            if operation == "read_file":
                path = self._path(str(request.get("path", "")))
                start = max(1, int(request.get("start_line", 1)))
                count = min(2000, max(1, int(request.get("line_count", 400))))
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
                body = "\n".join(f"{i}: {line}" for i, line in enumerate(lines[start - 1:start - 1 + count], start))
                return {"ok": True, "path": str(path.relative_to(self.root)), "content": _clip(body)}
            if operation == "list_files":
                base = self._path(str(request.get("path", ".")))
                pattern = str(request.get("pattern", "*"))
                limit = min(1000, max(1, int(request.get("limit", 300))))
                rows = []
                for path in base.rglob(pattern):
                    if path.is_file():
                        rows.append(str(path.relative_to(self.root)))
                    if len(rows) >= limit:
                        break
                return {"ok": True, "files": rows, "truncated": len(rows) >= limit}
            if operation == "search_text":
                pattern = re.compile(str(request.get("pattern", "")), re.I if request.get("ignore_case", True) else 0)
                base = self._path(str(request.get("path", ".")))
                limit = min(500, max(1, int(request.get("limit", 100))))
                rows = []
                for path in base.rglob(str(request.get("glob", "*"))):
                    if not path.is_file() or path.stat().st_size > 2_000_000:
                        continue
                    try:
                        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
                    except OSError:
                        continue
                    for line_no, line in enumerate(lines, 1):
                        if pattern.search(line):
                            rows.append({"path": str(path.relative_to(self.root)), "line": line_no, "text": _clip(line, 1000)})
                            if len(rows) >= limit:
                                return {"ok": True, "matches": rows, "truncated": True}
                return {"ok": True, "matches": rows, "truncated": False}
            if operation == "list_changed_tests":
                return self._changed_tests()
            if operation == "read_test_change":
                return self._test_change(str(request.get("path", "")))
            if operation == "search_test_contract":
                return self._search_tests(request)
            return self._git(operation)
        except Exception as error:
            return {"ok": False, "error": f"{type(error).__name__}: {error}"}

    @staticmethod
    def _is_test_path(path: str) -> bool:
        name = Path(path).name.lower()
        return (name.endswith("_test.go") or name.startswith("test_")
                or name.endswith(("_test.py", ".spec.js", ".test.js", ".spec.ts", ".test.ts"))
                or "/tests/" in "/" + path.replace("\\", "/").lower())

    def _changed_tests(self) -> dict[str, Any]:
        result = self._run_git(["status", "--short"])
        if not result["ok"]:
            return result
        rows = []
        for line in result["stdout"].splitlines():
            if len(line) < 4:
                continue
            status, path = line[:2], line[3:].strip()
            if " -> " in path:
                path = path.split(" -> ", 1)[1]
            if self._is_test_path(path):
                rows.append({"status": status, "path": path})
        return {"ok": True, "changed_tests": rows, "count": len(rows)}

    def _test_change(self, value: str) -> dict[str, Any]:
        path = self._path(value)
        relative = str(path.relative_to(self.root))
        if not self._is_test_path(relative):
            return {"ok": False, "error": "path is not recognized as a test file"}
        diff = self._run_git(["diff", "--no-ext-diff", "--", relative])
        content = ""
        if path.exists() and not diff.get("stdout"):
            content = _clip(path.read_text(encoding="utf-8", errors="replace"))
        return {"ok": diff["ok"], "path": relative, "diff": diff.get("stdout", ""),
                "content_if_untracked": content, "stderr": diff.get("stderr", "")}

    def _search_tests(self, request: Mapping[str, Any]) -> dict[str, Any]:
        pattern = re.compile(str(request.get("pattern", "")),
                             re.I if request.get("ignore_case", True) else 0)
        limit = min(500, max(1, int(request.get("limit", 100))))
        rows = []
        for path in self.root.rglob("*"):
            if not path.is_file() or not self._is_test_path(str(path.relative_to(self.root))):
                continue
            if path.stat().st_size > 2_000_000:
                continue
            for line_no, line in enumerate(path.read_text(
                    encoding="utf-8", errors="replace").splitlines(), 1):
                if pattern.search(line):
                    rows.append({"path": str(path.relative_to(self.root)), "line": line_no,
                                 "text": _clip(line, 1000)})
                    if len(rows) >= limit:
                        return {"ok": True, "matches": rows, "truncated": True}
        return {"ok": True, "matches": rows, "truncated": False}

    def _run_git(self, suffix: list[str]) -> dict[str, Any]:
        import subprocess
        args = ["git", *suffix]
        completed = subprocess.run(args, cwd=self.root, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        return {"ok": completed.returncode == 0, "returncode": completed.returncode,
                "stdout": _clip(completed.stdout), "stderr": _clip(completed.stderr, 4000)}

    def _git(self, operation: str) -> dict[str, Any]:
        suffix = ["status", "--short"] if operation == "git_status" else ["diff", "--no-ext-diff", "--"]
        return self._run_git(suffix)


class M0DeliberativeMonitor:
    """Persistent high-capability monitor executed by the concurrent worker."""

    def __init__(self, *, public_task: str, workspace: str | os.PathLike[str] | None,
                 config_name: str, artifact_dir: str | os.PathLike[str] | None = None,
                 max_inspections: int = 8, recent_trajectory_turns: int = 0,
                 m3_human_loop_enabled: bool = False,
                 m3_decision_value_enabled: bool = False,
                 m3_discriminative_control_enabled: bool = False,
                 m3_combined_control_enabled: bool = False,
                 history_soft_char_limit: int = 128000,
                 history_target_characters: int = 88000):
        session = resolve_session(config_name)
        if session is None:
            raise ValueError(f"Unsupported M0 monitor config: {config_name}")
        session.max_tokens = max(session.max_tokens or 0, 16000)
        # A relay may expose a temporary upstream failure as HTTP 400. Bounded
        # transport retries let the independent monitor survive without
        # freezing or killing the task Agent.
        session.max_retries = max(getattr(session, "max_retries", 0), 4)
        # Bound the whole worker review, not only periods with no bytes.
        # SSE keepalives otherwise defeat requests' inactivity read timeout.
        configured_total = float(getattr(session, "total_response_timeout", 0) or 0)
        session.total_response_timeout = min(
            configured_total if configured_total > 0 else 300.0, 300.0
        )
        self.session = session
        # Research telemetry distinguishes the supervised task model from the
        # monitor even when both use the same low-level provider client.
        self.session.research_call_type = "monitor"
        self.deep_reasoning_effort = getattr(session, "reasoning_effort", None)
        self.shadow_reasoning_effort = "high" if self.deep_reasoning_effort == "xhigh" else self.deep_reasoning_effort
        self.public_task = public_task
        self.inspector = PublicWorkspaceInspector(workspace)
        self.artifact_dir = Path(artifact_dir).resolve() if artifact_dir else None
        if self.artifact_dir is None:
            raise ValueError("persistent monitor requires an explicit artifact_dir")
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoints = MonitorCheckpointStore(self.artifact_dir, public_task)
        self.m3_human_loop_enabled = bool(m3_human_loop_enabled)
        self.m3_decision_value_enabled = bool(m3_decision_value_enabled)
        self.m3_discriminative_control_enabled = bool(
            m3_discriminative_control_enabled
        )
        self.m3_combined_control_enabled = bool(m3_combined_control_enabled)
        self.adaptive_review_planning_enabled = True
        self.history_soft_char_limit = max(16000, int(history_soft_char_limit))
        self.history_target_characters = max(
            12000, min(int(history_target_characters), self.history_soft_char_limit)
        )
        if self.m3_decision_value_enabled and not self.m3_human_loop_enabled:
            raise ValueError("M3-B requires the M3-A human-loop parent")
        if (self.m3_discriminative_control_enabled
                and not self.m3_human_loop_enabled):
            raise ValueError("M3-C requires the M3-A human-loop parent")
        if (self.m3_decision_value_enabled
                and self.m3_discriminative_control_enabled):
            raise ValueError("M3-B and M3-C must remain independent candidates")
        if (self.m3_combined_control_enabled
                and not self.m3_discriminative_control_enabled):
            raise ValueError("M3-D requires the M3-C discriminative-control parent")
        self.semantic_files = MonitorSemanticFiles(self.artifact_dir, public_task)
        self.max_inspections = max_inspections
        self.recent_trajectory_turns = max(0, min(50, recent_trajectory_turns))
        self.notes = "No observations yet. Preserve every explicit task obligation and UNKNOWN."
        # This root scope is deliberately independent of the currently open
        # repair episode. A delegated subtask or local repair may finish without
        # shrinking the public task that must be audited at final completion.
        self.root_completion_basis = (
            "The original public task remains open until a root completion boundary "
            "accounts for every explicit obligation with public evidence or preserved UNKNOWN."
        )
        # Agent-authored specifications, audits, and tests are evidence, never
        # authority.  Keep challenged artifacts visible for provenance while
        # excluding them from the monitor's active task basis.
        self.contested_artifacts: dict[str, dict[str, Any]] = {}
        self.intervention_signatures: dict[str, int] = {}
        # A monitor may form many hypotheses, but uncertainty must not silently
        # become authority to keep steering the task Agent.  Track probe holds
        # inside an episode so one diagnostic request can run before another is
        # considered.
        self.pending_discriminating_probe: dict[str, Any] | None = None
        # M3-A keeps the monitor oriented around the Agent's current consequential
        # decision.  Values remain open natural language and never become a
        # deterministic gate: this is recoverable attention state, not a checker.
        self.decision_focus: dict[str, Any] | None = None
        # M3-B records the qualitative value of another information action.
        # It remains optional reflective state, never a deterministic score.
        self.decision_value: dict[str, Any] | None = None
        # M3-C carries at most the current one-step discriminating inquiry.
        # The runtime persists it but never interprets or scores alternatives.
        self.discriminative_step: dict[str, Any] | None = None
        # M3-D adds lifecycle memory around that same natural inquiry rather
        # than asking the model to maintain a second structured value form.
        # The runtime records cursor/transition facts but never judges whether
        # evidence is semantically sufficient.
        self.last_closed_inquiry: dict[str, Any] | None = None
        # The monitor chooses its own semantic patrol cadence. The runtime only
        # counts public task turns and returns this natural-language bookmark;
        # it never interprets focus/reason as a classifier.
        self.observation_plan: dict[str, Any] | None = {
            "review_after_turns": 20,
            "focus": "Reconstruct material task progress from the next public work window.",
            "expected_progress": "Ordinary task progress or a new decision-relevant artifact.",
            "reason": "Default recovery-safe patrol used until I choose a semantic cadence.",
            "updated_turn": 0,
            "source": "default",
        }
        self.recovery_level = 0
        self.open_episode: dict[str, Any] | None = None
        # Message index of the first wake that opened the current repair. H3
        # compaction must preserve this suffix verbatim while it remains open.
        self.open_episode_history_start: int | None = None
        self.history_review_starts: list[int] = []
        self.history_compaction_count = 0
        # One bounded navigation bookmark survives local release. It is not a
        # second task model and carries no automatic reopen semantics.
        self.last_closed_repair: dict[str, Any] | None = None
        # M3.5 working memory is deliberately narrower than the semantic task
        # model.  It preserves the monitor's current train of thought across
        # stateless LLM calls without duplicating obligations or raw history.
        self.cognitive_checkpoint: dict[str, Any] | None = None
        self.bootstrap_initialized = False
        self.decisions: list[dict[str, Any]] = []
        self.last_raw = ""
        # Ephemeral handoff to the asynchronous delivery runtime. Durable
        # authority remains in the checkpointed open_episode.
        self.last_intervention_delivery: dict[str, Any] | None = None
        self.attention_mode = "patrol"
        # Factual cross-turn observations only.  The monitor, not this data
        # structure, decides whether they indicate progress or drift.
        self.trajectory: list[dict[str, Any]] = []
        self._observed_archive_ids: set[str] = set()
        self.action_occurrences: dict[str, int] = {}
        self.history: list[dict[str, Any]] = [{
            "role": "user", "content": [{"type": "text", "text": self._base_prompt()}],
        }, {
            "role": "assistant", "content": [{"type": "text", "text": "I will monitor this public task under the stated boundary."}],
        }]
        self._inspection_result_cache: dict[str, str] = {}
        self._restore_checkpoint()

    def _restore_checkpoint(self) -> None:
        checkpoint = self.checkpoints.load()
        # A matching task hash is the authority for reconnecting archives.
        # Never attach an old run's raw history to a different public task just
        # because an artifact directory was accidentally reused.
        trajectory, decisions = self.checkpoints.load_archives() if checkpoint else ([], [])
        if checkpoint:
            decisions = decisions[:max(0, int(checkpoint.get("decision_count", 0) or 0))]
        self.trajectory = trajectory
        self.decisions = decisions
        for row in trajectory:
            archive_id = str(row.get("archive_event_id", ""))
            if archive_id:
                self._observed_archive_ids.add(archive_id)
            fingerprint = str(row.get("action_fingerprint", ""))
            if fingerprint:
                self.action_occurrences[fingerprint] = self.action_occurrences.get(fingerprint, 0) + 1
        if not checkpoint:
            return
        self.notes = str(checkpoint.get("notes", self.notes))
        self.root_completion_basis = str(
            checkpoint.get(
                "root_completion_basis",
                checkpoint.get("root_task_release_basis", self.root_completion_basis),
            )
        )
        self.contested_artifacts = dict(checkpoint.get("contested_artifacts", {}))
        self.open_episode = checkpoint.get("open_repair_episode")
        restored_episode_start = checkpoint.get("open_episode_history_start")
        self.pending_discriminating_probe = checkpoint.get("pending_discriminating_probe")
        restored_focus = checkpoint.get("m3_decision_focus")
        if self.m3_human_loop_enabled and isinstance(restored_focus, Mapping):
            self.decision_focus = dict(restored_focus)
        restored_value = checkpoint.get("m3_decision_value")
        if self.m3_decision_value_enabled and isinstance(restored_value, Mapping):
            self.decision_value = dict(restored_value)
        restored_step = checkpoint.get("m3_discriminative_step")
        if (self.m3_discriminative_control_enabled
                and isinstance(restored_step, Mapping)):
            self.discriminative_step = dict(restored_step)
        restored_closed_inquiry = checkpoint.get("m3d_last_closed_inquiry")
        if (self.m3_combined_control_enabled
                and isinstance(restored_closed_inquiry, Mapping)):
            self.last_closed_inquiry = dict(restored_closed_inquiry)
        restored_plan = checkpoint.get("observation_plan")
        if self.adaptive_review_planning_enabled and isinstance(restored_plan, Mapping):
            self.observation_plan = dict(restored_plan)
        restored_repair = checkpoint.get("last_closed_repair")
        if isinstance(restored_repair, Mapping):
            self.last_closed_repair = dict(restored_repair)
        restored_cognition = checkpoint.get("cognitive_checkpoint")
        if isinstance(restored_cognition, Mapping):
            self.cognitive_checkpoint = dict(restored_cognition)
        restored_history = checkpoint.get("monitor_history")
        if isinstance(restored_history, list):
            valid_history = self._validated_monitor_history(restored_history)
            # A task-hash-matched checkpoint may restore procedural cognition,
            # but never replace the immutable current policy/task prefix.
            if len(valid_history) >= 2:
                self.history = self.history[:2] + valid_history[2:]
        raw_starts = checkpoint.get("history_review_starts", [])
        if isinstance(raw_starts, list):
            self.history_review_starts = sorted({
                max(2, min(int(item), len(self.history)))
                for item in raw_starts
                if isinstance(item, int) or str(item).isdigit()
            })
        self.history_compaction_count = max(
            0, int(checkpoint.get("history_compaction_count", 0) or 0)
        )
        if self.open_episode is not None:
            try:
                self.open_episode_history_start = max(
                    2, min(int(restored_episode_start), len(self.history))
                )
            except (TypeError, ValueError):
                self.open_episode_history_start = 2
        self.bootstrap_initialized = bool(
            checkpoint.get("bootstrap_initialized", False)
            or self.cognitive_checkpoint
        )
        self.recovery_level = int(checkpoint.get("recovery_level", 0))
        restored_attention = str(
            checkpoint.get("attention_mode", self.attention_mode)
        ).strip().lower()
        self.attention_mode = {
            "shadow": "patrol", "deliberate": "focused",
        }.get(restored_attention, restored_attention)
        if self.attention_mode not in ATTENTION_MODES:
            self.attention_mode = "focused" if self.open_episode else "patrol"
        # authoritative_state is a convenience view; checkpoint is the commit
        # authority. Rebuild the view after any crash-window reconciliation.
        try:
            self._write_authoritative_state(checkpoint.get("last_internal_turn"))
        except BaseException as error:
            emit("authoritative_view_rebuild_failed", {
                "error_type": type(error).__name__,
                "error": str(error)[:1000],
                "checkpoint_authority_preserved": True,
            })

    def _checkpoint_state(self, internal_turn: Any) -> dict[str, Any]:
        state = {
            "root_completion_basis": self.root_completion_basis,
            "contested_artifacts": self.contested_artifacts,
            "open_repair_episode": self.open_episode,
            "pending_discriminating_probe": self.pending_discriminating_probe,
            "recovery_level": self.recovery_level,
            "attention_mode": self.attention_mode,
            "notes": self.notes,
            "last_internal_turn": internal_turn,
            "trajectory_count": len(self.trajectory),
            "decision_count": len(self.decisions),
            "last_state_transaction_id": f"decision:{len(self.decisions):04d}",
        }
        if self.m3_human_loop_enabled:
            state["m3_human_loop_enabled"] = True
            state["m3_decision_focus"] = self.decision_focus
        if self.m3_decision_value_enabled:
            state["m3_decision_value_enabled"] = True
            state["m3_decision_value"] = self.decision_value
        if self.m3_discriminative_control_enabled:
            state["m3_discriminative_control_enabled"] = True
            state["m3_discriminative_step"] = self.discriminative_step
        if self.m3_combined_control_enabled:
            state["m3_combined_control_enabled"] = True
            state["m3d_last_closed_inquiry"] = self.last_closed_inquiry
        state["observation_plan"] = self.observation_plan
        state["last_closed_repair"] = self.last_closed_repair
        state["cognitive_checkpoint"] = self.cognitive_checkpoint
        state["bootstrap_initialized"] = self.bootstrap_initialized
        state["monitor_history"] = self.history
        state["open_episode_history_start"] = self.open_episode_history_start
        state["history_review_starts"] = self.history_review_starts
        state["history_compaction_count"] = self.history_compaction_count
        state["monitor_semantic_files"] = True
        return state

    def _base_prompt(self) -> str:
        return self._semantic_files_base_prompt()

    def _semantic_files_base_prompt(self) -> str:
        """Stable, framework-neutral policy for the model-owned file interface."""
        optional: list[str] = []
        if self.m3_human_loop_enabled:
            optional.append(
                'decision_focus: the current consequential decision, threatened transition, '
                'why attention is warranted, and the observable repair exit.'
            )
        if self.m3_decision_value_enabled:
            optional.append(
                'decision_value: the live decision, materially different outcomes, how they '
                'change action, and when another observation stops being useful.'
            )
        if self.m3_discriminative_control_enabled:
            optional.append(
                'discriminative_step: one short first-person inquiry whose outcomes would '
                'change the next action, or empty when no such ambiguity remains.'
            )
        if self.adaptive_review_planning_enabled:
            optional.append(
                'observation_plan: review_after_turns plus a natural-language focus, expected '
                'progress, and reason. It is an attention estimate, never evidence.'
            )
        optional_text = "\n".join(f"- {item}" for item in optional) or "- none"
        return f"""You are a persistent human-style monitor supervising a long-running task Agent.
Improve the eventual task outcome while preserving the Agent's useful autonomy. The Agent owns
ordinary implementation and experimentation. You maintain task understanding, observe its public
reasoning and work, and send only sparse, evidence-grounded user-like corrections.

BOUNDARY
- Use only the public task, Agent messages and intentions, public tool calls/results, workspace files,
  tests, diffs, and your own versioned history. Never use hidden tests, gold answers, native verifier
  results, or future events. Claims and self-authored tests are provisional evidence.
- Keep UNKNOWN when public evidence cannot decide. Not observed is not absent; local success is not
  root completion. Do not invent requirements from conventions, best practices, or your own helpers.
- The original public task is immutable authority. Explicit task changes outrank inferred compatibility
  concerns. When exact wording matters, open the original task rather than trusting a recollection.

HUMAN CONTROL LOOP
- In patrol, cheaply orient to meaningful new progress and normally stay quiet. Retrieve detail only
  when it can change a current judgment. In focused attention, follow an active correction through the
  Agent's interpretation, intended next action, implementation, and evidence until reasonable uptake.
- Inspect publicly stated causal reasoning before it becomes code or a test when it already conflicts
  with the task and the planned action would encode the error. Otherwise allow ordinary safe failures
  and natural self-repair; do not interrupt merely because a first attempt is incomplete.
- Treat tests as the Agent's executable interpretation of the task. When a changed test matters, inspect
  its assertions, fixture/oracle validity, discriminative power, and production diff. A green test
  supports only the behavior it actually distinguishes.
- If several causes remain plausible, prefer one bounded comparison whose different outcomes change
  the next action. Once the Agent accepts and performs that safe comparison, observe without repeatedly
  redesigning it. Stop investigating when the relevant decision is already supported.

INTERVENTION
- Speak only for a confirmed public conflict, an observed material failure the Agent is mishandling,
  an imminent unsafe change based on unresolved causality, or unsupported closure over an explicit
  material requirement. A watch item alone receives no message.
- One intervention should identify the exact task basis, public conflict, contested artifact or claim,
  a concrete next action, and an observable release condition. Do not batch unrelated UNKNOWNs or ask
  the Agent to build a comprehensive checker, audit, or requirements document.
- After intervening, remain focused while the correction is being understood and applied. Stay silent
  during correct repair progress. Re-correct a public residual misunderstanding promptly; return to
  patrol when the local discrepancy has reasonable behavioral uptake, even if unrelated root work remains.

ROOT COMPLETION
At a completion proposal, revisit the complete original task and your persistent task model. Check for
omitted explicit requirements, invalidated evidence, proxy tests, target substitution, and local results
promoted to global completion. UNKNOWN alone does not require more work: continue only for a concrete
material discrepancy or one bounded, executable, decision-changing observation. Otherwise preserve
residual uncertainty and allow completion; this does not certify hidden correctness.

PERSISTENT NATURAL-LANGUAGE WORKSPACE
You own a framework-independent filesystem. Use list_files/read_file/search_text with scope=monitor and
edit_file with scope=monitor. task/original_task.md is read-only. Files under state/ and evidence/ are
your revisable cognition, not a fixed schema. Organize or add natural-language files as this task needs.
Do not maintain backend ids. Exact trajectory, code, tests, and diffs remain authoritative at source.

Before changing an existing monitor file, read it and pass its returned hash. Use patch for one exact
local replacement, replace when the file's organization no longer serves your understanding, and
append/prepend only when position itself is appropriate. Use create for a new file. A failed or conflicting
edit changes nothing: read the current file and continue. Successful changes are durable and versioned.
Edit only when understanding materially changes; do not perform a fixed read/write ritual. Important
progress, invalidated support, a changed repair residual, and root-completion understanding must not
exist only in a transient final response.
When new public evidence contradicts or invalidates earlier support, revise the affected understanding
instead of appending a disconnected note: reopen the claim in ordinary language, retain the source anchor,
and let the version history preserve what was previously believed. New evidence may restore support later.

OBSERVATION ADAPTER
The execution framework may vary. Depend only on these generic meanings: immutable public task;
append-only public trajectory and recent delta; readable task workspace; changed files/tests/diff;
prior monitor history; model-owned monitor files; and a user-like intervention channel. Use the tools
that expose those meanings, never framework-specific internal classes or storage paths.

TOOL LOOP
To inspect or edit, return one JSON object using one of these compact contracts:
{self._inspection_schema()}
After each result, continue the same review: inspect again, repair a failed edit, or make one final
decision. Tool failure is an observation, never evidence about task correctness.

For an ordinary wake, return exactly one final object of this shape:
{self._decision_schema(completion=False, omit_redundant=True)}

For a ROOT completion proposal, return exactly one final object of this shape:
{self._decision_schema(completion=True, omit_redundant=True)}

Optional durable control updates - emit only when your live judgment changes them:
{optional_text}

This is one continuing monitor identity. Your prior monitor conversation and persistent files carry
context across wakes. A wake is a navigation signal, not a semantic packet and not an instruction to
inspect. Continue from what you know, retrieve what the current decision needs, and remain silent when
the Agent is proceeding reasonably.

ORIGINAL PUBLIC TASK:
{self.public_task}
"""

    @staticmethod
    def _validated_monitor_history(value: list[Any]) -> list[dict[str, Any]]:
        """Accept only provider-safe public messages from a durable checkpoint."""
        result: list[dict[str, Any]] = []
        for row in value:
            if not isinstance(row, Mapping) or row.get("role") not in {"user", "assistant"}:
                continue
            blocks = row.get("content")
            if not isinstance(blocks, list):
                continue
            safe_blocks = []
            for block in blocks:
                if not isinstance(block, Mapping) or block.get("type") != "text":
                    continue
                text = block.get("text")
                if isinstance(text, str):
                    safe_blocks.append({"type": "text", "text": text})
            if safe_blocks:
                result.append({"role": row["role"], "content": safe_blocks})
        return result

    @staticmethod
    def _stable_json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, default=str, sort_keys=True,
                          separators=(",", ":"))

    def _trajectory_entry(self, packet: Mapping[str, Any]) -> dict[str, Any]:
        calls = packet.get("tool_calls", []) or []
        results = packet.get("tool_results", []) or []
        public_calls = []
        signatures = []
        for call in calls:
            if isinstance(call, Mapping):
                item = {"tool_name": str(call.get("tool_name", "")),
                        "args": call.get("args", {})}
            else:
                item = {"tool_name": "", "args": str(call)}
            public_calls.append(item)
            signatures.append(self._stable_json(item))
        action_signature = hashlib.sha256(
            "\n".join(signatures).encode("utf-8", errors="replace")
        ).hexdigest()[:16]
        prior_count = self.action_occurrences.get(action_signature, 0)
        self.action_occurrences[action_signature] = prior_count + 1
        result_text = self._stable_json(results)
        return {
            "archive_event_id": packet.get("archive_event_id"),
            "archive_sequence": packet.get("archive_sequence"),
            "internal_turn": packet.get("internal_turn"),
            "boundary": packet.get("boundary"),
            "agent_response": str(packet.get("response_content", "")),
            "tool_calls": public_calls,
            "tool_results": list(results),
            "action_fingerprint": action_signature,
            "same_action_seen_before": prior_count,
            "result_fingerprint": hashlib.sha256(
                result_text.encode("utf-8", errors="replace")
            ).hexdigest()[:16],
        }

    def _observe_boundary(self, packet: Mapping[str, Any]) -> bool:
        archive_id = str(packet.get("archive_event_id", ""))
        if archive_id and archive_id in self._observed_archive_ids:
            return False
        entry = self._trajectory_entry(packet)
        self.trajectory.append(entry)
        if archive_id:
            self._observed_archive_ids.add(archive_id)
        if self.artifact_dir:
            with (self.artifact_dir / "public_trajectory.jsonl").open(
                "a", encoding="utf-8"
            ) as stream:
                stream.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        return True

    def observe_archived_boundaries(self, packets: list[Mapping[str, Any]]) -> int:
        """Update the cheap trajectory index without invoking the monitor model."""
        return sum(1 for packet in packets if self._observe_boundary(packet))

    def baseline_observation(self, observed_boundaries: int, *, limit: int = 20,
                             character_budget: int = 24000) -> dict[str, Any]:
        """Return a bounded, deterministic first look at newly indexed public work.

        This is perception, not semantic adjudication: paired intent/result
        boundaries are coalesced by turn and no claim is classified as correct,
        risky, supported, or complete here. The full append-only trajectory stays
        available for autonomous follow-up inspection.
        """
        count = max(0, int(observed_boundaries))
        rows = self.trajectory[-count:] if count else []
        turns: dict[int, dict[str, Any]] = {}
        for row in rows:
            turn = int(row.get("internal_turn") or 0)
            view = self._first_look_trajectory_view(row)
            current = turns.setdefault(turn, {
                "internal_turn": turn, "boundary_types": [], "agent_response": "",
                "tool_calls": [], "tool_results": [],
                "first_archive_sequence": view.get("archive_sequence"),
                "last_archive_sequence": view.get("archive_sequence"),
            })
            sequence = view.get("archive_sequence")
            if sequence is not None:
                if current["first_archive_sequence"] is None:
                    current["first_archive_sequence"] = sequence
                current["last_archive_sequence"] = sequence
            boundary = str(view.get("boundary", ""))
            if boundary and boundary not in current["boundary_types"]:
                current["boundary_types"].append(boundary)
            response = str(view.get("agent_response", ""))
            if response:
                current["agent_response"] = response
            calls = list(view.get("tool_calls") or [])
            results = list(view.get("tool_results") or [])
            # The post-tool boundary normally repeats intent/calls and adds
            # results. Prefer its richer version without duplicating the pair.
            if len(calls) >= len(current["tool_calls"]):
                current["tool_calls"] = calls
            if results:
                current["tool_results"] = results
        ordered = [turns[key] for key in sorted(turns)]
        bounded_limit = min(50, max(1, int(limit)))
        candidates = ordered[-bounded_limit:]
        # Turn count is not an information budget: one file_write can contain
        # an entire source file. Keep a deterministic newest-first directory
        # while full public events remain available through trajectory tools.
        char_budget = max(2000, min(24000, int(character_budget)))
        included_reversed = []
        used = 0
        for item in reversed(candidates):
            size = len(self._stable_json(item))
            if not included_reversed and size > char_budget:
                # Preserve a useful newest-event directory even when an
                # unusually wide tool schema alone exceeds the wake budget.
                item = {
                    "internal_turn": item.get("internal_turn"),
                    "boundary_types": item.get("boundary_types", []),
                    "agent_response": _clip(item.get("agent_response", ""), 1200),
                    "tool_calls": [{
                        "tool_name": call.get("tool_name", ""),
                        "args_fingerprint": call.get("args_fingerprint", ""),
                        "omitted_large_fields": call.get("omitted_large_fields", []),
                    } for call in (item.get("tool_calls") or [])[:8]
                     if isinstance(call, Mapping)],
                    "tool_results": [],
                    "oversize_event_compacted": True,
                }
                size = len(self._stable_json(item))
            if included_reversed and used + size > char_budget:
                break
            included_reversed.append(item)
            used += size
        included = list(reversed(included_reversed))
        return {
            "contract": (
                "Deterministic first-look sensor over public boundaries since the prior "
                "observation. It reports behavior, not correctness. Use tools for exact "
                "task wording, files, tests, diffs, older history, or disputed evidence."
            ),
            "observed_boundaries": len(rows),
            "observed_turns": len(ordered),
            "included_turns": len(included),
            "truncated": len(included) < len(ordered),
            "character_budget": char_budget,
            "included_characters": used,
            "events": included,
        }

    @classmethod
    def _first_look_trajectory_view(cls, row: Mapping[str, Any]) -> dict[str, Any]:
        """Build a navigation view; exact semantic evidence stays retrievable."""
        calls = []
        for raw in (row.get("tool_calls") or [])[:8]:
            if not isinstance(raw, Mapping):
                calls.append({"tool_name": "", "args_preview": _clip(raw, 500)})
                continue
            args = raw.get("args")
            preview: dict[str, Any] = {}
            omitted = []
            if isinstance(args, Mapping):
                for key, value in args.items():
                    if key in {"content", "old_content", "new_content", "patch"}:
                        omitted.append(str(key))
                    elif isinstance(value, (str, int, float, bool)) or value is None:
                        preview[str(key)] = _clip(value, 700)
                    else:
                        preview[str(key)] = _clip(value, 500)
            else:
                preview["value"] = _clip(args, 700)
            calls.append({
                "tool_name": str(raw.get("tool_name", raw.get("name", ""))),
                "args_preview": preview,
                "omitted_large_fields": omitted,
                "args_fingerprint": hashlib.sha256(
                    cls._stable_json(args).encode("utf-8", errors="replace")
                ).hexdigest()[:16],
            })
        return {
            "archive_event_id": row.get("archive_event_id"),
            "archive_sequence": row.get("archive_sequence"),
            "boundary": row.get("boundary"),
            "internal_turn": row.get("internal_turn"),
            "agent_response": _clip(row.get("agent_response", ""), 1600),
            "tool_calls": calls,
            "tool_results": [_clip(item, 1600)
                             for item in (row.get("tool_results") or [])[:4]],
            "action_fingerprint": row.get("action_fingerprint"),
            "result_fingerprint": row.get("result_fingerprint"),
        }

    def bootstrap_task_state(self) -> dict[str, Any]:
        """Initialize durable task cognition before reviewing any execution delta."""
        if self.bootstrap_initialized and self.cognitive_checkpoint:
            return {"status": "restored"}
        prompt = """You are initializing the durable state of a concurrent task monitor before
reviewing any Agent execution. Use only the ORIGINAL PUBLIC TASK below. Do not inspect files, predict
the implementation, judge progress, or send an intervention. Write a compact natural-language task model
that preserves the task's explicit objectives, constraints, completion conditions, and important
relationships without inventing implicit requirements. Everything begins unresolved because no execution
evidence exists. Organize the prose in the form most useful for your own later reasoning; do not create ids
or fill a prescribed ontology. Also leave a concise first-person working note and choose a revisable
initial patrol distance in task turns.

Return exactly one JSON object:
{"task_model":"natural Markdown task understanding for my own future use",
"working_note":"short first-person cognitive handoff",
"observation_plan":{"review_after_turns":20,"focus":"question to revisit","expected_progress":"likely public progress","reason":"why this initial distance is reasonable"},
"notes":"optional short operational note"}

ORIGINAL PUBLIC TASK:
""" + self.public_task
        bootstrap_message = {
            "role": "user", "content": [{"type": "text", "text": prompt}],
        }
        # Turn zero belongs to the same monitor thread.  The immutable H0
        # prefix teaches the monitor how the observation adapter exposes later evidence;
        # the bootstrap response then becomes the first task-specific memory.
        messages = [*self.history, bootstrap_message]
        emit("monitor_context_view", {
            "mode": "turn0_task_bootstrap", "message_count": 1,
            "wire_characters": len(self._stable_json(messages)),
            "trajectory_events_available": len(self.trajectory),
            "monitor_decisions_available": len(self.decisions),
            "inspection_results_in_view": 0,
        })
        raw = "".join(self.session.raw_ask(messages)).strip()
        if not raw or raw.startswith("!!!Error:"):
            raise RuntimeError(f"monitor bootstrap provider failure: {raw[:300] or '<empty>'}")
        self.history.extend([bootstrap_message, {
            "role": "assistant", "content": [{"type": "text", "text": raw}],
        }])
        value = _json_object(raw)
        task_model = str(value.get("task_model", "")).strip()
        note = str(value.get("working_note", "")).strip()
        if not task_model:
            raise ValueError("monitor bootstrap requires a non-empty natural task model")
        if not note:
            raise ValueError("monitor bootstrap requires a working note")
        supplied_plan = value.get("observation_plan")
        if not isinstance(supplied_plan, Mapping):
            supplied_plan = {}
        try:
            requested_turns = int(supplied_plan.get("review_after_turns", 20))
        except (TypeError, ValueError):
            requested_turns = 20
        self.cognitive_checkpoint = {
            "continuation_note": _clip(note, 5000),
            "source_anchors": ["original public task"],
            "reviewed_through_turn": 0,
            "reviewed_through_archive_sequence": 0,
            "attention_mode": "patrol",
            "repair_episode_open": False,
            "decision_index": 0,
            "carried_forward": False,
            "source": "turn0_task_bootstrap",
        }
        self.observation_plan = {
            "review_after_turns": max(1, min(requested_turns, 100)),
            "requested_review_after_turns": requested_turns,
            "focus": str(supplied_plan.get("focus", "")).strip(),
            "expected_progress": str(supplied_plan.get("expected_progress", "")).strip(),
            "reason": str(supplied_plan.get("reason", "")).strip(),
            "updated_turn": 0, "source": "turn0_task_bootstrap",
        }
        self.notes = str(value.get("notes", "")).strip() or self.notes
        semantic_seed = self.semantic_files.initialize_task_model(task_model)
        emit("monitor_semantic_files_initialized", {
            "changed": bool(semantic_seed.get("changed")),
            "ok": bool(semantic_seed.get("ok")),
        })
        self.bootstrap_initialized = True
        state = self._checkpoint_state(0)
        self.checkpoints.save(state)
        if self.artifact_dir:
            self.checkpoints.write_json(self.artifact_dir / "bootstrap_state.json", {
                "schema_version": "m35-monitor-bootstrap/1",
                "public_task_sha256": hashlib.sha256(
                    self.public_task.encode("utf-8", errors="replace")
                ).hexdigest(),
                **state,
            })
        emit("monitor_bootstrap_completed", {
            "review_after_turns": self.observation_plan["review_after_turns"],
            "checkpoint_characters": len(note), "reviewed_through_archive_sequence": 0,
        })
        return {"status": "initialized"}

    def _authority_loss(self, packet: Mapping[str, Any]) -> bool:
        text = str(packet.get("response_content", "")).lower()
        patterns = (
            "original task is unavailable", "original requirements are unavailable",
            "please resend", "cannot access the original", "can't access the original",
            "reconstruct the requirements from", "infer the requirements from",
        )
        return any(pattern in text for pattern in patterns)

    @staticmethod
    def _delegates_root_state(message: str) -> bool:
        lowered = message.lower()
        authority_object = any(term in lowered for term in (
            "root audit", "global audit", "requirements document", "requirement document",
            "clause-by-clause audit", "clause-by-clause mapping", "complete task ledger",
        ))
        delegated_action = any(term in lowered for term in (
            "write", "rewrite", "create", "regenerate", "provide", "produce",
            "enumerate every", "enumerates every", "reconstruct",
        ))
        return authority_object and delegated_action

    @staticmethod
    def _inferred_contested_artifacts(packet: Mapping[str, Any]) -> list[dict[str, Any]]:
        text = str(packet.get("response_content", ""))
        if not re.search(r"audit|requirements?|surrogate|reconstruct|infer", text, re.I):
            return []
        paths = sorted(set(re.findall(
            r"(?:^|[\s`'\"])([A-Za-z0-9_.-]*(?:AUDIT|REQUIREMENTS?)[A-Za-z0-9_.-]*\.md)",
            text, re.I,
        )))
        return [{"path": path, "reason": "Agent-authored task surrogate is provisional evidence",
                 "turn": packet.get("internal_turn")} for path in paths]

    @staticmethod
    def _intervention_signature(decision: Mapping[str, Any]) -> str:
        basis = "\n".join([
            str(decision.get("authority_basis", "")),
            str(decision.get("discrepancy", "")),
            str(decision.get("exit_condition", "")),
        ]).lower()
        basis = re.sub(r"\b\d+\b", "#", basis)
        basis = re.sub(r"\s+", " ", basis).strip()
        return hashlib.sha256(basis.encode("utf-8", errors="replace")).hexdigest()[:16]

    def _recovery_message(self, decision: Mapping[str, Any], *, authority_loss: bool,
                          repeat_count: int) -> str:
        message = str(decision.get("intervention_message", "")).strip()
        # Repetition is evidence for the deliberative monitor, not permission
        # for deterministic code to replace its chosen intervention. Escalate
        # automatically only for observed loss of the original task authority.
        if not authority_loss:
            return message
        self.recovery_level = max(self.recovery_level, 2)
        task = _clip(self.public_task, 24000)
        contaminated = sorted(self.contested_artifacts)
        return "\n".join([
            "[MONITOR AUTHORITATIVE RECOVERY PACKAGE]",
            "The monitor, not Agent-authored audits/tests, owns the root task state.",
            "Authoritative original public task:",
            task,
            "Current supported conflict:",
            str(decision.get("discrepancy", "")).strip() or "See the intervention below.",
            "Contested artifacts excluded from authority:",
            ", ".join(contaminated) if contaminated else "none recorded",
            "Concrete recovery action:",
            str(decision.get("next_safe_action", "")).strip() or message,
            "Release condition:",
            str(decision.get("exit_condition", "")).strip() or "Observable contract-faithful uptake.",
            "Do not reconstruct or rewrite a global requirements/audit document. Repair the concrete",
            "implementation/test/evidence residual above; the monitor will maintain the root audit.",
            "",
            message,
        ]).strip()

    def _inspect_trajectory(self, request: Mapping[str, Any]) -> dict[str, Any]:
        operation = str(request.get("operation", ""))
        if operation == "list_monitor_history_archives":
            directory = self.artifact_dir / "monitor_history_archives" if self.artifact_dir else None
            rows = []
            for path in sorted(directory.glob("compaction_*.json")) if directory and directory.exists() else []:
                try:
                    value = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                rows.append({
                    "id": path.stem, "status": value.get("status"),
                    "internal_turn": value.get("internal_turn"),
                    "history_characters": value.get("history_characters"),
                    "compacted_before_message": value.get("compacted_before_message"),
                })
            return {"ok": True, "archives": rows, "count": len(rows)}
        if operation == "read_monitor_history_archive":
            archive_id = str(request.get("id", "")).strip()
            if not re.fullmatch(r"compaction_\d{4,}", archive_id):
                return {"ok": False, "error": "invalid monitor history archive id"}
            path = (
                self.artifact_dir / "monitor_history_archives" / f"{archive_id}.json"
                if self.artifact_dir else None
            )
            if path is None or not path.exists():
                return {"ok": False, "error": "monitor history archive id not found"}
            text = path.read_text(encoding="utf-8", errors="replace")
            start = max(0, int(request.get("start_char", 0)))
            count = min(
                INSPECTION_RESULT_PAGE_CHARACTERS,
                max(1000, int(request.get(
                    "char_count", INSPECTION_RESULT_PAGE_CHARACTERS
                ))),
            )
            end = min(len(text), start + count)
            response = {
                "ok": True, "id": archive_id, "content": text[start:end],
                "start_char": start, "end_char": end,
                "total_characters": len(text), "truncated": end < len(text),
            }
            if end < len(text):
                response["continuation"] = {
                    "operation": "read_monitor_history_archive", "id": archive_id,
                    "start_char": end, "char_count": count,
                }
            return response
        if operation == "read_inspection_result":
            result_id = str(request.get("id", "")).strip()
            text = self._inspection_result_cache.get(result_id)
            path = (
                self.artifact_dir / "inspection_results" / f"{result_id}.json"
                if self.artifact_dir and result_id else None
            )
            if text is None and path is not None and path.exists():
                text = path.read_text(encoding="utf-8", errors="replace")
                self._inspection_result_cache[result_id] = text
            if text is None:
                return {"ok": False, "error": "inspection result id not found"}
            start = max(0, int(request.get("start_char", 0)))
            count = min(
                INSPECTION_RESULT_PAGE_CHARACTERS,
                max(1000, int(request.get(
                    "char_count", INSPECTION_RESULT_PAGE_CHARACTERS
                ))),
            )
            end = min(len(text), start + count)
            response = {
                "ok": True, "result_id": result_id,
                "content": text[start:end], "start_char": start,
                "end_char": end, "total_characters": len(text),
                "truncated": end < len(text),
            }
            if end < len(text):
                response["continuation"] = {
                    "operation": "read_inspection_result", "id": result_id,
                    "start_char": end, "char_count": count,
                }
            return response
        if operation == "read_original_task":
            return {"ok": True, "public_task": _clip(self.public_task, 50000),
                    "sha256": hashlib.sha256(
                        self.public_task.encode("utf-8", errors="replace")
                    ).hexdigest()}
        if operation == "read_recent_delta":
            requested_limit = max(1, int(request.get("limit", 5)))
            limit = min(20, requested_limit)
            rows = self.trajectory[-limit:]
            observation = self.baseline_observation(
                len(rows), limit=limit, character_budget=9000
            )
            events = list(observation.get("events") or [])
            return {
                "ok": True,
                "contract": (
                    "Newest-end-preserving orientation over recent public activity. "
                    "Events are displayed chronologically after selecting from the newest "
                    "end. Use read_public_trajectory for exact wider evidence."
                ),
                "events": events,
                "requested_limit": requested_limit,
                "effective_boundary_limit": limit,
                "available_boundaries": len(self.trajectory),
                "selected_turns": len(events),
                "first_selected_sequence": (
                    events[0].get("first_archive_sequence") if events else None
                ),
                "last_selected_sequence": (
                    events[-1].get("last_archive_sequence") if events else None
                ),
                "latest_available_sequence": (
                    self.trajectory[-1].get("archive_sequence")
                    if self.trajectory else None
                ),
                "older_recent_content_omitted": bool(observation.get("truncated")),
                "character_budget": observation.get("character_budget"),
                "included_characters": observation.get("included_characters"),
            }
        if operation == "read_repair_episode":
            if not self.open_episode:
                return {"ok": True, "open_episode": None, "events": [], "decisions": []}
            start = int(self.open_episode.get("opened_turn") or 1)
            limit = min(50, max(1, int(request.get("limit", 30))))
            events = [row for row in self.trajectory
                      if int(row.get("internal_turn") or 0) >= start]
            decisions = [row for row in self.decisions
                         if int(row.get("internal_turn") or 0) >= start]
            return {"ok": True, "open_episode": self.open_episode,
                    "events": events[-limit:], "decisions": decisions[-limit:]}
        source = self.decisions if "monitor_decisions" in operation else self.trajectory
        if operation in {"read_public_trajectory", "read_monitor_decisions"}:
            start = max(1, int(request.get("start_turn", 1)))
            end = max(start, int(request.get("end_turn", len(self.trajectory))))
            limit = min(50, max(1, int(request.get("limit", 20))))
            rows = [row for row in source
                    if start <= int(row.get("internal_turn") or 0) <= end]
            return {"ok": True, "events": [self._public_trajectory_view(row) for row in rows[:limit]],
                    "matched": len(rows),
                    "truncated": len(rows) > limit}
        if operation in {"search_public_trajectory", "search_monitor_decisions"}:
            pattern = str(request.get("pattern", "")).strip()
            if not pattern:
                return {"ok": False, "error": "pattern is required"}
            try:
                expression = re.compile(pattern, re.I)
            except re.error as error:
                return {"ok": False, "error": f"invalid regex: {error}"}
            limit = min(50, max(1, int(request.get("limit", 20))))
            rows = [row for row in source
                    if expression.search(self._stable_json(row))]
            return {"ok": True, "events": [self._public_trajectory_view(row) for row in rows[:limit]],
                    "matched": len(rows),
                    "truncated": len(rows) > limit}
        return {"ok": False, "error": f"unsupported trajectory inspection: {operation}"}

    def _bounded_inspection_result(
            self, request: Mapping[str, Any], result: Mapping[str, Any]) -> dict[str, Any]:
        """Archive an exact large result and expose one deterministic, pageable view."""
        serialized = json.dumps(result, ensure_ascii=False, default=str, indent=2)
        if (request.get("operation") == "read_inspection_result"
                or len(serialized) <= INSPECTION_RESULT_ARCHIVE_THRESHOLD):
            return dict(result)
        result_id = hashlib.sha256(
            serialized.encode("utf-8", errors="replace")
        ).hexdigest()[:24]
        self._inspection_result_cache[result_id] = serialized
        if self.artifact_dir:
            directory = self.artifact_dir / "inspection_results"
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / f"{result_id}.json"
            if not path.exists():
                path.write_text(serialized, encoding="utf-8")
        end = min(INSPECTION_RESULT_PAGE_CHARACTERS, len(serialized))
        return {
            "ok": bool(result.get("ok", True)),
            "operation": request.get("operation"),
            "result_id": result_id,
            "content": serialized[:end],
            "start_char": 0,
            "end_char": end,
            "total_characters": len(serialized),
            "truncated": True,
            "continuation": {
                "operation": "read_inspection_result", "id": result_id,
                "start_char": end,
                "char_count": INSPECTION_RESULT_PAGE_CHARACTERS,
            },
        }

    @staticmethod
    def _public_trajectory_view(row: Mapping[str, Any]) -> dict[str, Any]:
        value = dict(row)
        if "agent_response" in value:
            value["agent_response"] = _clip(value["agent_response"], 6000)
        if "tool_results" in value:
            value["tool_results"] = [_clip(item, 6000)
                                     for item in value["tool_results"]]
        return value

    def _inspection_schema(self) -> str:
        return (
            '\n- Monitor list: {"action":"INSPECT","reason":"...","inspection":'
            '{"operation":"list_files","scope":"monitor","path":".","glob":"*","start":0,"limit":200}}'
            '\n- Monitor read: {"action":"INSPECT","reason":"...","inspection":'
            '{"operation":"read_file","scope":"monitor","path":"state/file.md","start":1,"limit":800}}'
            '\n- Monitor search: {"action":"INSPECT","reason":"...","inspection":'
            '{"operation":"search_text","scope":"monitor","path":".","pattern":"regex","glob":"*",'
            '"start":0,"limit":100,"before":0,"after":0}}'
            '\n- Monitor edit: {"action":"INSPECT","reason":"...","inspection":'
            '{"operation":"edit_file","scope":"monitor","path":"state/file.md",'
            '"mode":"create|patch|replace|append|prepend","hash":"hash from read_file for existing files",'
            '"old":"exact text for patch","content":"new content"}}'
            '\n- Public workspace: use operation read_file, list_files, search_text, git_diff, git_status, '
            'list_changed_tests, read_test_change, or search_test_contract without scope=monitor; include only '
            'the path, search, or range fields that operation needs.'
            '\n- Public history: use operation read_original_task, read_recent_delta, read_public_trajectory, '
            'search_public_trajectory, read_monitor_decisions, search_monitor_decisions, read_repair_episode, '
            'read_inspection_result, list_monitor_history_archives, or read_monitor_history_archive; include only '
            'the range or search fields needed.'
        )


    def _inspect_monitor_files(self, request: Mapping[str, Any]) -> dict[str, Any]:
        operation = str(request.get("operation", ""))
        translated = dict(request)
        if operation == "search_text":
            translated["operation"] = "search"
        return self.semantic_files.execute(translated)




    def _decision_schema(self, *, completion: bool = False,
                         omit_redundant: bool = False) -> str:
        prefix = (
            '{"termination_decision":"allow_complete|continue_task",'
            '"intervention_message":"required user-like next instruction for continue_task, empty for allow_complete",'
            if completion else
            '{"intervention_message":"user-like correction injected at the next safe task turn, or empty",'
            '"attention":{"mode":"patrol|focused","reason":"why this observation intensity is appropriate"},'
        )

        base = (
            prefix +
            '"epistemic_status":"confirmed_conflict|unsupported_closure|observed_failure|causal_uncertainty|watch",'
            '"intervention_mode":"repair|discriminating_probe|prevent_irreversible|none","imminent_action_anchor":"public Agent statement/action that makes unresolved uncertainty unsafe to merely watch, otherwise empty",'
            '"reason":"...","public_anchors":["..."],"discrepancy":"... or empty",'
            '"exit_condition":"observable evidence needed before returning to patrol, or empty","authority_basis":"user_contract|safety|correctness_evidence|agent_workflow|none",'
            '"material_task_impact":"specific causal harm if not intervening, or empty","why_silence_is_insufficient":"why one more silent observation is unsafe, or empty",'
            '"evidence_availability":"obtainable_now|environment_blocked|unknown|not_applicable","next_safe_action":"specific executable implementation/test/investigation action, never \'write a root audit\'",'
            '"unresolved_unknown":"explicit residual uncertainty preserved when returning to patrol, otherwise empty","contested_artifacts":[{"path":"public relative path","reason":"contract/evidence conflict"}]'
        )
        if self.m3_human_loop_enabled and not omit_redundant:
            base += (
                ',"decision_focus":{"consequential_decision":"the concrete decision the Agent is '
                'currently making, or none","threatened_transition":"the material transition that '
                'could become unsafe or unsupported, or none","materiality_reversibility":"natural-language '
                'assessment of impact and whether another safe observation remains","control_rationale":"why '
                'the chosen intervention and attention mode best preserve progress now","repair_exit_condition":"observable '
                'condition for ending focused control, or empty"}'
            )
        if self.m3_decision_value_enabled and not omit_redundant:
            base += (
                ',"decision_value":{"live_decision":"decision that another observation could change, '
                'or none","distinguishing_outcomes":"few materially different observable outcomes, '
                'or none","action_sensitivity":"how those outcomes would change control or the next '
                'safe task action","task_impact_and_cost":"qualitative benefit versus delay/attention '
                'cost","exit_or_switch_condition":"observable condition to stop, resume, or change '
                'strategy, or empty"}'
            )
        if self.m3_discriminative_control_enabled and not omit_redundant:
            base += (
                ',"discriminative_step":"one concise first-person working note naming the bounded '
                'comparison I chose, how its outcomes change my next action, and the observable '
                'result after which I will reconsider, or empty"'
            )
        if self.adaptive_review_planning_enabled and not omit_redundant:
            base += (
                ',"observation_plan":{"review_after_turns":"positive integer estimated by you, '
                'not an event class","focus":"open natural-language question to revisit",'
                '"expected_progress":"what may be worth examining then",'
                '"reason":"why this distance preserves progress and situational awareness"}'
            )
        if not omit_redundant:
            base += (
                ',"cognitive_checkpoint":{"continuation_note":"concise first-person working-memory '
                'handoff for the next invocation, not a task summary",'
                '"source_anchors":["few public turn/file/test/diff anchors needed to resume"]}'
            )
        return base + '}'

    def _incremental_inspection_prompt(
            self, entries: list[Mapping[str, Any]], packet: Mapping[str, Any]) -> str:
        """Continue one live review without replaying earlier inspection results."""
        return (
            "[MONITOR CONTINUATION] Continue the same public boundary review from your "
            "existing conversation history. The entries below are only the newly returned "
            "tool result or protocol feedback; all earlier requests/results remain in history "
            "and are intentionally not repeated. You may issue one further INSPECT request or "
            "return the final JSON decision under the previously supplied contract.\n"
            + self._stable_json({
                "boundary": packet.get("boundary"),
                "internal_turn": packet.get("internal_turn"),
                "new_entries": entries,
            })
        )

    def _replace_consumed_archived_results_with_receipts(
            self, review_history_start: int, internal_turn: Any) -> int:
        """Keep cognition while eliding exact, already-consumed tool payloads."""
        replaced = 0
        characters_removed = 0
        result_ids: list[str] = []
        for index in range(max(2, review_history_start), len(self.history)):
            message = self.history[index]
            if message.get("role") != "user":
                continue
            content = message.get("content")
            if not isinstance(content, list) or len(content) != 1:
                continue
            text = content[0].get("text") if isinstance(content[0], Mapping) else None
            if not isinstance(text, str) or not text.startswith("[MONITOR CONTINUATION]"):
                continue
            payload_start = text.find("\n{")
            if payload_start < 0:
                continue
            try:
                payload = json.loads(text[payload_start + 1:])
            except (json.JSONDecodeError, TypeError):
                continue
            entries = payload.get("new_entries")
            if not isinstance(entries, list) or not entries:
                continue
            receipts: list[dict[str, Any]] = []
            safe = True
            for entry in entries:
                if not isinstance(entry, Mapping) or "protocol_feedback" in entry:
                    safe = False
                    break
                request = entry.get("request")
                result = entry.get("result")
                if not isinstance(request, Mapping) or not isinstance(result, Mapping):
                    safe = False
                    break
                operation = str(request.get("operation", ""))
                if operation == "read_monitor_history_archive":
                    result_id = str(result.get("id", ""))
                    archive = (
                        self.artifact_dir / "monitor_history_archives" / f"{result_id}.json"
                    )
                    retrieval_operation = "read_monitor_history_archive"
                else:
                    result_id = str(result.get("result_id", ""))
                    archive = self.artifact_dir / "inspection_results" / f"{result_id}.json"
                    retrieval_operation = "read_inspection_result"
                if not result_id or not archive.is_file():
                    safe = False
                    break
                receipts.append({
                    "request": dict(request),
                    "result": {
                        "ok": bool(result.get("ok", True)),
                        "operation": result.get("operation"),
                        "result_id": result_id,
                        "total_characters": result.get("total_characters"),
                        "exact_retrieval": {
                            "operation": retrieval_operation,
                            "id": result_id,
                            "start_char": 0,
                        },
                    },
                })
                result_ids.append(result_id)
            if not safe:
                continue
            receipt_text = (
                "[MONITOR CONTINUATION — CONSUMED EVIDENCE RECEIPT]\n"
                "You already inspected and reasoned over the exact public evidence below. "
                "Its raw payload remains externally retrievable; your subsequent assistant "
                "judgment and decision remain verbatim in this same history. Re-open the "
                "exact result only if a current judgment depends on omitted detail.\n"
                + self._stable_json({
                    "boundary": payload.get("boundary"),
                    "internal_turn": payload.get("internal_turn"),
                    "archived_inspections": receipts,
                })
            )
            characters_removed += max(0, len(text) - len(receipt_text))
            self.history[index] = {
                **message,
                "content": [{**content[0], "text": receipt_text}],
            }
            replaced += 1
        if replaced:
            self.checkpoints.save(self._checkpoint_state(internal_turn))
            emit("monitor_inspection_payloads_elided", {
                "internal_turn": internal_turn,
                "continuations_replaced": replaced,
                "characters_removed": characters_removed,
                "result_ids": result_ids,
                "open_episode_preserved": self.open_episode is not None,
            })
        return replaced

    def _minimal_wake_prompt(self, packet: Mapping[str, Any]) -> str:
        """Expose only neutral navigation facts; semantic evidence stays pull-based."""
        archive_delta = packet.get("archive_delta")
        cursor = None
        if isinstance(archive_delta, Mapping):
            cursor = archive_delta.get("last_sequence")
        if cursor is None and self.trajectory:
            cursor = self.trajectory[-1].get("archive_sequence")
        inquiry_evidence_advanced = False
        if self.m3_combined_control_enabled and self.discriminative_step:
            previous_cursor = self.discriminative_step.get(
                "reconsidered_archive_sequence",
                self.discriminative_step.get("opened_archive_sequence"),
            )
            try:
                inquiry_evidence_advanced = (
                    cursor is not None and previous_cursor is not None
                    and int(cursor) > int(previous_cursor)
                )
            except (TypeError, ValueError):
                inquiry_evidence_advanced = bool(cursor != previous_cursor)
        completion = packet.get("boundary") == "completion_proposal"
        signal = {
            "boundary": packet.get("boundary"),
            "internal_turn": packet.get("internal_turn"),
            "archive_cursor": cursor,
            "attention_mode": self.attention_mode,
            "repair_episode_open": self.open_episode is not None,
            **({
                "bounded_inquiry_open": self.discriminative_step is not None,
                "public_activity_since_inquiry_review": inquiry_evidence_advanced,
            } if self.m3_combined_control_enabled else {}),
            "wake_reason": (
                "root_completion_proposal" if completion
                else str(
                    packet.get("wake_reason")
                    or (archive_delta.get("review_trigger")
                        if isinstance(archive_delta, Mapping) else "")
                    or "scheduled_monitor_wake"
                )
            ),
        }
        freshness = signal["wake_reason"] == "prepublish_intervention_freshness"
        return (
            "[ROOT COMPLETION WAKE]\n" if completion else "[MONITOR WAKE]\n"
        ) + self._stable_json(signal) + (
            "\nContinue this monitor thread. This is only a completion signal; autonomously "
            "retrieve the public evidence needed for a fresh root-task judgment, then use the "
            "stable root-completion protocol above."
            if completion else (
            "\nYour last nonempty correction has not been delivered yet, and newer public "
            "activity arrived while you were deciding. Re-establish the current situation "
            "from that activity. An empty intervention_message withdraws the pending "
            "correction; a nonempty one replaces it. Use your own judgment and evidence, "
            "not cursor distance alone."
            if freshness else
            "\nContinue the same supervision. Public activity advanced while you were quiet. "
            "Re-establish enough present-tense awareness to judge what changed and how it relates "
            "to your ongoing concern; autonomously choose whether and how to retrieve evidence, "
            "intervene, remain focused, or return to patrol under the stable protocol above."
            + (
                " A bounded inquiry is open and public activity has advanced since its last "
                "review. Determine from public evidence whether its awaited result arrived and, "
                "if so, whether further inquiry could still change the root-task decision; close, "
                "narrow, or replace the inquiry accordingly."
                if inquiry_evidence_advanced else ""
            )
            )
        )

    @staticmethod
    def _inquiry_text(inquiry: Mapping[str, Any] | None) -> str:
        if not inquiry:
            return ""
        if inquiry.get("working_inquiry"):
            return str(inquiry["working_inquiry"]).strip()
        return " | ".join(
            str(inquiry.get(key, "")).strip()
            for key in (
                "live_uncertainty", "action_relevant_alternatives",
                "next_observation", "outcome_to_action", "reconsider_after",
            )
            if str(inquiry.get(key, "")).strip()
        )

    def _close_inquiry(self, inquiry: Mapping[str, Any] | None, *,
                       packet: Mapping[str, Any], decision: Mapping[str, Any],
                       status: str) -> None:
        """Archive navigation facts for a closed local inquiry, not a verdict."""
        text = self._inquiry_text(inquiry)
        if not text:
            return
        self.last_closed_inquiry = {
            "inquiry": _clip(text, 3000),
            "status": status,
            "opened_turn": inquiry.get("opened_turn", inquiry.get("updated_turn")),
            "closed_turn": packet.get("internal_turn"),
            "opened_archive_sequence": inquiry.get("opened_archive_sequence"),
            "closed_archive_sequence": (
                (packet.get("archive_delta") or {}).get("last_sequence")
                if isinstance(packet.get("archive_delta"), Mapping) else None
            ),
            "resolution_reason": _clip(decision.get("reason", ""), 1800),
            "public_anchors": list(decision.get("public_anchors", []))[:12],
            "root_task_still_requires_independent_completion": True,
        }




    def _prompt(self, packet: Mapping[str, Any], inspection_results: list[dict[str, Any]]) -> str:
        return self._minimal_wake_prompt(packet)

    def _ask(self, prompt: str) -> dict[str, Any]:
        if hasattr(self.session, "reasoning_effort"):
            self.session.reasoning_effort = (
                self.deep_reasoning_effort if self.attention_mode == "focused"
                else self.shadow_reasoning_effort
            )
        user_message = {"role": "user", "content": [{"type": "text", "text": prompt}]}
        # The same monitor conversation carries cognitive continuity. Task
        # evidence remains external unless this monitor retrieves it.
        messages = [*self.history, user_message]
        wire_characters = len(json.dumps(
            messages, ensure_ascii=False, default=str, separators=(",", ":")
        ))
        emit("monitor_context_view", {
            "mode": "persistent_history_minimal_frontstage",
            "message_count": len(messages),
            "wire_characters": wire_characters,
            "trajectory_events_available": len(self.trajectory),
            "monitor_decisions_available": len(self.decisions),
            "inspection_results_in_view": prompt.count('"request"'),
        })
        raw = "".join(self.session.raw_ask(messages)).strip()
        self.last_raw = raw
        if not raw or raw.startswith("!!!Error:"):
            raise RuntimeError(f"monitor provider failure: {raw[:300] or '<empty>'}")
        self.history.extend([user_message, {
            "role": "assistant", "content": [{"type": "text", "text": raw}],
        }])
        # Save after every completed provider call. A later parse or protocol
        # failure must not erase what this monitor actually saw.
        self.checkpoints.save(self._checkpoint_state(None))
        try:
            value = _json_object(raw)
        except (json.JSONDecodeError, ValueError) as error:
            # A malformed monitor envelope must not silently erase an otherwise
            # useful control boundary. Ask once for a concise serialization of
            # the same judgment; this is protocol recovery, not new evidence or
            # a second deliberation opportunity.
            emit("monitor_protocol_retry", {
                "error_type": type(error).__name__,
                "error": str(error)[:500],
                "raw_characters": len(raw),
            })
            retry = {
                "role": "user",
                "content": [{"type": "text", "text": (
                    "[PROTOCOL RETRY] Your preceding monitor decision was not valid JSON. "
                    "Serialize the same judgment again as one concise JSON object matching the "
                    "required schema. Do not inspect, reconsider, or add evidence. Keep strings "
                    "brief, omit optional prose, and output JSON only."
                )}],
            }
            retry_messages = [*self.history, retry]
            retry_raw = "".join(self.session.raw_ask(retry_messages)).strip()
            self.last_raw = retry_raw
            if not retry_raw or retry_raw.startswith("!!!Error:"):
                raise RuntimeError(
                    f"monitor protocol retry provider failure: {retry_raw[:300] or '<empty>'}"
                ) from error
            self.history.extend([retry, {
                "role": "assistant", "content": [{"type": "text", "text": _clip(
                    retry_raw, 12000
                )}],
            }])
            self.checkpoints.save(self._checkpoint_state(None))
            value = _json_object(retry_raw)
            emit("monitor_protocol_recovered", {
                "original_error_type": type(error).__name__,
                "retry_characters": len(retry_raw),
                "task_execution_blocked": False,
            })
        for key in ("decision", "control_decision", "result"):
            if not any(value.get(name) for name in (
                    "action", "attention", "intervention_message", "termination_decision"
            )) and isinstance(value.get(key), Mapping):
                value = dict(value[key])
                break
        return value

    def _history_characters(self) -> int:
        return len(json.dumps(
            self.history, ensure_ascii=False, default=str, separators=(",", ":")
        ))

    def _bound_history_for_next_call(self) -> bool:
        """Keep cognitive continuation while externalizing exact old dialogue.

        This is a deterministic storage operation, not a semantic summarizer.
        The model's own latest working note remains foreground; exact omitted
        dialogue stays retrievable from the history archive.
        """
        if (self.attention_mode == "focused"
                or self.open_episode is not None
                or self._history_characters() <= self.history_soft_char_limit
                ):
            return False
        before = copy.deepcopy(self.history)
        self.history_compaction_count += 1
        archive_dir = self.artifact_dir / "monitor_history_archives"
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive_path = archive_dir / (
            f"compaction_{self.history_compaction_count:04d}.json"
        )
        before_characters = self._history_characters()
        self.checkpoints.write_json(archive_path, {
            "schema_version": "m35-monitor-history-archive/1",
            "compaction_index": self.history_compaction_count,
            "history_characters": before_characters,
            "full_history": before,
            "status": "deterministic_externalization",
        })
        checkpoint = self.cognitive_checkpoint or {}
        working_note = str(checkpoint.get("continuation_note", "")).strip()
        if not working_note:
            working_note = str(self.notes).strip()
        if self.open_episode is not None:
            residual = str(self.open_episode.get("current_residual", "")).strip()
            exit_condition = str(
                self.open_episode.get("current_exit_condition", "")
            ).strip()
            if residual:
                working_note += " I am still following this repair: " + residual
            if exit_condition:
                working_note += " I will release it when: " + exit_condition
        memory = {
            "role": "user", "content": [{"type": "text", "text": (
                "[MONITOR CONTINUITY] Exact older dialogue is archived at "
                f"{archive_path.name}. Continue from your own working state below; "
                "retrieve exact history only when the current judgment depends on it.\n"
                + _clip(working_note, 8000)
            )}],
        }
        ack = {
            "role": "assistant", "content": [{"type": "text", "text": (
                "I will continue from this working state and actively retrieve omitted "
                "evidence only when it can change the current decision."
            )}],
        }
        # H0 already survives verbatim in ``self.history[:2]``.  Never copy it
        # into the recent tail as well when a short history contains one very
        # large inspection result.
        tail_start = max(2, len(self.history) - 8)
        tail = copy.deepcopy(self.history[tail_start:])
        for message in tail:
            for content in message.get("content", []) if isinstance(message, Mapping) else []:
                if isinstance(content, Mapping) and len(str(content.get("text", ""))) > 16000:
                    text = str(content.get("text", ""))
                    content["text"] = (
                        "[EXACT MESSAGE EXTERNALIZED TO " + archive_path.name + "]\n"
                        + _clip(text, 4000)
                    )
        self.history = self.history[:2] + [memory, ack] + tail
        self.history_review_starts = []
        self.open_episode_history_start = 2 if self.open_episode is not None else None
        self.checkpoints.save(self._checkpoint_state(None))
        emit("monitor_history_bounded", {
            "compaction_index": self.history_compaction_count,
            "before_characters": before_characters,
            "after_characters": self._history_characters(),
            "open_episode_preserved": self.open_episode is not None,
            "archive": str(archive_path),
        })
        return True


    def _refresh_cognitive_checkpoint(
            self, decision: Mapping[str, Any], normalized: Mapping[str, Any],
            packet: Mapping[str, Any]) -> None:
        """Persist a compact public working-state handoff, never hidden reasoning."""
        supplied = decision.get("cognitive_checkpoint")
        note = ""
        anchors: list[str] = []
        if isinstance(supplied, Mapping):
            note = str(supplied.get("continuation_note", "")).strip()
            raw_anchors = supplied.get("source_anchors", [])
            if isinstance(raw_anchors, list):
                anchors = [str(item).strip() for item in raw_anchors
                           if str(item).strip()][:12]
        if not note:
            # Missing optional handoff must not block the task. Carry forward
            # the last cognitive frame explicitly as stale instead of silently
            # pretending it incorporated this review.
            previous = self.cognitive_checkpoint or {}
            note = str(previous.get("continuation_note", "")).strip()
            if not anchors:
                anchors = list(previous.get("source_anchors", []))[:12]
            carried_forward = bool(note)
        else:
            carried_forward = False
        if not note:
            # Recovery seed for old checkpoints and protocol-compatible models.
            # This is composed only from the public final decision, not hidden
            # reasoning, and will be replaced by the next authored handoff.
            parts = [
                str(normalized.get("reason", "")).strip(),
                str(normalized.get("discrepancy", "")).strip(),
                str(normalized.get("unresolved_unknown", "")).strip(),
                str(normalized.get("exit_condition", "")).strip(),
            ]
            note = " ".join(part for part in parts if part) or (
                "No material concern is active; resume patrol from the next public delta."
            )
            anchors = anchors or [
                str(item) for item in normalized.get("public_anchors", [])
            ][:12]
            carried_forward = False
        archive_delta = packet.get("archive_delta")
        reviewed_sequence = None
        if isinstance(archive_delta, Mapping):
            reviewed_sequence = archive_delta.get("last_sequence")
        if reviewed_sequence is None and self.trajectory:
            reviewed_sequence = self.trajectory[-1].get("archive_sequence")
        self.cognitive_checkpoint = {
            "continuation_note": _clip(note, 5000),
            "source_anchors": anchors,
            "reviewed_through_turn": packet.get("internal_turn"),
            "reviewed_through_archive_sequence": reviewed_sequence,
            "attention_mode": self.attention_mode,
            "repair_episode_open": self.open_episode is not None,
            "decision_index": len(self.decisions) + 1,
            "carried_forward": carried_forward,
        }
        emit("monitor_cognitive_checkpoint_updated", {
            "internal_turn": packet.get("internal_turn"),
            "reviewed_through_archive_sequence": reviewed_sequence,
            "attention_mode": self.attention_mode,
            "repair_episode_open": self.open_episode is not None,
            "carried_forward": carried_forward,
            "characters": len(str(self.cognitive_checkpoint["continuation_note"])),
        })

    def _record(self, decision: dict[str, Any], packet: Mapping[str, Any]) -> None:
        transaction_id = f"decision:{len(self.decisions) + 1:04d}"
        row = {
            "schema_version": "m0-monitor-decision/2",
            "state_transaction_id": transaction_id,
            "internal_turn": packet.get("internal_turn"), **decision,
        }
        self.decisions.append(row)
        if self.artifact_dir:
            index = len(self.decisions)
            self.checkpoints.write_json(
                self.artifact_dir / f"decision_{index:04d}.json", row
            )
            self._write_authoritative_state(packet.get("internal_turn"))
        self.checkpoints.save(self._checkpoint_state(packet.get("internal_turn")))
        emit("m0_monitor_decision", row)

    def _write_authoritative_state(self, internal_turn: Any) -> None:
        if not self.artifact_dir:
            return
        self.checkpoints.write_json(
            self.artifact_dir / "authoritative_state.json",
            {
                "schema_version": "monitor-authoritative-state/3",
                "public_task_sha256": hashlib.sha256(
                    self.public_task.encode("utf-8", errors="replace")
                ).hexdigest(),
                "state_transaction_id": f"decision:{len(self.decisions):04d}",
                "root_completion_basis": self.root_completion_basis,
                "contested_artifacts": self.contested_artifacts,
                "open_repair_episode": self.open_episode,
                "pending_discriminating_probe": self.pending_discriminating_probe,
                **({"m3_decision_focus": self.decision_focus}
                   if self.m3_human_loop_enabled else {}),
                **({
                    "m3_decision_value_enabled": True,
                    "m3_decision_value": self.decision_value,
                } if self.m3_decision_value_enabled else {}),
                **({
                    "m3_discriminative_control_enabled": True,
                    "m3_discriminative_step": self.discriminative_step,
                } if self.m3_discriminative_control_enabled else {}),
                **({
                    "m3_combined_control_enabled": True,
                    "m3d_last_closed_inquiry": self.last_closed_inquiry,
                } if self.m3_combined_control_enabled else {}),
                "observation_plan": self.observation_plan,
                "cognitive_checkpoint": self.cognitive_checkpoint,
                "recovery_level": self.recovery_level,
                "last_internal_turn": internal_turn,
            },
        )

    def review(self, packet: Mapping[str, Any]) -> str:
        """Run one review with rollback around all semantic control state."""
        fields = (
            "notes", "root_completion_basis",
            "contested_artifacts", "open_episode", "open_episode_history_start",
            "pending_discriminating_probe", "attention_mode", "decision_focus",
            "decision_value", "discriminative_step", "last_closed_inquiry",
            "observation_plan", "last_closed_repair",
            "cognitive_checkpoint", "bootstrap_initialized", "recovery_level",
            "history", "history_review_starts", "history_compaction_count",
            "decisions", "intervention_signatures", "last_intervention_delivery",
        )
        snapshot = {name: copy.deepcopy(getattr(self, name)) for name in fields}
        try:
            result = self._review_transaction(packet)
        except BaseException as error:
            for name, value in snapshot.items():
                setattr(self, name, value)
            try:
                self.checkpoints.save(self._checkpoint_state(packet.get("internal_turn")))
                self._write_authoritative_state(packet.get("internal_turn"))
            except BaseException as rollback_error:
                emit("monitor_transaction_rollback_persist_failed", {
                    "error_type": type(rollback_error).__name__,
                    "error": str(rollback_error)[:1000],
                })
            emit("monitor_transaction_rolled_back", {
                "internal_turn": packet.get("internal_turn"),
                "error_type": type(error).__name__, "error": str(error)[:1000],
            })
            raise
        return result

    def _review_transaction(self, packet: Mapping[str, Any]) -> str:
        self.last_intervention_delivery = None
        if not packet.get("archive_wake_only"):
            self._observe_boundary(packet)
        inspections: list[dict[str, Any]] = []
        delivered_inspections = 0
        # Compaction changes history indices.  Establish the bounded history
        # before recording this review's live range, so inspection receipts and
        # an episode opened below always point into the same coordinate space.
        self._bound_history_for_next_call()
        review_history_start = len(self.history)
        self.history_review_starts.append(review_history_start)
        inspection_count = 0
        protocol_failures = 0
        while inspection_count <= self.max_inspections:
            try:
                if inspections:
                    newly_available = inspections[delivered_inspections:]
                    prompt = self._incremental_inspection_prompt(
                        newly_available, packet
                    )
                    delivered_inspections = len(inspections)
                else:
                    prompt = self._prompt(packet, inspections)
                decision = self._ask(prompt)
            except (ValueError, json.JSONDecodeError) as error:
                protocol_failures += 1
                inspections.append({
                    "protocol_feedback": (
                        f"Your previous response was not a valid monitor JSON decision: {error}. "
                        "Return exactly one documented INSPECT or final decision object."
                    ),
                    "invalid_response_excerpt": _clip(self.last_raw, 4000),
                })
                if protocol_failures <= 2:
                    continue
                return self._protocol_fallback(packet, inspections, str(error))
            # The preceding provider call has now consumed every continuation
            # result delivered before it. Replace only those exact archived
            # payload previews immediately, so a long multi-tool review does
            # not carry them through all later calls in the same repair.
            try:
                self._replace_consumed_archived_results_with_receipts(
                    review_history_start, packet.get("internal_turn")
                )
            except BaseException as error:
                emit("monitor_inspection_elision_failed", {
                    "internal_turn": packet.get("internal_turn"),
                    "error_type": type(error).__name__,
                    "error": str(error)[:1000],
                    "intervention_preserved": bool(
                        str(decision.get("intervention_message", "")).strip()
                    ),
                    "task_execution_blocked": False,
                })
            operation = str(decision.get("action", "")).upper()
            if operation == "INSPECT":
                self.attention_mode = "focused"
                inspection_count += 1
                request = decision.get("inspection")
                if not isinstance(request, Mapping):
                    inspections.append({"ok": False, "error": "missing inspection object"})
                else:
                    operation = str(request.get("operation", ""))
                    monitor_file_operation = (
                        str(request.get("scope", "")).strip().lower() == "monitor"
                        or operation == "edit_file"
                    )
                    if monitor_file_operation:
                        result = self._inspect_monitor_files(request)
                    elif operation in TRAJECTORY_INSPECTIONS:
                        result = self._inspect_trajectory(request)
                    else:
                        result = self.inspector.execute(request)
                    result = self._bounded_inspection_result(request, result)
                    inspections.append({"request": dict(request), "result": result})
                continue
            completion_boundary = packet.get("boundary") == "completion_proposal"
            termination_decision = str(
                decision.get("termination_decision", "")
            ).strip().lower()
            attention = decision.get("attention")
            if completion_boundary:
                attention_mode = (
                    "focused" if termination_decision == "continue_task" else "patrol"
                )
                attention = {
                    "mode": attention_mode,
                    "reason": "root completion boundary decision",
                }
            else:
                attention_mode = (
                    str(attention.get("mode", "")).strip().lower()
                    if isinstance(attention, Mapping) else ""
                )
            intervention_message = str(
                decision.get("intervention_message", "")
            ).strip()
            intervening = bool(intervention_message)
            # A present native-v2 attention object with an empty mode is a
            # recoverable serialization omission, not a reason to discard an
            # otherwise valid judgment. Preserve focused follow-up when it is
            # already active; any real intervention necessarily enters focus.
            # Missing attention objects and legacy action envelopes still go
            # through the strict protocol-retry path below.
            if (not completion_boundary and isinstance(attention, Mapping)
                    and not attention_mode):
                attention_mode = (
                    "focused" if intervening or self.attention_mode == "focused"
                    or self.open_episode is not None else "patrol"
                )
                emit("monitor_attention_mode_recovered", {
                    "internal_turn": packet.get("internal_turn"),
                    "recovered_mode": attention_mode,
                    "intervention_present": intervening,
                    "open_repair_episode": self.open_episode is not None,
                    "previous_attention_mode": self.attention_mode,
                })
            if completion_boundary and termination_decision not in {
                "allow_complete", "continue_task"
            }:
                protocol_failures += 1
                inspections.append({
                    "protocol_feedback": (
                        "A completion decision requires termination_decision="
                        "allow_complete or continue_task."
                    ),
                    "invalid_response_excerpt": _clip(self.last_raw, 4000),
                })
                if protocol_failures <= 2:
                    continue
                return self._protocol_fallback(
                    packet, inspections, "invalid completion termination decision"
                )
            if completion_boundary and (
                    (termination_decision == "continue_task") != intervening):
                protocol_failures += 1
                inspections.append({
                    "protocol_feedback": (
                        "continue_task requires a non-empty intervention_message; "
                        "allow_complete requires it to be empty."
                    ),
                    "invalid_response_excerpt": _clip(self.last_raw, 4000),
                })
                if protocol_failures <= 2:
                    continue
                return self._protocol_fallback(
                    packet, inspections, "completion message/decision mismatch"
                )
            if attention_mode not in ATTENTION_MODES:
                protocol_failures += 1
                inspections.append({
                    "protocol_feedback": (
                        f"Invalid or missing attention.mode {attention_mode!r}. Return either "
                        "patrol or focused in the documented final-decision schema."
                    ),
                    "invalid_response_excerpt": _clip(self.last_raw, 4000),
                })
                if protocol_failures <= 2:
                    continue
                return self._protocol_fallback(
                    packet, inspections, f"invalid attention mode {attention_mode!r}"
                )
            if intervening and attention_mode != "focused":
                protocol_failures += 1
                inspections.append({
                    "protocol_feedback": (
                        "A non-empty intervention_message starts or continues corrective follow-up; "
                        "set attention.mode=focused."
                    ),
                    "invalid_response_excerpt": _clip(self.last_raw, 4000),
                })
                if protocol_failures <= 2:
                    continue
                return self._protocol_fallback(
                    packet, inspections, "intervention attempted without focused attention"
                )
            if intervening and self._delegates_root_state(intervention_message):
                protocol_failures += 1
                inspections.append({
                    "protocol_feedback": (
                        "Do not delegate the authoritative root audit or task reconstruction to the "
                        "task Agent. You own that ledger. Replace this with a concrete, batched recovery "
                        "message containing the relevant original clause, affected artifacts, executable "
                        "repair/investigation actions, and release evidence."
                    ),
                    "invalid_response_excerpt": _clip(self.last_raw, 4000),
                })
                if protocol_failures <= 2:
                    continue
                return self._protocol_fallback(packet, inspections, "delegated authoritative audit")
            epistemic_status = str(decision.get("epistemic_status", "")).strip()
            intervention_mode = str(decision.get("intervention_mode", "none")).strip()
            imminent_anchor = str(decision.get("imminent_action_anchor", "")).strip()
            if epistemic_status not in {
                "confirmed_conflict", "unsupported_closure", "observed_failure",
                "causal_uncertainty", "watch"
            }:
                protocol_failures += 1
                inspections.append({
                    "protocol_feedback": (
                        "Classify epistemic_status as confirmed_conflict, unsupported_closure, "
                        "observed_failure, causal_uncertainty, or watch. Do not convert a "
                        "hypothesis into a conflict."
                    ),
                    "invalid_response_excerpt": _clip(self.last_raw, 4000),
                })
                if protocol_failures <= 2:
                    continue
                return self._protocol_fallback(packet, inspections, "missing epistemic classification")
            if intervening and epistemic_status == "watch":
                protocol_failures += 1
                inspections.append({
                    "protocol_feedback": (
                        "A watch-level risk does not justify messaging the Agent. Preserve it in notes "
                        "and continue observing unless new public evidence raises its status."
                    ),
                    "invalid_response_excerpt": _clip(self.last_raw, 4000),
                })
                if protocol_failures <= 2:
                    continue
                return self._protocol_fallback(packet, inspections, "watch hypothesis attempted intervention")
            if intervening and epistemic_status == "causal_uncertainty" and (
                intervention_mode != "discriminating_probe" or not imminent_anchor
            ):
                protocol_failures += 1
                inspections.append({
                    "protocol_feedback": (
                        "Causal uncertainty justifies an intervention only to prevent a publicly anchored material "
                        "change/closure and request or reassert a bounded discriminating probe. Set "
                        "intervention_mode=discriminating_probe and cite the imminent Agent action; "
                        "otherwise preserve watch and keep observing. Pending-probe memory informs this judgment but "
                        "does not prohibit re-correction when the Agent abandons, weakens, misunderstands, "
                        "or closes over the requested comparison."
                    ),
                    "invalid_response_excerpt": _clip(self.last_raw, 4000),
                })
                if protocol_failures <= 2:
                    continue
                return self._protocol_fallback(packet, inspections, "uncertainty intervention lacks a bounded public anchor")
            if intervening and (
                str(decision.get("authority_basis", "")).strip() in {"", "agent_workflow", "none"}
                or not str(decision.get("material_task_impact", "")).strip()
                or not str(decision.get("why_silence_is_insufficient", "")).strip()
            ):
                protocol_failures += 1
                inspections.append({
                    "protocol_feedback": (
                        "An intervention requires non-workflow authority, a concrete material task impact, and "
                        "an evidence-based reason one more silent observation is unsafe. Agent SOP or "
                        "workflow noncompliance alone must remain an unmessaged watch item."
                    ),
                    "invalid_response_excerpt": _clip(self.last_raw, 4000),
                })
                if protocol_failures <= 2:
                    continue
                return self._protocol_fallback(packet, inspections, "intervention failed authority/materiality audit")
            if packet.get("boundary") == "completion_proposal" and intervening and (
                str(decision.get("evidence_availability", "")).strip() != "obtainable_now"
                or not str(decision.get("next_safe_action", "")).strip()
            ):
                protocol_failures += 1
                inspections.append({
                    "protocol_feedback": (
                        "At completion, continue_task requires a concrete safe action that is executable "
                        "now and can produce stronger public evidence. If evidence is blocked by the "
                        "public environment and the Agent accurately preserves UNKNOWN, allow completion "
                        "with evidence_availability=environment_blocked and unresolved_unknown populated. "
                        "Allowing completion with UNKNOWN does not certify correctness."
                    ),
                    "invalid_response_excerpt": _clip(self.last_raw, 4000),
                })
                if protocol_failures <= 2:
                    continue
                return self._protocol_fallback(packet, inspections, "terminal intervention lacks an executable action")
            contested = []
            for item in decision.get("contested_artifacts", []) or []:
                if isinstance(item, Mapping) and str(item.get("path", "")).strip():
                    contested.append({
                        "path": str(item["path"]).strip(),
                        "reason": str(item.get("reason", "")).strip(),
                        "turn": packet.get("internal_turn"),
                    })
            contested.extend(self._inferred_contested_artifacts(packet))
            normalized = {
                "intervention_message": intervention_message,
                "attention": {
                    "mode": attention_mode,
                    "reason": str(attention.get("reason", "")).strip(),
                },
                "epistemic_status": epistemic_status,
                "intervention_mode": intervention_mode,
                "imminent_action_anchor": imminent_anchor,
                "reason": str(decision.get("reason", "")).strip(),
                "public_anchors": list(decision.get("public_anchors", [])),
                "discrepancy": str(decision.get("discrepancy", "")).strip(),
                "exit_condition": str(decision.get("exit_condition", "")).strip(),
                "authority_basis": str(decision.get("authority_basis", "none")).strip(),
                "material_task_impact": str(decision.get("material_task_impact", "")).strip(),
                "why_silence_is_insufficient": str(decision.get("why_silence_is_insufficient", "")).strip(),
                "evidence_availability": str(decision.get("evidence_availability", "not_applicable")).strip(),
                "next_safe_action": str(decision.get("next_safe_action", "")).strip(),
                "unresolved_unknown": str(decision.get("unresolved_unknown", "")).strip(),
                "contested_artifacts": contested,
                "notes": str(decision.get("notes", "")).strip() or self.notes,
                "inspections": inspections,
            }
            if completion_boundary:
                normalized["termination_decision"] = termination_decision
            if self.m3_human_loop_enabled:
                supplied_focus = decision.get("decision_focus")
                if isinstance(supplied_focus, Mapping):
                    focus = {
                        key: str(supplied_focus.get(key, "")).strip()
                        for key in (
                            "consequential_decision", "threatened_transition",
                            "materiality_reversibility", "control_rationale",
                            "repair_exit_condition",
                        )
                    }
                    focus["updated_turn"] = packet.get("internal_turn")
                    focus["attention_mode"] = attention_mode
                    focus["intervened"] = intervening
                    self.decision_focus = focus
                    normalized["decision_focus"] = self.decision_focus
            if self.m3_decision_value_enabled:
                supplied_value = decision.get("decision_value")
                if isinstance(supplied_value, Mapping):
                    value = {
                        key: str(supplied_value.get(key, "")).strip()
                        for key in (
                            "live_decision", "distinguishing_outcomes",
                            "action_sensitivity", "task_impact_and_cost",
                            "exit_or_switch_condition",
                        )
                    }
                    value["updated_turn"] = packet.get("internal_turn")
                    value["attention_mode"] = attention_mode
                    value["intervened"] = intervening
                    self.decision_value = value
                    normalized["decision_value"] = self.decision_value
            if self.m3_discriminative_control_enabled:
                previous_step = copy.deepcopy(self.discriminative_step)
                inquiry_transition = "carried" if previous_step else "none"
                supplied_step = decision.get("discriminative_step")
                archive_delta = packet.get("archive_delta")
                current_archive_sequence = (
                    archive_delta.get("last_sequence")
                    if isinstance(archive_delta, Mapping) else None
                )
                if isinstance(supplied_step, str):
                    working_inquiry = supplied_step.strip()
                    if working_inquiry:
                        same_inquiry = (
                            self._inquiry_text(previous_step) == working_inquiry
                        )
                        if previous_step and not same_inquiry and self.m3_combined_control_enabled:
                            self._close_inquiry(
                                previous_step, packet=packet, decision=normalized,
                                status="switched",
                            )
                        inquiry_transition = "reconsidered" if same_inquiry else (
                            "switched" if previous_step else "opened"
                        )
                        self.discriminative_step = {
                            "working_inquiry": working_inquiry,
                            "opened_turn": (
                                previous_step.get("opened_turn", previous_step.get("updated_turn"))
                                if same_inquiry and previous_step else packet.get("internal_turn")
                            ),
                            "opened_archive_sequence": (
                                previous_step.get("opened_archive_sequence")
                                if same_inquiry and previous_step else current_archive_sequence
                            ),
                            "reconsidered_archive_sequence": current_archive_sequence,
                            "updated_turn": packet.get("internal_turn"),
                            "attention_mode": attention_mode,
                            "intervened": intervening,
                        }
                    else:
                        if previous_step and self.m3_combined_control_enabled:
                            self._close_inquiry(
                                previous_step, packet=packet, decision=normalized,
                                status="decision_sufficient",
                            )
                        inquiry_transition = "closed" if previous_step else "none"
                        self.discriminative_step = None
                    normalized["discriminative_step"] = self.discriminative_step
                elif isinstance(supplied_step, Mapping):
                    step = {
                        key: str(supplied_step.get(key, "")).strip()
                        for key in (
                            "live_uncertainty", "action_relevant_alternatives",
                            "next_observation", "outcome_to_action",
                            "reconsider_after",
                        )
                    }
                    step["updated_turn"] = packet.get("internal_turn")
                    step["attention_mode"] = attention_mode
                    step["intervened"] = intervening
                    substantive = any(step[key] for key in (
                        "live_uncertainty", "action_relevant_alternatives",
                        "next_observation", "outcome_to_action",
                    ))
                    if substantive:
                        same_inquiry = (
                            self._inquiry_text(previous_step) == self._inquiry_text(step)
                        )
                        if previous_step and not same_inquiry and self.m3_combined_control_enabled:
                            self._close_inquiry(
                                previous_step, packet=packet, decision=normalized,
                                status="switched",
                            )
                        inquiry_transition = "reconsidered" if same_inquiry else (
                            "switched" if previous_step else "opened"
                        )
                        step["opened_turn"] = (
                            previous_step.get("opened_turn", previous_step.get("updated_turn"))
                            if same_inquiry and previous_step else packet.get("internal_turn")
                        )
                        step["opened_archive_sequence"] = (
                            previous_step.get("opened_archive_sequence")
                            if same_inquiry and previous_step else current_archive_sequence
                        )
                        step["reconsidered_archive_sequence"] = current_archive_sequence
                        self.discriminative_step = step
                    else:
                        if previous_step and self.m3_combined_control_enabled:
                            self._close_inquiry(
                                previous_step, packet=packet, decision=normalized,
                                status="decision_sufficient",
                            )
                        inquiry_transition = "closed" if previous_step else "none"
                        self.discriminative_step = None
                    normalized["discriminative_step"] = self.discriminative_step
                if self.m3_combined_control_enabled:
                    normalized["m3d_inquiry_transition"] = inquiry_transition
            if self.adaptive_review_planning_enabled:
                supplied_plan = decision.get("observation_plan")
                if isinstance(supplied_plan, Mapping):
                    try:
                        requested_turns = int(supplied_plan.get("review_after_turns", 20))
                    except (TypeError, ValueError):
                        requested_turns = 20
                    # This is only a recovery-safe maximum sleep bound. Within
                    # it, cadence is entirely monitor-authored and may change
                    # after every semantic patrol.
                    effective_turns = max(1, min(requested_turns, 100))
                    self.observation_plan = {
                        "review_after_turns": effective_turns,
                        "requested_review_after_turns": requested_turns,
                        "focus": str(supplied_plan.get("focus", "")).strip(),
                        "expected_progress": str(
                            supplied_plan.get("expected_progress", "")
                        ).strip(),
                        "reason": str(supplied_plan.get("reason", "")).strip(),
                        "updated_turn": packet.get("internal_turn"),
                        "source": "monitor",
                    }
                    normalized["observation_plan"] = self.observation_plan
            self.notes = normalized["notes"]
            for item in contested:
                self.contested_artifacts[item["path"]] = item
            if packet.get("boundary") == "completion_proposal":
                if intervening:
                    self.root_completion_basis = (
                        "Root completion must continue. "
                        + (normalized["exit_condition"] or normalized["discrepancy"])
                    )
                else:
                    self.root_completion_basis = (
                        "Root completion was allowed after the monitor's fresh task-wide review."
                    )
            previous_attention = self.attention_mode
            self.attention_mode = attention_mode
            normalized["attention_transition"] = (
                f"{previous_attention}->{attention_mode}"
                if previous_attention != attention_mode else "unchanged"
            )
            if intervening:
                signature = self._intervention_signature(normalized)
                repeat_count = self.intervention_signatures.get(signature, 0) + 1
                self.intervention_signatures[signature] = repeat_count
                normalized["intervention_signature"] = signature
                normalized["intervention_repeat_count"] = repeat_count
                normalized["intervention_message"] = self._recovery_message(
                    normalized,
                    authority_loss=self._authority_loss(packet),
                    repeat_count=repeat_count,
                )
                if epistemic_status == "causal_uncertainty":
                    if self.pending_discriminating_probe is None:
                        self.pending_discriminating_probe = {
                            "requested_turn": packet.get("internal_turn"),
                            "discrepancy": normalized["discrepancy"],
                            "next_safe_action": normalized["next_safe_action"],
                            "reasserted_turns": [],
                        }
                    else:
                        # Pending is deliberative memory, not a semaphore. Keep
                        # the original request visible while recording that the
                        # same control episode required renewed correction.
                        self.pending_discriminating_probe.setdefault(
                            "reasserted_turns", []
                        ).append(packet.get("internal_turn"))
                        self.pending_discriminating_probe["latest_discrepancy"] = normalized[
                            "discrepancy"
                        ]
                        self.pending_discriminating_probe["latest_safe_action"] = normalized[
                            "next_safe_action"
                        ]
                challenge = {key: normalized[key] for key in (
                    "discrepancy", "exit_condition", "public_anchors", "intervention_message"
                )}
                if self.open_episode is None:
                    self.open_episode = {
                        "episode_id": (
                            f"repair-{packet.get('internal_turn')}-"
                            f"{len(self.decisions) + 1}"
                        ),
                        "revision": 1,
                        "opened_turn": packet.get("internal_turn"),
                        "original_discrepancy": normalized["discrepancy"],
                        "original_exit_condition": normalized["exit_condition"],
                        "discrepancy": normalized["discrepancy"],
                        "exit_condition": normalized["exit_condition"],
                        "current_residual": normalized["discrepancy"],
                        "current_exit_condition": normalized["exit_condition"],
                        "public_anchors": normalized["public_anchors"],
                        "challenges": [challenge],
                    }
                    self.open_episode_history_start = review_history_start
                else:
                    # Preserve the scope that justified taking control. Later
                    # challenges may refine a residual, but must not silently
                    # redefine the repair episode into an expanding audit.
                    self.open_episode["current_residual"] = normalized["discrepancy"]
                    self.open_episode["current_exit_condition"] = normalized["exit_condition"]
                    self.open_episode["public_anchors"] = normalized["public_anchors"]
                    self.open_episode.setdefault("challenges", []).append(challenge)
                    self.open_episode.setdefault(
                        "episode_id",
                        f"repair-{self.open_episode.get('opened_turn')}-legacy",
                    )
                    self.open_episode["revision"] = max(
                        0, int(self.open_episode.get("revision", 0) or 0)
                    ) + 1
                self.last_intervention_delivery = {
                    "episode_id": self.open_episode["episode_id"],
                    "episode_revision": self.open_episode["revision"],
                    "intervention_signature": normalized.get(
                        "intervention_signature"
                    ),
                }
            elif attention_mode == "patrol":
                released_repair = self.open_episode is not None
                if self.open_episode is not None:
                    self.last_closed_repair = {
                        "opened_turn": self.open_episode.get("opened_turn"),
                        "closed_turn": packet.get("internal_turn"),
                        "original_discrepancy": _clip(
                            self.open_episode.get("original_discrepancy", ""), 1800
                        ),
                        "final_residual": _clip(
                            self.open_episode.get("current_residual", ""), 1800
                        ),
                        "release_reason": _clip(normalized.get("reason", ""), 1800),
                        "release_evidence": list(normalized.get("public_anchors", []))[:12],
                        "history_reference": {
                            "from_turn": self.open_episode.get("opened_turn"),
                            "through_turn": packet.get("internal_turn"),
                            "from_message": self.open_episode_history_start,
                            "through_message": max(1, len(self.history) - 1),
                        },
                        "use": (
                            "Navigation only. Revisit if later public evidence bears on the "
                            "original discrepancy or invalidates the cited release evidence."
                        ),
                    }
                self.open_episode = None
                self.open_episode_history_start = None
                self.pending_discriminating_probe = None
                # A patrol transition that closes a focused repair is the
                # natural lifecycle end of that repair's bounded inquiry. Do
                # not require the model to repeat an empty optional field just
                # to prevent stale investigation state from leaking forward.
                if released_repair and self.m3_discriminative_control_enabled:
                    if self.discriminative_step and self.m3_combined_control_enabled:
                        self._close_inquiry(
                            self.discriminative_step, packet=packet,
                            decision=normalized, status="released_to_patrol",
                        )
                        normalized["m3d_inquiry_transition"] = "closed_on_patrol"
                    self.discriminative_step = None
                    normalized["discriminative_step"] = None
            self._refresh_cognitive_checkpoint(decision, normalized, packet)
            self._record(normalized, packet)
            return normalized["intervention_message"]
        # Inspection exhaustion is a monitor limitation, not evidence that the
        # root task is complete.  Preserve the ledger and hold a completion
        # proposal for another bounded audit pass instead of crashing and
        # accidentally allowing termination.
        return self._protocol_fallback(
            packet,
            inspections,
            f"inspection budget {self.max_inspections} exhausted; durable task state preserved",
        )

    def review_completion(self, proposal: Any, turn: int,
                          provider_link: Mapping[str, Any] | None = None,
                          response_content: str = "") -> CompletionDecision:
        """Apply the same persistent monitor at the public completion boundary."""
        message = self.review({
            "boundary": "completion_proposal",
            "internal_turn": turn,
            "response_content": response_content or getattr(proposal, "response_preview", ""),
            "tool_calls": [],
            "tool_results": [],
            "provider_link": dict(provider_link or {}),
        })
        termination = self.decisions[-1].get("termination_decision")
        if termination == "continue_task" and message:
            return CompletionDecision(
                decision="CONTINUE",
                reason_codes=("M0_CONTINUE_TASK",),
                next_prompt=message,
            )
        return CompletionDecision(
            decision="ALLOW_COMPLETE",
            reason_codes=("M0_ALLOW_COMPLETE",),
        )

    def _protocol_fallback(self, packet: Mapping[str, Any], diagnostics: list[dict[str, Any]], error: str) -> str:
        """Do not terminate or steer the task Agent because the monitor broke."""
        completion = packet.get("boundary") == "completion_proposal"
        message = (
            "The monitor could not complete its internal root-task audit. Keep working from the "
            "original public task and do not write or reconstruct a replacement global audit. "
            "Continue only with concrete implementation, test, or investigation work already "
            "supported by public evidence; the monitor will retry its own audit later."
            if completion else ""
        )
        decision = {
            "termination_decision": "continue_task" if completion else None,
            "intervention_message": message,
            "attention": {
                "mode": "focused" if completion else self.attention_mode,
                "reason": "protocol recovery" if completion else "preserve current attention",
            },
            "reason": (
                f"Monitor protocol failure; root completion retained for a later valid review: {error}"
                if completion else
                f"Monitor protocol failure; task Agent allowed to continue without a valid review: {error}"
            ),
            "public_anchors": [],
            "discrepancy": "Root-task coverage is not yet auditable." if completion else "",
            "exit_condition": "A valid clause-by-clause public audit." if completion else "",
            "notes": self.notes,
            "inspections": diagnostics,
            "control_valid": False,
        }
        if completion:
            self.attention_mode = "focused"
            if self.open_episode is None:
                self.open_episode = {
                    "opened_turn": packet.get("internal_turn"),
                    "original_discrepancy": decision["discrepancy"],
                    "original_exit_condition": decision["exit_condition"],
                    "current_residual": decision["discrepancy"],
                    "current_exit_condition": decision["exit_condition"],
                    "public_anchors": [],
                    "challenges": [{
                        "discrepancy": decision["discrepancy"],
                        "exit_condition": decision["exit_condition"],
                        "public_anchors": [],
                        "intervention_message": message,
                    }],
                }
                self.open_episode_history_start = max(2, len(self.history) - 2)
        self._record(decision, packet)
        return message
