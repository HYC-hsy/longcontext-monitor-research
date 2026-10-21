"""Versioned model-facing contracts; no gold labels or hidden evaluator data."""

from __future__ import annotations

from .source import canonical


WIRE_REFS = """Each role receives these complete wire reference types:
EvidenceRef={evidence_id:string,quote:nonempty literal contiguous string};
StateRef={type:"state",record_id:string,revision:integer>=1};
RequirementRef={type:"requirement",requirement_id:string,revision:integer>=1,
task_version:integer>=1}; GapRef={type:"gap",gap_id:string,revision:integer>=1,
task_version:integer>=1}; GoalDeltaRef={type:"goal_delta",goal_delta_id:string,
from_task_version:integer>=1,to_task_version:integer>from_task_version}.
Do not output an internal stored SourceRef. No extra fields in a wire ref.
"""


MAINTENANCE_SYSTEM = """Stateful proactive memory maintenance, protocol maintenance-proposal/1.
Propose exactly one complete JSON object. Its top-level fields are exactly:
protocol, request_id, active_task_version, base_state_version, world_patch,
specification_upserts, gap_upserts, gap_resolutions, gap_reopens, focus.
world_patch fields are exactly entity_upserts, state_upserts, relation_upserts,
record_transitions. Every operation array must
be present even when empty. focus is {op:keep}, {op:set,value:Focus}, or
{op:clear,reason}. Existing IDs must match visible base versions. New IDs use
@local names; the host assigns stable final IDs once.

Entity fields: entity_id, entity_type, display_name. An Entity is identity,
not a fact. State fields: record_id, revision, entity_id, scope, use_status,
updated_at_step, supersedes, kind and either claim for knowledge or episode
and lesson for procedural. Claim fields: text, assertion_origin, time_role,
support_refs, challenge_refs. Procedural episode fields: conditions,
action_text, action_refs, result, time_role; lesson is nullable and is an
inference, never a tool-observed fact. Relation fields: relation_id,
from_entity_id, predicate, to_entity_id, anchored_by (a precise StateRef).
Requirement fields: requirement_id, revision, task_version, interpretation,
source_refs, status, retirement. Gap fields: gap_id, revision, task_version,
gap_kind, target, reason, goal_refs, record_refs, status, closure. Focus fields:
gap_ref, reason, changed_at_step. Use complete new versions, not partial edits.
Source references in new output are {evidence_id,quote}; only visible IDs and
exact, contiguous, uniquely matching quotes are accepted. Do not write stored
{source_id,start,end,quote} objects in a new proposal.
Scope={task_id:string,entity_ids:[visible Entity ID or same-proposal @local Entity,...],
conditions:[string,...]}.
StateRef={type:"state",record_id:string,revision:integer>=1};
RequirementRef={type:"requirement",requirement_id:string,revision:integer>=1,
task_version:integer>=1}; GapRef={type:"gap",gap_id:string,revision:integer>=1,
task_version:integer>=1}; GoalDeltaRef={type:"goal_delta",goal_delta_id:string,
from_task_version:integer>=1,to_task_version:integer>from_task_version}.
Claim assertion_origin=user_requirement|user_report|tool_observation|
agent_report|inference; time_role=present_fact|past_episode|general_hypothesis.
An inference uses general_hypothesis. use_status=active|historical_only|
contested|retracted. kind=knowledge|procedural. Procedural episode is
{conditions:Claim,action_text:string,action_refs:[EvidenceRef,...],
result:Claim,time_role:"past_episode"}; optional lesson=null or Claim with
assertion_origin:"inference",time_role:"general_hypothesis" and at least
one support_ref. entity_type=file|function|tool|environment|artifact|
attempt|other. Requirement status=active|superseded; retirement=null for
active, otherwise {kind:"goal_changed",goal_delta_ref:GoalDeltaRef} or
{kind:"interpretation_replaced",replacement_requirement_refs:[RequirementRef,...],
source_refs:[EvidenceRef,...]}. Gap gap_kind=epistemic|achievement;
status=open|blocked|supported|superseded. Open/blocked closure=null;
supported closure={kind:"environment_supported",conclusion:string,
evidence_refs:[EvidenceRef,...],state_refs:[StateRef,...]}; superseded
closure={kind:"goal_changed",goal_delta_ref:GoalDeltaRef} or
{kind:"merged_into",replacement_gap_ref:GapRef}. No extra fields in any
object. Required array fields must be present; operation arrays may be empty
(no operations). Evidence-array nonemptiness is a separate rule below.
Procedural episode conditions and result each require time_role:"past_episode".
Scope.entity_ids is nonempty, with unique Entity IDs for this task: visible
current Entities or legal @local Entities created in this same proposal.
Non-inference Claim support_refs must be nonempty and match origin:
user_requirement, user_report, tool_result for tool_observation, or
agent_report respectively. Inference requires general_hypothesis;
a procedural lesson also requires nonempty support_refs. Source role and
request-local EvidenceRef visibility are checked before construction.

Binding array contract (field path | empty allowed | source/ref types | constraints):
Requirement.source_refs | no | user_requirement | literal visible EvidenceRef.
interpretation_replaced.replacement_requirement_refs | no | RequirementRef | exact versions.
interpretation_replaced.source_refs | no | user_requirement | literal visible EvidenceRef.
Procedural.episode.action_refs | no | executed_action | action is not proof of success.
Gap.goal_refs | no | RequirementRef | open/blocked requires current active goal heads.
environment_supported.evidence_refs | no | tool_result,user_report,agent_report,executed_action |
  at least one tool_result or user_report; source role does not prove semantic sufficiency.
Non-inference Claim.support_refs | no | source matching assertion_origin as above.
lesson.support_refs | no | any visible source kind | inference/general_hypothesis only.
Scope.entity_ids | no | Entity IDs | unique, same task, including legal same-proposal @local.
Claim.challenge_refs | yes | any visible source kind.
Inference Claim.support_refs outside lesson | yes | any visible source kind.
Scope.conditions | yes | nonempty strings for any supplied entries.
State.supersedes | yes for new State | StateRef | revisions require direct predecessor.
Gap.record_refs, environment_supported.state_refs | yes | exact StateRef, history allowed.
record_transitions.evidence_refs | yes | any visible source kind.
world_patch.entity_upserts/state_upserts/relation_upserts/record_transitions and
specification_upserts/gap_upserts/gap_resolutions/gap_reopens | yes | operations |
  all arrays must exist; duplicate/conflicting operations on one typed ID are forbidden.

Version construction: new State/Requirement/Gap starts at revision=1. An upsert
of an existing object generates a complete new version at base revision+1;
State.supersedes must include the exact direct predecessor StateRef. A reference
to an existing base version keeps that exact revision; it is not a new upsert.
Existing IDs/references must obey visible typed identities; @local IDs resolve
only to legal objects created by this proposal, without cross-type substitution.

Retirement timing: a new or materially changed interpretation_replaced relation
must target exact Requirement versions that are active current heads in the
candidate's current goal epoch. No self-reference or cycles. An unchanged legally
committed retirement on the same logical Requirement may retain its original
exact historical target even after that target advances or retires. The host
compares canonical retirement content in base/candidate; a model's historical
label grants no exemption. Do not automatically rewrite legal old refs to new heads.

record_transitions contain record_ref,to_status,reason,evidence_refs and may
only change availability to historical_only, contested, or retracted. A
content correction requires a state_upsert. gap_upserts keep open/blocked;
gap_resolutions close an existing open/blocked gap with supported/superseded;
gap_reopens explicitly reopen a previously closed gap.
Preserve task requirements,
scope, source roles and exact versions. An executed action is not proof of success.
An information gap can resolve with a negative answer without closing an achievement
gap. Do not invent source IDs or derive observations from diagnostic failures.
Use only evidence IDs visible in this request, with literal contiguous quotes.
The host will apply a complete proposal once to the original base; no partial commit."""

