"""Shared S2/R2 evidence selection, strict arguments and one-phase bank transaction."""
from __future__ import annotations

import copy
import json
import re
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
RECONCILE_V2_RULES = """
memory_reconcile takes the exact active memory_id shown before the separate vN
version label: never send "ID v1" as memory_id. For revise, provide non-empty
replacement content, statement_type, and either non-empty current source_refs
or valid zero-based inherit_source_ref_indices (both are allowed). evidence_refs
justify the decision but never supply replacement provenance. For retain,
retract, or unresolved, omit replacement fields (explicit null is also accepted);
non-null replacement fields are rejected. The schema shows optional fields
because they apply only to revise; the host enforces these conditional rules.
"""

_RECEIPT_REASONS = {
    "argument_shape": "arguments do not match the required tool schema",
    "unknown_source": "source handle or reference is unknown",
    "window_invisible": "source is not visible in the current window",
    "invalid_range": "source line range is invalid",
    "version_stale": "memory ID or version is not active",
    "memory_not_active": "memory_id must be an exact active memory ID; omit the displayed version label",
    "unknown_tool": "tool name is not supported",
    "bank_integrity": "bank validation failed",
    "transaction_abort": "operation was rolled back with the transaction",
    "text_tool_call_forbidden": "text tool calls are not executable",
    "host_integrity": "host integrity check failed",
}

_ARGUMENT_HINTS = {
    "replacement_content_required": ("content", "revise requires non-empty replacement content"),
    "replacement_type_required": ("statement_type", "revise requires statement_type"),
    "replacement_sources_required": ("source_refs", "revise requires non-empty source_refs or valid inherit_source_ref_indices; evidence_refs do not replace them"),
    "replacement_field_forbidden": ("replacement", "retain, retract and unresolved do not accept non-null replacement fields"),
}


class InactiveMemoryID(ValueError):
    """An exact active ID was not found; never infer a version or repair an ID."""


