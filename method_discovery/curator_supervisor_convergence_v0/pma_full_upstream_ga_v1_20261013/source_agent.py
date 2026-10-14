"""Opt-in S/R adapters around the pinned upstream two-phase MemoryAgent."""
from __future__ import annotations

import copy
import json
import re
from types import SimpleNamespace

from memory_agent.memory.memory_agent import (
    BANK_TOOLS, PHASE1_SYSTEM, PHASE2_SYSTEM, MemoryAgent, MemoryOperation,
)

from source_memory import SourceMemory


SOURCE_RULES = """
For each saved knowledge/procedural entry include statement_type
(task_requirement, tool_observation, agent_report, or inference) and source_refs.
Each source ref is {event_id, role, quote}: quote an exact, unique substring of
a currently visible public event. A Task statement remains an agent_report,
not a verified tool observation. Citations establish provenance, not truth.
Do not cite hidden reasoning, unavailable output, future events, or evaluator data.
"""
RECONCILE_RULES = """
For old memories touched by current evidence, explicitly reconcile each as
retain, revise, retract, or unresolved using memory_reconcile. Cite current
public evidence and give a short reason, not hidden reasoning. Newer or
different information does not automatically contradict old information.
Do not silently turn unresolved into a verified fact.
"""
REMINDER_RULES = """
Keep the original selective-attention decision: synthesize freely or stay silent.
For a reminder, use <context_for_action>free synthesized note</context_for_action>
followed by <memory_refs>[{"id":"active ID","version":1}]</memory_refs>.
Cite active memories actually relied on. Distinguish new inferences as
inferences; citations do not prove the synthesized claim. Silence remains
<no_intervention/>. Invalid citations cause no delivery, not a repair call.
"""


def _tools(variant: str) -> list[dict]:
    tools = copy.deepcopy(BANK_TOOLS)
    for tool in tools[:2]:
        params = tool["function"]["parameters"]
        params["properties"].update({
            "statement_type": {"type": "string", "enum": sorted(SourceMemory.TYPES)},
            "source_refs": {"type": "array", "items": {"type": "object"}},
        })
        params["required"] += ["statement_type", "source_refs"]
    if variant == "R":
        tools.append({"type": "function", "function": {
            "name": "memory_reconcile",
            "description": "Record current evidence coordination for an old memory.",
            "parameters": {"type": "object", "properties": {
                "memory_id": {"type": "string"},
                "decision": {"type": "string", "enum": ["retain", "revise", "retract", "unresolved"]},
                "reason": {"type": "string"},
                "evidence_refs": {"type": "array", "items": {"type": "object"}},
                "content": {"type": "string"},
                "statement_type": {"type": "string", "enum": sorted(SourceMemory.TYPES)},
                "source_refs": {"type": "array", "items": {"type": "object"}},
            }, "required": ["memory_id", "decision", "reason", "evidence_refs"]},
        }})
    return tools


