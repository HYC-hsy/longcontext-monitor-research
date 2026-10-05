"""Independent persistent Monitor Agent."""

from __future__ import annotations

import json
import hashlib
import os
import sys
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
from .path_control_v0 import (
    SYSTEM_PROMPT as PATH_CONTROL_SYSTEM_PROMPT,
    CONTINUATION_PROMPT as PATH_CONTROL_CONTINUATION_PROMPT,
    WORKING_GUIDANCE as PATH_CONTROL_WORKING_GUIDANCE,
    recent_public_events,
)
from .root_scope_v1 import ROOT_SYSTEM_PROMPT, ROOT_NOTE_GUIDANCE, root_input, task_budget_view
from .verification_loop_v0 import GUIDANCE as VERIFICATION_GUIDANCE, SelectedVerification
from .eis_v0 import GUIDANCE as EIS_GUIDANCE, executable_interpretation_surface
from .cfs_v0 import SituationState
from .dcm_v0 import DecisionMeasurementBoundary
from .cqs_v0 import ControlQuestionState


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


def verification_tools():
    """Same seven tool names, with opt-in check metadata and dispositions."""
    tools = json.loads(json.dumps(MONITOR_TOOLS))
    indexed = {tool['function']['name']: tool['function'] for tool in tools}
    indexed['code_run']['parameters']['properties']['verification'] = {
        'type': 'object', 'additionalProperties': False, 'properties': {
            'scope': {'type': 'string', 'enum': ['local', 'root']},
            'basis': {'type': 'string'}, 'question': {'type': 'string'},
            'artifacts': {'type': 'array', 'items': {'type': 'string'}, 'minItems': 1, 'maxItems': 8},
            'prior_disposition': {'type': 'string', 'enum': ['withdraw', 'revise']},
            'prior_reason': {'type': 'string'},
        }, 'required': ['scope', 'basis', 'question', 'artifacts']}
    indexed['code_run']['description'] += (
        ' In runtime-managed mode, optional verification metadata selects one public check and queues it '
        'for the next safe Task boundary. In manual mode, code_run executes once and the Supervisor '
        'organizes follow-up. Scope, basis, question and artifact paths define limited reach when selected. '
        'Analysis cwd remains monitor/; use the live task/workspace absolute path from the environment map in project commands.')
    indexed['wait']['parameters']['properties'].update({
        'result': {'type': 'string', 'enum': ['resolve', 'withdraw', 'revise', 'defer']},
        'reason': {'type': 'string'}})
    indexed['allow_complete']['parameters']['properties'].update({
        'result': {'type': 'string', 'enum': ['resolve', 'defer']},
        'reason': {'type': 'string'}})
    return tools

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

