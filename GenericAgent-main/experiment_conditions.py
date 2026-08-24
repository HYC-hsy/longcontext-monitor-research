"""Prompt-only baseline conditions for long-horizon method discovery."""
from __future__ import annotations

import dataclasses
import hashlib
import json
import os
from pathlib import Path
from typing import Optional, Sequence

from research_runtime import emit, new_id, register_pending_intervention


CONTRACT_VERSION = "baseline-condition/1"
VALID_CONDITIONS = frozenset({"original", "always_visible_task", "static_checklist"})


@dataclasses.dataclass(frozen=True)
class BaselineCondition:
    name: str
    original_task: str = ""
    obligations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.name not in VALID_CONDITIONS:
            raise ValueError(f"Unknown baseline condition: {self.name}")
        if self.name == "always_visible_task" and not self.original_task.strip():
            raise ValueError("always_visible_task requires original_task")
        if self.name == "static_checklist" and not self.obligations:
            raise ValueError("static_checklist requires obligations")
        if any(not str(item).strip() for item in self.obligations):
            raise ValueError("obligations must be non-empty strings")

    @classmethod
    def static_checklist(cls, obligations: Sequence[str]) -> "BaselineCondition":
        return cls("static_checklist", obligations=tuple(obligations))


def _injection(condition: BaselineCondition) -> str:
    if condition.name == "always_visible_task":
        return (
            "[RESEARCH BASELINE: ALWAYS-VISIBLE TASK]\n"
            "The original task is reproduced verbatim below. Continue using current observations and tools.\n"
            f"<original_task>\n{condition.original_task}\n</original_task>"
        )
    checklist = "\n".join(f"{index}. [ ] {item}" for index, item in enumerate(condition.obligations, 1))
    return (
        "[RESEARCH BASELINE: STATIC CHECKLIST]\n"
        "Track these fixed obligations while acting:\n"
        f"{checklist}\n"
        "This checklist is a reminder only; it does not certify that any item is complete."
    )


def apply_condition(next_prompt: str, condition: Optional[BaselineCondition], *, internal_turn: int,
                    position: str = "post_tool_pre_next_llm") -> str:
    """Append the configured baseline injection; Original is byte-transparent."""
    if condition is None or condition.name == "original":
        return next_prompt
    if position not in {"pre_first_llm", "post_tool_pre_next_llm"}:
        raise ValueError(f"Unsupported injection position: {position}")
    injection = _injection(condition)
    digest = hashlib.sha256(injection.encode("utf-8")).hexdigest()
    occurrence_id = new_id("injection")
    event = emit("intervention", {
        "intervention_kind": condition.name,
        "injection_id": f"{condition.name}:{digest[:16]}",
        "injection_occurrence_id": occurrence_id,
        "injection_sha256": digest,
        "injection_chars": len(injection),
        "contract_version": CONTRACT_VERSION,
        "position": position,
    }, condition_id=condition.name, internal_turn=internal_turn)
    if event is not None:
        register_pending_intervention(event, occurrence_id)
    return f"{next_prompt}\n\n{injection}"


def condition_initial_task(task: str, condition: Optional[BaselineCondition]) -> str:
    """Make a treatment visible on the first call as well as later turns."""
    return apply_condition(task, condition, internal_turn=0, position="pre_first_llm")


def condition_from_environment(default_task: str) -> Optional[BaselineCondition]:
    """Load a frozen Stage 4 condition without coupling GA to the experiment runner."""
    name = os.environ.get("GA_BASELINE_CONDITION")
    if not name:
        return None
    if name == "original":
        return BaselineCondition("original")
    if name == "always_visible_task":
        task_path = os.environ.get("GA_ORIGINAL_TASK_PATH")
        original = Path(task_path).read_text(encoding="utf-8") if task_path else default_task
        return BaselineCondition(name, original_task=original)
    if name == "static_checklist":
        card_path = os.environ.get("GA_TASK_CARD_PATH")
        if not card_path:
            raise ValueError("GA_TASK_CARD_PATH is required for static_checklist")
        card = json.loads(Path(card_path).read_text(encoding="utf-8"))
        if card.get("schema_version") != "obligation-state/1":
            raise ValueError("Unsupported task card schema")
        obligations = tuple(item["description"] for item in card.get("obligations", []))
        return BaselineCondition.static_checklist(obligations)
    raise ValueError(f"Unknown GA_BASELINE_CONDITION: {name}")