class SourceMemoryAgent(MemoryAgent):
    def __init__(self, *, variant: str, **kwargs):
        if variant not in {"S", "R"}:
            raise ValueError("unknown source-memory candidate")
        super().__init__(**kwargs)
        if not isinstance(self.memory, SourceMemory):
            raise TypeError("S/R require SourceMemory")
        self.variant = variant
        self.last_delivery_status = "not_run"
        self.last_reminder_refs: list[dict] = []
        self.coordination: list[dict] = []

    async def process(self, observation: str, step_count: int = 0):
        self.last_delivery_status = "phase2_error_or_not_completed"
        self.last_reminder_refs = []
        return await super().process(observation=observation, step_count=step_count)

    def pending_refs_valid(self) -> bool:
        if self.last_delivery_status != "selected_validated_not_delivered":
            return False
        for ref in self.last_reminder_refs:
            meta = self.memory.metadata.get(ref["id"])
            if self.memory.get(ref["id"]) is None or meta is None or meta["version"] != ref["version"]:
                return False
            for source_ref in meta["source_refs"]:
                if not self.memory.source_ref_valid(source_ref):
                    return False
        return True

    def get_tools_schema(self) -> list[dict]:
        return _tools(self.variant)

    async def _call_llm_phase1(self, user_prompt: str):
        kwargs = {"prompt": user_prompt,
                  "system": PHASE1_SYSTEM + SOURCE_RULES + (RECONCILE_RULES if self.variant == "R" else "")}
        if self.use_structured_tools:
            kwargs["tools"] = _tools(self.variant)
        return await self.llm.call(**kwargs)

    async def _call_llm_phase2(self, user_prompt: str):
        return await self.llm.call(prompt=user_prompt,
                                   system=PHASE2_SYSTEM + REMINDER_RULES)

    def _format_memory_list(self, entries):
        if not entries:
            return "(empty)"
        return "\n".join(
            f"[{e.id} v{self.memory.metadata[e.id]['version']}] {e.content} "
            f"[type={self.memory.metadata[e.id]['statement_type']}; "
            f"sources={json.dumps(self.memory.metadata[e.id]['source_refs'], ensure_ascii=False)}]"
            for e in entries)

    def _build_phase1_prompt(self, observation: str, step_count: int) -> str:
        prompt = super()._build_phase1_prompt(observation, step_count)
        handles = [{k: source[k] for k in ("event_id", "role", "order", "sha256")}
                   for event_id in self.memory.current_source_ids
                   if (source := self.memory.sources.get(event_id))]
        return prompt + "\n## Visible public source handles (quote exact text above)\n" + json.dumps(
            handles, ensure_ascii=False, sort_keys=True)

    def _execute_tool_calls(self, response) -> list[MemoryOperation]:
        calls = getattr(response, "tool_calls", None) or []
        if not calls:
            raw = self._strip_thinking(getattr(response, "content", None) or "")
            calls = [SimpleNamespace(function=SimpleNamespace(name=name, arguments=args))
                     for name, args in self._parse_tool_calls_from_text(raw)]
        operations = []
        for call in calls:
            try:
                name, args = self._extract_tool_call(call)
                if name in {"memory_save_knowledge", "memory_save_procedural"}:
                    category = "knowledge" if name.endswith("knowledge") else "procedural"
                    memory_id = self.memory.save_sourced(category, args.get("content"),
                        args.get("statement_type"), args.get("source_refs"))
                    operations.append(MemoryOperation(action=name, memory_id=memory_id,
                                                      content=args["content"]))
                elif name == "memory_reconcile" and self.variant == "R":
                    operations.append(self._reconcile(args))
                elif name in {"memory_delete", "memory_update_status"}:
                    operations.extend(super()._execute_tool_calls(
                        SimpleNamespace(tool_calls=[call], content="")))
                else:
                    operations.append(MemoryOperation(action=str(name), success=False,
                                                      error="unknown candidate tool"))
            except Exception as exc:
                operations.append(MemoryOperation(action="candidate_tool", success=False,
                                                  error=f"{type(exc).__name__}: {exc}"))
        return operations

    def _reconcile(self, args: dict) -> MemoryOperation:
        memory_id = args.get("memory_id")
        decision = args.get("decision")
        reason = args.get("reason")
        if decision not in {"retain", "revise", "retract", "unresolved"} or not isinstance(reason, str) or not reason:
            raise ValueError("invalid reconciliation decision or reason")
        evidence = self.memory.resolve_refs(args.get("evidence_refs"), "inference")
        if decision == "revise":
            new_id = self.memory.revise(memory_id, args.get("content"),
                args.get("statement_type"), args.get("source_refs"), reason, evidence)
        elif decision == "retract":
            if not self.memory.retract(memory_id, reason, evidence):
                raise ValueError("unknown memory to retract")
            new_id = None
        else:
            if self.memory.get(memory_id) is None:
                raise ValueError("unknown active memory")
            new_id = None
        self.coordination.append({"memory_id": memory_id, "decision": decision,
                                  "reason": reason, "evidence": evidence, "new_id": new_id})
        return MemoryOperation(action=decision, memory_id=new_id or memory_id)

    def _parse_phase2_response(self, raw: str) -> str | None:
        self.last_reminder_refs = []
        text = self._strip_thinking(raw)
        if re.fullmatch(r"\s*<no_intervention\s*/>\s*", text):
            self.last_delivery_status = "deliberate_silence"
            return None
        body = re.fullmatch(
            r"\s*<context_for_action>(.*?)</context_for_action>\s*"
            r"<memory_refs>(.*?)</memory_refs>\s*", text, re.DOTALL)
        if body is None or not body.group(1).strip():
            self.last_delivery_status = "format_rejected"
            return None
        try:
            refs = json.loads(body.group(2))
            if not isinstance(refs, list) or not refs:
                raise ValueError("nonempty memory refs required")
            for ref in refs:
                if not isinstance(ref, dict) or set(ref) != {"id", "version"}:
                    raise ValueError("invalid memory ref shape")
                entry = self.memory.get(ref["id"])
                meta = self.memory.metadata.get(ref["id"])
                if entry is None or meta is None or type(ref["version"]) is not int or meta["version"] != ref["version"]:
                    raise ValueError("inactive or mismatched memory ref")
                for source_ref in meta["source_refs"]:
                    if not self.memory.source_ref_valid(source_ref):
                        raise ValueError("invalid memory source")
            self.last_reminder_refs = refs
            self.last_delivery_status = "selected_validated_not_delivered"
            return body.group(1).strip()
        except (ValueError, KeyError, TypeError):
            self.last_delivery_status = "invalid_reference_no_delivery"
            return None