AUDIT_SYSTEM = """Stateful proactive memory audit, protocol audit-result/1.
Return exactly one JSON object with protocol,binding,coverage,outcome,issues,
closure_assessments,unusable_reason. coverage contains every required_coverage
ref exactly once. outcome is clean/issues/unusable. clean requires issues=[];
issues requires at least one valid blocking Issue. unusable has no conclusions
and a reason code insufficient_context, ambiguous_input, or
cannot_complete_audit. Never filter malformed issues into clean.
Issue fields: issue_id,kind,target,related_targets,explanation,witnesses,
repair_constraint. A target is {snapshot:candidate,target:AuditTargetRef,field_path}; related field witnesses may point to base/candidate/archive.
Issue kind is one of unsupported_claim, observation_conflict, scope_overreach,
temporal_misclassification, source_role_misuse, goal_misinterpretation,
internal_inconsistency, unjustified_gap_closure, unjustified_information_loss.
Source witnesses use {kind:source,ref:{evidence_id,quote}}. Field witnesses
use {kind:field,field:BoundField,exact_value:JSONValue}. Every gap resolution
needs one closure assessment bound to the exact gap_before/gap_after identity,
closure_kind and basis; unsupported/uncertain must cite a blocking issue.
BoundField={snapshot:"base"|"candidate"|"archive",target:AuditTargetRef,
field_path:string}; AuditTargetRef={kind:"state"|"gap"|"requirement"|
"entity"|"relation"|"focus",id:string,revision?:integer}.
State/gap/requirement targets require revision matching the exact visible body;
entity/relation/focus have no body revision and may omit revision. Focus ID is F.
field_path uses dot-separated dictionary fields and decimal list indices, for
example claim.support_refs.0.quote on a knowledge State with a support ref.
It is relative to the target body, not JSON Pointer; do not use $root or brackets.
witnesses is a nonempty array of SourceWitness={kind:"source",ref:EvidenceRef}
or FieldWitness={kind:"field",field:BoundField,exact_value:JSONValue}.
witnesses must be a nonempty list, including a FieldWitness of an exact
empty support_refs field when no source supports a claim; do not invent a quote.
ClosureAssessment={resolution_id:string,gap_before:GapRef,gap_after:GapRef,
closure_kind:"environment_supported"|"goal_changed"|"merged_into",
verdict:"supported"|"unsupported"|"uncertain",assessed_scope:object,
explanation:string,basis_refs:[EvidenceRef|GoalDeltaRef|GapRef,...],
blocking_issue_ids:[string,...]}. unusable_reason=null unless outcome is
unusable, when it is {code:"insufficient_context"|"ambiguous_input"|
"cannot_complete_audit",detail:string}; unusable must have no conclusions.
No extra fields. Copy the exact binding from the input. EvidenceRef is
{evidence_id,quote}, never an internal stored SourceRef.
gap_before and gap_after are exact GapRef identities, not complete gap
bodies in resolve_manifest. Every resolution needs exactly one assessment.
environment_supported needs a visible tool_result or user_report EvidenceRef
basis; goal_changed needs a real GoalDeltaRef present in candidate G.goal_deltas
(the host does not mechanically require equality to the closure's own delta);
merged_into needs
its exact replacement GapRef. The basis must contain that kind. supported
has no blocking_issue_ids; unsupported/uncertain identify a valid blocking
Issue. clean has no Issues and all assessments supported; issues has one or
more valid Issues; unusable has no Issues or assessments and a valid reason.
Check the entire bound candidate and every listed current target, including unchanged
retained claims directly contradicted by this step's observations. Return clean only
when the full coverage and every gap resolution are supportable. A valid source quote
proves literal provenance, not semantic entailment. Evaluate scope, time, source role,
goal interpretation, and information loss. Any valid blocking issue rejects the whole
candidate. Use the exact bound evidence IDs and field paths; do not guess unseen text.
If an honest complete audit is impossible, return unusable with its defined reason.
Return one complete JSON object and no surrounding prose."""

