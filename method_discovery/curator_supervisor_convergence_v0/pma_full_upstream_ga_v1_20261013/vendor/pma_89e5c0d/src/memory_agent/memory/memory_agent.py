"""Two-phase predictive memory with GA-style per-phase conversation history.

P1 and P2 retain separate public/tool transcripts across wakes. Signed provider
thinking blocks are retained as opaque provider-only state and never in audit
text; each phase still receives its own existing system prompt.
"""

import json
import logging
import re
from dataclasses import dataclass

from .universal_memory import UniversalMemory, MemoryEntry
from .ga_context_history import prepare_history, GAHistoryIntegrityError

logger = logging.getLogger(__name__)


# =============================================================================
# Tool Definitions — Phase 1 only (bank management)
# =============================================================================

BANK_TOOLS = [{
    "type": "function",
    "function": {
        "name": "memory_add",
        "description": "Save information expected to be useful within the next 10 turns.",
        "parameters": {"type": "object", "properties": {
            "content": {"type": "string", "description": "Information to save."}
        }, "required": ["content"]},
    },
}]

# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class MemoryOperation:
    """Record of a memory operation performed."""
    action: str
    memory_id: str | None = None
    content: str | None = None
    success: bool = True
    error: str | None = None


@dataclass
class MemoryAgentResult:
    """Result from a Memory Agent processing step."""
    operations: list[MemoryOperation]
    should_inject: bool
    context_for_action: str | None = None
    raw_response_phase1: str | None = None
    raw_response_phase2: str | None = None
    reasoning_phase1: str | None = None
    reasoning_phase2: str | None = None
    user_prompt_phase1: str | None = None
    user_prompt_phase2: str | None = None


# =============================================================================
# System Prompts — with_strategy variant
# =============================================================================

PHASE1_SYSTEM = """You organize information from the task execution.

Based on the task description, the task agent's recent trajectory, and the information already saved, organize and save information expected to be useful within the next 10 turns."""

PHASE2_SYSTEM = '''You are a Selective Attention module for an Action Agent working on a task.

Your role is like selective attention — review the agent's current work and provide relevant information from memory when a reminder is needed. When things are fine, the agent doesn't need help.

## PROCESS:
1. Review the memory bank contents
2. Review the agent's recent trajectory (what it's doing now)
3. DECIDE: Is it necessary to remind the agent of information from the memory bank right now?

## WHEN TO INTERVENE (output <context_for_action>):
- Relevant information from the memory bank is needed for the agent's current work
- For example, the agent appears to overlook a requirement, repeat a failure, or act inconsistently with saved information

## WHEN NOT TO INTERVENE (output <no_intervention/>):
- No information from the memory bank needs to be brought to the agent's attention now
- The information is already visible in the recent trajectory and the agent's actions indicate that it has taken it into account
- The reminder would not help the agent's current work

## OUTPUT FORMAT:
If intervention needed, write:
<context_for_action>
Your synthesized context note here. Include relevant information needed for the current work. You can:
- Highlight relevant information that appears to have been overlooked
- Connect information in memory with the agent's current behavior
Write as helpful observations, not commands.
</context_for_action>

If no intervention needed, write:
<no_intervention/>

## GUIDELINES:
- Your DEFAULT is <no_intervention/> — intervene only when a reminder is needed now
- When you do intervene, be thoughtful: synthesize, don't just dump memory entries
- Frame as observations: "The task requires X" not "You MUST do X"
- Don't repeat information already visible in the recent trajectory when the agent's actions indicate it has taken it into account
- Be calibrated: don't present uncertain information as certain
- You CAN connect dots and highlight patterns — not limited to verbatim copies from bank
- The action agent is a strong model — help it with relevant information, don't try to control it
'''


# =============================================================================
# Memory Agent
# =============================================================================

