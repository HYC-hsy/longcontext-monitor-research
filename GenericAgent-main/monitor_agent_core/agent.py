"""Independent persistent Monitor Agent."""

from __future__ import annotations

import json
import hashlib
import os
import tempfile
import threading
import time
import uuid
import warnings
from dataclasses import asdict

from .actions import MonitorAction, ToolOutcome
from .loop import run_review
from .process_runner import AnalysisSessions
from .workspace import MonitorWorkspace
from .grounded_context import read_with_sources
from .handoff_validation import validate_handoff, note_text, ContinuationContractError
from .advice_basis import AdviceBasis, ADVICE_PROMPT, advice_tools
from .feedback_focus import FeedbackFocus, FOCUS_PROMPT
from .inquiry import Inquiry, INQUIRY_PROMPT
from .working_context import (
    DCEC_WORKING_VIEW_DEFAULT_CHARS,
    DCEC_WORKING_VIEW_MAX_CHARS,
    DCEC_WORKING_VIEW_MIN_CHARS,
    current_working_context,
    dcec_working_context,
)
from .live_awareness import LiveAwareness
from .decision_context import DecisionContext


def _tool(name, description, properties, required):
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": properties,
                       "required": required, "additionalProperties": False},
    }}


MONITOR_TOOLS = [
    _tool("file_read", "Read task/ evidence or monitor/ private files. Use tail=true for the latest count lines "
          "(omit start). Large ranges return next_read arguments for continuation, including within long lines. "
          "Full evidence remains accessible; this tool does not summarize or select relevant content.", {
        "path": {"type": "string"}, "start": {"type": "integer", "minimum": 1, "default": 1},
        "count": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 200},
        "tail": {"type": "boolean", "default": False},
        "offset": {"type": "integer", "minimum": 0, "default": 0,
                   "description": "Normally omit; use the character offset returned in next_read."},
        "max_chars": {"type": "integer", "minimum": 1, "maximum": 200000, "default": 20000},
    }, ["path"]),
    _tool("file_write", "Write only a monitor/ private file.", {
        "path": {"type": "string"}, "content": {"type": "string"},
        "mode": {"type": "string", "enum": ["replace", "append", "prepend"], "default": "replace"},
    }, ["path", "content"]),
    _tool("file_patch", "Replace one exact text span in a monitor/ private file.", {
        "path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"},
    }, ["path", "old_text", "new_text"]),
    _tool("code_run", "Run general analysis in monitor/. Supply code to start, or session_id to read new output. "
          "Short commands finish directly; long commands return a session and archived output path. "
          "Use cancel=true with session_id to stop that analysis, not the Task Agent. "
          "Live source paths are in the environment map. Sessions survive reviews, not process restarts. "
          "Returning a session does not release an existing task pause; normal wait/intervene still controls that.", {
        "code": {"type": "string"},
        "session_id": {"type": "string"},
        "cancel": {"type": "boolean", "default": False},
        "wait_seconds": {"type": "number", "minimum": 0, "maximum": 5, "default": 1},
        "type": {"type": "string", "enum": ["python", "powershell"] if os.name == "nt" else ["python", "bash"], "default": "python"},
        "timeout": {"type": "integer", "minimum": 1, "maximum": 300, "default": 60},
    }, []),
    _tool("wait", "Let the task run and look again after more public turns, counted from now. "
          "mode=follow (default) keeps observation concurrent, without cancelling task execution. "
          "Use mode=patrol only when leaving the current investigation; the next patrol wake stops "
          "the task for assessment. Both end this review, not your history.", {
        "after_turns": {"type": "integer", "minimum": 1},
        "mode": {"type": "string", "enum": ["follow", "patrol"], "default": "follow"},
    }, ["after_turns"]),
    _tool("intervene", "Send a natural user-like correction or answer a clarification; interrupt if running.", {
        "message": {"type": "string", "minLength": 1},
    }, ["message"]),
    _tool("allow_complete", "Allow only the currently pending root completion.", {}, []),
]

