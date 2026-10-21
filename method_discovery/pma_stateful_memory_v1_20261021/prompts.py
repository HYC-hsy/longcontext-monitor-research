"""Versioned model-facing contracts; no gold labels or hidden evaluator data."""

from __future__ import annotations

from .source import canonical


MAINTENANCE_SYSTEM = """Stateful proactive memory maintenance, protocol maintenance-proposal/1.
Propose one complete JSON object matching the declared MaintenanceProposal fields.
All operation arrays must be present, even when empty. Preserve task requirements,
scope, source roles and exact versions. An executed action is not proof of success.
An information gap can resolve with a negative answer without closing an achievement
gap. Do not invent source IDs or derive observations from diagnostic failures.
Use only evidence IDs visible in this request, with literal contiguous quotes.
The host will apply a complete proposal once to the original base; no partial commit."""

AUDIT_SYSTEM = """Stateful proactive memory audit, protocol audit-result/1.
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
