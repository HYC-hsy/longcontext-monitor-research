"""Online Stage 6D candidate gates over frozen public lineage evidence."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from evidence_lineage import LineageTrustPolicy, derive_independence_verdict
from online_evidence_gate import OnlineEvidenceCompletionGate
from research_runtime import CompletionDecision, emit


@dataclass(frozen=True)
class _Decision:
    verdict: str
    reason_codes: tuple[str, ...]
    target_guard_ids: tuple[str, ...]
    accepted_evidence_ids: tuple[str, ...]
    rejected_evidence_ids: tuple[str, ...]
    verification_used: int = 0

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


class CandidateOnlineEvidenceGate(OnlineEvidenceCompletionGate):
    """Replace only the completion verdict; reuse the same public-state frontend."""

    def __init__(self, *args, policy_id: str,
                 max_stagnant_verifications: int = 3, **kwargs):
        if policy_id not in {"K4", "K5", "K5M2"}:
            raise ValueError("Unsupported Stage 6D candidate policy")
        if max_stagnant_verifications < 1:
            raise ValueError("max_stagnant_verifications must be positive")
        super().__init__(*args, **kwargs)
        self.policy_id = policy_id
        self.max_stagnant_verifications = max_stagnant_verifications
        self._verification_fingerprints: set[tuple[int, tuple[str, ...]]] = set()
        self._progress_frontier: tuple[tuple[str, ...], tuple[str, ...]] | None = None
        self._stagnant_verifications = 0

    def _candidate_input(self, proposal: Any):
        by_guard: dict[tuple[str, str], list[dict[str, Any]]] = {}
        warrants: dict[tuple[str, str], list[str]] = {}
        for lineage in self.lineage:
            if not lineage.get("normalization", {}).get("accepted_as_observation"):
                continue
            facts = lineage["facts"]
            semantic = lineage["semantic_proposals"]
            trust = derive_independence_verdict(lineage, LineageTrustPolicy())
            for predicate_id in facts["predicate_ids"]:
                key = (facts["obligation_id"], predicate_id)
                by_guard.setdefault(key, []).append({
                    "evidence_id": lineage["lineage_proposal_id"],
                    "relation": "supports",
                    "origin": (
                        "natural_pre_intervention"
                        if facts["intervention_exposure"] == "pre_intervention"
                        else "monitor_requested"
                    ),
                    "current_version": True,
                    "behavioral": semantic["evidence_scope"] == "behavioral",
                    "intervention_independence": trust["intervention_independence"]["status"],
                    "producer_independence": trust["producer_independence"]["status"],
                })
                if semantic.get("warrant"):
                    warrants.setdefault(key, []).append(semantic["warrant"])
        guards = []
        for guard in self.contract.guards:
            key = (guard.obligation_id, guard.predicate_id)
            evidence = by_guard.get(key, [])
            predicate = self.state.obligations[key[0]].predicates[key[1]]
            guards.append({
                "guard_id": f"{key[0]}/{key[1]}",
                "status": predicate.epistemic_status,
                "warrant": (warrants.get(key) or [None])[0],
                "evidence": evidence,
            })
        return guards

    def _candidate_decision(self, proposal: Any) -> _Decision:
        accepted: list[str] = []
        rejected: list[str] = []
        unresolved: list[str] = []
        for guard in self._candidate_input(proposal):
            support = []
            for item in guard["evidence"]:
                assurance_ok = bool(guard["warrant"]) and (
                    item["behavioral"] or item["producer_independence"] == "supported"
                )
                causal_ok = (
                    item["origin"] != "monitor_requested"
                    or item["intervention_independence"] == "supported"
                    or item["producer_independence"] == "supported"
                )
                admissible = assurance_ok if self.policy_id == "K4" else causal_ok
                (support if admissible else rejected).append(item["evidence_id"])
            accepted.extend(support)
            if not support:
                unresolved.append(guard["guard_id"])
        if not unresolved:
            return _Decision(
                "ALLOW_COMPLETE", ("ADMISSIBLE_SUPPORT_GRAPH",), (),
                tuple(accepted), tuple(dict.fromkeys(rejected)),
            )
        if self.policy_id == "K5M2":
            frontier = (
                tuple(unresolved),
                tuple(sorted(set(accepted))),
            )
            if frontier == self._progress_frontier:
                self._stagnant_verifications += 1
            else:
                self._progress_frontier = frontier
                self._stagnant_verifications = 1
            if self._stagnant_verifications > self.max_stagnant_verifications:
                return _Decision(
                    "ABSTAIN", ("STAGNANT_VERIFICATION_FRONTIER",), tuple(unresolved),
                    tuple(accepted), tuple(dict.fromkeys(rejected)),
                    self._stagnant_verifications - 1,
                )
        fingerprint = (self.state.state_version, tuple(unresolved))
        if self.policy_id != "K5M2" and fingerprint in self._verification_fingerprints:
            return _Decision(
                "ABSTAIN", ("VERIFICATION_BUDGET_EXHAUSTED",), tuple(unresolved),
                tuple(accepted), tuple(dict.fromkeys(rejected)), 1,
            )
        self._verification_fingerprints.add(fingerprint)
        return _Decision(
            "VERIFY", ("BOUNDED_UNKNOWN_VERIFICATION",), tuple(unresolved),
            tuple(accepted), tuple(dict.fromkeys(rejected)), 1,
        )

    def snapshot(self) -> dict[str, Any]:
        value = super().snapshot()
        value["candidate_policy_id"] = self.policy_id
        value["candidate_verification_fingerprints"] = [
            [version, list(guards)]
            for version, guards in sorted(self._verification_fingerprints)
        ]
        value["candidate_max_stagnant_verifications"] = self.max_stagnant_verifications
        value["candidate_progress_frontier"] = (
            [list(self._progress_frontier[0]), list(self._progress_frontier[1])]
            if self._progress_frontier is not None else None
        )
        value["candidate_stagnant_verifications"] = self._stagnant_verifications
        return value

    def restore_snapshot(self, value) -> None:
        super().restore_snapshot(value)
        snapshot_policy = value.get("candidate_policy_id")
        if snapshot_policy and snapshot_policy != self.policy_id:
            raise ValueError("Candidate policy snapshot mismatch")
        self._verification_fingerprints = {
            (int(version), tuple(guards))
            for version, guards in value.get("candidate_verification_fingerprints", [])
        }
        saved_limit = value.get("candidate_max_stagnant_verifications")
        if saved_limit is not None and int(saved_limit) != self.max_stagnant_verifications:
            raise ValueError("Candidate stagnant-verification limit mismatch")
        frontier = value.get("candidate_progress_frontier")
        self._progress_frontier = (
            (tuple(frontier[0]), tuple(frontier[1])) if frontier is not None else None
        )
        self._stagnant_verifications = int(
            value.get("candidate_stagnant_verifications", 0)
        )

    def decide(self, proposal: Any) -> CompletionDecision:
        prepared_error = self.prepare(proposal)
        if prepared_error is not None:
            return prepared_error
        candidate = self._candidate_decision(proposal)
        emit("candidate_completion_decision", candidate.as_dict())
        next_prompt = None
        if candidate.verdict == "VERIFY":
            next_prompt = self._candidate_prompt(candidate.target_guard_ids)
        decision = CompletionDecision(
            decision=candidate.verdict,
            reason_codes=tuple(candidate.reason_codes),
            next_prompt=next_prompt,
            target_obligation_ids=tuple(dict.fromkeys(
                item.split("/", 1)[0] for item in candidate.target_guard_ids
            )),
        )
        self._record_intervention(proposal, decision)
        return decision

    def _candidate_prompt(self, guard_ids: tuple[str, ...]) -> str:
        lines = [
            f"[EVIDENCE ASSURANCE {self.policy_id}] Completion is not yet supported.",
            "The following public-task claims lack admissible evidence:",
        ]
        lines.extend(f"- {guard_id}" for guard_id in guard_ids)
        if self.policy_id == "K4":
            lines.append("Obtain evidence whose demonstrated scope entails each listed behavior; a file, build, or summary alone is insufficient.")
        else:
            lines.append("Obtain ordinary public observations that do not merely restate evidence requested by this intervention.")
            if self.policy_id == "K5M2":
                lines.append(
                    "Verification is bounded: prioritize a new public observation that changes the unresolved support frontier."
                )
        lines.append("Do not claim completion until the remaining claims have admissible public support.")
        return "\n".join(lines)

    __call__ = decide