INDEPENDENT_CHECK_TOOL = _tool(
    "independent_check",
    "Ask a fresh, isolated verifier one concrete local question. Give the question and only the "
    "task evidence paths needed to answer it. The verifier cannot intervene or approve; use its "
    "scoped result as evidence, not as a whole-task decision.",
    {
        "question": {"type": "string", "minLength": 1},
        "paths": {"type": "array", "minItems": 1, "maxItems": 8,
                  "items": {"type": "string"}},
    }, ["question", "paths"],
)


MONITOR_SYSTEM_PROMPT = """You are the persistent Monitor Agent for a long-running Task Agent.
Detect material task drift from public evidence, especially omitted requirements and completion claims based
on inadequate evidence. Tests and Agent statements are provisional evidence, never ground truth. At
initialization, read the original task and form your own durable working understanding; use natural private
notes when helpful, without forcing a fixed schema.
Keep monitor/working.md as your revisable understanding when decisions change what your future self needs
to know, not as a transcript or a form to fill every wake. Preserve why a concern remains open, what evidence
supports or challenges your interpretation, and what subsequent behavior would let you move on. Keep explicit
requirements distinct from your interpretation and proposed implementation; a note is not a new authority.
When a consequential correction depends on what the task says, verify the relevant original passage rather
than reconstructing its wording from recent dialogue. Missing support in the starting environment is an
implementation problem to investigate, not permission to delete an explicit requirement. Revise your own
advice when its premises fail, rather than making the environment conform to an unsupported premise. Keep the root task
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

After intervening, remain engaged across the next understanding, intent, action, and result. Assess recovery
against the task, not merely compliance with your advice. Ask whether the observed check would also pass
if the required behavior were absent or wrong; choose a small discriminating observation when that would
change your decision. Symbol existence and compilation support only what they actually establish. A cancelled
check establishes neither success nor a defect. Let a sound proposed check run instead of repeatedly
interrupting it to refine the plan. Return to patrol once the local issue is reasonably resolved; local release
is not root completion. Do not verify every unknown or impose code-review perfectionism: unresolved details
matter when they could change task fulfillment or the next consequential action, not simply because they exist.

On waking from patrol, the host stops task execution while you assess the situation. Use intervene
directly when a correction is warranted, or wait to resume without correction; do not arrange pauses
with scripts. Sending the first correction resumes execution. Follow-up observation is concurrent:
attend to the latest public response and send a further correction when needed, without waiting for a
finished artifact if the mistaken intent is already clear. Actual model and tool latency still applies.
When awaiting a sound action or check, wait in follow mode: observing again does not cancel it.
Choose patrol when you are ready to leave the local investigation, not merely waiting for its result.

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

DCEC_SYSTEM_PROMPT = """Use monitor/working.md as your only current cognitive state, not as an evidence
archive, task checklist, concern list or second memory. Keep one current consequential decision and its scope,
one focal unresolved premise whose answer could change your control action, and only the current grounds and
limits needed for that decision. Grounds must say what was actually observed, the scope it supports, and what
it does not establish here. Keep claims and summaries source-qualified. Revise or replace superseded grounds;
do not accumulate repeated claims, summaries or notes as independent support.

Before moving an open or recovering concern to resolved, require an actually completed observation whose
scope covers the scope being closed and whose possible outcomes distinguish actions for the current decision.
Also check the observation boundary: what part of the behavior did it actually measure, and did it bypass
the path that produces, propagates or exposes the distinction relevant to this decision? Could the blocking
behavior still exist while the observation returns the same favorable result because that boundary was
bypassed? If so, retain the result as a qualified partial ground, state what it does and does not establish,
and keep or replace the one focal uncertainty. Choose a measurement at a more relevant boundary before a
broader resolution or allow_complete; success in one component does not automatically establish the
task-specified behavior. This calls for the smallest boundary needed for the current decision, not a full
path model or a fixed end-to-end check.
Intervention starts recovery but is not resolution. Local evidence can resolve only local scope; it cannot be
promoted into universal, target-wide or whole-task support. At most one current decision-critical observation
dependency may be kept, distinguishing requested, running, interrupted and completed. Requested, running and
interrupted are not positive evidence. If an unfinished observation could still change the current decision,
retain it until a result is obtained, a different discriminating observation replaces it, or a changed decision
makes it irrelevant. Do not build workflow history.