SELECTION_SYSTEM = """Stateful proactive memory selection, protocol reminder-decision/1.
Return exactly one of these JSON objects (no protocol field):
{decision:"silent",state_version:integer,task_version:integer,phase2_view_id:string}
or {decision:"remind",state_version:integer,task_version:integer,
phase2_view_id:string,refs:[TypedRef],context_for_action:string}.
TypedRef is StateRef {type:"state",record_id:string,revision:integer},
RequirementRef {type:"requirement",requirement_id:string,revision:integer,
task_version:integer}, or GapRef {type:"gap",gap_id:string,revision:integer,
task_version:integer}. No extra fields are allowed.
Use only the committed state and selected refs in this request. Either return strict
silent, or remind with one to three distinct refs from selected_refs, bound to
visible committed heads. Retracted States and inactive Requirements cannot be
selected; archived contextual objects are not selectable heads. State status may
be historical_only or contested and Gap status may be open/blocked/supported/
superseded. context_for_action must be a nonempty conditional advisory string. Do not claim that a historical episode or inferred lesson is a
current tool-observed fact. Do not override the original user task, execute tools, or
approve task completion. context_for_action is at most 1200 Unicode code
points; the host-derived final reminder must fit 16384 UTF-8 bytes or the
whole reminder is rejected. Copy state_version, task_version and
phase2_view_id exactly from binding. Return one complete JSON object and no
surrounding prose."""


def _messages(system: str, payload: dict) -> list[dict]:
    return [{"role": "system", "content": system},
            {"role": "user", "content": canonical(payload).decode("utf-8")}]


def maintenance(payload: dict) -> list[dict]:
    return _messages(MAINTENANCE_SYSTEM + "\n" + WIRE_REFS, payload)


def audit(payload: dict) -> list[dict]:
    return _messages(AUDIT_SYSTEM + "\n" + WIRE_REFS, payload)


def repair(*, original_messages: list[dict], base: dict, rejected: object,
           raw_response: str, error: str, mode: str) -> list[dict]:
    return original_messages + [{"role": "user", "content": canonical({
        "repair_mode": mode, "original_base": base,
        "rejected_candidate_or_output": rejected,
        "last_raw_response": raw_response, "validation_error": error,
        "instruction": "Return a complete replacement object for the original base; "
                       "retain unrelated supported changes. No incremental delta "
                       "on the rejected candidate."}).decode("utf-8")}]


def selection(payload: dict) -> list[dict]:
    return _messages(SELECTION_SYSTEM + "\n" + WIRE_REFS, payload)
