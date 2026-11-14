"""One persistent memory manager: optional tool rounds, explicit wake decision."""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
import json
import re

from .context_predictive_memory_agent import ContextPredictiveMemoryAgent, PMAPhaseError
from .ga_context_history import (GAHistoryConfig, GAHistoryIntegrityError,
                                 trim_observer_history, provider_history,
                                 _history_bytes)
from .predictive_memory_agent import (BANK_TOOLS as ADD_TOOLS, MemoryOperation,
                                      MemoryAgentResult, PHASE2_SYSTEM)

PHASE1_SYSTEM = """You are a memory manager for the task agent.

Based on the task description and the task agent's trajectory, first anticipate the problems the task agent may encounter or the decisions it may need to make over the next 10 turns, and what information it will need then; organize and save that information accordingly.

Before using memory tools, briefly state in ordinary reply text the upcoming problems or decisions you anticipate and the information you plan to preserve for them. Give a concise public summary, not private reasoning. No special format is needed.

Use memory_add to save information. When you need to look up information already saved, use memory_read with bank_id="knowledge"."""

# One coherent instruction for the existing single memory-management loop.
# PHASE1_SYSTEM and the imported PHASE2_SYSTEM remain unchanged for compatibility.
UNIFIED_SYSTEM = """You are the task's information organizer. Some information that appears during task execution remains valuable much later in the task, while other information only becomes valuable then. Your role is to predict and save this information, and remind the task agent when it is relevant to its current or upcoming work, helping it use existing information to complete the task.

The <task_description> tags contain the task agent's original task, and the <task_trajectory> tags contain the task agent's newly observed execution trajectory.

Based on the task description and the task agent's trajectory, carry out the following steps:

1. Predict and save. You must predict which information received this time will still be worth presenting to the task agent to support subsequent task work after the task has progressed for another eight turns, and organize and save that information in the knowledge bank. Before saving, briefly state which information you have selected.

2. Recall and remind. After organizing the information for this wake, use memory_read to read the knowledge bank. Based on the task agent's current and upcoming work, decide whether to remind it of information in the knowledge bank.

## Tools
- memory_add: Save information in the knowledge bank.
- memory_read: Read all information currently saved in the knowledge bank. Set bank_id to "knowledge" when calling it.

Organize information and decide whether to provide a reminder in this same conversation. When ready to finish this wake, end your reply with exactly one of the following decision tags:

If a reminder is needed:
<context_for_action>
Information to remind the task agent of.
</context_for_action>

If no reminder is needed:
<no_intervention/>"""

DECISION_RECOVERY_PROMPT = (
    "No valid final decision was received. Continue managing memory if needed, "
    "or end with exactly one nonempty <context_for_action>...</context_for_action> "
    "or <no_intervention/>. Do not repeat successful memory writes.")
TOOL_RECOVERY_PROMPT = (
    "One or more memory tools failed. The decision in that response was not "
    "accepted. Review the actual tool receipts, correct the failed calls if "
    "needed, and decide again. Do not repeat successful memory writes.")
MAX_CONSECUTIVE_DECISION_ERROR_ROUNDS = 2


@dataclass
class UnifiedMemoryAgentResult(MemoryAgentResult):
    loop_mode: str = "unified"
    loop_rounds: list[dict] = field(default_factory=list)
    termination: str | None = None


class PMADecisionRecoveryExhausted(RuntimeError):
    """Missing/malformed decisions are failures, never silent no-intervention."""


def _mask_decision_code(text):
    """Ignore fenced examples as protocol, retaining offsets into the original."""
    return re.sub(r"```.*?(?:```|$)|~~~.*?(?:~~~|$)",
                  lambda match: " " * len(match.group(0)), text, flags=re.DOTALL)


def parse_final_decision(raw):
    """Extract an unambiguous public decision tag anywhere; no semantic checker."""
    if not isinstance(raw, str):
        return None, None
    # Fail closed on malformed/nested hidden spans. A single regex replacing
    # the first closing tag could expose text still inside an outer block.
    visible, end, hidden = [], 0, None
    for token in re.finditer(r"</?(think|thinking|tool_call)\b[^>]*>",
                             _mask_decision_code(raw), re.IGNORECASE):
        closing = token.group(0).startswith("</")
        name = token.group(1).lower()
        if closing:
            if hidden != name:
                return None, None
            hidden = None
        else:
            if hidden is not None:
                return None, None
            visible.append(raw[end:token.start()])
            hidden = name
        end = token.end()
    if hidden is not None:
        return None, None
    visible.append(raw[end:])
    public = "".join(visible)
    protocol = _mask_decision_code(public)
    if re.search(r"<\s*/?\s*(?:think|thinking|tool_call)\b", protocol, re.IGNORECASE):
        return None, None
    tokens = re.findall(r"</?(?:context_for_action|no_intervention)\b[^>]*>", protocol)
    if tokens == ["<no_intervention/>"]:
        return "no_intervention", None
    if tokens == ["<context_for_action>", "</context_for_action>"]:
        match = re.search(r"<context_for_action>(.*?)</context_for_action>", protocol, re.DOTALL)
        if match:
            # Protocol recognition must never rewrite the reminder payload.
            content = public[match.start(1):match.end(1)].strip()
            if content:
                return "context_for_action", content
    return None, None