def _safe_validation_hint(name: str, args: object, exc: ValidationError) -> dict:
    """Classify validation shape only; never return Pydantic input or exception text."""
    if name == "memory_reconcile" and isinstance(args, dict):
        if args.get("decision") == "revise":
            if not isinstance(args.get("content"), str) or not args["content"].strip():
                code = "replacement_content_required"
            elif args.get("statement_type") is None:
                code = "replacement_type_required"
            elif not (args.get("source_refs") or args.get("inherit_source_ref_indices")):
                code = "replacement_sources_required"
            else:
                code = None
        elif args.get("decision") in ("retain", "retract", "unresolved") and any(
                args.get(key) is not None for key in
                ("content", "statement_type", "source_refs", "inherit_source_ref_indices")):
            code = "replacement_field_forbidden"
        else:
            code = None
        if code:
            path, hint = _ARGUMENT_HINTS[code]
            if code == "replacement_field_forbidden":
                path = next(key for key in ("content", "statement_type", "source_refs",
                                            "inherit_source_ref_indices")
                            if args.get(key) is not None)
            return {"rule_code": code, "field_path": path, "hint": hint}
    # Only report model-declared top-level fields; never echo arbitrary locations.
    fields = set(MODELS[name].model_fields) if name in MODELS else set()
    for error in exc.errors():
        loc = error.get("loc", ())
        if loc and isinstance(loc[0], str) and loc[0] in fields:
            return {"rule_code": "field_invalid", "field_path": loc[0],
                    "hint": "provide this field with the declared type and shape"}
    return {"rule_code": "argument_shape", "field_path": "arguments",
            "hint": "arguments must match the tool schema and conditional decision rules"}


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
        self._previous_receipts: list[dict] = []
        self._previous_transaction: dict = {}
        self.blocked_phase2_attempts = 0

    async def process(self, observation: str, step_count: int = 0):
        self._previous_receipts = copy.deepcopy(self.last_receipts)
        self._previous_transaction = copy.deepcopy(self.last_transaction)
        self.last_receipts = []
        self.last_transaction = {"status": "phase1_not_executed", "committed": False,
                                 "receipts": []}
        self._fatal_error = None
        result = await super().process(observation, step_count)
        if self._fatal_error is not None:
            raise self._fatal_error
        return result

    def get_tools_schema(self) -> list[dict]:
        descriptions = {tool["function"]["name"]: tool["function"]["description"]
                        for tool in BANK_TOOLS}
        if self.variant == "R2":
            descriptions["memory_reconcile"] = (
                "Coordinate an exact active memory ID. revise requires non-empty content, "
                "statement_type and source_refs or valid inherit_source_ref_indices; "
                "evidence_refs alone do not bind replacement sources. Other decisions "
                "must omit non-null replacement fields. Conditional rules are host-validated.")
        return [tool_schema(name, description) for name, description in descriptions.items()]

    @staticmethod
    def _model_transaction_view(transaction: dict, receipts: list[dict]) -> dict:
        """Project execution feedback, never bank snapshots or raw exceptions, to a request."""
        summary = {key: transaction[key] for key in
                   ("transaction_id", "status", "committed", "commit_version",
                    "phase2_blocked", "error_type") if key in transaction}
        visible_receipts = []
        for receipt in receipts:
            row = {key: receipt[key] for key in
                   ("call_index", "tool_name", "status", "memory_id", "commit_version",
                    "rule_code", "field_path", "hint")
                   if key in receipt}
            code = receipt.get("error_code")
            if code is not None:
                # Raw exception text can contain memory/source contents. The fixed
                # explanation is sufficient to correct a tool argument next time.
                row["error_code"] = code if code in _RECEIPT_REASONS else "operation_rejected"
                row["reason"] = _RECEIPT_REASONS.get(code, "operation was rejected")
            visible_receipts.append(row)
        return {"transaction": summary, "receipts": visible_receipts}

    async def _call_llm_phase1(self, user_prompt: str):
        from memory_agent.memory.memory_agent import PHASE1_SYSTEM
        system = PHASE1_SYSTEM + SOURCE_LINES_RULES + RECEIPT_RULES
        if self.variant == "R2":
            system += RECONCILE_RULES.replace("{event_id, role, quote}",
                                             "{source_handle, start_line, end_line}")
            system += RECONCILE_V2_RULES
        try:
            return await self.llm.call(prompt=user_prompt, system=system,
                                       tools=self.get_tools_schema())
        except Exception as exc:
            self.last_transaction = {"status": "phase1_request_failed",
                                     "committed": False, "receipts": [],
                                     "error_type": type(exc).__name__}
            self._fatal_error = exc
            raise

    async def _call_llm_phase2(self, user_prompt: str):
        if self._fatal_error is not None:
            self.blocked_phase2_attempts += 1
            self.last_transaction["phase2_blocked"] = "phase1_request_failed_or_host_integrity"
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
                json.dumps(self._model_transaction_view(self._previous_transaction,
                                                        self._previous_receipts), ensure_ascii=False))

    def _build_phase2_prompt(self, observation: str, step_count: int) -> str:
        prompt = super()._build_phase2_prompt(observation, step_count)
        return prompt + "\n## This phase-1 execution result\n" + json.dumps(
            self._model_transaction_view(self.last_transaction, self.last_receipts),
            ensure_ascii=False)

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
                raise InactiveMemoryID("memory ID not active")
            return args["memory_id"], "committed"
        if name == "memory_reconcile" and self.variant == "R2":
            if args["decision"] in {"revise", "retain", "unresolved"} and self.memory.get(
                    args["memory_id"]) is None:
                raise InactiveMemoryID("memory ID not active")
            if args["decision"] == "retract" and self.memory.get(args["memory_id"]) is None and not any(
                    h.get("id") == args["memory_id"] and h.get("action") == "retract"
                    for h in self.memory.history):
                raise InactiveMemoryID("memory ID not active")
            operation = self._reconcile(args)
            return operation.memory_id, "committed"
        raise ValueError("unknown tool")

    @staticmethod
    def _error_code(exc: BaseException) -> str:
        if isinstance(exc, InactiveMemoryID):
            return "memory_not_active"
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
            if re.search(r"<\s*/?\s*tool_call\b|<\s*function\s*=|<\s*parameter\s*=",
                         raw, re.IGNORECASE):
                txn = f"p1-{self._phase_step}-{uuid.uuid4().hex[:12]}"
                receipt = {"transaction_id": txn, "call_index": 1,
                           "tool_name": "text_tool_call", "status": "rejected",
                           "error_code": "text_tool_call_forbidden", "memory_id": None}
                version = __import__("hashlib").sha256(json.dumps(
                    self.memory.to_dict(), ensure_ascii=False, sort_keys=True).encode()).hexdigest()
                receipt["commit_version"] = version
                self.last_receipts = [receipt]
                self.last_transaction = {"transaction_id": txn, "status": "format_rejected",
                    "committed": False, "commit_version": version,
                    "receipts": copy.deepcopy(self.last_receipts),
                    "before_bank": self._bank_view(self.memory.to_dict()),
                    "after_bank": self._bank_view(self.memory.to_dict())}
                return [MemoryOperation(action="text_tool_call", success=False,
                                        error="text_tool_call_forbidden")]
        txn = f"p1-{self._phase_step}-{uuid.uuid4().hex[:12]}"
        original = self.memory
        before_bank = original.to_dict()
        working = copy.deepcopy(original)
        coordination_length = len(self.coordination)
        receipts: list[dict] = []
        failed = False
        for number, call in enumerate(calls, 1):
            name = getattr(getattr(call, "function", call), "name", None)
            raw_args = None
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
                if isinstance(exc, ValidationError):
                    row.update(_safe_validation_hint(name, raw_args, exc))
                elif isinstance(exc, InactiveMemoryID):
                    row.update(rule_code="memory_not_active", field_path="memory_id",
                               hint=_RECEIPT_REASONS["memory_not_active"])
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
                if row["status"] in {"committed", "no_change"}:
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
        changed = before_bank != after_bank
        self.last_transaction = {"transaction_id": txn,
                                 "status": ("transaction_aborted" if failed else
                                            "committed" if changed else "no_change"),
                                 "committed": not failed,
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
