"""Independent persistent Monitor Agent."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import uuid
import warnings
from copy import deepcopy
from dataclasses import asdict

from .actions import MonitorAction, ToolOutcome
from .loop import run_review
from .process_runner import run_analysis
from .workspace import MonitorWorkspace
from .grounded_context import read_with_sources
from .handoff_validation import validate_handoff, note_text
from .advice_basis import AdviceBasis, ADVICE_PROMPT, advice_tools
from .feedback_focus import FeedbackFocus, FOCUS_PROMPT
from .inquiry import Inquiry, INQUIRY_PROMPT
from .working_context import current_working_context
from .live_awareness import LiveAwareness
from .decision_context import DecisionContext


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

On waking from silence, the host stops task execution while you assess the situation. Use intervene
directly when a correction is warranted, or wait to resume without correction; do not arrange pauses
with scripts. Sending the first correction resumes execution. Follow-up observation is concurrent:
attend to the latest public response and send a further correction when needed, without waiting for a
finished artifact if the mistaken intent is already clear. Actual model and tool latency still applies.

Task evidence is read-only by role under task/. Private cognition is writable under monitor/. Broad analysis
starts in monitor/ and can read the live absolute paths in the environment map; do not modify task sources.
This local execution tool is not a filesystem sandbox."""

TOOL_FEEDBACK_GUIDANCE = """On an ordinary wake, continue from your existing history and use the chronological synopsis as navigation,
not proof. When an uncertain judgment would change whether you intervene, what you advise, or whether you
end an investigation, use existing tools to check its key grounds. Compare the actual observations with
the original requirement, then retain or revise your judgment, including your own earlier advice. External
feedback can itself come from a flawed test. Pay particular attention to causal intent, changed tests as
executable interpretations of the contract, and local success being mistaken for root completion.
If evidence is already sufficient, act without a ceremonial extra check. If investigation makes no material
progress, you may retain uncertainty and let the task proceed instead of repeating the same checks.
Intervene only for a concrete material discrepancy supported by public evidence. Explain the conflicting
requirement or evidence and what should be re-checked; do not take over the whole task."""


def monitor_system_prompt(tool_feedback=False):
    if not tool_feedback:
        return MONITOR_SYSTEM_PROMPT
    start = MONITOR_SYSTEM_PROMPT.index('On an ordinary wake,')
    end = MONITOR_SYSTEM_PROMPT.index('\n\nA tool-free Task Agent message', start)
    return MONITOR_SYSTEM_PROMPT[:start] + TOOL_FEEDBACK_GUIDANCE + MONITOR_SYSTEM_PROMPT[end:]


REVIEW_MODE_PROMPT = """You are conducting an active review. Every review must end by calling exactly one
control action: wait, intervene, or allow_complete (only for a pending root completion).
Calling wait is normal silence."""

CONTINUATION_MODE_PROMPT = """This request is a private memory handoff within the same Monitor session,
not an active review. Tools and control actions are unavailable. Return only a natural-language note for
your future self; do not simulate file writes, tool calls, or messages to the Task Agent. Earlier review
instructions to call a control action do not apply to this handoff. Preserve uncertainty and the grounds
for decisions, including evidence that could change your own advice; do not turn your inferences into
additional task requirements."""

GROUNDED_TOOL = _tool("read_with_sources",
    "Read a private Markdown note together with current excerpts from its inline local links. "
    "Use task/ or monitor/ paths, e.g. [source](task/original_task.txt#L10-L30). "
    "Expands up to eight links from the selected note lines, one hop only; reports omissions and "
    "text changes since the previous read. Ordinary file and code tools remain available.", {
        "path": {"type": "string"},
        "start": {"type": "integer", "minimum": 1, "default": 1},
        "count": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 200},
    }, ["path"])

GROUNDED_PROMPT = """When useful, leave links to the sources of a live question in your natural private
notes. read_with_sources restores the selected note alongside current source text, rather than asking you
to reconstruct quotations from memory. You decide when restoration is useful and how to revise your
understanding. It is optional, not a prerequisite for intervening or completing; linked text is evidence
to interpret, not automatic support for the note. No prescribed note schema or per-wake writing is needed."""

