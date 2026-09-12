"""Public, auditable terminal-transition contracts for Stage 6D."""
from __future__ import annotations

import dataclasses
from typing import Any, Mapping

from evidence_state import EvidenceCarryingState


CONTRACT_SCHEMA = "completion-transition-contract/0"


@dataclasses.dataclass(frozen=True)
class TerminalGuard:
    obligation_id: str
    predicate_id: str
    requirement_quote: str
    requirement_source_pointer: str


@dataclasses.dataclass(frozen=True)
class CompletionContract:
    task_id: str
    guards: tuple[TerminalGuard, ...]
    extraction_status: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any], state: EvidenceCarryingState,
                  public_task_text: str) -> "CompletionContract":
        if value.get("schema_version") != CONTRACT_SCHEMA:
            raise ValueError("Unsupported completion contract schema")
        if value.get("task_id") != state.task_id:
            raise ValueError("Completion contract task_id mismatch")
        extraction_status = str(value.get("extraction_status", ""))
        if extraction_status not in {"compiled", "abstained"}:
            raise ValueError("Unsupported completion contract extraction_status")
        guards = []
        seen = set()
        for raw in value.get("terminal_guards", []):
            obligation_id = str(raw.get("obligation_id", ""))
            predicate_id = str(raw.get("predicate_id", ""))
            obligation = state.obligations.get(obligation_id)
            if obligation is None or predicate_id not in obligation.predicates:
                raise ValueError("Terminal guard references an unknown state predicate")
            key = (obligation_id, predicate_id)
            if key in seen:
                raise ValueError("Duplicate terminal guard")
            quote = str(raw.get("requirement_quote", "")).strip()
            if not quote or quote not in public_task_text:
                raise ValueError("Terminal guard quote is not an exact public-task span")
            source_pointer = str(raw.get("requirement_source_pointer", "")).strip()
            if not source_pointer:
                raise ValueError("Terminal guard requires a source pointer")
            if not obligation.predicates[predicate_id].specification.observable_by:
                raise ValueError("Terminal guard predicate is not publicly observable")
            guards.append(TerminalGuard(
                obligation_id, predicate_id, quote, source_pointer,
            ))
            seen.add(key)
        if extraction_status == "compiled" and not guards:
            raise ValueError("Compiled completion contract needs terminal guards")
        if extraction_status == "abstained" and guards:
            raise ValueError("Abstained completion contract cannot contain guards")
        return cls(state.task_id, tuple(guards), extraction_status)
