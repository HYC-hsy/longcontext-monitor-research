"""Shared S2/R2 source selections and strict tool arguments (research-only)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class SourceLines(StrictArgs):
    source_handle: str = Field(min_length=1)
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)


class SaveArgs(StrictArgs):
    content: str = Field(min_length=1)
    statement_type: Literal["task_requirement", "tool_observation", "agent_report", "inference"]
    source_refs: list[SourceLines] = Field(min_length=1)


class StatusArgs(StrictArgs):
    content: str


class DeleteArgs(StrictArgs):
    memory_id: str = Field(min_length=1)


class ReconcileArgs(StrictArgs):
    memory_id: str = Field(min_length=1)
    decision: Literal["retain", "revise", "retract", "unresolved"]
    reason: str = Field(min_length=1)
    evidence_refs: list[SourceLines] = Field(min_length=1)
    content: str | None = None
    statement_type: Literal["task_requirement", "tool_observation", "agent_report", "inference"] | None = None
    source_refs: list[SourceLines] | None = None
    inherit_source_ref_indices: list[int] | None = None

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
