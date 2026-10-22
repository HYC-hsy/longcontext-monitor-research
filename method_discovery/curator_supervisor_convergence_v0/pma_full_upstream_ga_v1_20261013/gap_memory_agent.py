"""Two-phase gap view adapter over the pinned PMA MemoryAgent."""

from copy import deepcopy
from types import SimpleNamespace

from memory_agent.memory.memory_agent import (
    BANK_TOOLS, MemoryAgent, MemoryOperation, PHASE1_SYSTEM, PHASE2_SYSTEM,
)
from gap_prompts import MAINTENANCE, phase2_system
from gap_store import GapMemory


GAP_TOOL = {
    "type": "function",
    "function": {
        "name": "memory_save_gap",
        "description": "Save a natural-language gap directly; program assigns ID and time.",
        "parameters": {
            "type": "object",
            "properties": {"content": {"type": "string"}},
            "required": ["content"],
            "additionalProperties": False,
        },
    },
}


class GapMemoryAgent(MemoryAgent):
    def __init__(self, *, task, memory=None, **kwargs):
        bank = memory if memory is not None else GapMemory()
        if not isinstance(bank, GapMemory):
            raise TypeError("adapter requires GapMemory; preserve the host bank identity")
        super().__init__(memory=bank, **kwargs)
        self.task = str(task)
        self.gaps = bank
        self._tools = deepcopy(BANK_TOOLS) + [deepcopy(GAP_TOOL)]
        self.last_gap_report = {}
        self.transport_phase = None
        self._active = False

    def get_tools_schema(self):
        return deepcopy(self._tools)

    async def process(self, observation, step_count=0):
        if self._active:
            raise RuntimeError("one serial gap cycle per agent is required")
        self._active = True
        self._observation, self._step = observation, step_count
        self._sent_phase2 = None
        self.last_gap_report = {"mode": "direct_two_phase", "operations": [],
                                "errors": [], "transport_errors": []}
        try:
            result = await super().process(observation, step_count)
            if self._sent_phase2 is not None:
                result.user_prompt_phase2 = self._sent_phase2
            self.last_gap_report["operations"] = [vars(op).copy() for op in result.operations]
            self.last_gap_report["gap_operations"] = [vars(op).copy() for op in result.operations
                                                       if op.action in {"save_gap", "delete_gap",
                                                                        "memory_save_gap"}
                                                       or (isinstance(op.memory_id, str)
                                                           and op.memory_id.startswith("gap_"))]
            self.last_gap_report["errors"] = [vars(op).copy() for op in result.operations if not op.success]
            self.last_gap_report["formal_gaps"] = [entry.to_dict() for entry in self.gaps.entries]
            self.last_gap_report["actual_phase2_prompt"] = result.user_prompt_phase2
            return result
        finally:
            self._active = False

    def _gap_view(self):
        text = self._format_memory_list(self.gaps.entries)
        return f"\n\n## Separate Gap View\n{text}\n"

    def _build_phase1_prompt(self, observation, step_count):
        return super()._build_phase1_prompt(observation, step_count) + self._gap_view()

    def _build_phase2_prompt(self, observation, step_count):
        return super()._build_phase2_prompt(observation, step_count) + self._gap_view()

    async def _call_llm_phase1(self, user_prompt):
        self.transport_phase = "maintenance"
        kwargs = {"prompt": user_prompt, "system": PHASE1_SYSTEM + MAINTENANCE}
        if self.use_structured_tools:
            kwargs["tools"] = self.get_tools_schema()
        try:
            return await self.llm.call(**kwargs)
        except Exception as exc:
            self.last_gap_report["transport_errors"].append(
                {"phase": "maintenance", "type": type(exc).__name__})
            raise

    def _execute_tool_calls(self, response):
        """Keep vendor fallback and per-call extraction order; only route gap tools."""
        operations = []
        tool_calls = getattr(response, "tool_calls", None) or []
        has_empty_content = any(
            not self._extract_tool_call(call)[1].get("content")
            for call in tool_calls
        ) if tool_calls else False
        if not tool_calls or has_empty_content:
            raw = self._strip_thinking(getattr(response, "content", None) or "")
            if "<tool_call>" in raw:
                parsed = self._parse_tool_calls_from_text(raw)
                if parsed:
                    tool_calls = [SimpleNamespace(function=SimpleNamespace(name=name, arguments=args))
                                  for name, args in parsed]
        for call in tool_calls:
            name, args = self._extract_tool_call(call)
            if not name:
                continue
            key = args.get("memory_id", "") if isinstance(args, dict) else None
            gap_delete = name == "memory_delete" and isinstance(key, str) and key.startswith("gap_")
            try:
                if name == "memory_save_gap":
                    if not isinstance(args, dict):
                        raise ValueError("gap tool arguments must be an object")
                    if set(args) != {"content"}:
                        raise ValueError("gap save requires only content")
                    saved = self.gaps.save_gap(args["content"])
                    operations.append(MemoryOperation("save_gap", saved, args["content"]))
                elif gap_delete:
                    if not self.gaps.delete_gap(key):
                        raise ValueError("gap ID not found")
                    operations.append(MemoryOperation("delete_gap", key))
                else:
                    call = SimpleNamespace(function=SimpleNamespace(name=name, arguments=args))
                    normalized = SimpleNamespace(content="", tool_calls=[call])
                    operations.extend(super()._execute_tool_calls(normalized))
            except Exception as exc:
                operations.append(MemoryOperation(name, memory_id=key,
                                                  success=False, error=str(exc)))
        return operations

    async def _call_llm_phase2(self, user_prompt):
        self._sent_phase2 = user_prompt
        self.last_gap_report["actual_phase2_prompt"] = user_prompt
        self.transport_phase = "selection"
        try:
            return await self.llm.call(prompt=user_prompt, system=phase2_system())
        except Exception as exc:
            self.last_gap_report["transport_errors"].append(
                {"phase": "selection", "type": type(exc).__name__})
            raise
