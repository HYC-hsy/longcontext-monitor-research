"""Reference-only gap adapter over pinned PMA; no host registration or runner."""

from copy import deepcopy
import json
import re
from types import SimpleNamespace

from memory_agent.memory.memory_agent import (
    BANK_TOOLS, MemoryAgent, MemoryOperation, PHASE1_SYSTEM, PHASE2_SYSTEM,
)
from gap_prompts import MAINTENANCE, REVIEW, REPAIR, phase2_system
from gap_store import GapMemory


GAP_TOOL = {
    "type": "function",
    "function": {
        "name": "memory_save_gap",
        "description": "Stage a natural-language gap for review; program assigns ID and time.",
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
        self._gap_error = None
        self._sent_phase2 = None
        self.last_gap_report = {"status": "pending", "reviews": [], "repair_count": 0}
        try:
            try:
                self.gaps.begin()
            except Exception as exc:
                self._gap_error = type(exc).__name__
            result = await super().process(observation, step_count)
            if self._sent_phase2 is not None:
                result.user_prompt_phase2 = self._sent_phase2
            return result
        finally:
            try:
                self.gaps.discard()
            except Exception as exc:
                self.last_gap_report["cleanup_error"] = type(exc).__name__
            self._active = False

    def _gap_view(self):
        try:
            text = self._format_memory_list(self.gaps.entries)
            state = self.last_gap_report.get("status", "not_reviewed")
            return f"\n\n## Separate Gap View ({state})\n{text}\n"
        except Exception as exc:
            self._gap_error = type(exc).__name__
            return "\n\n## Separate Gap View\nUnavailable/stale; do not assume gaps resolved.\n"

    def _build_phase1_prompt(self, observation, step_count):
        return super()._build_phase1_prompt(observation, step_count) + self._gap_view()

    def _build_phase2_prompt(self, observation, step_count):
        return super()._build_phase2_prompt(observation, step_count) + self._gap_view()

    async def _call_llm_phase1(self, user_prompt):
        try:
            self.transport_phase = "maintenance"
            kwargs = {"prompt": user_prompt, "system": PHASE1_SYSTEM + MAINTENANCE}
            if self.use_structured_tools:
                kwargs["tools"] = self.get_tools_schema()
            return await self.llm.call(**kwargs)
        except Exception as exc:
            self._gap_error = type(exc).__name__
            raise

    def _calls(self, response):
        """Retain upstream fallback precedence and use its actual parsers."""
        calls = getattr(response, "tool_calls", None) or []
        parsed = []
        for call in calls:
            try:
                name, args = self._extract_tool_call(call)
                if not isinstance(args, dict):
                    raise ValueError("tool arguments must be an object")
                parsed.append((name, args))
            except Exception as exc:
                self._gap_error = type(exc).__name__
        if not calls or any(not args.get("content") for _, args in parsed):
            raw = self._strip_thinking(getattr(response, "content", None) or "")
            if "<tool_call>" in raw:
                parsed = self._parse_tool_calls_from_text(raw)
        return parsed

    def _dispatch(self, response, *, gap_only=False):
        operations = []
        for name, args in self._calls(response):
            key = args.get("memory_id", "")
            gap_delete = name == "memory_delete" and isinstance(key, str) and key.startswith("gap_")
            try:
                if name == "memory_save_gap":
                    if set(args) != {"content"}:
                        raise ValueError("gap save requires only content")
                    saved = self.gaps.stage_save(args["content"])
                    operations.append(MemoryOperation("stage_save_gap", saved, args["content"]))
                elif gap_delete:
                    if not self.gaps.stage_delete(key):
                        raise ValueError("gap ID not found")
                    operations.append(MemoryOperation("stage_delete_gap", key))
                elif gap_only:
                    raise ValueError("repair permits gap operations only")
                else:
                    call = SimpleNamespace(function=SimpleNamespace(name=name, arguments=args))
                    normalized = SimpleNamespace(content="", tool_calls=[call])
                    operations.extend(super()._execute_tool_calls(normalized))
            except Exception as exc:
                self._gap_error = type(exc).__name__ + ": " + str(exc)
                operations.append(MemoryOperation(name, success=False, error=str(exc)))
        return operations

    def _execute_tool_calls(self, response):
        try:
            return self._dispatch(response)
        except Exception as exc:
            self._gap_error = type(exc).__name__
            return [MemoryOperation("gap_dispatch", success=False, error=str(exc))]

    def _review_material(self):
        return json.dumps({
            "original_task": self.task,
            "current_cycle_actual_material": self._observation,
            "ordinary_memory_projection": self._format_memory_bank(self._observation),
            "old_gaps": [entry.to_dict() for entry in self.gaps.entries],
            "candidate_gaps": [entry.to_dict() for entry in self.gaps.candidate],
            "changes": self.gaps.changes,
        }, ensure_ascii=False)

    async def _review(self):
        prompt = self._review_material()
        self.transport_phase = ("gap_review" if not self.last_gap_report["reviews"]
                                else "gap_rereview")
        response = await self.llm.call(prompt=prompt, system=REVIEW)
        raw = getattr(response, "content", None)
        match = re.fullmatch(r"(ACCEPT|REVISE)(?::([\s\S]*))?", raw.strip()) if isinstance(raw, str) else None
        feedback = match[2] if match else None
        valid = bool(match
                     and ((match[1] == "ACCEPT" and feedback is None)
                          or (feedback is not None and feedback.strip()))
                     and not re.search(r"\b(?:ACCEPT|REVISE)\b", feedback or "")
                     and not getattr(response, "tool_calls", None))
        self.last_gap_report["reviews"].append({"prompt": prompt, "response": raw, "valid": valid})
        if not valid:
            raise ValueError("invalid gap review response")
        return match[1], (feedback or "").strip()

    async def _settle_gaps(self):
        if self._gap_error:
            raise ValueError(self._gap_error)
        decision, feedback = await self._review()
        if decision == "REVISE":
            self.last_gap_report["repair_count"] = 1
            tools = [t for t in self.get_tools_schema()
                     if t["function"]["name"] in {"memory_save_gap", "memory_delete"}]
            kwargs = {
                "prompt": self._review_material() + "\nReview feedback:\n" + feedback,
                "system": REPAIR,
            }
            if self.use_structured_tools:
                kwargs["tools"] = tools
            self.transport_phase = "gap_repair"
            response = await self.llm.call(**kwargs)
            self._dispatch(response, gap_only=True)
            if self._gap_error:
                raise ValueError(self._gap_error)
            decision, feedback = await self._review()
        if decision != "ACCEPT":
            raise ValueError("gap repair not accepted: " + feedback)
        self.gaps.commit()
        self.last_gap_report["status"] = "accepted"

    async def _call_llm_phase2(self, user_prompt):
        try:
            await self._settle_gaps()
        except Exception as exc:
            self.last_gap_report.update(status="stale", error=type(exc).__name__ + ": " + str(exc))
        try:
            actual = self._build_phase2_prompt(self._observation, self._step)
            system = phase2_system()
        except Exception as exc:
            self.last_gap_report["prompt_error"] = type(exc).__name__
            actual = MemoryAgent._build_phase2_prompt(self, self._observation, self._step)
            actual += "\nGap assistance unavailable/stale; use task and observations."
            system = PHASE2_SYSTEM
        self._sent_phase2 = actual
        self.last_gap_report["actual_phase2_prompt"] = actual
        self.transport_phase = "selection"
        return await self.llm.call(prompt=actual, system=system)
