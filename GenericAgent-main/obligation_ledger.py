"""Deterministic evidence-gated obligation state for method discovery.

The ledger trusts only explicit evidence envelopes.  Free-form model text,
summaries, and arbitrary tool output never become evidence implicitly.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence

from research_runtime import (
    CompletionDecision,
    emit,
    new_id,
    register_pending_intervention,
)


CARD_SCHEMA = "obligation-ledger-card/1"
STATE_SCHEMA = "obligation-ledger-state/1"
EVIDENCE_SCHEMA = "obligation-evidence/1"
CONTRACT_VERSION = "evidence-gated-ledger/1"

STRENGTH_ORDER = {
    "SELF_REPORT": 0,
    "ARTIFACT_EXISTS": 1,
    "STATIC_CHECK": 2,
    "LOCAL_BEHAVIOR_CHECK": 3,
    "SOURCE_NATIVE_CHECK": 4,
    "OFFICIAL_VERIFIER": 5,
}
STATUSES = frozenset({"pending", "active", "provisionally_satisfied", "reopened"})


def _nonempty(value: Any, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{label} must be a non-empty string")
    return text


def _hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclasses.dataclass(frozen=True)
class AcceptancePredicate:
    predicate_id: str
    description: str
    checker_id: str
    minimum_strength: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "AcceptancePredicate":
        strength = _nonempty(value.get("minimum_strength"), "minimum_strength")
        if strength not in STRENGTH_ORDER:
            raise ValueError(f"Unknown evidence strength: {strength}")
        return cls(
            predicate_id=_nonempty(value.get("predicate_id"), "predicate_id"),
            description=_nonempty(value.get("description"), "predicate description"),
            checker_id=_nonempty(value.get("checker_id"), "checker_id"),
            minimum_strength=strength,
        )


@dataclasses.dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    obligation_id: str
    predicate_ids: tuple[str, ...]
    checker_id: str
    result: str
    strength: str
    subject_version: int
    artifact_refs: tuple[str, ...]
    content_hash: str
    observed_at: str

    @classmethod
    def from_envelope(cls, value: Mapping[str, Any]) -> "EvidenceRecord":
        if value.get("schema_version") != EVIDENCE_SCHEMA:
            raise ValueError("Unsupported evidence schema")
        result = _nonempty(value.get("result"), "result")
        if result not in {"pass", "fail", "unknown", "error"}:
            raise ValueError(f"Unsupported evidence result: {result}")
        strength = _nonempty(value.get("strength"), "strength")
        if strength not in STRENGTH_ORDER:
            raise ValueError(f"Unknown evidence strength: {strength}")
        predicate_ids = tuple(dict.fromkeys(
            _nonempty(item, "predicate_id") for item in value.get("predicate_ids", [])
        ))
        if not predicate_ids:
            raise ValueError("Evidence must name at least one predicate_id")
        subject_version = int(value.get("subject_version", 0))
        if subject_version < 1:
            raise ValueError("subject_version must be >= 1")
        normalized = {
            "obligation_id": value.get("obligation_id"),
            "predicate_ids": predicate_ids,
            "checker_id": value.get("checker_id"),
            "result": result,
            "strength": strength,
            "subject_version": subject_version,
            "artifact_refs": tuple(str(item) for item in value.get("artifact_refs", [])),
        }
        supplied_hash = str(value.get("content_hash") or "")
        return cls(
            evidence_id=_nonempty(value.get("evidence_id"), "evidence_id"),
            obligation_id=_nonempty(value.get("obligation_id"), "obligation_id"),
            predicate_ids=predicate_ids,
            checker_id=_nonempty(value.get("checker_id"), "checker_id"),
            result=result,
            strength=strength,
            subject_version=subject_version,
            artifact_refs=normalized["artifact_refs"],
            content_hash=supplied_hash or _hash(normalized),
            observed_at=str(value.get("observed_at") or datetime.now(timezone.utc).isoformat()),
        )


@dataclasses.dataclass
class ObligationRecord:
    obligation_id: str
    description: str
    predicates: dict[str, AcceptancePredicate]
    requirement_source_pointer: str
    status: str = "pending"
    version: int = 1
    evidence: list[EvidenceRecord] = dataclasses.field(default_factory=list)

    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise ValueError(f"Unknown obligation status: {self.status}")
        if not self.predicates:
            raise ValueError(f"Obligation {self.obligation_id} has no acceptance predicates")


class ObligationLedger:
    """A small state machine for evidence-gated completion decisions."""

    def __init__(self, task_id: str, obligations: Sequence[ObligationRecord], *,
                 checker_runner: Optional[Callable[[ObligationRecord, AcceptancePredicate],
                                                   Optional[Mapping[str, Any]]]] = None):
        self.task_id = _nonempty(task_id, "task_id")
        self.obligations = {item.obligation_id: item for item in obligations}
        if not self.obligations or len(self.obligations) != len(obligations):
            raise ValueError("Task card must contain unique obligations")
        self.state_version = 1
        self._seen_evidence_ids: set[str] = set()
        self._pending_counterevidence: set[str] = set()
        self._checker_runner = checker_runner
        self._action_epoch = 0
        self._last_block_fingerprint: Optional[tuple[int, int]] = None

    @classmethod
    def from_card(cls, card: Mapping[str, Any], *, checker_runner=None) -> "ObligationLedger":
        if card.get("schema_version") != CARD_SCHEMA:
            raise ValueError("Unsupported obligation ledger card schema")
        obligations = []
        for item in card.get("obligations", []):
            obligation_id = _nonempty(item.get("obligation_id"), "obligation_id")
            predicates = [AcceptancePredicate.from_dict(p) for p in item.get("acceptance_predicates", [])]
            predicate_map = {p.predicate_id: p for p in predicates}
            if len(predicate_map) != len(predicates):
                raise ValueError(f"Duplicate predicate in {obligation_id}")
            obligations.append(ObligationRecord(
                obligation_id=obligation_id,
                description=_nonempty(item.get("description"), "obligation description"),
                predicates=predicate_map,
                requirement_source_pointer=_nonempty(
                    item.get("requirement_source_pointer"), "requirement_source_pointer"
                ),
            ))
        return cls(_nonempty(card.get("task_id"), "task_id"), obligations,
                   checker_runner=checker_runner)

    @classmethod
    def from_card_path(cls, path: str | Path, *, checker_runner=None) -> "ObligationLedger":
        return cls.from_card(json.loads(Path(path).read_text(encoding="utf-8")),
                             checker_runner=checker_runner)

    def _transition(self, obligation: ObligationRecord, status: str, reason: str,
                    evidence_ids: Iterable[str] = ()) -> bool:
        if status not in STATUSES:
            raise ValueError(f"Unknown obligation status: {status}")
        if obligation.status == status:
            return False
        previous = obligation.status
        obligation.status = status
        self.state_version += 1
        emit("obligation_transition", {
            "obligation_id": obligation.obligation_id,
            "previous_status": previous,
            "new_status": status,
            "reason": reason,
            "obligation_version": obligation.version,
            "state_version": self.state_version,
            "evidence_ids": list(evidence_ids),
        })
        return True

    def advance_subject_version(self, obligation_id: str, reason: str = "SUBJECT_CHANGED") -> int:
        """Invalidate evidence after the checked artifact or dependency changes."""
        obligation = self.obligations[obligation_id]
        obligation.version += 1
        self.state_version += 1
        if obligation.status == "provisionally_satisfied":
            self._transition(obligation, "reopened", reason)
        emit("obligation_subject_version_advanced", {
            "obligation_id": obligation_id,
            "subject_version": obligation.version,
            "reason": reason,
            "state_version": self.state_version,
        })
        return obligation.version

    def activate(self, obligation_id: str) -> None:
        obligation = self.obligations[obligation_id]
        if obligation.status in {"pending", "reopened"}:
            self._transition(obligation, "active", "WORK_STARTED")

    def record_evidence(self, envelope: Mapping[str, Any]) -> bool:
        evidence = EvidenceRecord.from_envelope(envelope)
        if evidence.evidence_id in self._seen_evidence_ids:
            return False
        obligation = self.obligations.get(evidence.obligation_id)
        if obligation is None:
            raise ValueError(f"Unknown obligation_id: {evidence.obligation_id}")
        if evidence.subject_version != obligation.version:
            raise ValueError("Evidence subject_version does not match current obligation version")
        unknown = set(evidence.predicate_ids) - set(obligation.predicates)
        if unknown:
            raise ValueError(f"Evidence names unknown predicates: {sorted(unknown)}")
        wrong_checker = [pid for pid in evidence.predicate_ids
                         if obligation.predicates[pid].checker_id != evidence.checker_id]
        if wrong_checker:
            raise ValueError(f"Checker is not authorized for predicates: {wrong_checker}")
        self._seen_evidence_ids.add(evidence.evidence_id)
        obligation.evidence.append(evidence)
        emit("obligation_evidence_recorded", {
            "evidence_id": evidence.evidence_id,
            "obligation_id": evidence.obligation_id,
            "predicate_ids": list(evidence.predicate_ids),
            "checker_id": evidence.checker_id,
            "result": evidence.result,
            "strength": evidence.strength,
            "subject_version": evidence.subject_version,
            "content_hash": evidence.content_hash,
            "observed_at": evidence.observed_at,
            "artifact_ref_count": len(evidence.artifact_refs),
        })
        if evidence.result in {"fail", "error"}:
            self._pending_counterevidence.add(obligation.obligation_id)
            if obligation.status == "provisionally_satisfied":
                self._transition(obligation, "reopened", "COUNTEREVIDENCE", (evidence.evidence_id,))
        return True

    def ingest_tool_results(self, tool_results: Iterable[Any]) -> int:
        """Ingest only explicit evidence envelopes; ignore all ordinary output."""
        accepted = 0
        for result in tool_results:
            candidate = result.get("ga_evidence") if isinstance(result, Mapping) else None
            if isinstance(candidate, Mapping) and self.record_evidence(candidate):
                accepted += 1
        return accepted

    def note_action(self) -> None:
        """Mark that the Agent acted after a completion block."""
        self._action_epoch += 1

    def run_independent_checks(self) -> int:
        """Ask an injected checker runner for evidence at a closure boundary."""
        if self._checker_runner is None:
            return 0
        accepted = 0
        for obligation in self.obligations.values():
            if obligation.status == "provisionally_satisfied":
                continue
            for predicate in obligation.predicates.values():
                envelope = self._checker_runner(obligation, predicate)
                if envelope is not None and self.record_evidence(envelope):
                    accepted += 1
            self.propose_obligation_closure(obligation.obligation_id)
        return accepted

    def _coverage(self, obligation: ObligationRecord) -> tuple[set[str], set[str], set[str]]:
        covered: set[str] = set()
        failed: set[str] = set()
        for evidence in obligation.evidence:
            if evidence.subject_version != obligation.version:
                continue
            for predicate_id in evidence.predicate_ids:
                predicate = obligation.predicates[predicate_id]
                if evidence.result in {"fail", "error"}:
                    failed.add(predicate_id)
                elif (evidence.result == "pass" and
                      STRENGTH_ORDER[evidence.strength] >= STRENGTH_ORDER[predicate.minimum_strength]):
                    covered.add(predicate_id)
        missing = set(obligation.predicates) - covered
        return covered, missing, failed

    def propose_obligation_closure(self, obligation_id: str) -> bool:
        obligation = self.obligations[obligation_id]
        covered, missing, failed = self._coverage(obligation)
        if missing or failed:
            emit("obligation_closure_rejected", {
                "obligation_id": obligation_id,
                "missing_predicate_ids": sorted(missing),
                "failed_predicate_ids": sorted(failed),
                "state_version": self.state_version,
            })
            return False
        evidence_ids = [e.evidence_id for e in obligation.evidence if e.result == "pass"]
        self._transition(obligation, "provisionally_satisfied", "EVIDENCE_COVERAGE", evidence_ids)
        return True

    def unresolved(self) -> list[tuple[ObligationRecord, set[str], set[str]]]:
        result = []
        for obligation in self.obligations.values():
            covered, missing, failed = self._coverage(obligation)
            if obligation.status != "provisionally_satisfied" or missing or failed:
                result.append((obligation, missing, failed))
        return result

    def _intervention(self, unresolved: Sequence[tuple[ObligationRecord, set[str], set[str]]],
                      internal_turn: int) -> str:
        lines = ["[EVIDENCE-GATED COMPLETION] Completion is not yet supported."]
        for obligation, missing, failed in unresolved:
            details = []
            if missing:
                details.append("missing evidence for " + ", ".join(sorted(missing)))
            if failed:
                details.append("counterevidence for " + ", ".join(sorted(failed)))
            lines.append(f"- {obligation.obligation_id}: {'; '.join(details) or obligation.status}")
        lines.append("Continue working or explicitly report these obligations as unresolved. Do not claim completion.")
        prompt = "\n".join(lines)
        occurrence_id = new_id("injection")
        event = emit("intervention", {
            "intervention_kind": "evidence_gated_completion",
            "injection_occurrence_id": occurrence_id,
            "injection_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "injection_chars": len(prompt),
            "contract_version": CONTRACT_VERSION,
            "position": "completion_gate_pre_next_llm",
            "target_obligation_ids": [item[0].obligation_id for item in unresolved],
        }, internal_turn=internal_turn)
        if event is not None:
            register_pending_intervention(event, occurrence_id)
        return prompt

    def completion_gate(self, proposal: Any) -> CompletionDecision:
        self.run_independent_checks()
        unresolved = self.unresolved()
        if not unresolved:
            self._last_block_fingerprint = None
            return CompletionDecision(
                decision="ALLOW_COMPLETE", reason_codes=("ALL_OBLIGATIONS_PROVISIONAL",),
                checker_ids=tuple(sorted({p.checker_id for o in self.obligations.values()
                                          for p in o.predicates.values()})),
            )
        fingerprint = (self.state_version, self._action_epoch)
        if fingerprint == self._last_block_fingerprint:
            return CompletionDecision(
                decision="ABSTAIN",
                reason_codes=("NO_PROGRESS_AFTER_COMPLETION_BLOCK",),
                target_obligation_ids=tuple(item[0].obligation_id for item in unresolved),
            )
        self._last_block_fingerprint = fingerprint
        prompt = self._intervention(unresolved, int(getattr(proposal, "turn", 0)))
        return CompletionDecision(
            decision="CONTINUE",
            reason_codes=("UNRESOLVED_OBLIGATIONS",),
            next_prompt=prompt,
            target_obligation_ids=tuple(item[0].obligation_id for item in unresolved),
        )

    def counterevidence_prompt(self, internal_turn: int) -> Optional[str]:
        targets = sorted(self._pending_counterevidence)
        self._pending_counterevidence.clear()
        if not targets:
            return None
        unresolved = [item for item in self.unresolved() if item[0].obligation_id in targets]
        return self._intervention(unresolved, internal_turn) if unresolved else None

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema_version": STATE_SCHEMA,
            "task_id": self.task_id,
            "state_version": self.state_version,
            "obligations": [{
                "obligation_id": item.obligation_id,
                "description": item.description,
                "status": item.status,
                "version": item.version,
                "requirement_source_pointer": item.requirement_source_pointer,
                "predicate_ids": sorted(item.predicates),
                "evidence_ids": [e.evidence_id for e in item.evidence],
            } for item in self.obligations.values()],
        }
