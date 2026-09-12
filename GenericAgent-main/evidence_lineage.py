"""Audit-only evidence lineage records for Stage 6D discovery.

Deterministic facts and semantic frontend proposals are deliberately separate.
Nothing in this module upgrades evidence status or authorizes completion.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
from typing import Any, Mapping, Sequence


LINEAGE_SCHEMA = "evidence-lineage-proposal/0"
SCOPE_VALUES = frozenset({"behavioral", "structural", "existence", "unknown"})
INDEPENDENCE_VALUES = frozenset({"independent", "dependent", "unknown"})
BASIS_TYPES = frozenset({
    "none", "task_precommitted_probe", "external_readonly_producer",
    "separated_evaluator",
})


@dataclasses.dataclass(frozen=True)
class InterventionRef:
    event_id: str
    turn: int
    decision: str


@dataclasses.dataclass(frozen=True)
class LineageTrustPolicy:
    """Public, predeclared identities; never inferred from evidence text."""
    precommitted_probe_ids: frozenset[str] = frozenset()
    external_readonly_producer_ids: frozenset[str] = frozenset()
    separated_evaluator_ids: frozenset[str] = frozenset()


def _text(value: Any, default: str = "unknown") -> str:
    text = str(value or "").strip()
    return text or default


def _proposal_id(value: Mapping[str, Any]) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return "lineage-" + hashlib.sha256(raw).hexdigest()[:20]


def build_lineage_proposal(
    row: Mapping[str, Any],
    event: Mapping[str, Any] | None,
    subject_version: int | None,
    interventions: Sequence[InterventionRef],
    *,
    accepted: bool,
    rejection_reason: str | None = None,
) -> dict[str, Any]:
    """Build a telemetry record without treating semantic labels as facts."""
    event_turn = int(event.get("turn", 0)) if event else None
    prior = [item for item in interventions if event_turn is not None and item.turn < event_turn]
    scope = _text(row.get("evidence_scope"))
    if scope not in SCOPE_VALUES:
        scope = "unknown"
    independence = _text(row.get("independence_claim"))
    if independence not in INDEPENDENCE_VALUES:
        independence = "unknown"
    basis = tuple(dict.fromkeys(
        str(item).strip() for item in row.get("independence_basis", []) if str(item).strip()
    ))
    facts = {
        "source_event_id": _text(row.get("source_event_id"), ""),
        "source_event_known": event is not None,
        "source_kind": _text(event.get("source_kind") if event else None),
        "event_turn": event_turn,
        "tool_name": _text(event.get("tool_name") if event else None),
        "obligation_id": _text(row.get("obligation_id"), ""),
        "predicate_ids": list(dict.fromkeys(str(item) for item in row.get("predicate_ids", []))),
        "subject_version": subject_version,
        "intervention_exposure": "post_intervention" if prior else "pre_intervention",
        "prior_intervention_ids": [item.event_id for item in prior],
    }
    proposals = {
        "warrant": _text(row.get("warrant")),
        "evidence_scope": scope,
        "independence_claim": independence,
        "independence_basis": list(basis),
        "independence_basis_type": (
            _text(row.get("independence_basis_type"), "none")
            if _text(row.get("independence_basis_type"), "none") in BASIS_TYPES else "none"
        ),
        "basis_ref_ids": list(dict.fromkeys(
            str(item).strip() for item in row.get("basis_ref_ids", []) if str(item).strip()
        )),
        "producer_id": _text(row.get("producer_id")),
        "epistemic_authority": "frontend_proposal_only",
    }
    body = {
        "schema_version": LINEAGE_SCHEMA,
        "facts": facts,
        "semantic_proposals": proposals,
        "normalization": {
            "accepted_as_observation": bool(accepted),
            "rejection_reason": rejection_reason,
        },
    }
    return {"lineage_proposal_id": _proposal_id(body), **body}


def validate_lineage_proposal(value: Mapping[str, Any]) -> None:
    if value.get("schema_version") != LINEAGE_SCHEMA:
        raise ValueError("Unsupported evidence lineage schema")
    facts = value.get("facts")
    proposals = value.get("semantic_proposals")
    normalization = value.get("normalization")
    if not isinstance(facts, Mapping) or not isinstance(proposals, Mapping):
        raise ValueError("Lineage needs facts and semantic_proposals")
    if not isinstance(normalization, Mapping):
        raise ValueError("Lineage needs normalization outcome")
    if proposals.get("epistemic_authority") != "frontend_proposal_only":
        raise ValueError("Semantic lineage labels cannot have decision authority")
    if proposals.get("evidence_scope") not in SCOPE_VALUES:
        raise ValueError("Unsupported proposed evidence scope")
    if proposals.get("independence_claim") not in INDEPENDENCE_VALUES:
        raise ValueError("Unsupported proposed independence claim")
    if proposals.get("independence_basis_type") not in BASIS_TYPES:
        raise ValueError("Unsupported independence basis type")
    prior = facts.get("prior_intervention_ids")
    if not isinstance(prior, list):
        raise ValueError("prior_intervention_ids must be a list")
    expected = "post_intervention" if prior else "pre_intervention"
    if facts.get("intervention_exposure") != expected:
        raise ValueError("Intervention exposure conflicts with explicit prior links")


def unknown_semantics() -> dict[str, Any]:
    """Canonical abstention fields for a frontend that cannot support a label."""
    return {
        "warrant": "unknown",
        "evidence_scope": "unknown",
        "independence_claim": "unknown",
        "independence_basis": [],
        "independence_basis_type": "none",
        "basis_ref_ids": [],
        "producer_id": "unknown",
    }


def derive_independence_verdict(
    value: Mapping[str, Any], policy: LineageTrustPolicy,
) -> dict[str, Any]:
    """Derive two narrow verdicts from facts and predeclared identities.

    Free-text frontend claims and rationales are never decision inputs.
    """
    validate_lineage_proposal(value)
    facts = value["facts"]
    proposals = value["semantic_proposals"]
    exposure = facts["intervention_exposure"]
    basis_type = proposals["independence_basis_type"]
    refs = frozenset(proposals["basis_ref_ids"])
    producer = proposals["producer_id"]

    intervention_status = "unknown"
    intervention_reason = "NO_MACHINE_CHECKABLE_INTERVENTION_BASIS"
    if exposure == "pre_intervention":
        intervention_status = "supported"
        intervention_reason = "EVIDENCE_PREEXISTS_CURRENT_INTERVENTION"
    elif basis_type == "task_precommitted_probe" and refs & policy.precommitted_probe_ids:
        intervention_status = "supported"
        intervention_reason = "PRECOMMITTED_PROBE_ID_MATCH"
    producer_status = "unknown"
    producer_reason = "NO_PREDECLARED_SEPARATE_PRODUCER"
    if (basis_type == "external_readonly_producer"
            and producer in policy.external_readonly_producer_ids):
        producer_status = "supported"
        producer_reason = "EXTERNAL_READONLY_PRODUCER_ID_MATCH"
    elif (basis_type == "separated_evaluator"
          and producer in policy.separated_evaluator_ids):
        producer_status = "supported"
        producer_reason = "SEPARATED_EVALUATOR_ID_MATCH"

    return {
        "schema_version": "evidence-lineage-verdict/0",
        "lineage_proposal_id": value["lineage_proposal_id"],
        "intervention_independence": {
            "status": intervention_status, "reason": intervention_reason,
        },
        "producer_independence": {
            "status": producer_status, "reason": producer_reason,
        },
        "ignored_frontend_fields": ["independence_claim", "independence_basis"],
    }
