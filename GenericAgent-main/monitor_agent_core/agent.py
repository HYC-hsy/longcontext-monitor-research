"""Independent persistent Monitor Agent."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import uuid
import warnings
from dataclasses import asdict

from .actions import MonitorAction, ToolOutcome
from .loop import run_review
from .process_runner import run_analysis
from .workspace import MonitorWorkspace


def _tool(name, description, properties, required):
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": properties,
                       "required": required, "additionalProperties": False},
    }}


MONITOR_TOOLS = [
    _tool("file_read", "Read a bounded range from task/ evidence or monitor/ private files.", {
        "path": {"type": "string"}, "start": {"type": "integer", "minimum": 1, "default": 1},
        "count": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 200},
    }, ["path"]),
    _tool("file_write", "Write only a monitor/ private file.", {
        "path": {"type": "string"}, "content": {"type": "string"},
        "mode": {"type": "string", "enum": ["replace", "append", "prepend"], "default": "replace"},
    }, ["path", "content"]),
    _tool("file_patch", "Replace one exact text span in a monitor/ private file.", {
        "path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"},
    }, ["path", "old_text", "new_text"]),
    _tool("code_run", "Run general analysis in monitor/. Live source paths are provided in the environment map. Output returns when the script ends; use short reads for timely observation.", {
        "code": {"type": "string"},
        "type": {"type": "string", "enum": ["python", "powershell"] if os.name == "nt" else ["python", "bash"], "default": "python"},
        "timeout": {"type": "integer", "minimum": 1, "maximum": 300, "default": 60},
    }, ["code"]),
    _tool("wait", "Remain silent and wake after more public Task Agent turns.", {
        "after_turns": {"type": "integer", "minimum": 1},
    }, ["after_turns"]),
    _tool("intervene", "Send a natural user-like correction or answer a clarification; interrupt if running.", {
        "message": {"type": "string", "minLength": 1},
    }, ["message"]),
    _tool("allow_complete", "Allow only the currently pending root completion.", {}, []),
]


MONITOR_SYSTEM_PROMPT = """You are the persistent Monitor Agent for a long-running Task Agent.
Detect material task drift from public evidence, especially omitted requirements and completion claims based
on inadequate evidence. Tests and Agent statements are provisional evidence, never ground truth. At
initialization, read the original task and form your own durable working understanding; use natural private
notes when helpful, without forcing a fixed schema.
Keep monitor/working.md as your revisable understanding when decisions change what your future self needs
to know, not as a transcript or a form to fill every wake. Preserve why a concern remains open, what evidence
supports or challenges your interpretation, and what subsequent behavior would let you move on. Distinguish
your hypotheses from observations; correct your own earlier advice when evidence changes. Keep the root task
in view without reopening adequately supported local work. Recent dialogue carries the active correction;
ending a review is not the end of that correction. You choose the note's organization and level of detail.

On an ordinary wake, continue from your existing history, use the chronological synopsis as navigation, and
retrieve original evidence where it can change the decision. A synopsis is not proof. Pay particular
attention to causal intent, changed tests as executable interpretations of the contract, and local success
being mistaken for root completion. Intervene only for a concrete material discrepancy supported by public
evidence. Explain the conflicting requirement or evidence and what should be re-checked; do not take over the
whole task.

A tool-free Task Agent message may be a question or blocker, not a completion claim. Respond to its actual
need. If it has lost the requirements, restore the relevant original requirements and give a path it can
actually read, rather than repeatedly asking it to re-check an inaccessible source. Your task/ paths are
virtual observation paths, not Task Agent paths. Confirm restored understanding through its subsequent
public intent and actions; no fixed confirmation form is needed.

After intervening, remain engaged across the next understanding, intent, action, and result. Intervene again
if the correction is misunderstood or evidence still cannot support the decision. Return to patrol once the
local issue is reasonably resolved; local release is not root completion. Do not verify every unknown, react
to harmless exploration, or impose code-review perfectionism.

