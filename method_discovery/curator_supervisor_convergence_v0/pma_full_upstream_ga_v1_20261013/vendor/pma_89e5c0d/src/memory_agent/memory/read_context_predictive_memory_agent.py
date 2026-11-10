"""Opt-in continuous P1 with an on-demand, read-all flat memory tool."""
from __future__ import annotations

import copy
import json
import re

from .context_predictive_memory_agent import ContextPredictiveMemoryAgent, PMAPhaseError
from .ga_context_history import (GAHistoryConfig, GAHistoryIntegrityError,
                                 trim_observer_history, provider_history,
                                 _history_bytes)
from .predictive_memory_agent import BANK_TOOLS as ADD_TOOLS, MemoryOperation

PHASE1_SYSTEM = """You are a memory manager for the task agent.

Based on the task description and the task agent's trajectory, first anticipate the problems the task agent may encounter or the decisions it may need to make over the next 10 turns, and what information it will need then; organize and save that information accordingly.

Before using memory tools, briefly state in ordinary reply text the upcoming problems or decisions you anticipate and the information you plan to preserve for them. Give a concise public summary, not private reasoning. No special format is needed.

Use memory_add to save information. When you need to look up information already saved, use memory_read with bank_id="knowledge"."""

PUBLIC_FORECAST_REMINDER = (
    "Remember to include a brief public summary of the upcoming problems or "
    "decisions you anticipate and the information you plan to preserve. "
    "Do not disclose private reasoning.")


def has_public_text(text):
    """Lexical presence only, not a judgment of forecast quality or ordering.

    Read only public reply text. Native reasoning/opaque state is never an
    input. Markup and punctuation placeholders alone do not count; even 'OK'
    does count, so this must not be reported as a verified forecast.
    """
    if not isinstance(text, str):
        return False
    text = re.sub(r"<(think|thinking|tool_call)\b[^>]*>.*?(?:</\1\s*>|$)",
                  "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]*>", "", text)
    return any(character.isalnum() for character in text)


BANK_TOOLS = copy.deepcopy(ADD_TOOLS) + [{
    "type": "function",
    "function": {
        "name": "memory_read",
        "description": "Read all information currently saved in the knowledge memory bank.",
        "parameters": {"type": "object", "properties": {
            "bank_id": {"type": "string", "enum": ["knowledge"],
                        "description": "Memory bank to read. Use knowledge."}
        }, "required": ["bank_id"], "additionalProperties": False},
    },
}]
BANK_TOOLS[0]["function"]["parameters"]["additionalProperties"] = False
BANK_TOOLS[0]["function"]["description"] = "Save information in the knowledge memory bank."

MAX_CONSECUTIVE_TOOL_ERROR_ROUNDS = 3


class PMAToolRecoveryExhausted(RuntimeError):
    """Consecutive error-bearing tool rounds exhausted this wake's recovery."""