PUBLIC_FORECAST_REMINDER = (
    "Briefly state which information you have selected that you predict will still "
    "be worth presenting to the task agent to support subsequent task work after "
    "the task has progressed for another eight turns.")


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
BANK_TOOLS[0]["function"]["description"] = (
    "Save the text supplied in content to the knowledge bank. "
    "Your surrounding reply is not saved by this tool. Call it more than once when needed."
)
BANK_TOOLS[0]["function"]["parameters"]["properties"]["content"]["description"] = (
    "The selected information, with the concrete details needed to understand and use it later. "
    "Include the information itself, not just its name or a statement that it was saved. "
    "This may include original text, code, or formulas."
)

MAX_CONSECUTIVE_TOOL_ERROR_ROUNDS = 3


class PMAToolRecoveryExhausted(RuntimeError):
    """Consecutive error-bearing tool rounds exhausted this wake's recovery."""


class ReadContextPredictiveMemoryAgent(ContextPredictiveMemoryAgent):
    """Reuse GA-derived native history/tools; phase1 names are storage aliases."""

    transport_phase = "unified_memory"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.use_structured_tools:
            raise ValueError("read-context memory manager requires native structured tools")

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
        self._unified_rounds = []

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
            return "<task_description>\n" + self._original_task + "\n</task_description>"
        return "<task_trajectory>\n" + self._new_trajectory + "\n</task_trajectory>"

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

    def _p1_messages(self):
        return ([self._task_anchor] if self._task_anchor is not None else []) + \
            self._completed_phase1 + self._active_phase1

    async def process(self, observation, step_count=0):
        self._step = step_count
        self._unified_rounds = []
        self._phase1_operations = []
        try:
            prompt = self._build_phase1_prompt(observation, step_count)
            response = await self._call_llm_phase1(prompt)
            raw = getattr(response, "content", None) or ""
            kind, context = parse_final_decision(raw)
            return UnifiedMemoryAgentResult(
                operations=list(self._phase1_operations),
                should_inject=kind == "context_for_action", context_for_action=context,
                # Legacy slot names are retained for older archive readers. There
                # is no second phase/request, so its slots remain explicitly empty.
                raw_response_phase1=raw, user_prompt_phase1=prompt,
                loop_rounds=copy.deepcopy(self._unified_rounds), termination=kind)
        except Exception as exc:
            raise PMAPhaseError("unified", exc) from exc

    async def _call_llm_phase1(self, user_prompt):
        self._phase1_operations = []
        self._unified_rounds = []
        prior = self._p1_prior(user_prompt, new_wake=True)
        self._new_trajectory = None  # A second wake must receive new host input.
        error_rounds = decision_error_rounds = 0
        while True:
            system = UNIFIED_SYSTEM
            if self._p1_public_text_missing:
                system += "\n\n" + PUBLIC_FORECAST_REMINDER
            try:
                response = await self.llm.call(prompt=user_prompt, system=system,
                                               tools=self.get_tools_schema(),
                                               message_history=prior)
                # Execute the entire ordered batch and persist actual receipts
                # before inspecting any proposed end tag. Never replay history.
                operations, _ = self._record_p1_response(response)
            except Exception as exc:
                raise PMAPhaseError("unified", exc) from exc
            raw = getattr(response, "content", None) or ""
            self._p1_public_text_missing = not has_public_text(raw)
            self._phase1_operations.extend(operations)
            failed = any(not operation.success for operation in operations)
            kind, _ = parse_final_decision(raw)
            accepted = kind is not None and not failed
            self._unified_rounds.append({
                "round": len(self._unified_rounds) + 1, "prompt": user_prompt,
                "content": raw, "operation_count": len(operations),
                "tool_error": failed, "decision": kind,
                "decision_accepted": accepted})
            if accepted:
                return response
            error_rounds = error_rounds + 1 if failed else 0
            if not operations:
                decision_error_rounds += 1
            elif any(operation.success for operation in operations):
                decision_error_rounds = 0
            if error_rounds >= MAX_CONSECUTIVE_TOOL_ERROR_ROUNDS:
                error = PMAToolRecoveryExhausted(
                    f"{error_rounds} consecutive tool-error rounds; no decision accepted")
                raise PMAPhaseError("unified", error) from error
            if decision_error_rounds >= MAX_CONSECUTIVE_DECISION_ERROR_ROUNDS:
                error = PMADecisionRecoveryExhausted(
                    f"{decision_error_rounds} responses without tools or a valid decision "
                    "since last successful tool progress")
                raise PMAPhaseError("unified", error) from error
            user_prompt = (TOOL_RECOVERY_PROMPT if failed else
                           "Continue." if operations else DECISION_RECOVERY_PROMPT)
            prior = self._p1_prior(user_prompt, new_wake=False)

    def _record_p1_response(self, response, *, allowed_tools=None):
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
                if allowed_tools is not None and name not in allowed_tools:
                    raise ValueError("tool unavailable in this stage; allowed: " + ", ".join(sorted(allowed_tools)))
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
        # Compatibility accessor only; process never executes calls a second time.
        return list(self._phase1_operations)

    def get_tools_schema(self):
        return copy.deepcopy(BANK_TOOLS)