class MemoryAgent:
    """Maintain separate GA-style P1 and P2 histories across task wakes."""

    def __init__(
        self,
        llm=None,
        memory: UniversalMemory | None = None,
        max_memory_in_prompt: int = 50,
        use_bm25_prefilter: bool = True,
        keep_thinking: bool = False,
        use_structured_tools: bool = True,
    ):
        self.llm = llm
        self.memory = memory if memory is not None else UniversalMemory()
        self.max_memory_in_prompt = max_memory_in_prompt
        self.use_bm25_prefilter = use_bm25_prefilter
        self.keep_thinking = keep_thinking
        self.use_structured_tools = use_structured_tools
        # Separate GA-style conversations preserve each phase's role.
        self._phase1_history = []
        self._phase2_history = []
        self._last_phase1_records = []

    def reset_conversation_history(self):
        self._phase1_history.clear()
        self._phase2_history.clear()
        self._last_phase1_records.clear()

    # -----------------------------------------------------------------
    # LLM calls (overridable for training)
    # -----------------------------------------------------------------

    async def _call_llm_phase1(self, user_prompt: str):
        """Phase 1: bank management with tools."""
        prior = prepare_history(self._phase1_history, user_prompt)
        kwargs = dict(prompt=user_prompt, system=PHASE1_SYSTEM, message_history=prior)
        if self.use_structured_tools:
            kwargs["tools"] = BANK_TOOLS
        return await self.llm.call(**kwargs)

    async def _call_llm_phase2(self, user_prompt: str):
        """Phase 2: context decision, text only (no tools)."""
        prior = prepare_history(self._phase2_history, user_prompt)
        response = await self.llm.call(
            prompt=user_prompt, system=PHASE2_SYSTEM, message_history=prior,
        )
        assistant = {"role": "assistant", "content": [
            {"type": "text", "text": getattr(response, "content", None) or ""}]}
        if getattr(response, "thinking_blocks", None):
            assistant["_provider_thinking_blocks"] = response.thinking_blocks
        self._phase2_history.append(assistant)
        return response

    # -----------------------------------------------------------------
    # Memory formatting
    # -----------------------------------------------------------------

    def _format_memory_list(self, entries: list[MemoryEntry]) -> str:
        if not entries:
            return "(empty)"
        return "\n".join([f"[{e.id}] {e.content}" for e in entries])

    def _format_memory_bank(self, observation: str = "") -> str:
        # One flat bank; legacy storage field remains internal only.
        entries = self.memory.knowledge + self.memory.procedural
        return "<memory_bank>\n" + self._format_memory_list(entries) + "\n</memory_bank>"

    def _build_phase1_prompt(self, observation: str, step_count: int) -> str:
        return f"""## Task description and recent trajectory
{observation}

## Saved information
{self._format_memory_bank(observation)}

Organize and save information expected to be useful within the next 10 turns.
"""

    def _build_phase2_prompt(self, observation: str, step_count: int) -> str:
        """Build Phase 2 prompt with UPDATED memory bank (after Phase 1 ops)."""
        memory_content = self._format_memory_bank(observation)
        return f"""## Step {step_count}

## Memory Bank (just updated)
{memory_content}

## Context (Task Description + Recent Trajectory)
{observation}

## Your Task
Review the memory bank and the agent's recent trajectory. Decide whether it is necessary to remind the agent of information from the memory bank right now.

If yes, write a <context_for_action> note with the relevant context.
If no, write <no_intervention/>.
"""

    # -----------------------------------------------------------------
    # Main entry point
    # -----------------------------------------------------------------

    async def process(
        self,
        observation: str,
        step_count: int = 0,
    ) -> MemoryAgentResult:
        """Process observation through two-phase multi-turn conversation.

        Phase 1: Bank management (tool calls)
        Phase 2: Context decision (text generation with updated memory bank)

        Args:
            observation: Memory agent context (task description + sliding window).
            step_count: Current step number.

        Returns:
            MemoryAgentResult with operations, injection decision, and metadata.
        """
        # Phase 1: Bank management
        phase1_prompt = self._build_phase1_prompt(observation, step_count)
        operations = []
        raw1 = None

        reasoning1 = None
        try:
            response1 = await self._call_llm_phase1(phase1_prompt)
            raw1 = getattr(response1, 'content', None)
            reasoning1 = getattr(response1, 'reasoning_content', None)
            native_calls = getattr(response1, 'tool_calls', None) or []
            # Check the entire batch before any write, so malformed calls cannot
            # leave a partially mutated bank without corresponding history.
            seen_ids = set()
            for call in native_calls:
                try:
                    name, args = self._extract_tool_call(call)
                    call_id = call.get('id') if isinstance(call, dict) else getattr(call, 'id', None)
                    if (not name or not isinstance(args, dict) or not isinstance(call_id, str)
                            or not call_id or call_id in seen_ids):
                        raise ValueError("invalid tool call or missing/duplicate ID")
                    seen_ids.add(call_id)
                except Exception as exc:
                    raise GAHistoryIntegrityError("invalid phase-one tool-call history") from exc
            if (native_calls and '<tool_call>' in (getattr(response1, 'content', None) or '')
                    and any(not self._extract_tool_call(call)[1].get('content') for call in native_calls)):
                raise GAHistoryIntegrityError("ambiguous structured and text tool calls")
            if native_calls and reasoning1 and not getattr(response1, 'thinking_blocks', None):
                raise GAHistoryIntegrityError("signed thinking blocks unavailable for tool continuation")
            operations = self._execute_tool_calls(response1)
            self._record_phase1_response(response1)
        except GAHistoryIntegrityError:
            raise
        except Exception as e:
            logger.error(f"Phase 1 error: {e}", exc_info=True)

        logger.info(
            f"Phase 1: {len(operations)} ops, "
            f"bank={len(self.memory.knowledge)}K/{len(self.memory.procedural)}P"
        )

        # Phase 2: Context decision (with updated memory bank)
        phase2_prompt = self._build_phase2_prompt(observation, step_count)
        should_inject = False
        context_for_action = None
        raw2 = None
        reasoning2 = None

        try:
            response2 = await self._call_llm_phase2(phase2_prompt)
            raw2 = getattr(response2, 'content', None) or ""
            reasoning2 = getattr(response2, 'reasoning_content', None)
            context_for_action = self._parse_phase2_response(raw2)
            should_inject = context_for_action is not None
        except GAHistoryIntegrityError:
            raise
        except Exception as e:
            logger.error(f"Phase 2 error: {e}", exc_info=True)

        logger.info(f"Phase 2: {'INJECT' if should_inject else 'NO-OP'}")

        return MemoryAgentResult(
            operations=operations,
            should_inject=should_inject,
            context_for_action=context_for_action,
            raw_response_phase1=raw1,
            raw_response_phase2=raw2,
            # Provider-only reasoning is never written to trajectory artifacts.
            reasoning_phase1=None,
            reasoning_phase2=None,
            user_prompt_phase1=phase1_prompt,
            user_prompt_phase2=phase2_prompt,
        )

    # -----------------------------------------------------------------
    # Tool execution (Phase 1)
    # -----------------------------------------------------------------

    def _parse_tool_calls_from_text(self, text: str) -> list[tuple[str, dict]]:
        """Fallback: parse tool calls from raw XML text when structured tool_calls are empty.

        Handles the XML format output by SFT-trained models:
            <tool_call>
            <function=memory_save_knowledge>
            <parameter=content>...</parameter>
            </function>
            </tool_call>
        """
        parsed = []
        for block in re.finditer(r"<tool_call>(.*?)</tool_call>", text, re.DOTALL):
            block_text = block.group(1)
            # Extract function name: <function=memory_xxx> or {"function=memory_xxx>
            func_match = re.search(r'[<{]"?function=(\w+)', block_text)
            if not func_match:
                continue
            name = func_match.group(1)

            # Extract parameters
            args = {}
            for param in re.finditer(
                r"<parameter=(\w+)>(.*?)(?:</parameter>|$)", block_text, re.DOTALL
            ):
                args[param.group(1)] = param.group(2).strip()

            # Fallback: if no <parameter=content> found, extract text between
            # <function=name>\n and </parameter> or </function>
            if not args.get("content") and name != "delete":
                func_end = func_match.end()
                remaining = block_text[func_end:].lstrip(">\n")
                # Strip closing tags
                remaining = re.sub(r"</parameter>\s*</function>.*", "", remaining, flags=re.DOTALL)
                remaining = re.sub(r"</function>.*", "", remaining, flags=re.DOTALL)
                remaining = remaining.strip()
                if remaining:
                    # Unwrap JSON format: {"content": "..."} or {"content": "...", "memory_id": "..."}
                    if remaining.startswith("{") and '"content"' in remaining[:20]:
                        try:
                            parsed_json = json.loads(remaining)
                            args.update(parsed_json)
                        except json.JSONDecodeError:
                            args["content"] = remaining
                    else:
                        args["content"] = remaining

            parsed.append((name, args))
        return parsed

    def _record_phase1_response(self, response) -> None:
        """Store actual public response and operation receipts; never replay calls."""
        content = getattr(response, "content", None) or ""
        blocks = [{"type": "text", "text": content}] if content else []
        records = self._last_phase1_records
        native = bool(records) and all(record['id'] for record in records)
        if native:
            blocks.extend({"type": "tool_use", "id": record['id'],
                           "name": record['name'], "input": record['args']}
                          for record in records)
        elif records:
            # Some text-only/fake transports have no native call IDs. Preserve
            # the actual operations as labeled text, not fabricated tool calls.
            blocks.append({"type": "text", "text": "[Executed memory calls] " +
                           json.dumps([{k: v for k, v in r.items() if k != 'id'}
                                       for r in records], ensure_ascii=False)})
        assistant = {"role": "assistant", "content": blocks}
        if getattr(response, "thinking_blocks", None):
            assistant["_provider_thinking_blocks"] = response.thinking_blocks
        self._phase1_history.append(assistant)
        if native:
            self._phase1_history.append({"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": record['id'],
                 "content": json.dumps(record['receipt'], ensure_ascii=False)}
                for record in records]})

    def _execute_tool_calls(self, response) -> list[MemoryOperation]:
        """Execute bank management tool calls from Phase 1 response."""
        operations = []
        self._last_phase1_records = []
        tool_calls = getattr(response, "tool_calls", None) or []

        # Fallback: if no structured tool_calls, or if structured calls have empty content
        has_empty_content = any(
            not (self._extract_tool_call(tc)[1].get("content"))
            for tc in tool_calls
        ) if tool_calls else False

        if not tool_calls or has_empty_content:
            raw = getattr(response, "content", None) or ""
            raw = self._strip_thinking(raw)
            if "<tool_call>" in raw:
                # Use fallback parser instead of broken structured calls
                tool_calls = []
                parsed = self._parse_tool_calls_from_text(raw)
                if parsed:
                    logger.debug(f"Parsed {len(parsed)} tool calls from raw text (fallback)")
                    for name, args in parsed:
                        tool_calls.append(type("TC", (), {
                            "function": type("F", (), {"name": name, "arguments": args})()
                        })())

        for tool_call in tool_calls:
            name, args = self._extract_tool_call(tool_call)
            if not name:
                continue

            try:
                if name == "memory_add":
                    content = args.get("content", "")
                    if not isinstance(content, str) or not content.strip():
                        raise ValueError("memory content must be nonempty text")
                    mem_id = self.memory.save_knowledge(content)
                    operations.append(MemoryOperation(action="add", memory_id=mem_id, content=content))
                else:
                    operations.append(MemoryOperation(action=name, success=False, error="unsupported tool"))

            except Exception as e:
                logger.warning(f"Failed to execute {name}: {e}")
                operations.append(MemoryOperation(action=name, success=False, error=str(e)))

            op = operations[-1]
            self._last_phase1_records.append({
                'id': (tool_call.get('id') if isinstance(tool_call, dict)
                       else getattr(tool_call, 'id', None)), 'name': name, 'args': args,
                'receipt': {'action': op.action, 'success': op.success,
                            'memory_id': op.memory_id, 'error': op.error}})

        return operations

    # -----------------------------------------------------------------
    # Phase 2 response parsing
    # -----------------------------------------------------------------

    def _strip_thinking(self, text: str) -> str:
        """Strip <think>...</think> blocks from text unless keep_thinking is True."""
        if self.keep_thinking:
            return text
        return re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL).strip()

    def _parse_phase2_response(self, raw: str) -> str | None:
        """Parse Phase 2 text response.

        Returns context_for_action string if intervention, None if no-op.
        """
        # Strip thinking tokens if present in raw content
        raw = self._strip_thinking(raw)
        match = re.search(
            r"<context_for_action>(.*?)</context_for_action>",
            raw,
            re.DOTALL,
        )
        if match:
            context = match.group(1).strip()
            if context:
                return context

        if "<no_intervention" in raw:
            return None

        # Fallback: no XML tags found → default no-op
        logger.warning("Phase 2: No XML tags found, defaulting to no intervention")
        return None

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------

    def _extract_tool_call(self, tool_call) -> tuple[str | None, dict]:
        """Extract name and args from a tool call object."""
        if isinstance(tool_call, dict):
            function = tool_call.get("function") or tool_call
            name = function.get("name")
            args = function.get("arguments", function.get("args", {}))
        elif hasattr(tool_call, "function"):
            name = tool_call.function.name
            args = tool_call.function.arguments
        else:
            name = getattr(tool_call, "name", None)
            args = getattr(tool_call, "args", {}) or getattr(tool_call, "arguments", {})
        if isinstance(args, str):
            args = json.loads(args)
        return name, args

    def get_tools_schema(self) -> list[dict]:
        """Get the bank management tool schema."""
        return BANK_TOOLS
