"""Versioned model-facing contracts; no gold labels or hidden evaluator data."""

from __future__ import annotations

from .source import canonical


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
repair_constraint. A target is {snapshot:candidate,target:{kind,id,revision?},
field_path}; related field witnesses may point to base/candidate/archive.
Issue kind is one of unsupported_claim, observation_conflict, scope_overreach,
temporal_misclassification, source_role_misuse, goal_misinterpretation,
internal_inconsistency, unjustified_gap_closure, unjustified_information_loss.
Source witnesses use {kind:source,ref:{evidence_id,quote}}. Field witnesses
use {kind:field,field:BoundField,exact_value:JSONValue}. Every gap resolution
needs one closure assessment bound to the exact gap_before/gap_after identity,
closure_kind and basis; unsupported/uncertain must cite a blocking issue.
Check the entire bound candidate and every listed current target, including unchanged
retained claims directly contradicted by this step's observations. Return clean only
when the full coverage and every gap resolution are supportable. A valid source quote
proves literal provenance, not semantic entailment. Evaluate scope, time, source role,
goal interpretation, and information loss. Any valid blocking issue rejects the whole
candidate. Use the exact bound evidence IDs and field paths; do not guess unseen text.
If an honest complete audit is impossible, return unusable with its defined reason.
Return one complete JSON object and no surrounding prose."""

SELECTION_SYSTEM = """Stateful proactive memory selection, protocol reminder-decision/1.
Use only the committed state and selected refs in this request. Either return strict
silent, or remind with at most three distinct visible committed refs and a conditional
context_for_action. Do not claim that a historical episode or inferred lesson is a
current tool-observed fact. Do not override the original user task, execute tools, or
approve task completion. Return one complete JSON object and no surrounding prose."""


def _messages(system: str, payload: dict) -> list[dict]:
    return [{"role": "system", "content": system},
            {"role": "user", "content": canonical(payload).decode("utf-8")}]


def maintenance(payload: dict) -> list[dict]:
    return _messages(MAINTENANCE_SYSTEM, payload)


def audit(payload: dict) -> list[dict]:
    return _messages(AUDIT_SYSTEM, payload)


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
    return _messages(SELECTION_SYSTEM, payload)
