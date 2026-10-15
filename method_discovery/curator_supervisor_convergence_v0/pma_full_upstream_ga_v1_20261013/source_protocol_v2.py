"""Shared S2/R2 source selections and strict tool arguments (research-only)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

STATEMENT_TYPE_GUIDANCE = (
    "statement_type describes the claim, independently of knowledge/procedural memory use: "
    "task_requirement is an explicit task instruction (cite task_instruction); "
    "tool_observation is directly returned by a tool (cite tool_observation), not an unobserved effect; "
    "agent_report is a Task statement, plan or working-memory summary (cite agent_report); "
    "inference is your synthesis or debugging lesson from cited premises, not a verified fact. "
    "Split mixed claims or label the whole claim inference and cite its premises. "
    "A test source states an expected behavior, not that the implementation passed; "
    "an edit receipt shows an edit, not runtime behavior; old source does not observe the current implementation. "
    "A valid citation establishes provenance, not truth or entailment."
)


class StrictArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class SourceLines(StrictArgs):
    source_handle: str = Field(min_length=1, description="Exact handle of one visible source leaf; a JSON wrapper and decoded stdout use different handles.")
    start_line: int = Field(ge=1, description="Inclusive 1-based line in this handle's own total_lines, not a line number printed inside its text.")
    end_line: int = Field(ge=1, description="Inclusive 1-based line in the same handle; must not exceed its total_lines.")


class SaveArgs(StrictArgs):
    content: str = Field(min_length=1)
    statement_type: Literal["task_requirement", "tool_observation", "agent_report", "inference"] = Field(description=STATEMENT_TYPE_GUIDANCE)
    source_refs: list[SourceLines] = Field(min_length=1)


class StatusArgs(StrictArgs):
    content: str


class DeleteArgs(StrictArgs):
    memory_id: str = Field(min_length=1)


class ReconcileArgs(StrictArgs):
    memory_id: str = Field(min_length=1, description="Exact active memory ID only; the displayed 'ID v1' includes a separate version and is not an ID.")
    decision: Literal["retain", "revise", "retract", "unresolved"]
    reason: str = Field(min_length=1)
    evidence_refs: list[SourceLines] = Field(min_length=1, description="Current evidence for the decision; does not supply replacement sources for revise.")
    content: str | None = Field(default=None, description="For revise only: required non-empty replacement text. Omit or use null for other decisions.")
    statement_type: Literal["task_requirement", "tool_observation", "agent_report", "inference"] | None = Field(default=None, description="For revise only: required replacement statement type. Omit or use null otherwise. " + STATEMENT_TYPE_GUIDANCE)
    source_refs: list[SourceLines] | None = Field(default=None, description="For revise only: current visible replacement sources; supply a non-empty list here or valid inherit_source_ref_indices. Omit or use null otherwise.")
    inherit_source_ref_indices: list[int] | None = Field(default=None, description="For revise only: zero-based indices of this memory's already-bound sources. A non-empty valid list can replace or accompany source_refs. Omit or use null otherwise.")

    @model_validator(mode="after")
    def check_decision_fields(self):
        replacement = (self.content, self.statement_type, self.source_refs,
                       self.inherit_source_ref_indices)
        if self.decision == "revise":
            if (not isinstance(self.content, str) or not self.content.strip()
                    or self.statement_type is None
                    or not (self.source_refs or self.inherit_source_ref_indices)):
                raise ValueError("revision requires replacement content, type and bound sources")
        elif any(value is not None for value in replacement):
            raise ValueError("non-revision must not provide replacement fields")
        return self


MODELS = {
    "memory_save_knowledge": SaveArgs,
    "memory_save_procedural": SaveArgs,
    "memory_update_status": StatusArgs,
    "memory_delete": DeleteArgs,
    "memory_reconcile": ReconcileArgs,
}


def tool_schema(name: str, description: str) -> dict:
    """Use the same Pydantic type for transmitted schema and local validation."""
    schema = MODELS[name].model_json_schema()
    definitions = schema.pop("$defs", {})

    def inline(node):
        if isinstance(node, list):
            return [inline(value) for value in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            key = node["$ref"].removeprefix("#/$defs/")
            if key not in definitions:
                raise ValueError("unknown schema reference")
            return inline(definitions[key])
        return {key: inline(value) for key, value in node.items()}

    return {"type": "function", "function": {
        "name": name, "description": description, "parameters": inline(schema)}}
