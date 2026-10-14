"""Shared S2/R2 evidence selection, strict arguments and one-phase bank transaction."""
from __future__ import annotations

import copy
import json
import uuid

from memory_agent.memory.memory_agent import BANK_TOOLS, MemoryOperation
from pydantic import ValidationError

from source_agent import RECONCILE_RULES, REMINDER_RULES, SourceMemoryAgent
from source_memory_v2 import SourceMemoryV2
from source_protocol_v2 import MODELS, tool_schema


SOURCE_LINES_RULES = """
Use only the numbered, visible public source leaves below. For each citation choose
{source_handle, start_line, end_line}, with inclusive 1-based line numbers. The host
binds exact bytes, role and event; do not repeat a quote or invent an event ID.
Working-memory summaries and Task responses are agent_report, not tool observations.
An old excerpt may be inherited only through the cited entry's explicit index.
"""
RECEIPT_RULES = """
Phase-1 memory operations are one transaction. A rejected operation aborts every
operation in that phase, including otherwise valid saves/deletes. Receipts report
execution, not task facts. Use the receipts to correct the next bank action without
assuming an aborted or rejected operation changed memory.
"""


class SourceMemoryAgentV2(SourceMemoryAgent):
    def __init__(self, *, variant: str, **kwargs):
        if variant not in {"S2", "R2"}:
            raise ValueError("v2 candidate required")
        super().__init__(variant="R" if variant == "R2" else "S", **kwargs)
        if not isinstance(self.memory, SourceMemoryV2):
            raise TypeError("v2 line-addressed bank required")
        self.variant = variant
        self.last_receipts: list[dict] = []
        self.last_transaction: dict = {}
        self._phase_step = 0
        self.collateral_aborts = 0
        self._fatal_error: Exception | None = None

    async def process(self, observation: str, step_count: int = 0):
        self._fatal_error = None
        result = await super().process(observation, step_count)
        if self._fatal_error is not None:
            raise self._fatal_error
        return result

    def get_tools_schema(self) -> list[dict]:
        descriptions = {tool["function"]["name"]: tool["function"]["description"]
                        for tool in BANK_TOOLS}
        if self.variant == "R2":
            descriptions["memory_reconcile"] = "Coordinate an active memory with current evidence."
        return [tool_schema(name, description) for name, description in descriptions.items()]

    async def _call_llm_phase1(self, user_prompt: str):
        from memory_agent.memory.memory_agent import PHASE1_SYSTEM
        system = PHASE1_SYSTEM + SOURCE_LINES_RULES + RECEIPT_RULES
        if self.variant == "R2":
            system += RECONCILE_RULES.replace("{event_id, role, quote}",
                                             "{source_handle, start_line, end_line}")
        return await self.llm.call(prompt=user_prompt, system=system,
                                   tools=self.get_tools_schema())

    async def _call_llm_phase2(self, user_prompt: str):
        if self._fatal_error is not None:
            raise self._fatal_error
        from memory_agent.memory.memory_agent import PHASE2_SYSTEM
        return await self.llm.call(prompt=user_prompt,
                                   system=PHASE2_SYSTEM + REMINDER_RULES + RECEIPT_RULES)

    def _build_phase1_prompt(self, observation: str, step_count: int) -> str:
        self._phase_step = step_count
        self._current_evidence_chars = 0
        from memory_agent.memory.memory_agent import MemoryAgent
        prompt = MemoryAgent._build_phase1_prompt(self, observation, step_count)
        self.evidence_chars_by_phase["phase1"] = self._current_evidence_chars
        lines = self.memory.visible_lines()
        return (prompt + "\n## Numbered visible public source leaves\n" +
                json.dumps(lines, ensure_ascii=False) +
                "\n## Previous phase-1 execution receipts\n" +
                json.dumps(self.last_receipts, ensure_ascii=False))

    def _build_phase2_prompt(self, observation: str, step_count: int) -> str:
        prompt = super()._build_phase2_prompt(observation, step_count)
        return prompt + "\n## This phase-1 execution receipts\n" + json.dumps(
            self.last_receipts, ensure_ascii=False)

    def _dispatch_one(self, name: str, args: dict) -> tuple[str | None, str]:
        if name in {"memory_save_knowledge", "memory_save_procedural"}:
            category = "knowledge" if name.endswith("knowledge") else "procedural"
            return self.memory.save_sourced(category, args["content"],
                                            args["statement_type"], args["source_refs"]), "committed"
        if name == "memory_update_status":
            old = self.memory.status
            self.memory.update_status(args["content"])
            return None, "no_change" if self.memory.status == old else "committed"
        if name == "memory_delete":
            if not self.memory.delete(args["memory_id"]):
                raise ValueError("memory ID not active")
            return args["memory_id"], "committed"
        if name == "memory_reconcile" and self.variant == "R2":
            operation = self._reconcile(args)
            return operation.memory_id, "committed"
        raise ValueError("unknown tool")

    @staticmethod
    def _error_code(exc: BaseException) -> str:
        if isinstance(exc, ValidationError):
            return "argument_shape"
        message = str(exc)
        if "window-invisible" in message:
            return "window_invisible"
        if "line range" in message or "empty source" in message:
            return "invalid_range"
        if "handle" in message or "source" in message:
            return "unknown_source"
        if "version" in message or "active" in message:
            return "version_stale"
        if "unknown tool" in message:
            return "unknown_tool"
        return "argument_shape"

    def _execute_tool_calls(self, response) -> list[MemoryOperation]:
        calls = getattr(response, "tool_calls", None) or []
        if not calls:
            raw = self._strip_thinking(getattr(response, "content", None) or "")
            calls = [type("Call", (), {"function": type("Function", (), {
                "name": name, "arguments": args})()})()
                     for name, args in self._parse_tool_calls_from_text(raw)]
            if "<tool_call>" in raw and not calls:
                calls = [type("Call", (), {"function": type("Function", (), {
                    "name": "unparsed_text_tool_call", "arguments": {}})()})()]
        txn = f"p1-{self._phase_step}-{uuid.uuid4().hex[:12]}"
        original = self.memory
        before_bank = original.to_dict()
        working = copy.deepcopy(original)
        coordination_length = len(self.coordination)
        receipts: list[dict] = []
        failed = False
        for number, call in enumerate(calls, 1):
            name = getattr(getattr(call, "function", call), "name", None)
            row = {"transaction_id": txn, "call_index": number, "tool_name": name,
                   "status": "rejected", "error_code": None, "memory_id": None}
            try:
                name, raw_args = self._extract_tool_call(call)
                if name not in self.get_tools_schema_names():
                    raise ValueError("unknown tool")
                args = MODELS[name].model_validate(raw_args).model_dump(exclude_none=True)
                self.memory = working
                memory_id, status = self._dispatch_one(name, args)
                row.update(status=status, memory_id=memory_id)
            except (ValueError, TypeError, ValidationError) as exc:
                failed = True
                row.update(error_code=self._error_code(exc), error_type=type(exc).__name__,
                           error=str(exc))
            except Exception as exc:
                failed = True
                self._fatal_error = exc
                row.update(status="integrity_error", error_code="host_integrity",
                           error_type=type(exc).__name__, error=str(exc))
            finally:
                self.memory = original
            receipts.append(row)
        if not failed:
            try:
                working.validate_bank()
            except Exception as exc:
                failed = True
                self._fatal_error = exc
                receipts.append({"transaction_id": txn, "call_index": len(calls) + 1,
                                 "tool_name": "validate_bank", "status": "rejected",
                                 "error_code": "bank_integrity", "error": str(exc)})
        if failed:
            for row in receipts:
                if row["status"] == "committed":
                    row["status"] = "transaction_aborted"
                    row["error_code"] = "transaction_abort"
                    self.collateral_aborts += 1
            del self.coordination[coordination_length:]
        else:
            original.__dict__.update(working.__dict__)
        after_bank = original.to_dict()
        version = __import__("hashlib").sha256(json.dumps(after_bank,
            ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        for row in receipts:
            row["commit_version"] = version
        self.last_receipts = receipts
        self.last_transaction = {"transaction_id": txn, "committed": not failed,
                                 "commit_version": version, "receipts": copy.deepcopy(receipts),
                                 "before_bank": self._bank_view(before_bank),
                                 "after_bank": self._bank_view(after_bank)}
        return [MemoryOperation(action=row["tool_name"] or "unknown", memory_id=row.get("memory_id"),
                                success=row["status"] in {"committed", "no_change"},
                                error=row.get("error_code")) for row in receipts]

    def get_tools_schema_names(self) -> set[str]:
        return {tool["function"]["name"] for tool in self.get_tools_schema()}

    @staticmethod
    def _bank_view(state: dict) -> dict:
        # Full source registry is persisted separately in bank_states.jsonl;
        # transaction records retain the complete active bank and history.
        return {key: copy.deepcopy(value) for key, value in state.items()
                if key != "sources"}