# The prior implementation above remains available as a historical comparator.
# Production read-context wiring below uses a prompt-guided, same-session loop.
REMIND_FIRST_SYSTEM = """You are the task's information organizer. Some information that appears during task execution remains valuable much later in the task, while other information only becomes valuable then. Your role is to predict and save this information, and remind the task agent when it is relevant to its current or upcoming work, helping it use existing information to complete the task.

The <task_description> tags contain the task agent's original task, and the <task_trajectory> tags contain the task agent's newly observed execution trajectory.

Carry out these steps in this same conversation:

1. Recall and decide the reminder. Use memory_read to read the existing knowledge bank. After receiving its result, consider both the conversation context and the knowledge bank to decide whether to remind the task agent, and what to remind it of, based on its current and upcoming work. Express the reminder decision with one of:
<context_for_action>
Information to remind the task agent of.
</context_for_action>
<no_intervention/>

2. Predict and save. You must predict which information received this time will still be worth presenting to the task agent to support subsequent task work after the task has progressed for another eight turns, and organize and save that information in the knowledge bank. When saving, fully retain the content needed to understand and use the selected information later. Before saving, briefly state which information you have selected.

## Tools
- memory_add: Save information in the knowledge bank.
- memory_read: Read all information currently saved in the knowledge bank. Set bank_id to "knowledge" when calling it.
"""


def is_organize_completion(response):
    """GA-style no-tool completion candidate, not a semantic quality verifier."""
    if getattr(response, "tool_calls", None):
        return False
    raw = getattr(response, "content", None) or ""
    if not isinstance(raw, str):
        return False
    # Normal adapters raise on provider truncation. Also reject explicit markers
    # from GA-compatible/synthetic adapters rather than treating them as done.
    if any(marker in raw[-100:] for marker in (
            "[!!! 流异常中断", "!!!Error:", "max_tokens !!!]")):
        return False
    if getattr(response, "finish_reason", None) in {"length", "max_tokens", "error"}:
        return False
    if getattr(response, "stop_reason", None) in {"length", "max_tokens", "error"}:
        return False
    return True


class RemindFirstMemoryAgent(ReadContextPredictiveMemoryAgent):
    """Prompt-guided reminder then organization; tools and tags are independent.

    The class name remains the host's compatibility entry point. The program no
    longer implements reminder/organization stages or freezes a reminder before
    writes. Native tools, history, receipts and reminder transport are reused.
    """

    def reset_conversation_history(self):
        super().reset_conversation_history()
        self._reminder_decision = (None, None)

    async def process(self, observation, step_count=0):
        self._step = step_count
        self._unified_rounds = []
        self._phase1_operations = []
        self._reminder_decision = (None, None)
        try:
            prompt = self._build_phase1_prompt(observation, step_count)
            response = await self._call_llm_phase1(prompt)
            kind, context = self._reminder_decision
            return UnifiedMemoryAgentResult(
                operations=list(self._phase1_operations),
                should_inject=kind == "context_for_action", context_for_action=context,
                raw_response_phase1=getattr(response, "content", None) or "",
                user_prompt_phase1=prompt, loop_mode="remind_first",
                loop_rounds=copy.deepcopy(self._unified_rounds),
                termination="no_tool")
        except Exception as exc:
            raise PMAPhaseError("unified", exc) from exc

    async def _call_llm_phase1(self, user_prompt):
        prior = self._p1_prior(user_prompt, new_wake=True)
        self._new_trajectory = None
        while True:
            system = REMIND_FIRST_SYSTEM
            if self._p1_public_text_missing:
                system += "\n\n" + PUBLIC_FORECAST_REMINDER
            response = await self.llm.call(prompt=user_prompt, system=system,
                tools=self.get_tools_schema(), message_history=prior)
            operations, _ = self._record_p1_response(response)
            self._phase1_operations.extend(operations)
            raw = getattr(response, "content", None) or ""
            kind, context = parse_final_decision(raw)
            if kind is not None:
                self._reminder_decision = (kind, context)
            completed = is_organize_completion(response)
            self._unified_rounds.append({
                "round": len(self._unified_rounds) + 1,
                "prompt": user_prompt, "content": raw,
                "operation_count": len(operations),
                "tool_error": any(not op.success for op in operations),
                "decision": kind, "decision_accepted": kind is not None,
                "organize_completed": completed})
            self._p1_public_text_missing = not has_public_text(raw)
            if completed:
                return response
            if not getattr(response, "tool_calls", None):
                # A transport failure is not a normal model completion.
                raise GAHistoryIntegrityError("incomplete memory-manager response")
            user_prompt = "Continue."
            prior = self._p1_prior(user_prompt, new_wake=False)