DCEC_SYSTEM_PROMPT = """Use monitor/working.md as bounded current cognitive state, not an evidence archive,
task checklist or second memory. Keep one consequential decision, one focal action ambiguity, and relevant
grounds and limits. Set the evidential reference from the public task and contemplated action: which material
states require different control? Revise it when the decision, public-task interpretation or action-relevant
distinction changes. Difficulty, infeasibility, unavailable measurement, cost, budget or apparent progress
may alter the feasible action, not the explicit public requirement or its evidential demand.

Keep a bounded action-relevant information state: public-task-grounded material states still compatible with
evidence, not only your favored state; do not enumerate a formal set. A decision resolves only when these
states are control-equivalent over its consequence horizon, not merely the next tool call. Different
consequences mean uncertainty even without a named defect. Patrol may relax amid action-irrelevant unknowns;
recovery and whole-task completion need support for their own consequences.

Before a decision-critical measurement intended to resolve the focal ambiguity, consider what supported and
action-divergent states would each produce and why results differ. Navigation, file finding and cheap
reconnaissance need no such precondition. Judge completed observations by actual reach, scope and conditions:
if material violation could leave a favorable result substantially unchanged, it is partial evidence.
Compilation need not distinguish runtime behavior; local repair need not reach unrelated scope. Treat
verified/complete/resolved labels, builds, Agent summaries and apparent quality as revisable shorthand,
not independent grounds. Repeating a proxy does not extend reach.

Keep one focal residual gap: a concrete discrepancy or premise, or material public reference outside the
grounds' reach. Satisfaction and violation may both remain compatible; no recognized defect is not evidence
of satisfaction. Do not invent or enumerate hypothetical defects outside public-task-grounded action relevance.

Choose one resolving observation that reduces consequential ambiguity, not a mechanical check of every
requirement. One observation may jointly reach several obligations if their violation would change its result.
Tighten by improving discrimination, not adding calls. If measurement is unavailable, interrupted, infeasible
or too costly, change the scheme, not the contrast or public reference; a proxy favorable in both states cannot
resolve it. If none is feasible, retain uncertainty and choose a public-task-consistent action. Information
must exclude an action-changing alternative, correct reach or discrimination basis, or reveal a material
discrepancy warranting intervention. Repeated checks without such change call for a new scheme, revised premise
or justified action, not cumulative proxy support. Keep at most one decision-critical observation dependency
(requested, running, interrupted or completed). Unfinished observation is not positive evidence. Intervention
starts recovery, not resolution; local evidence resolves only local scope. Retain an unfinished dependency until
its result, a discriminating replacement or changed decision supersedes it. Do not build workflow history.

Task Agent changes are world transitions, not positive evidence. Retain only grounds future consequential
decisions may reuse, with enough context to recall why an observation distinguished alternatives, what it
reached, and whether later changes preserve that discrimination basis. Same-review transient observations
need no bookkeeping entry. Carry an old ground when its basis still applies; Reopen the alternative when a
transition crossed it, without denying the historical observation; Prune it when irrelevant. At a
high-consequence decision, unknown applicability means withhold current positive support and boundedly
requalify, not default-Carry. Change is not invalidation: changed direct-file hash does not automatically
Reopen; unchanged direct-file hash does not automatically Carry when related dispatch/config/API/wiring changed.
Source, hash, cursor and receipts are transition facts, not semantic verdicts. Unrelated changes permit Carry.

At root handoff, set the reference to public whole-task completion and requalify grounds against it. After
local repair, return to this root;
local adequacy alone never authorizes allow_complete. Use current observations or old grounds legitimately
transported/requalified to the current world, not favorable labels summed across snapshots. Reuse adequate
transported grounds without ceremonial retest. An uncovered public obligation remains open even without a
specific defect; seek bounded discrimination, not a ledger or exhaustive proof. If the decision changes
mid-review, immediately recondition the reference before higher-consequence control. A completion proposal
arising during patrol, follow or recovery requires whole-task requalification in that review.

When compatible material states are control-equivalent and no unfinished observation could change the action,
clear dependency, prune superseded grounds and relax to patrol, continued execution or justified scoped action.
Allow whole-task completion only when evidence reach makes its public reference action-determined. Runtime
metadata supplies procedural facts; you judge meaning and adequacy. Update working.md only when future control
should change, not every wake."""

