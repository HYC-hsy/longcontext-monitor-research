"""No-checker completion decisions over an EvidenceCarryingState.

The kernel is deliberately read-only.  It never runs commands, calls a model,
or changes epistemic state.  It only decides whether a completion proposal is
supported by the public evidence already recorded by Stage 6B/6C.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Iterable

from evidence_state import EvidenceCarryingState
from research_runtime import CompletionDecision
from completion_contract import CompletionContract


ACCEPTABLE = frozenset({"observed", "supported"})
VERIFY_STATUSES = frozenset({"claimed", "contested"})
CONTINUE_STATUSES = frozenset({"unknown", "superseded"})


@dataclass(frozen=True)
class CompletionFinding:
    obligation_id: str
    predicate_id: str
    status: str
    reason_code: str
    source_event_ids: tuple[str, ...]


class EvidenceCompletionKernel:
    """A bounded completion gate conditioned only on public typed state."""

    def __init__(self, state: EvidenceCarryingState,
                 contract: CompletionContract | None = None,
                 recovery_style: str = "flat"):
        if recovery_style not in {"flat", "hierarchical"}:
            raise ValueError("Unsupported recovery_style")
        self.state = state
        self.contract = contract
        self.recovery_style = recovery_style
        self._last_block_fingerprint: str | None = None

    @staticmethod
    def _is_due(required_at: Iterable[str]) -> bool:
        normalized = {str(item).strip().lower() for item in required_at}
        return bool(normalized & {
            "before_completion", "before_producing_artifacts", "at_completion",
            "termination", "final", "always", "throughout_implementation",
        })

    def findings(self) -> list[CompletionFinding]:
        guard_keys = (
            {(guard.obligation_id, guard.predicate_id) for guard in self.contract.guards}
            if self.contract is not None else None
        )
        due_ids = ({item[0] for item in guard_keys} if guard_keys is not None else {
            item.obligation_id for item in self.state.obligations.values()
            if item.termination_condition or self._is_due(item.required_at)
        })
        findings: list[CompletionFinding] = []
        for obligation in self.state.obligations.values():
            if obligation.obligation_id not in due_ids:
                continue
            # A dependency edge is planning structure, not completion authority.
            # If a dependency is required for termination, the public contract
            # compiler must cite and include its predicate as an explicit guard.
            for predicate_id, predicate in obligation.predicates.items():
                if guard_keys is not None and (obligation.obligation_id, predicate_id) not in guard_keys:
                    continue
                status = predicate.epistemic_status
                if status in ACCEPTABLE:
                    continue
                reason = {
                    "claimed": "CLAIMED_ONLY",
                    "contested": "COUNTEREVIDENCE_PRESENT",
                    "unknown": "MISSING_PUBLIC_EVIDENCE",
                    "superseded": "STALE_EVIDENCE",
                }.get(status, "UNSUPPORTED_STATUS")
                findings.append(CompletionFinding(
                    obligation.obligation_id, predicate_id, status, reason,
                    tuple(predicate.source_event_ids),
                ))
        return findings

    def _fingerprint(self, findings: list[CompletionFinding]) -> str:
        body = {
            "state_version": self.state.state_version,
            "findings": [finding.__dict__ for finding in findings],
        }
        raw = json.dumps(body, sort_keys=True, default=list).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def _prompt(self, decision: str, findings: list[CompletionFinding]) -> str:
        if self.recovery_style == "hierarchical":
            return self._hierarchical_prompt(decision, findings)
        lines = [
            "[EVIDENCE-GATED COMPLETION] The current public state does not support completion.",
            f"Decision: {decision}.",
        ]
        for item in findings:
            lines.append(
                f"- {item.obligation_id}/{item.predicate_id}: "
                f"{item.status} ({item.reason_code})"
            )
        lines.append(
            "Do not claim completion. Continue work or obtain a public observation "
            "for the listed acceptance predicates."
        )
        return "\n".join(lines)

    def _hierarchical_prompt(
        self, decision: str, findings: list[CompletionFinding],
    ) -> str:
        by_obligation: dict[str, list[CompletionFinding]] = {}
        for item in findings:
            by_obligation.setdefault(item.obligation_id, []).append(item)
        guard_ids: dict[str, set[str]] = {}
        if self.contract is not None:
            for guard in self.contract.guards:
                guard_ids.setdefault(guard.obligation_id, set()).add(guard.predicate_id)

        omitted: list[tuple[str, list[CompletionFinding]]] = []
        partial: list[tuple[str, list[CompletionFinding]]] = []
        for obligation_id, missing in by_obligation.items():
            total = len(guard_ids.get(obligation_id, ())) or len(missing)
            (omitted if len(missing) == total else partial).append((obligation_id, missing))

        lines = [
            "[EVIDENCE-GATED COMPLETION] Completion is not yet supported.",
            f"Decision: {decision}.",
            "The original task has top-level obligations that are absent or only partially evidenced.",
        ]
        if omitted:
            lines.append("FIRST recover obligations with no current public evidence:")
            for obligation_id, missing in omitted:
                obligation = self.state.obligations[obligation_id]
                predicates = ", ".join(item.predicate_id for item in missing)
                lines.append(f"- {obligation_id}: {obligation.description} [missing: {predicates}]")
        if partial:
            lines.append("THEN address only the remaining gaps in partially evidenced obligations:")
            for obligation_id, missing in partial:
                predicates = ", ".join(item.predicate_id for item in missing)
                lines.append(f"- {obligation_id}: missing {predicates}")
        lines.extend([
            "Do not redo obligations that are already fully evidenced.",
            "Do not claim completion from a build or summary alone; obtain public observations for the gaps.",
        ])
        return "\n".join(lines)

    def decide(self, proposal: Any) -> CompletionDecision:
        if self.contract is not None and self.contract.extraction_status == "abstained":
            return CompletionDecision(
                decision="ABSTAIN", reason_codes=("SPEC_UNKNOWN",),
            )
        findings = self.findings()
        if not findings:
            self._last_block_fingerprint = None
            return CompletionDecision(
                decision="ALLOW_COMPLETE",
                reason_codes=("ALL_DUE_PREDICATES_PUBLICLY_OBSERVED",),
            )

        fingerprint = self._fingerprint(findings)
        targets = tuple(dict.fromkeys(item.obligation_id for item in findings))
        reasons = tuple(dict.fromkeys(item.reason_code for item in findings))
        if fingerprint == self._last_block_fingerprint:
            return CompletionDecision(
                decision="ABSTAIN",
                reason_codes=("NO_STATE_CHANGE_AFTER_COMPLETION_BLOCK",),
                target_obligation_ids=targets,
            )
        self._last_block_fingerprint = fingerprint

        decision = (
            "CONTINUE" if any(item.status == "contested" for item in findings)
            else "VERIFY"
        )
        return CompletionDecision(
            decision=decision,
            reason_codes=reasons,
            next_prompt=self._prompt(decision, findings),
            target_obligation_ids=targets,
        )

    __call__ = decide