FOCUS_TOOL = _tool('feedback_focus',
    'Open, read or close one private follow-up view. Reads original public progress and delivery receipts '
    'incrementally, only when requested. begin replaces an existing focus, preserving it in the archive. '
    'Without after_event, begin starts at the current archive end. Ordinary tools can read earlier history.', {
        'action': {'type': 'string', 'enum': ['begin', 'read', 'close']},
        'note': {'type': 'string', 'description': 'For begin: your freely phrased concern or intended recovery.'},
        'after_event': {'type': 'integer', 'minimum': 0,
                        'description': 'For begin: start after this public event; 0 includes all history.'},
        'limit': {'type': 'integer', 'minimum': 256, 'maximum': 64000, 'default': 12000,
                  'description': 'Maximum UTF-8 bytes per stream on read; large records continue next read.'},
    }, ['action'])


INQUIRY_TOOL = _tool('inquiry',
    'Select or replace one current investigation: your question and original source ranges. '
    'Returns them now and restores current passages once at later wakes until closed. '
    'Does not send input, judge correctness, schedule wakes or limit ordinary tools.', {
        'action': {'type': 'string', 'enum': ['open', 'close']},
        'question': {'type': 'string', 'description': 'For open: the decision you are investigating.'},
        'sources': {'type': 'array', 'minItems': 1, 'maxItems': 8, 'items': {
            'type': 'object', 'properties': {
                'path': {'type': 'string'},
                'start': {'type': 'integer', 'minimum': 1, 'default': 1},
                'count': {'type': 'integer', 'minimum': 1, 'maximum': 1000, 'default': 80},
            }, 'required': ['path'], 'additionalProperties': False}},
    }, ['action'])


