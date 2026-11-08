"""Isolated f838 predictive PMA with the pinned GA-style per-phase history."""

from __future__ import annotations

import copy
import json

from .ga_context_history import GAHistoryIntegrityError, prepare_history, _history_bytes
from .predictive_memory_agent import BANK_TOOLS, MemoryAgent as PredictiveMemoryAgent
from .predictive_memory_agent import PHASE1_SYSTEM, PHASE2_SYSTEM, MemoryAgentResult


class PMAPhaseError(GAHistoryIntegrityError):
    """Failed phases are not decisions; cross both upstream silence handlers."""

    def __init__(self, phase, error):
        self.phase = phase
        self.error_type = type(error).__name__
        super().__init__(f"{phase} failed ({self.error_type}); no decision produced")


class ContextPredictiveMemoryAgent(PredictiveMemoryAgent):
    """Keep P1 and P2 continuations separate without changing their prompts."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.reset_conversation_history()

    def reset_conversation_history(self):
        self._phase1_history = []
        self._phase2_history = []
        self._history_transforms = []

    def _prior(self, phase, prompt):
        history = self._phase1_history if phase == "P1" else self._phase2_history
        before_count = len(history)
        before_bytes = _history_bytes(history)
        prior = prepare_history(history, prompt)
        self._history_transforms.append({
            "phase": phase, "prior_messages": len(prior),
            "before_messages": before_count, "after_messages": len(history),
            "before_chars": before_bytes,
            "after_chars": _history_bytes(history),
            "policy": {"context_win": 30000, "trim_keep_rate": 0.6,
                       "cut_msg_interval": 5},
        })
        return prior

    async def _call_llm_phase1(self, user_prompt):
        kwargs = {"prompt": user_prompt, "system": PHASE1_SYSTEM,
                  "message_history": self._prior("P1", user_prompt)}
        if self.use_structured_tools:
            kwargs["tools"] = BANK_TOOLS
        return await self.llm.call(**kwargs)

    async def _call_llm_phase2(self, user_prompt):
        response = await self.llm.call(
            prompt=user_prompt, system=PHASE2_SYSTEM,
            message_history=self._prior("P2", user_prompt))
        assistant = {"role": "assistant", "content": [{
            "type": "text", "text": getattr(response, "content", None) or ""}]}
        if getattr(response, "thinking_blocks", None):
            assistant["_provider_thinking_blocks"] = copy.deepcopy(response.thinking_blocks)
        if getattr(response, "openai_output_items", None):
            assistant["_openai_output_items"] = copy.deepcopy(response.openai_output_items)
        self._phase2_history.append(assistant)
        return response

    def _extract_tool_call(self, call):
        if isinstance(call, dict):
            function = call.get("function") or call
            name = function.get("name")
            args = function.get("arguments", function.get("args", {}))
            if isinstance(args, str):
                args = json.loads(args)
            return name, args
        return super()._extract_tool_call(call)

    def _execute_tool_calls(self, response):
        native = getattr(response, "tool_calls", None) or []
        parsed = []
        seen = set()
        for call in native:
            try:
                name, args = self._extract_tool_call(call)
                call_id = call.get("id") if isinstance(call, dict) else getattr(call, "id", None)
                if (not name or not isinstance(args, dict) or not isinstance(call_id, str)
                        or not call_id or call_id in seen):
                    raise ValueError("missing or duplicate native tool-call identity")
                seen.add(call_id)
                parsed.append((call_id, name, args))
            except Exception as exc:
                raise GAHistoryIntegrityError("invalid P1 tool-call history") from exc
        raw = getattr(response, "content", None) or ""
        if native and "<tool_call>" in raw and any(not args.get("content") for _, _, args in parsed):
            raise GAHistoryIntegrityError("ambiguous native and text P1 tool calls")
        if native and getattr(response, "reasoning_content", None) and not getattr(response, "thinking_blocks", None):
            raise GAHistoryIntegrityError("signed thinking blocks unavailable for tool continuation")
        if not native and "<tool_call>" in raw:
            parsed = [(None, name, args) for name, args in self._parse_tool_calls_from_text(self._strip_thinking(raw))]
        operations = super()._execute_tool_calls(response)
        if len(parsed) != len(operations):
            raise GAHistoryIntegrityError("P1 operation receipts do not match tool calls")
        blocks = ([{"type": "text", "text": raw}] if raw else [])
        if native:
            blocks.extend({"type": "tool_use", "id": call_id, "name": name,
                           "input": copy.deepcopy(args)} for call_id, name, args in parsed)
        elif parsed:
            blocks.append({"type": "text", "text": "[Executed memory calls] " +
                           json.dumps([{"name": name, "arguments": args}
                                       for _, name, args in parsed], ensure_ascii=False)})
        assistant = {"role": "assistant", "content": blocks}
        if getattr(response, "thinking_blocks", None):
            assistant["_provider_thinking_blocks"] = copy.deepcopy(response.thinking_blocks)
        self._phase1_history.append(assistant)
        if native:
            self._phase1_history.append({"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": call_id,
                 "content": json.dumps({"action": operation.action,
                                        "success": operation.success,
                                        "memory_id": operation.memory_id,
                                        "error": operation.error}, ensure_ascii=False)}
                for (call_id, _, _), operation in zip(parsed, operations)]})
        return operations

    async def process(self, observation, step_count=0):
        # Keep the predictive prompts, operations and decision parser unchanged.
        # Unlike its historical best-effort process, neither phase may fail into
        # a valid no-intervention result. BaseException also crosses the host's
        # upstream except-Exception handler; cancellation remains untouched.
        try:
            phase1_prompt = self._build_phase1_prompt(observation, step_count)
            response1 = await self._call_llm_phase1(phase1_prompt)
            raw1 = getattr(response1, 'content', None)
            operations = self._execute_tool_calls(response1)
        except Exception as exc:
            raise PMAPhaseError("P1", exc) from exc
        try:
            phase2_prompt = self._build_phase2_prompt(observation, step_count)
            response2 = await self._call_llm_phase2(phase2_prompt)
            raw2 = getattr(response2, 'content', None) or ""
            context_for_action = self._parse_phase2_response(raw2)
        except Exception as exc:
            raise PMAPhaseError("P2", exc) from exc
        return MemoryAgentResult(
            operations=operations,
            should_inject=context_for_action is not None,
            context_for_action=context_for_action,
            raw_response_phase1=raw1,
            raw_response_phase2=raw2,
            reasoning_phase1=None,
            reasoning_phase2=None,
            user_prompt_phase1=phase1_prompt,
            user_prompt_phase2=phase2_prompt,
        )