class ReadContextPredictiveMemoryAgent(ContextPredictiveMemoryAgent):
    """P2 is inherited unchanged; only P1 uses incremental input and lookup."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.use_structured_tools:
            raise ValueError("read-context P1 requires native structured tools")

    def reset_conversation_history(self):
        super().reset_conversation_history()
        self._original_task = None
        self._new_trajectory = None
        self._task_anchor = None
        self._completed_phase1 = []
        self._active_phase1 = []
        self._phase1_operations = []
        self._seen_call_ids = set()
        self._p1_public_text_missing = False

    def set_phase1_context(self, *, task, trajectory):
        """Receive exact host fields, never parse task markers from model text."""
        if not isinstance(task, str) or not isinstance(trajectory, str):
            raise GAHistoryIntegrityError("P1 context must contain text")
        if self._original_task is not None and self._original_task != task:
            raise GAHistoryIntegrityError("reset history before changing the task")
        self._original_task = task
        self._new_trajectory = trajectory

    def _build_phase1_prompt(self, observation, step_count):
        if self._original_task is None or self._new_trajectory is None:
            raise GAHistoryIntegrityError("P1 requires explicit host task and trajectory")
        if self._task_anchor is None:
            return "[Task Description]\n" + self._original_task
        return self._new_trajectory

    def _p1_prior(self, prompt, *, new_wake):
        first = self._task_anchor is None
        if new_wake:
            self._completed_phase1.extend(self._active_phase1)
            self._active_phase1 = []
        message = {"role": "user", "content": [{"type": "text", "text": prompt}]}
        if first:
            self._task_anchor = message
        else:
            self._active_phase1.append(message)
        before = self._p1_messages()
        protected = ([self._task_anchor] if self._task_anchor is not None else []) + self._active_phase1
        state = trim_observer_history(self._completed_phase1, protected, GAHistoryConfig(),
            round_number=1 + sum(item["phase"] == "P1" for item in self._history_transforms))
        self._phase1_history = self._p1_messages()
        self._history_transforms.append({
            "phase": "P1", "before_messages": len(before),
            "after_messages": len(self._phase1_history),
            "before_chars": _history_bytes(before), "after_chars": _history_bytes(self._phase1_history),
            "policy": {"context_win": GAHistoryConfig.context_win,
                       "trim_keep_rate": GAHistoryConfig.trim_keep_rate,
                       "cut_msg_interval": GAHistoryConfig.cut_msg_interval,
                       "protected": "original_task_and_active_wake",
                       "eviction": "closed_native_tool_groups"},
            **state,
        })
        # LiteLLM appends this call's prompt itself. All prior visible messages
        # and opaque provider continuation items keep their original ordering.
        return provider_history(self._phase1_history[:-1])

    def _prior(self, phase, prompt):
        if phase != "P2":
            return super()._prior(phase, prompt)
        # P2 has its own persistent provider conversation. Pin its first task
        # prompt and the current full prompt, independently of P1's history.
        before = self._phase2_history
        anchor = before[:1]
        completed = list(before[1:])
        current = {"role": "user", "content": [{"type": "text", "text": prompt}]}
        state = trim_observer_history(completed, anchor + [current], GAHistoryConfig(),
            round_number=1 + sum(item["phase"] == "P2" for item in self._history_transforms))
        self._phase2_history = anchor + completed + [current]
        self._history_transforms.append({
            "phase": "P2", "before_messages": len(before),
            "after_messages": len(self._phase2_history),
            "before_chars": _history_bytes(before), "after_chars": _history_bytes(self._phase2_history),
            "policy": {"context_win": GAHistoryConfig.context_win,
                       "trim_keep_rate": GAHistoryConfig.trim_keep_rate,
                       "cut_msg_interval": GAHistoryConfig.cut_msg_interval,
                       "protected": "original_task_and_active_wake",
                       "eviction": "closed_native_tool_groups"},
            **state,
        })
        return provider_history(self._phase2_history[:-1])

    def _p1_messages(self):
        return ([self._task_anchor] if self._task_anchor is not None else []) + \
            self._completed_phase1 + self._active_phase1

    async def _call_llm_phase1(self, user_prompt):
        self._phase1_operations = []
        prior = self._p1_prior(user_prompt, new_wake=True)
        self._new_trajectory = None  # A second wake must receive new host input.
        continuing = False
        error_rounds = 0
        while True:
            # Soft guidance on an already-scheduled request only. Keep the raw
            # task/batch unchanged; never add a call or block a tool for this.
            system = PHASE1_SYSTEM
            if self._p1_public_text_missing:
                system += "\n\n" + PUBLIC_FORECAST_REMINDER
            try:
                response = await self.llm.call(prompt=user_prompt, system=system,
                                               tools=self.get_tools_schema(),
                                               message_history=prior)
            except Exception as exc:
                # Do not turn a broken read continuation into a normal P2/no-op.
                raise PMAPhaseError("P1", exc) from exc
            operations, called_read = self._record_p1_response(response)
            self._p1_public_text_missing = not has_public_text(
                getattr(response, "content", None))
            self._phase1_operations.extend(operations)
            failed = any(not operation.success for operation in operations)
            error_rounds = error_rounds + 1 if failed else 0
            if error_rounds >= MAX_CONSECUTIVE_TOOL_ERROR_ROUNDS:
                error = PMAToolRecoveryExhausted(
                    f"{error_rounds} consecutive tool-error rounds; P2 not entered")
                raise PMAPhaseError("P1", error) from error
            # An invalid call must receive feedback in this wake, even before
            # the first read. Keep successful add-only behavior unchanged.
            continuing = continuing or called_read or failed
            if not operations or not continuing:
                return response
            user_prompt = "Continue."
            prior = self._p1_prior(user_prompt, new_wake=False)

    def _record_p1_response(self, response):
        native = getattr(response, "tool_calls", None) or []
        raw = getattr(response, "content", None) or ""
        parsed, ids = [], set()
        # Validate the entire native envelope before any bank mutation.
        for call in native:
            try:
                name, args = self._extract_tool_call(call)
                call_id = call.get("id") if isinstance(call, dict) else getattr(call, "id", None)
                if (not isinstance(name, str) or not name or not isinstance(args, dict)
                        or not isinstance(call_id, str) or not call_id
                        or call_id in ids or call_id in self._seen_call_ids):
                    raise ValueError("invalid or repeated native call identity")
                ids.add(call_id)
                parsed.append((call_id, name, args))
            except Exception as exc:
                raise GAHistoryIntegrityError("invalid P1 tool-call history") from exc
        if not native and "<tool_call>" in self._strip_thinking(raw):
            raise GAHistoryIntegrityError("text tool calls lack native call identities")
        thinking = getattr(response, "thinking_blocks", None)
        if native and getattr(response, "reasoning_content", None) and not thinking:
            raise GAHistoryIntegrityError("signed thinking blocks unavailable for tool continuation")
        blocks = [{"type": "text", "text": raw}] if raw else []
        assistant = {"role": "assistant", "content": blocks}
        if thinking:
            assistant["_provider_thinking_blocks"] = copy.deepcopy(thinking)
        if getattr(response, "openai_output_items", None):
            assistant["_openai_output_items"] = copy.deepcopy(response.openai_output_items)
        if parsed:
            blocks.extend({"type": "tool_use", "id": call_id, "name": name,
                           "input": copy.deepcopy(args)} for call_id, name, args in parsed)
        self._active_phase1.append(assistant)
        self._seen_call_ids.update(ids)
        operations, results = [], []
        for call_id, name, args in parsed:
            try:
                if name == "memory_read":
                    if set(args) != {"bank_id"} or args["bank_id"] != "knowledge":
                        raise ValueError('memory_read requires exactly {"bank_id": "knowledge"}')
                    operation = MemoryOperation(action="read", content=self._format_memory_bank())
                elif name == "memory_add":
                    if set(args) != {"content"}:
                        raise ValueError("memory_add accepts only content")
                    content = args.get("content", "")
                    if not isinstance(content, str) or not content.strip():
                        raise ValueError("memory content must be nonempty text")
                    operation = MemoryOperation(action="add",
                        memory_id=self.memory.save_knowledge(content), content=content)
                else:
                    raise ValueError("unsupported tool; available tools: memory_add, memory_read")
            except Exception as exc:
                operation = MemoryOperation(action=name, success=False, error=str(exc))
            operations.append(operation)
            receipt = {"action": operation.action, "success": operation.success,
                       "memory_id": operation.memory_id, "error": operation.error}
            if name == "memory_read" and operation.success:
                receipt["content"] = operation.content
            results.append({"type": "tool_result", "tool_use_id": call_id,
                            "content": json.dumps(receipt, ensure_ascii=False)})
        if results:
            self._active_phase1.append({"role": "user", "content": results})
        self._phase1_history = self._p1_messages()
        return operations, any(name == "memory_read" for _, name, _ in parsed)

    def _execute_tool_calls(self, response):
        # The inherited process records these once, after P1's internal loop.
        return list(self._phase1_operations)

    def get_tools_schema(self):
        return copy.deepcopy(BANK_TOOLS)