Task evidence is read-only by role under task/. Private cognition is writable under monitor/. Broad analysis
starts in monitor/ and can read the live absolute paths in the environment map; do not modify task sources.
This local execution tool is not a filesystem sandbox."""

REVIEW_MODE_PROMPT = """You are conducting an active review. Every review must end by calling exactly one
control action: wait, intervene, or allow_complete (only for a pending root completion).
Calling wait is normal silence."""

CONTINUATION_MODE_PROMPT = """This request is a private memory handoff within the same Monitor session,
not an active review. Tools and control actions are unavailable. Return only a natural-language note for
your future self; do not simulate file writes, tool calls, or messages to the Task Agent. Earlier review
instructions to call a control action do not apply to this handoff. Preserve uncertainty and the grounds
for decisions, including evidence that could change your own advice; do not turn your inferences into
additional task requirements."""


class MonitorAgent:
    def __init__(self, client, workspace: MonitorWorkspace, max_review_turns=20):
        self.client = client
        self.workspace = workspace
        self.max_review_turns = int(max_review_turns)
        self.completion_pending = False
        self.stop_event = threading.Event()
        self.review_id = None
        self._progress_warning = False
        self.intervention_callback = None
        self._sent_messages = set()
        self.client.progress_callback = self._progress
        self.semantic_continuity = getattr(client, "config", {}).get("monitor_semantic_continuity", True)
        if self.semantic_continuity:
            self.client.prepare_continuation = self._prepare_continuation
            self.client.archive_continuation_history = self._archive_continuation_history

    def _atomic_private_text(self, relative_path, text):
        path = self.workspace.private_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(text)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def _archive_continuation_history(self, history):
        relative = "audit/history/" + uuid.uuid4().hex + ".json"
        self._atomic_private_text(relative, json.dumps(history, ensure_ascii=False))
        return "monitor/" + relative

    def _audit_dialogue(self, event, **payload):
        """Persist completed observations immediately, independently of model input."""
        path = self.workspace.private_root / 'audit' / 'dialogue.jsonl'
        path.parent.mkdir(parents=True, exist_ok=True)
        record = dict(timestamp=time.time(), review_id=self.review_id, event=event, **payload)
        with path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(record, ensure_ascii=False, default=str) + '\n')
            stream.flush()

    def _prepare_continuation(self):
        """Same model, existing history, no tool actions during pre-compaction handoff."""
        note_path = self.workspace.private_root / "working.md"
        previous = note_path.read_text(encoding="utf-8") if note_path.exists() else ""
        prompt = (
            "Before older dialogue is compacted, write a concise natural-language working understanding "
            "for yourself to continue this same task. Preserve unresolved reasoning and corrections, their "
            "public evidence locations, what actually happened after advice, and remaining root scope. "
            "Revise stale beliefs rather than copying them. Do not treat unobserved uptake as success. "
            "Keep details that change future decisions, not a chronology. No fixed schema; return only the note. "
            "Do not issue task interventions in this maintenance response. Existing private working note:\n" + previous
        )
        self._progress("continuation_started")
        previous_system = self.client.system
        self.client.system = MONITOR_SYSTEM_PROMPT + "\n\n" + CONTINUATION_MODE_PROMPT
        self.client.history.append({"role": "user", "content": [{"type": "text", "text": prompt}]})
        try:
            blocks, usage = self.client._request([])
            self.client.usage_records.append(dict(usage, purpose="pre_compaction_continuation"))
            if any(block.get("type") == "tool_use" for block in blocks):
                raise ValueError("Continuation unexpectedly requested a tool")
            note = "\n".join(block.get("text", "") for block in blocks if block.get("type") == "text").strip()
            if not note:
                raise ValueError("Empty continuation; keeping original history")
            self.workspace.write_text("monitor/audit/continuations.jsonl", json.dumps({
                "timestamp": time.time(), "review_id": self.review_id, "note": note,
            }, ensure_ascii=False) + "\n", mode="append")
            self._atomic_private_text("working.md", note)
            self._progress("continuation_saved")
            return note
        finally:
            self.client.history.pop()
            self.client.system = previous_system

    def _progress(self, event, **fields):
        # Metadata only: never put credentials, prompts, code or reasoning here.
        path = self.workspace.private_root / 'audit' / 'progress.jsonl'
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(dict(timestamp=time.time(), review_id=self.review_id,
                                             event=event, **fields), ensure_ascii=False) + '\n')
        except OSError as exc:
            if not self._progress_warning:
                warnings.warn(f'Monitor progress recording unavailable: {type(exc).__name__}')
                self._progress_warning = True

    def dispatch(self, name: str, arguments: dict) -> ToolOutcome:
        tool_id = uuid.uuid4().hex
        started = time.monotonic()
        self._progress('tool_started', tool_id=tool_id, name=name)
        try:
            return self._dispatch(name, arguments)
        finally:
            self._progress('tool_finished', tool_id=tool_id, name=name,
                           duration_seconds=time.monotonic() - started)

    def _dispatch(self, name: str, arguments: dict) -> ToolOutcome:
        try:
            if name == "file_read":
                data = self.workspace.read_text(
                    arguments["path"], arguments.get("start", 1), arguments.get("count", 200)
                )
            elif name == "file_write":
                data = self.workspace.write_text(
                    arguments["path"], arguments["content"], arguments.get("mode", "replace")
                )
            elif name == "file_patch":
                data = self.workspace.patch_text(
                    arguments["path"], arguments["old_text"], arguments["new_text"]
                )
            elif name == "code_run":
                data = run_analysis(
                    arguments["code"], arguments.get("type", "python"),
                    min(300, max(1, int(arguments.get("timeout", 60)))),
                    str(self.workspace.private_root), self.stop_event,
                )
            elif name == "wait":
                return ToolOutcome(None, False, MonitorAction(
                    "wait", {"after_turns": max(1, int(arguments["after_turns"]))}
                ))
            elif name == "intervene":
                message = str(arguments.get("message", "")).strip()
                if not message: raise ValueError("message must not be empty")
                if self.intervention_callback is not None:
                    if message in self._sent_messages:
                        return ToolOutcome({"status": "already_submitted",
                                            "message": "Observe subsequent behavior before repeating the same input."})
                    receipt = self.intervention_callback(message)
                    self._sent_messages.add(message)
                    self.completion_pending = False
                    return ToolOutcome({"status": "submitted", "receipt": receipt,
                                        "note": "Submission is not proof of delivery or uptake. Continue observing; wait when appropriate."})
                return ToolOutcome(None, False, MonitorAction("intervene", {"message": message}))
            elif name == "allow_complete":
                if not self.completion_pending: raise ValueError("No root completion is pending")
                return ToolOutcome(None, False, MonitorAction("allow_complete", {}))
            else:
                data = {"status": "error", "error": f"Unknown tool: {name}"}
        except Exception as exc:
            data = {"status": "error", "error": str(exc)}
        return ToolOutcome(data)

    def review(self, wake_context: str, completion_pending=False) -> MonitorAction:
        started = time.time()
        self.review_id = uuid.uuid4().hex
        self._progress('review_started', completion_pending=bool(completion_pending))
        before = self.client.history_measure()
        self.completion_pending = bool(completion_pending)
        self._sent_messages.clear()
        action = None
        try:
            wake_context += "\nLive environment map (read task sources, write only private cognition): " + json.dumps({
                "task/": str(self.workspace.evidence_root),
                **{f"task/{name}/": str(path) for name, path in self.workspace.task_mounts.items()},
                "monitor/": str(self.workspace.private_root),
            }, ensure_ascii=False)
            mode = REVIEW_MODE_PROMPT
            if self.intervention_callback is not None:
                mode = ("You may call intervene as soon as public evidence supports a useful correction, "
                        "then continue this same investigation. It sends input without ending your review. "
                        "You need not finish unrelated checks before sending, nor send merely because you can. "
                        "Delivery feedback is available at monitor/delivery_feedback.jsonl; it may arrive after submission. "
                        "Read subsequent public behavior to assess uptake. End with wait when ready to be silent, "
                        "or allow_complete only for a still-pending, justified root completion. "
                        "After an intervention that completion proposal is no longer pending.")
            action = run_review(
                self.client, MONITOR_SYSTEM_PROMPT + "\n\n" + mode, wake_context, MONITOR_TOOLS,
                self.dispatch, self.max_review_turns,
                audit=self._audit_dialogue,
            )
            return action
        finally:
            self._progress('review_finished', action=action.kind if action else None,
                           duration_seconds=time.time() - started)
            telemetry = self.client.drain_telemetry() if hasattr(self.client, "drain_telemetry") else {}
            self.workspace.write_text(
                "monitor/audit/reviews.jsonl",
                json.dumps({
                    "started_at": started, "duration_seconds": time.time() - started,
                    "history_before": before, "history_after": self.client.history_measure(),
                    "action": asdict(action) if action else None,
                }, ensure_ascii=False) + "\n", mode="append",
            )
            self.workspace.write_text(
                "monitor/audit/provider_history.json",
                json.dumps(self.client.export_history(), ensure_ascii=False), mode="replace",
            )
            for usage in telemetry.get("usage", []):
                self.workspace.write_text(
                    "monitor/audit/provider_usage.jsonl",
                    json.dumps(usage, ensure_ascii=False) + "\n", mode="append",
                )
            for transform in telemetry.get("history_transforms", []):
                self.workspace.write_text(
                    "monitor/audit/history_transforms.jsonl",
                    json.dumps(transform, ensure_ascii=False) + "\n", mode="append",
                )
            for attempt in telemetry.get('request_attempts', []):
                self.workspace.write_text(
                    'monitor/audit/request_attempts.jsonl',
                    json.dumps(attempt, ensure_ascii=False) + '\n', mode='append',
                )