At a root handoff, set the decision scope to whole-task completion and re-qualify existing grounds at that
scope. After investigating and resolving or reopening one focal uncertainty, return to the same root decision
anchor and re-evaluate. If current grounds reveal another plausible completion-blocking alternative whose
answer could change the completion action, replace the resolved focal uncertainty with that one and continue;
resolving one uncertainty never by itself authorizes allow_complete. Allow completion only when the current
whole-task grounds are adequate and you can identify neither a current decision-relevant unresolved alternative
nor an unfinished control dependency. This is bounded re-evaluation, not exhaustive enumeration or proof.

Tighten evidence-to-decision matching when scope or consequence increases, not by mechanically adding calls or
running a fixed test. If the measured boundary misses the relevant distinction, tighten by changing
measurement placement or abstraction level rather than repeating checks at the same boundary. Once completed
evidence covers the relevant boundary and adequately supports the current scope, resolve the
concern, clear the dependency, prune superseded grounds and relax to patrol or the appropriate scoped action;
do not create a permanent conservative barrier. Before investigating, ask which differing observation outcomes
would lead to different actions, then use existing tools directly. Runtime metadata identifies deterministic
source, receipt, range, version, truncation, interruption and exit facts; you alone judge meaning and adequacy.
Update working.md only when future control should change. No per-wake rewrite is required."""

DCEC_CONTINUATION_PROMPT = """Preserve only the bounded current decision-centered state in monitor/working.md:
the current decision anchor and scope, one focal unresolved premise, current grounds with their support scope
and limits (including what boundary a current ground measured and which decision-relevant distinction it
bypassed, only when this still affects future control), and at most one relevant decision-critical observation
status (requested, running, interrupted or completed). Return the current state, not a chronology, checklist,
concern list or evidence ledger. Replace
superseded grounds instead of accumulating derived repeats. Claims and summaries remain source-qualified.
Intervention is recovery, not resolution; unfinished observations are not positive evidence; local grounds do
not become whole-task support. Completed evidence that bypassed the relevant behavioral boundary remains
qualified partial support, not a reason by itself to close a broader decision. A resolved concern leaves the
frontier unless a new relevant conflict reopens it.
Under a whole-task anchor, resolving one focal uncertainty returns to the same root decision for re-evaluation;
it does not authorize completion while another currently recognizable blocking alternative or unfinished
dependency remains. Preserve relaxation too: after adequate completed discriminating evidence, clear the
dependency and prune the resolved concern rather than manufacturing permanent uncertainty. Do not reactivate
a resolved concern merely because older dialogue mentions it; require a new relevant conflict or change."""

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
    def __init__(self, client, workspace: MonitorWorkspace, max_review_turns=20, *, stop_event=None,
                 independent_check=None):
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
        self.stop_event = stop_event if stop_event is not None else threading.Event()
        self.independent_check = independent_check
        self.analysis = AnalysisSessions(workspace.private_root, self.stop_event)
        self.review_id = None
        self._progress_warning = False
        self.intervention_callback = None
        self._sent_messages = set()
        self.grounded_context = getattr(client, "config", {}).get("monitor_grounded_context", False)
        self.client.progress_callback = self._progress
        self.semantic_continuity = getattr(client, "config", {}).get("monitor_semantic_continuity", True)
        self.dcec_enabled = getattr(client, "config", {}).get("monitor_dcec", False)
        if type(self.dcec_enabled) is not bool:
            raise ValueError("monitor_dcec must be a boolean")
        if self.dcec_enabled and type(self.semantic_continuity) is not bool:
            raise ValueError("monitor_semantic_continuity must be a boolean with monitor_dcec")
        self.dcec_working_chars = getattr(
            client, "config", {}).get("monitor_dcec_working_chars", DCEC_WORKING_VIEW_DEFAULT_CHARS)
        if (type(self.dcec_working_chars) is not int or
                not DCEC_WORKING_VIEW_MIN_CHARS <= self.dcec_working_chars <= DCEC_WORKING_VIEW_MAX_CHARS):
            raise ValueError(
                f"monitor_dcec_working_chars must be between {DCEC_WORKING_VIEW_MIN_CHARS} "
                f"and {DCEC_WORKING_VIEW_MAX_CHARS}")
        active_context = getattr(client, "config", {}).get("monitor_active_working_context", False)
        if type(active_context) is not bool:
            raise ValueError("monitor_active_working_context must be a boolean")
        live_awareness = getattr(client, "config", {}).get("monitor_live_awareness", False)
        if type(live_awareness) is not bool:
            raise ValueError("monitor_live_awareness must be a boolean")
        decision_context = getattr(client, 'config', {}).get('monitor_decision_context', False)
        if type(decision_context) is not bool:
            raise ValueError('monitor_decision_context must be a boolean')
        pma_memory = getattr(client, 'config', {}).get('monitor_pma_memory', False)
        if type(pma_memory) is not bool:
            raise ValueError('monitor_pma_memory must be a boolean')
        self.root_decision_contract = getattr(client, 'config', {}).get(
            'monitor_root_decision_contract', False)
        if type(self.root_decision_contract) is not bool:
            raise ValueError('monitor_root_decision_contract must be a boolean')
        if self.root_decision_contract and not pma_memory:
            raise ValueError('monitor_root_decision_contract requires monitor_pma_memory')
        self.root_simple_check = getattr(client, 'config', {}).get('monitor_root_simple_check', False)
        if type(self.root_simple_check) is not bool:
            raise ValueError('monitor_root_simple_check must be a boolean')
        if self.root_simple_check and (not pma_memory or self.root_decision_contract):
            raise ValueError('root_simple_check requires PMA and is exclusive with root_decision_contract')
        self.pma_memory = None
        self.task_understanding = None
        task_model = getattr(client, 'config', {}).get('monitor_task_model', False)
        if type(task_model) is not bool:
            raise ValueError('monitor_task_model must be a boolean')
        if task_model:
            raise ValueError('monitor_task_model is retired for fused execution; use the PMA bank and original task')
        if self.dcec_enabled:
            if not self.semantic_continuity:
                raise ValueError("monitor_dcec requires the ordinary semantic continuation path")
            incompatible = {
                'monitor_tool_feedback': tool_feedback,
                'monitor_grounded_context': self.grounded_context,
                'monitor_handoff_validation': getattr(client, 'config', {}).get('monitor_handoff_validation', False),
                'monitor_advice_revision': getattr(client, 'config', {}).get('monitor_advice_revision', False),
                'monitor_feedback_focus': getattr(client, 'config', {}).get('monitor_feedback_focus', False),
                'monitor_inquiry': getattr(client, 'config', {}).get('monitor_inquiry', False),
                'monitor_active_working_context': active_context,
                'monitor_live_awareness': live_awareness,
                'monitor_decision_context': decision_context,
                'monitor_pma_memory': pma_memory,
                'monitor_root_decision_contract': self.root_decision_contract,
                'monitor_root_simple_check': self.root_simple_check,
                'monitor_task_model': task_model,
                'monitor_independent_c': independent_check is not None,
            }
            enabled = sorted(name for name, value in incompatible.items() if value)
            if enabled:
                raise ValueError('monitor_dcec cannot be stacked with historical candidates: ' + ', '.join(enabled))
            self.system_prompt += "\n\n" + DCEC_SYSTEM_PROMPT
        self.live_awareness = LiveAwareness(workspace) if live_awareness else None
        self.decision_context = DecisionContext(workspace) if decision_context else None
        if pma_memory:
            from .pma_fused import FusedPMA
            self.pma_memory = FusedPMA(workspace, self._atomic_private_text, self._audit_dialogue)
            if self.decision_context is not None:
                self.decision_context.bank_owned = True
        self.active_context_enabled = active_context
        if live_awareness or active_context or decision_context or pma_memory or self.dcec_enabled:
            self.client.prepare_active_context = self._active_working_context
        if active_context and not decision_context and not pma_memory:
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
        if self.task_understanding is not None:
            parts.append(self.task_understanding.context())
        if self.pma_memory is not None:
            parts.append(self.pma_memory.context())
        if self.active_context_enabled and self.decision_context is None and self.pma_memory is None:
            text = current_working_context(self.workspace)
            self._audit_dialogue('active_working_context', content=text)
            if text:
                parts.append(text)
        if self.dcec_enabled:
            text, metadata = dcec_working_context(self.workspace, self.dcec_working_chars)
            self._audit_dialogue('dcec_working_view', **metadata)
            self._progress('dcec_working_view', **metadata)
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
        previous = (self.pma_memory.context() if self.pma_memory is not None else
                    note_path.read_text(encoding="utf-8") if note_path.exists() else "")
        prompt = (
            "Before older dialogue is compacted, write a concise natural-language working understanding "
            "for yourself to continue this same task. Preserve unresolved reasoning and corrections, their "
            "public evidence locations, what actually happened after advice, and remaining root scope. "
            "Revise stale beliefs rather than copying them. Do not treat unobserved uptake as success. "
            "Keep details that change future decisions, not a chronology. No fixed schema; return only the note. "
            "Do not issue task interventions in this maintenance response. Existing private working note:\n" + previous
        )
        if self.dcec_enabled:
            prompt += "\n\nDCEC continuation contract:\n" + DCEC_CONTINUATION_PROMPT
        self._progress("continuation_started")
        if self.grounded_context:
            prompt += ("\nPreserve useful source links or paths to active inquiry notes so your future self "
                       "can restore the actual grounds. Do not replace source links with invented quotations.")
        previous_system = self.client.system
        previous_purpose = getattr(self.client, 'request_purpose', 'review')
        transaction = uuid.uuid4().hex
        self.client.continuation_transaction_id = transaction
        self.client.request_purpose = 'continuation'
        self.client.system = self.system_prompt + "\n\n" + CONTINUATION_MODE_PROMPT
        self.client.history.append({"role": "user", "content": [{"type": "text", "text": prompt}]})
        stage = 'request'
        try:
            for attempt in range(2):
                stage = 'request'
                self.client.last_response_metadata = {}
                blocks, usage = self.client._request([])
                self.client.usage_records.append(dict(usage,
                    purpose='continuation_format_repair' if attempt else 'pre_compaction_continuation'))
                stage = 'response_archive'
                location = f'audit/continuation_responses/{transaction}-{attempt + 1}.json'
                raw = json.dumps({'blocks': blocks, 'metadata': self.client.last_response_metadata,
                                  'request_id': getattr(self.client, '_progress_request_id', None)},
                                 ensure_ascii=False)
                self._atomic_private_text(location, raw)
                self._progress('continuation_response_archived', transaction_id=transaction,
                               attempt=attempt + 1,
                               request_id=getattr(self.client, '_progress_request_id', None),
                               archive='monitor/' + location,
                               sha256=hashlib.sha256(raw.encode('utf-8')).hexdigest(),
                               system_sha256=hashlib.sha256(self.client.system.encode('utf-8')).hexdigest(),
                               tools_sha256=hashlib.sha256(b'[]').hexdigest(),
                               expected_output_kind='continuation_note',
                               metadata=self.client.last_response_metadata)
                stage = 'note_validation'
                try:
                    note = note_text(blocks, self.client.last_response_metadata)
                    break
                except ContinuationContractError as exc:
                    self._progress('continuation_rejected', transaction_id=transaction,
                                   attempt=attempt + 1, code=exc.code)
                    if attempt or exc.code not in {
                            'unexpected_tool', 'empty_note', 'reasoning_echo', 'truncated_note'}:
                        raise
                    from .provider import ProviderRecoveryExhausted
                    deadline = getattr(self.client, 'recovery_deadline', None)
                    stopped = any(flag is not None and flag.is_set() for flag in (
                        getattr(self.client, '_cancelled', None),
                        getattr(self.client, 'recovery_stop', None)))
                    if stopped or (deadline is not None and time.monotonic() >= deadline):
                        raise ProviderRecoveryExhausted('Continuation repair cancelled or budget exhausted') from exc
                    # Replace only our temporary instruction. Rejected blocks never
                    # enter live History and no tool or phase operation is replayed.
                    self.client.history[-1]['content'][0]['text'] = prompt + (
                        '\nYour previous response did not satisfy the note-only output contract ('
                        + exc.code + '). Return only a concise complete continuation note. '
                        'Do not call tools or decide task control. Keep essential unresolved grounds '
                        'and source references; fit the note within the existing output limit.')
                    self.client.request_purpose = 'format_repair'
                    self._progress('continuation_format_repair', transaction_id=transaction)
            self._progress('continuation_note_validated', transaction_id=transaction)
            if self.handoff_validation:
                stage = 'optional_handoff_validation'
                note = validate_handoff(self, note, previous)
            stage = 'note_storage'
            self.workspace.write_text("monitor/audit/continuations.jsonl", json.dumps({
                "timestamp": time.time(), "review_id": self.review_id, "note": note,
            }, ensure_ascii=False) + "\n", mode="append")
            if self.pma_memory is None:
                self._atomic_private_text("working.md", note)
            self._progress("continuation_saved", transaction_id=transaction)
            return note
        except Exception as exc:
            self._progress('continuation_failed', transaction_id=transaction, stage=stage,
                           error_type=type(exc).__name__,
                           code=exc.code if isinstance(exc, ContinuationContractError) else None)
            raise
        finally:
            self.client.history.pop()
            self.client.system = previous_system
            self.client.request_purpose = previous_purpose

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
            if name == 'allow_complete':
                if arguments and set(arguments) != {'_noargs'}:
                    raise ValueError('allow_complete accepts no arguments')
                arguments = {}
            if name == "file_read":
                data = self.workspace.read_text(
                    arguments["path"], arguments.get("start", 1), arguments.get("count", 200),
                    tail=arguments.get("tail", False),
                    offset=arguments.get("offset", 0), max_chars=arguments.get("max_chars", 20000),
                )
            elif name == "read_with_sources" and self.grounded_context:
                data = read_with_sources(self.workspace, arguments["path"],
                                         arguments.get("start", 1), arguments.get("count", 200))
            elif name == 'feedback_focus' and self.feedback_focus is not None:
                data = self.feedback_focus.call(**arguments)
            elif name == 'inquiry' and self.inquiry is not None:
                data = self.inquiry.call(**arguments)
            elif name == "file_write":
                data = self.workspace.write_text(
                    arguments["path"], arguments["content"], arguments.get("mode", "replace")
                )
                if self.dcec_enabled and arguments["path"].replace('\\', '/').strip('/') == 'monitor/working.md':
                    self._progress('dcec_state_mutation', operation='file_write',
                                   mode=arguments.get('mode', 'replace'), **data)
            elif name == "file_patch":
                data = self.workspace.patch_text(
                    arguments["path"], arguments["old_text"], arguments["new_text"]
                )
                if self.dcec_enabled and arguments["path"].replace('\\', '/').strip('/') == 'monitor/working.md':
                    self._progress('dcec_state_mutation', operation='file_patch', **data)
            elif name == "code_run":
                session_id = arguments.get('session_id')
                if session_id:
                    if any(k in arguments for k in ('code', 'type', 'timeout')):
                        raise ValueError('Use session_id alone to read/cancel; do not submit new code with it')
                    data = self.analysis.read(session_id, arguments.get('wait_seconds', 1),
                                              arguments.get('cancel', False))
                else:
                    if arguments.get('cancel'):
                        raise ValueError('cancel requires session_id')
                    data = self.analysis.start(arguments.get('code'), arguments.get('type', 'python'),
                                               arguments.get('timeout', 60), arguments.get('wait_seconds', 1))
            elif name == "independent_check":
                if self.independent_check is None:
                    raise ValueError("independent verification is disabled")
                question = str(arguments.get("question", "")).strip()
                paths = arguments.get("paths")
                if not question or not isinstance(paths, list) or not paths:
                    raise ValueError("question and at least one evidence path are required")
                if len(paths) > 8 or any(not isinstance(path, str) or not path.startswith("task/")
                                         for path in paths):
                    raise ValueError("independent evidence paths must be task/ paths")
                data = self.independent_check(question, tuple(paths))
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
                mode = arguments.get('mode', 'follow')
                if mode not in ('follow', 'patrol'):
                    raise ValueError('wait mode must be follow or patrol')
                return ToolOutcome(None, False, MonitorAction(
                    "wait", {"after_turns": max(1, int(arguments["after_turns"])), 'mode': mode}
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
            if (self.dcec_enabled and name in {'file_write', 'file_patch'}
                    and str(arguments.get('path', '')).replace('\\', '/').strip('/') == 'monitor/working.md'):
                self._progress('dcec_state_mutation_failed', operation=name,
                               error_type=type(exc).__name__)
            data = {"status": "error", "error": str(exc)}
        return ToolOutcome(data)

    def _refresh_completion(self):
        if self.completion_state is None:
            self.client.observed_root_handoff = None
            return None
        current = self.completion_state()
        if current and current["generation"] == self._intervened_generation:
            current = None
        self.completion_pending = current is not None
        # This identity is updated while assembling each real parent request,
        # after compaction and immediately before transport.  It therefore
        # follows what the request actually observed, not how the review began.
        self.client.observed_root_handoff = dict(current) if current else None
        if current == self._seen_completion:
            return None
        self._seen_completion = current
        if current is None:
            return "Runtime update: the previously observed task handoff is no longer pending."
        return ("Runtime update: the Task Agent is waiting on a current handoff at "
                f"task/public_events.jsonl line {current['cursor']}. Inspect its public message as needed. "
                "You may handle this handoff in this same review. Approval applies only to this proposal; "
                "waiting for more Task Agent turns cannot advance it without a response."
                + ('\nOriginal whole task for this handoff:\n' +
                   self.workspace.resolve_read('task/original_task.txt').read_text(encoding='utf-8')
                   if self.pma_memory is not None else ''))

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
        self.client.review_id = self.review_id
        self._progress('review_started', completion_pending=bool(completion_pending))
        before = self.client.history_measure()
        self.completion_pending = bool(completion_pending)
        self._sent_messages.clear()
        action = None
        try:
            if self.pma_memory is not None:
                pma_tools = [*MONITOR_TOOLS]
                if self.independent_check is not None:
                    pma_tools.append(INDEPENDENT_CHECK_TOOL)
                action = self.pma_memory.review(self, wake_context, pma_tools)
                return action
            if completion_pending and self.completion_state is None and self.task_understanding is not None:
                wake_context += self.task_understanding.completion_context()
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
            if self.independent_check is not None:
                tools = [*tools, INDEPENDENT_CHECK_TOOL]
            if self.decision_context is not None:
                system += (
                    '\n\nmonitor/overview.md is a refreshed file entry to ongoing work and original materials, '
                    'not an evidence summary. Read it with ordinary tools when useful. Keep your own '
                    'understanding in monitor/working.md: what you are trying to determine, why, and what '
                    'observation would resolve it. Organize this naturally; no required fields or per-wake rewrite. '
                    'A sound local repair can finish while other task requirements remain unresolved. '
                    'When the decision changes to whole-task completion, reconsider the original scope and '
                    'the support actually obtained, rather than extending a local success to everything. '
                    'Choose the original code, tests or observations that can settle the question; navigation '
                    'and your previous conclusions do not settle it. You need not inspect every unknown.'
                )
            if self.live_awareness is not None:
                system += (
                    "\n\nFile activity is sampled before normal requests, not monitored semantically for you. "
                    "While following a correction, distinguish investigating its grounds from checking "
                    "the Task Agent's latest response; choose which now matters. Existing file_read can "
                    "use tail=true with count to read the latest lines of any permitted file. "
                    "You can still inspect any earlier range or use code_run; no mandatory reread is imposed."
                )
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