DCEC_CONTINUATION_PROMPT = """Preserve in monitor/working.md the current decision and public evidential
reference, one focal action-separating gap (including an unnamed uncovered obligation), and at most one
observation status. Keep only a few grounds future consequential control may reuse, with natural-language
context sufficient to reconsider their applicability after task changes. Do not turn "no remembered defect"
into "no gap", carry an old ground unconditionally into a changed world, or lower the public reference because
measurement is unavailable or costly. Keep current state, not chronology, a ledger or a fixed form. If the
decision changes, including mid-review completion, requalify grounds; after adequate evidence, prune and
relax. Old dialogue alone does not reopen a resolved gap; require new conflict or a changed premise."""

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
        self.base_system_prompt = self.system_prompt
        self.workspace = workspace
        self.max_review_turns = int(max_review_turns)
        self.completion_pending = False
        self.frame_kind = 'local'
        self.root_frame_handoff = None
        self._local_history_at_root = None
        self.completion_state = None
        self.task_budget_state = None
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
        self.path_control_v0 = getattr(client, "config", {}).get("monitor_path_control_v0", False)
        if type(self.path_control_v0) is not bool:
            raise ValueError("monitor_path_control_v0 must be a boolean")
        if self.path_control_v0 and not self.dcec_enabled:
            raise ValueError("monitor_path_control_v0 requires monitor_dcec")
        self.root_scope_v1 = getattr(client, 'config', {}).get('monitor_root_scope_v1', 'off')
        if self.root_scope_v1 not in {'off', 'retained', 'isolated'}:
            raise ValueError('monitor_root_scope_v1 must be off, retained or isolated')
        if self.root_scope_v1 != 'off' and not self.path_control_v0:
            raise ValueError('monitor_root_scope_v1 requires monitor_path_control_v0')
        self.verification_loop_v0 = getattr(client, 'config', {}).get('monitor_verification_loop_v0', False)
        self.verification_runtime_managed = getattr(
            client, 'config', {}).get('monitor_verification_runtime_managed', True)
        if type(self.verification_loop_v0) is not bool or type(self.verification_runtime_managed) is not bool:
            raise ValueError('verification loop switches must be boolean')
        if self.verification_loop_v0 and (not self.path_control_v0 or self.root_scope_v1 != 'off'):
            raise ValueError('verification_loop_v0 requires PATH and the old root scope off')
        self.eis_v0 = getattr(client, 'config', {}).get('monitor_executable_interpretation_surface', False)
        if type(self.eis_v0) is not bool:
            raise ValueError('monitor_executable_interpretation_surface must be a boolean')
        if self.eis_v0 and (not self.verification_loop_v0 or self.verification_runtime_managed):
            raise ValueError('EIS-v0 requires continuous verification in manual mode')
        self.cfs_v0 = getattr(client, 'config', {}).get('monitor_coarse_to_fine_surface', False)
        if type(self.cfs_v0) is not bool:
            raise ValueError('monitor_coarse_to_fine_surface must be a boolean')
        if self.cfs_v0 and (not self.verification_loop_v0 or self.verification_runtime_managed
                            or self.eis_v0):
            raise ValueError('CFS-v0 requires manual continuous verification and EIS off')
        self.situation = SituationState(workspace) if self.cfs_v0 else None
        self.dcm_v0 = getattr(client, 'config', {}).get('monitor_decision_conditioned_measurement', False)
        if type(self.dcm_v0) is not bool:
            raise ValueError('monitor_decision_conditioned_measurement must be a boolean')
        if self.dcm_v0 and (not self.cfs_v0 or not self.verification_loop_v0
                            or self.verification_runtime_managed or self.eis_v0):
            raise ValueError('DCM-v0 requires CFS, manual continuous verification and EIS off')
        self.dcm = DecisionMeasurementBoundary(self._audit_dialogue) if self.dcm_v0 else None
        self.cqs_v0 = getattr(client, 'config', {}).get('monitor_control_question_state', False)
        if type(self.cqs_v0) is not bool:
            raise ValueError('monitor_control_question_state must be a boolean')
        if self.cqs_v0 and (not self.dcm_v0 or not self.cfs_v0 or not self.verification_loop_v0
                            or self.verification_runtime_managed or self.eis_v0
                            or self.root_scope_v1 != 'off'
                            or getattr(client, 'config', {}).get('monitor_release_support_horizon', False)):
            raise ValueError('CQS-v0 requires CFS, DCM, manual continuous verification, EIS/RSH off')
        self.cqs = ControlQuestionState(self._audit_dialogue) if self.cqs_v0 else None
        self._dialogue_line = None
        if self.situation is not None:
            self.client.active_context_appended = self._cfs_context_appended
        self.root_routed = self.root_scope_v1 != 'off' or self.verification_loop_v0
        self.verification = (SelectedVerification(
            workspace, self.analysis, self._progress,
            getattr(client, 'verification_due_turn', None),
            getattr(client, 'verification_accepted_generation', None))
            if self.verification_loop_v0 and self.verification_runtime_managed else None)
        research_view = getattr(client, "config", {}).get("monitor_research_view", "off")
        research_intent = getattr(client, "config", {}).get("monitor_research_intent", "off")
        if type(research_view) is not str or research_view not in {"off", "flat", "framed"}:
            raise ValueError("monitor_research_view must be off, flat or framed")
        if type(research_intent) is not str or research_intent not in {"off", "note", "routed"}:
            raise ValueError("monitor_research_intent must be off, note or routed")
        if (research_view != "off" or research_intent != "off") and not self.dcec_enabled:
            raise ValueError("experimental working operations require monitor_dcec")
        self.experimental_control = None
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
            if self.path_control_v0 and (research_view != "off" or research_intent != "off"):
                raise ValueError("monitor_path_control_v0 requires experimental view and intent off")
            self.system_prompt += "\n\n" + (
                PATH_CONTROL_SYSTEM_PROMPT if self.path_control_v0 else DCEC_SYSTEM_PROMPT)
        if self.verification_loop_v0:
            self.system_prompt += "\n\n" + VERIFICATION_GUIDANCE
        if self.eis_v0:
            self.system_prompt += "\n\n" + EIS_GUIDANCE
        if research_view != "off" or research_intent != "off":
            from .experimental_control import ExperimentalControl
            self.experimental_control = ExperimentalControl(
                workspace, self.analysis, client, research_view, research_intent,
                intent_window_requests=getattr(client, "config", {}).get(
                    "monitor_research_intent_window_requests", 4))
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
        if self.frame_kind == 'root' and not self.verification_loop_v0:
            text, metadata = dcec_working_context(
                self.workspace, self.dcec_working_chars, ROOT_NOTE_GUIDANCE)
            self._audit_dialogue('root_working_view', **metadata)
            return text
        parts = []
        if self.verification_loop_v0:
            parts.append('Verification mode: runtime-managed selected checks and follow-up.'
                         if self.verification_runtime_managed else
                         'Verification mode: manual single code_run execution; organize follow-up yourself; '
                         'no automatic check queue or retest.')
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
            if self.cqs is not None:
                parts.append(self.cqs.render())
            else:
                if self.path_control_v0 and self.frame_kind != 'root':
                    text, metadata = dcec_working_context(
                        self.workspace, self.dcec_working_chars, PATH_CONTROL_WORKING_GUIDANCE)
                else:
                    text, metadata = dcec_working_context(self.workspace, self.dcec_working_chars)
                self._audit_dialogue('dcec_working_view', **metadata)
                self._progress('dcec_working_view', **metadata)
                parts.append(text)
            if self.path_control_v0 and not self.cfs_v0:
                window, window_metadata = recent_public_events(
                    self.workspace, getattr(self.client, 'observed_root_handoff', None))
                self._audit_dialogue('path_control_public_window', content=window, **window_metadata)
                parts.append(window)
            if self.situation is not None:
                used, limit = self.task_budget_state() if self.task_budget_state else (None, None)
                deadline = getattr(self.client, 'recovery_deadline', None)
                surface, metadata = self.situation.build(
                    handoff=getattr(self.client, 'observed_root_handoff', None),
                    used_turns=used, max_turns=limit,
                    remaining_seconds=deadline - time.monotonic() if deadline is not None else None)
                self._audit_dialogue('supervisory_situation_surface', content=surface, **metadata)
                parts.append(surface)
            if self.eis_v0:
                surface, surface_metadata = executable_interpretation_surface(self.workspace)
                self._audit_dialogue('executable_interpretation_surface', content=surface, **surface_metadata)
                parts.append(surface)
        if self.experimental_control is not None:
            block = self.experimental_control.active_block()
            if block:
                parts.append(block)
        if self.live_awareness is not None:
            text, metadata = self.live_awareness.context()
            self._audit_dialogue('live_awareness', content=text, **metadata)
            parts.append(text)
        if self.decision_context is not None:
            text = self.decision_context.attention()
            self._audit_dialogue('decision_attention', content=text)
            parts.append(text)
        return '\n\n'.join(parts) or None

    def _cfs_context_appended(self):
        shown = self.situation.context_appended()
        if shown is not None:
            self._audit_dialogue('supervisory_situation_injected',
                                 shown_through_cursor=shown['cursor'],
                                 manifest_locator=shown['manifest_locator'], content=shown['text'])
        if self.cqs is not None:
            self.cqs.surface_visible()

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
        if self.dcm is not None and event == 'tool_call':
            self.dcm.model_turn = payload.get('turn')
        path = self.workspace.private_root / 'audit' / 'dialogue.jsonl'
        path.parent.mkdir(parents=True, exist_ok=True)
        record = dict(timestamp=time.time(), review_id=self.review_id, event=event, **payload)
        with path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(record, ensure_ascii=False, default=str) + '\n')
            stream.flush()
        if self.cqs is not None:
            if self._dialogue_line is None:
                with path.open('rb') as stream:
                    self._dialogue_line = sum(1 for _ in stream)
            else:
                self._dialogue_line += 1
            self.cqs.observe(record, self._dialogue_line)

    def _prepare_continuation(self):
        """Same model, existing history, no tool actions during pre-compaction handoff."""
        note_path = self.workspace.resolve_private("monitor/working.md")
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
        if self.frame_kind == 'root' and not self.verification_loop_v0:
            prompt += ("\n\nPreserve the current handoff question, observed public grounds and limits, "
                       "and the next useful root decision. Do not turn prior local conclusions into "
                       "a whole-task verdict.")
        elif self.dcec_enabled:
            prompt += "\n\nDCEC continuation contract:\n" + (
                PATH_CONTROL_CONTINUATION_PROMPT if self.path_control_v0 else DCEC_CONTINUATION_PROMPT)
        self._progress("continuation_started")
        if self.grounded_context:
            prompt += ("\nPreserve useful source links or paths to active inquiry notes so your future self "
                       "can restore the actual grounds. Do not replace source links with invented quotations.")
        previous_system = self.client.system
        previous_purpose = getattr(self.client, 'request_purpose', 'review')
        transaction = uuid.uuid4().hex
        self.client.continuation_transaction_id = transaction
        self.client.request_purpose = 'continuation'
        active_system = (self.base_system_prompt + "\n\n" + ROOT_SYSTEM_PROMPT
                         if self.frame_kind == 'root' else self.system_prompt)
        self.client.system = active_system + "\n\n" + CONTINUATION_MODE_PROMPT
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
                self._atomic_private_text(self.workspace.working_note_target, note)
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
        if self.dcm is not None:
            self.dcm.next_tool(name, arguments)
        self._progress('tool_started', tool_id=tool_id, name=name)
        try:
            outcome = self._dispatch(name, arguments)
            if self.experimental_control is not None and name not in {'work_context', 'work_intent'}:
                try:
                    self.experimental_control.audit(
                        'ordinary_tool_outcome', name=name,
                        outcome_status=(outcome.data or {}).get('status') if isinstance(outcome.data, dict) else None,
                        control_action=outcome.action.kind if outcome.action is not None else None)
                except Exception as exc:
                    self._progress('experimental_registration_failed', name=name,
                                   error_type=type(exc).__name__)
            return outcome
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
            if name == 'work_context' and self.experimental_control is not None:
                if self.experimental_control.view == 'off':
                    raise ValueError('work_context is disabled')
                return ToolOutcome(self.experimental_control.context_tool(arguments))
            if name == 'work_intent' and self.experimental_control is not None:
                if self.experimental_control.intent == 'off':
                    raise ValueError('work_intent is disabled')
                return ToolOutcome(self.experimental_control.intent_tool(arguments))
            if name == 'allow_complete':
                allowed = {'_noargs', 'result', 'reason'} if self.verification_loop_v0 else {'_noargs'}
                if set(arguments) - allowed:
                    raise ValueError('allow_complete accepts no arguments')
                arguments = {key: value for key, value in arguments.items() if key != '_noargs'}
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
                    if any(k in arguments for k in ('code', 'type', 'timeout', 'verification')):
                        raise ValueError('Use session_id alone to read/cancel; do not submit new code with it')
                    data = self.analysis.read(session_id, arguments.get('wait_seconds', 1),
                                              arguments.get('cancel', False))
                else:
                    if arguments.get('cancel'):
                        raise ValueError('cancel requires session_id')
                    if self.verification is not None and arguments.get('verification') is not None:
                        if (isinstance(arguments['verification'], dict)
                                and arguments['verification'].get('scope') == 'root'
                                and self.frame_kind != 'root'):
                            raise ValueError('Root verification requires the current root decision frame')
                        used, _ = self.task_budget_state() if self.task_budget_state else (None, None)
                        data = self.verification.register(arguments, used or 0)
                    else:
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
                after_turns = max(1, int(arguments["after_turns"]))
                if self.dcm is not None:
                    if mode == 'patrol':
                        boundary = self.dcm.release('patrol', 'local', arguments)
                        if boundary is not None:
                            return ToolOutcome(boundary)
                    else:
                        self.dcm.abandon('changed_to_follow')
                if self.verification is not None and mode == 'patrol' and self.verification.follow_pending:
                    self.verification.dispose(arguments.get('result'), arguments.get('reason'))
                return ToolOutcome(None, False, MonitorAction(
                    "wait", {"after_turns": after_turns, 'mode': mode}
                ))
            elif name == "intervene":
                message = str(arguments.get("message", "")).strip()
                if not message: raise ValueError("message must not be empty")
                if (self.frame_kind == 'root' and
                        (self.completion_state is None or
                         self.completion_state() != self.root_frame_handoff)):
                    raise ValueError('This root handoff is no longer current; no correction was sent.')
                if (self.root_routed and self.frame_kind != 'root'
                        and self.completion_state is not None and self.completion_state()):
                    raise ValueError('A current handoff requires the root decision frame before control.')
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
                    if self.dcm is not None:
                        self.dcm.abandon('intervened')
                    if self.cqs is not None:
                        self.cqs.submitted_intervention(message)
                    if self.verification is not None:
                        self.verification.on_intervention(message)
                    if self._seen_completion:
                        self._intervened_generation = self._seen_completion["generation"]
                    self.completion_pending = False
                    if self.frame_kind == 'root':
                        return ToolOutcome(
                            {"status": "submitted", "receipt": receipt,
                             "note": "This handoff ended; later Task behavior remains to be observed."},
                            False, MonitorAction('root_intervened', {
                                'request_id': self.root_frame_handoff['request_id'],
                                'generation': self.root_frame_handoff['generation']}))
                    return ToolOutcome({"status": "submitted", "receipt": receipt,
                                        "note": "Submission is not proof of delivery or uptake. Continue observing; wait when appropriate.",
                                        **self._remember_advice(message, arguments)})
                self._remember_advice(message, arguments)
                if self.dcm is not None:
                    self.dcm.abandon('intervened')
                return ToolOutcome(None, False, MonitorAction("intervene", {"message": message}))
            elif name == "allow_complete":
                if self.verification_loop_v0 and arguments.get('result') not in {'resolve', 'defer'}:
                    raise ValueError('allow_complete result must be resolve or defer')
                if self.root_routed:
                    current = self.completion_state() if self.completion_state else None
                    if (self.frame_kind != 'root' or current != self.root_frame_handoff
                            or not current or current['generation'] == self._intervened_generation):
                        raise ValueError('Only the current root decision frame can approve this handoff.')
                if self.completion_state is not None:
                    current = self.completion_state()
                    if (not self._seen_completion or current != self._seen_completion
                            or current["generation"] == self._intervened_generation):
                        raise ValueError("The observed handoff is no longer current. Inspect the runtime update before deciding.")
                    if self.dcm is not None:
                        if arguments['result'] == 'resolve':
                            boundary = self.dcm.release('allow_complete', 'root', arguments)
                            if boundary is not None:
                                return ToolOutcome(boundary)
                        else:
                            self.dcm.abandon('deferred')
                    if self.verification is not None:
                        disposition = arguments.get('result')
                        self.verification.dispose(disposition, arguments.get('reason'), root=True)
                    if self.verification_loop_v0 and arguments['result'] == 'defer':
                        return ToolOutcome(None, False, MonitorAction('incomplete_delivery', {
                            'reason': arguments['reason'], 'request_id': current['request_id']}))
                    return ToolOutcome(None, False, MonitorAction(
                        "allow_complete", {"request_id": current["request_id"],
                                           "root_frame_generation": current['generation']}
                        if self.root_routed else
                        {"request_id": current["request_id"]}))
                if not self.completion_pending: raise ValueError("No root completion is pending")
                return ToolOutcome(None, False, MonitorAction("allow_complete", {}))
            else:
                data = {"status": "error", "error": f"Unknown tool: {name}"}
        except Exception as exc:
            if self.experimental_control is not None and name in {'work_context', 'work_intent'}:
                self.experimental_control.audit('operation_failed', name=name,
                                                error_type=type(exc).__name__)
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
        if self.verification is not None:
            if self.frame_kind == 'root' and self.verification.current is not None:
                used, _ = self.task_budget_state() if self.task_budget_state else (None, None)
                self.verification.run_due(used or 0, force=True)
            updates.append(self.verification.context())
        if self.root_routed and self.frame_kind == 'local':
            used, limit = self.task_budget_state() if self.task_budget_state else (None, None)
            deadline = getattr(self.client, 'recovery_deadline', None)
            updates.append(task_budget_view(
                used, limit, deadline - time.monotonic() if deadline is not None else None))
        if self.advice_basis is not None:
            try:
                updates.append(self.advice_basis.refresh())
            except Exception as exc:
                self._progress("advice_read_failed", error_type=type(exc).__name__)
                updates.append("Private advice note unavailable; use existing history and original evidence. "
                               + type(exc).__name__)
        return "\n\n".join(update for update in updates if update) or None

    def _enter_root_frame(self, handoff):
        if not handoff or self.completion_state is None or self.completion_state() != handoff:
            raise ValueError('Root frame requires the current pending handoff')
        self._local_history_at_root = self.client.export_history()
        self.root_frame_handoff = dict(handoff)
        self.frame_kind = 'root'
        if self.verification_loop_v0:
            self._progress('root_frame_entered', mode='verification_loop_v0',
                           generation=handoff['generation'], request_id=handoff['request_id'],
                           inherited_history_items=len(self.client.history))
            return
        relative = f"root_working/{handoff['generation']}.md"
        self.workspace.working_note_target = relative
        local_note = self.workspace.private_root / 'working.md'
        inherited = (local_note.read_text(encoding='utf-8')
                     if self.root_scope_v1 == 'retained' and local_note.is_file() else '')
        self._atomic_private_text(relative, inherited)
        self.client.restore_history(self._local_history_at_root if self.root_scope_v1 == 'retained' else [])
        self._progress('root_frame_entered', mode=self.root_scope_v1,
                       generation=handoff['generation'], request_id=handoff['request_id'],
                       inherited_history_items=len(self.client.history),
                       inherited_note_characters=len(inherited))

    def _leave_root_frame(self):
        if self.frame_kind != 'root':
            return
        handoff = self.root_frame_handoff
        if self.verification_loop_v0:
            self.frame_kind = 'local'
            self.root_frame_handoff = None
            self._local_history_at_root = None
            self._progress('root_frame_left', generation=handoff['generation'],
                           request_id=handoff['request_id'])
            return
        self._atomic_private_text(
            f"audit/root_frames/{handoff['generation']}/history.json",
            json.dumps(self.client.export_history(), ensure_ascii=False))
        self.client.restore_history(self._local_history_at_root)
        self.workspace.working_note_target = 'working.md'
        self.frame_kind = 'local'
        self.root_frame_handoff = None
        self._local_history_at_root = None
        self._progress('root_frame_left', generation=handoff['generation'],
                       request_id=handoff['request_id'])

    def review(self, wake_context: str, completion_pending=False, *,
               root_handoff=None, max_turns_override=None,
               root_transition_view=None) -> MonitorAction:
        started = time.time()
        self.review_id = uuid.uuid4().hex
        self.client.review_id = self.review_id
        if self.dcm is not None:
            self.dcm.begin_review(self.review_id)
        if self.cqs is not None:
            self.cqs.begin_review(self.review_id)
        if self.situation is not None:
            self.situation.begin_review(self.review_id)
        if root_handoff is not None:
            self._enter_root_frame(root_handoff)
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
            active_system = (self.base_system_prompt + "\n\n" + ROOT_SYSTEM_PROMPT
                             if self.frame_kind == 'root' and not self.verification_loop_v0
                             else self.system_prompt)
            system = active_system + "\n\n" + mode
            if self.frame_kind == 'root':
                remaining = getattr(self.client, 'recovery_deadline', None)
                used, limit = self.task_budget_state() if self.task_budget_state else (None, None)
                wake_context = root_input(
                    self.workspace, self.root_frame_handoff,
                    remaining_seconds=(remaining - time.monotonic()) if remaining is not None else None,
                    task_turns_used=used, task_max_turns=limit,
                    single_session=self.verification_loop_v0)
                if root_transition_view:
                    wake_context += "\n\n" + root_transition_view
                self._audit_dialogue('root_frame_input', mode=self.root_scope_v1,
                                     handoff=self.root_frame_handoff, content=wake_context)
            tools = verification_tools() if self.verification_loop_v0 else MONITOR_TOOLS
            if self.independent_check is not None:
                tools = [*tools, INDEPENDENT_CHECK_TOOL]
            if self.experimental_control is not None:
                from .experimental_control import GUIDANCE, WORK_CONTEXT_TOOL, WORK_INTENT_TOOL
                system += "\n\n" + GUIDANCE
                tools = [*tools]
                if self.experimental_control.view != 'off':
                    tools.append(WORK_CONTEXT_TOOL)
                if self.experimental_control.intent != 'off':
                    tools.append(WORK_INTENT_TOOL)
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
            if self.experimental_control is not None:
                self.experimental_control.audit(
                    'review_contract',
                    system_sha256=hashlib.sha256(system.encode('utf-8')).hexdigest(),
                    tools_sha256=hashlib.sha256(json.dumps(
                        tools, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest())
            action = run_review(
                self.client, system, wake_context, tools,
                self.dispatch, self.max_review_turns if max_turns_override is None else max_turns_override,
                audit=self._audit_dialogue,
                before_model=self._refresh_review_context,
                route_before_model=(lambda: bool(self.completion_state and self.completion_state())
                                    if self.root_routed and self.frame_kind == 'local'
                                    else None),
            )
            if self.cqs is not None:
                self.cqs.completed_wait(action)
            return action
        finally:
            if self.dcm is not None:
                error = sys.exc_info()[1]
                disposition = ('review_exhausted' if error is not None and
                               type(error).__name__ == 'MonitorLoopError' else
                               'error' if error is not None else 'review_ended')
                self.dcm.end_review(disposition)
            if self.situation is not None:
                self.situation.end_review(action)
            self._progress('review_finished', action=action.kind if action else None,
                           duration_seconds=time.time() - started,
                           frame=self.frame_kind,
                           handoff=self.root_frame_handoff)
            telemetry = self.client.drain_telemetry() if hasattr(self.client, "drain_telemetry") else {}
            self.workspace.write_text(
                "monitor/audit/reviews.jsonl",
                json.dumps({
                    "started_at": started, "duration_seconds": time.time() - started,
                    "history_before": before, "history_after": self.client.history_measure(),
                    "action": asdict(action) if action else None,
                    "frame": self.frame_kind, "handoff": self.root_frame_handoff,
                }, ensure_ascii=False) + "\n", mode="append",
            )
            self._leave_root_frame()
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