class MonitorAgent:
    def __init__(self, client, workspace: MonitorWorkspace, max_review_turns=20):
        self.client = client
        tool_feedback = getattr(client, 'config', {}).get('monitor_tool_feedback', False)
        if type(tool_feedback) is not bool:
            raise ValueError('monitor_tool_feedback must be a boolean')
        self.system_prompt = monitor_system_prompt(tool_feedback)
        self.workspace = workspace
        self.max_review_turns = int(max_review_turns)
        self.completion_pending = False
        self.completion_state = None
        self._seen_completion = None
        self._intervened_generation = None
        self.stop_event = threading.Event()
        self.review_id = None
        self._progress_warning = False
        self.intervention_callback = None
        self._sent_messages = set()
        self.grounded_context = getattr(client, "config", {}).get("monitor_grounded_context", False)
        self.client.progress_callback = self._progress
        self.semantic_continuity = getattr(client, "config", {}).get("monitor_semantic_continuity", True)
        active_context = getattr(client, "config", {}).get("monitor_active_working_context", False)
        if type(active_context) is not bool:
            raise ValueError("monitor_active_working_context must be a boolean")
        live_awareness = getattr(client, "config", {}).get("monitor_live_awareness", False)
        if type(live_awareness) is not bool:
            raise ValueError("monitor_live_awareness must be a boolean")
        self.live_awareness = LiveAwareness(workspace) if live_awareness else None
        decision_context = getattr(client, 'config', {}).get('monitor_decision_context', False)
        if type(decision_context) is not bool:
            raise ValueError('monitor_decision_context must be a boolean')
        self.decision_context = DecisionContext(workspace) if decision_context else None
        self.active_context_enabled = active_context
        if live_awareness or active_context or decision_context:
            self.client.prepare_active_context = self._active_working_context
        if active_context:
            self.system_prompt += (
                "\nYour current monitor/working.md is made available during normal reasoning without "
                "a separate read. Use it for the understanding you want available next time, not a log. "
                "You decide its content and when revision is useful; no per-wake update is required. "
                "It does not replace original evidence or your ongoing dialogue."
            )
        self.handoff_validation = getattr(client, "config", {}).get("monitor_handoff_validation", False)
        self.advice_basis = (AdviceBasis(workspace, self._atomic_private_text)
                            if getattr(client, "config", {}).get("monitor_advice_revision", False) else None)
        self.feedback_focus = (FeedbackFocus(workspace, self._atomic_private_text)
                               if getattr(client, 'config', {}).get('monitor_feedback_focus', False) else None)
        self.inquiry = (Inquiry(workspace, self._atomic_private_text)
                        if getattr(client, 'config', {}).get('monitor_inquiry', False) else None)
        if self.handoff_validation and not self.semantic_continuity:
            raise ValueError("Handoff validation requires semantic continuity")
        if self.semantic_continuity:
            self.client.prepare_continuation = self._prepare_continuation
            self.client.archive_continuation_history = self._archive_continuation_history

    def _active_working_context(self):
        parts = []
        if self.active_context_enabled:
            text = current_working_context(self.workspace)
            self._audit_dialogue('active_working_context', content=text)
            if text:
                parts.append(text)
        if self.live_awareness is not None:
            text, metadata = self.live_awareness.context()
            self._audit_dialogue('live_awareness', content=text, **metadata)
            parts.append(text)
        if self.decision_context is not None:
            text = self.decision_context.attention()
            self._audit_dialogue('decision_attention', content=text)
            parts.append(text)
        return '\n\n'.join(parts) or None

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
        if self.grounded_context:
            prompt += ("\nPreserve useful source links or paths to active inquiry notes so your future self "
                       "can restore the actual grounds. Do not replace source links with invented quotations.")
        previous_system = self.client.system
        self.client.system = self.system_prompt + "\n\n" + CONTINUATION_MODE_PROMPT
        self.client.history.append({"role": "user", "content": [{"type": "text", "text": prompt}]})
        try:
            blocks, usage = self.client._request([])
            self.client.usage_records.append(dict(usage, purpose="pre_compaction_continuation"))
            note = note_text(blocks)
            if self.handoff_validation:
                note = validate_handoff(self, note, previous)
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

    def _remember_advice(self, message, arguments):
        if self.advice_basis is None:
            return {}
        try:
            return {"private_advice": self.advice_basis.record(message, str(arguments.get("basis") or ""))}
        except Exception as exc:
            # The message has already been submitted: never report it as unsent.
            self._progress("advice_storage_failed", error_type=type(exc).__name__)
            return {"private_advice_error": str(exc), "note": "Input was submitted; private storage failed."}

    def _dispatch(self, name: str, arguments: dict) -> ToolOutcome:
        try:
            if name == "file_read":
                data = self.workspace.read_text(
                    arguments["path"], arguments.get("start", 1), arguments.get("count", 200),
                    tail=arguments.get("tail", False),
                )
            elif name == "read_with_sources" and self.grounded_context:
                data = read_with_sources(self.workspace, arguments["path"],
                                         arguments.get("start", 1), arguments.get("count", 200))
            elif name == 'review_context' and self.decision_context is not None:
                data = self.decision_context.read(**arguments)
            elif name == 'feedback_focus' and self.feedback_focus is not None:
                data = self.feedback_focus.call(**arguments)
            elif name == 'inquiry' and self.inquiry is not None:
                data = self.inquiry.call(**arguments)
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
                pending = self.completion_pending
                if self.completion_state is not None:
                    current = self.completion_state()
                    pending = bool(current and current['generation'] != self._intervened_generation)
                if pending:
                    return ToolOutcome({"status": "handoff_pending", "message":
                        "The Task Agent is waiting for a response; waiting for more task turns cannot "
                        "produce progress. Continue inspecting evidence as needed, approve if justified, "
                        "or send a concrete correction/answer. No message was sent to the Task Agent."})
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
                    if self.decision_context is not None:
                        try:
                            self.decision_context.record_input(message)
                        except Exception as exc:
                            self._progress('decision_context_receipt_failed', error_type=type(exc).__name__)
                    self._sent_messages.add(message)
                    if self._seen_completion:
                        self._intervened_generation = self._seen_completion["generation"]
                    self.completion_pending = False
                    return ToolOutcome({"status": "submitted", "receipt": receipt,
                                        "note": "Submission is not proof of delivery or uptake. Continue observing; wait when appropriate.",
                                        **self._remember_advice(message, arguments)})
                self._remember_advice(message, arguments)
                return ToolOutcome(None, False, MonitorAction("intervene", {"message": message}))
            elif name == "allow_complete":
                if self.completion_state is not None:
                    current = self.completion_state()
                    if (not self._seen_completion or current != self._seen_completion
                            or current["generation"] == self._intervened_generation):
                        raise ValueError("The observed handoff is no longer current. Inspect the runtime update before deciding.")
                    return ToolOutcome(None, False, MonitorAction(
                        "allow_complete", {"request_id": current["request_id"]}))
                if not self.completion_pending: raise ValueError("No root completion is pending")
                return ToolOutcome(None, False, MonitorAction("allow_complete", {}))
            else:
                data = {"status": "error", "error": f"Unknown tool: {name}"}
        except Exception as exc:
            data = {"status": "error", "error": str(exc)}
        return ToolOutcome(data)

    def _refresh_completion(self):
        if self.completion_state is None:
            return None
        current = self.completion_state()
        if current and current["generation"] == self._intervened_generation:
            current = None
        self.completion_pending = current is not None
        if current == self._seen_completion:
            return None
        self._seen_completion = current
        if current is None:
            return "Runtime update: the previously observed task handoff is no longer pending."
        return ("Runtime update: the Task Agent is waiting on a current handoff at "
                f"task/public_events.jsonl line {current['cursor']}. Inspect its public message as needed. "
                "You may handle this handoff in this same review. Approval applies only to this proposal; "
                "waiting for more Task Agent turns cannot advance it without a response.")

    def _refresh_review_context(self):
        updates = [self._refresh_completion()]
        if self.advice_basis is not None:
            try:
                updates.append(self.advice_basis.refresh())
            except Exception as exc:
                self._progress("advice_read_failed", error_type=type(exc).__name__)
                updates.append("Private advice note unavailable; use existing history and original evidence. "
                               + type(exc).__name__)
        return "\n\n".join(update for update in updates if update) or None

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
            system = self.system_prompt + "\n\n" + mode
            tools = MONITOR_TOOLS
            if self.decision_context is not None:
                system += (
                    '\n\nA small current synopsis and your last correction are available during reasoning. '
                    'Use them to decide whether the next useful move is investigation, correction, or waiting; '
                    'more reading is useful only if it can change that choice. review_context retrieves '
                    'source-linked task excerpts and private notes with bounded recent behavior, by default '
                    'after your last correction. It is optional navigation, not proof: inspect actual tests '
                    'or files where needed. A prior diagnosis, including your own, remains revisable.'
                )
                tools = [*tools, _tool('review_context',
                    'Get bounded previews: lexical task/private-note matches and recent public behavior. '
                    'Defaults to behavior after your last correction; false includes earlier recent events. '
                    'Use original files for full evidence. Does not judge, update memory or send input.', {
                        'query': {'type': 'string', 'default': ''},
                        'after_correction': {'type': 'boolean', 'default': True},
                        'steps': {'type': 'integer', 'minimum': 1, 'maximum': 32, 'default': 8},
                    }, [])]
            if self.live_awareness is not None:
                system += (
                    "\n\nFile activity is sampled before normal requests, not monitored semantically for you. "
                    "While following a correction, distinguish investigating its grounds from checking "
                    "the Task Agent's latest response; choose which now matters. Existing file_read can "
                    "use tail=true with count to read the latest lines of any permitted file. "
                    "You can still inspect any earlier range or use code_run; no mandatory reread is imposed."
                )
                tools = deepcopy(tools)
                tools[0]['function']['description'] += ' With tail=true, read the latest count lines; omit start.'
                tools[0]['function']['parameters']['properties']['tail'] = {
                    'type': 'boolean', 'default': False,
                }
            if self.grounded_context:
                system += "\n\n" + GROUNDED_PROMPT
                tools = [*tools, GROUNDED_TOOL]
            if self.advice_basis is not None:
                self.advice_basis.begin_review()
                system += "\n\n" + ADVICE_PROMPT
                tools = advice_tools(tools)
            if self.feedback_focus is not None:
                system += '\n\n' + FOCUS_PROMPT
                tools = [*tools, FOCUS_TOOL]
            if self.inquiry is not None:
                system += '\n\n' + INQUIRY_PROMPT
                tools = [*tools, INQUIRY_TOOL]
                try:
                    view = self.inquiry.restore()
                    if view:
                        wake_context += '\nYour selected investigation:\n' + json.dumps(view, ensure_ascii=False)
                except (OSError, ValueError) as exc:
                    self._progress('inquiry_restore_failed', error_type=type(exc).__name__)
                    wake_context += '\nSelected inquiry unavailable; original history and tools remain available.'
            action = run_review(
                self.client, system, wake_context, tools,
                self.dispatch, self.max_review_turns,
                audit=self._audit_dialogue,
                before_model=self._refresh_review_context,
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
