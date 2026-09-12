"""One-shot Stage R2 recovery-presentation treatments."""
from __future__ import annotations

from typing import Any

from candidate_online_gate import CandidateOnlineEvidenceGate
from research_runtime import CompletionDecision, emit


PRESENTATION_POLICIES = {"I0", "I1", "I2"}


class RecoveryPresentationGate(CandidateOnlineEvidenceGate):
    """Use K5 only to freeze open guards, then vary a single recovery message."""

    def __init__(self, *args, presentation_id: str, **kwargs):
        if presentation_id not in PRESENTATION_POLICIES:
            raise ValueError("Unsupported recovery presentation")
        super().__init__(*args, policy_id="K5", **kwargs)
        self.presentation_id = presentation_id
        self._presentation_armed = False

    def arm(self, proposal: Any) -> CompletionDecision:
        """Create the one treatment prompt at the frozen completion boundary."""
        base = super().decide(proposal)
        if base.decision != "VERIFY" or not base.target_obligation_ids:
            raise ValueError("Recovery presentation requires unresolved public guards")
        candidate = self._candidate_decision(proposal)
        if not candidate.target_guard_ids:
            raise ValueError("Recovery presentation requires target guards")
        prompt = self._render(candidate.target_guard_ids)
        self._presentation_armed = True
        emit("recovery_presentation_armed", {
            "presentation_id": self.presentation_id,
            "target_guard_ids": list(candidate.target_guard_ids),
            "disclosed_guard_ids": list(
                candidate.target_guard_ids[:1]
                if self.presentation_id == "I2" else candidate.target_guard_ids
            ),
            "asserted_environment_facts": [],
        })
        return CompletionDecision(
            decision="VERIFY",
            reason_codes=("ONE_SHOT_RECOVERY_PRESENTATION", self.presentation_id),
            next_prompt=prompt,
            target_obligation_ids=tuple(dict.fromkeys(
                guard_id.split("/", 1)[0] for guard_id in candidate.target_guard_ids
            )),
        )

    def decide(self, proposal: Any) -> CompletionDecision:
        """After the one-shot treatment, observe state but do not block completion."""
        if not self._presentation_armed:
            raise RuntimeError("Recovery presentation gate was not armed at checkpoint")
        prepared_error = self.prepare(proposal)
        if prepared_error is not None:
            emit("recovery_presentation_shadow_error", prepared_error.as_payload())
        decision = CompletionDecision(
            decision="ALLOW_COMPLETE",
            reason_codes=("ONE_SHOT_PRESENTATION_COMPLETE", self.presentation_id),
        )
        emit("recovery_presentation_completion", {
            **decision.as_payload(), "proposal_id": getattr(proposal, "proposal_id", None),
        })
        return decision

    __call__ = decide

    def _render(self, guard_ids: tuple[str, ...]) -> str:
        guards = []
        contract_index = {
            f"{guard.obligation_id}/{guard.predicate_id}": guard
            for guard in self.contract.guards
        }
        for guard_id in guard_ids:
            guard = contract_index[guard_id]
            predicate = self.state.obligations[guard.obligation_id].predicates[guard.predicate_id]
            guards.append((guard_id, guard.requirement_quote, predicate.epistemic_status))
        if self.presentation_id == "I0":
            lines = ["Completion is not yet supported. Verify these open requirements:"]
            lines.extend(
                f"- {guard_id}: {requirement} (No admissible public behavioral support.)"
                for guard_id, requirement, _status in guards
            )
            lines.append("Do not claim completion until each item has public behavioral support.")
            return "\n".join(lines)
        if self.presentation_id == "I1":
            lines = ["Current task state:"]
            lines.extend(
                f"- {guard_id} | {status.upper()} | {requirement} | "
                "No admissible public behavioral support."
                for guard_id, requirement, status in guards
            )
            lines.append("Continue from the highest-impact unresolved state.")
            return "\n".join(lines)
        guard_id, _requirement, _status = guards[0]
        return "\n".join((
            "Before finishing, examine this question:",
            f"What public observation distinguishes `{guard_id}` actually satisfying "
            "the required behavior from merely having an implementation or self-authored test?",
        ))

    def snapshot(self) -> dict[str, Any]:
        value = super().snapshot()
        value["recovery_presentation_id"] = self.presentation_id
        value["recovery_presentation_armed"] = self._presentation_armed
        return value

    def restore_snapshot(self, value) -> None:
        super().restore_snapshot(value)
        saved = value.get("recovery_presentation_id")
        if saved and saved != self.presentation_id:
            raise ValueError("Recovery presentation snapshot mismatch")
        self._presentation_armed = bool(value.get("recovery_presentation_armed", False))

