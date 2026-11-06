"""Zero-model checks for the isolated predictive conversation candidate."""

import asyncio
from types import SimpleNamespace

import pytest

from memory_agent.memory.context_predictive_memory_agent import ContextPredictiveMemoryAgent
from memory_agent.memory.ga_context_history import GAHistoryIntegrityError
from memory_agent.memory.predictive_memory_agent import PHASE1_SYSTEM, PHASE2_SYSTEM


class FakeLLM:
    def __init__(self, *, missing_id=False):
        self.calls = []
        self.missing_id = missing_id

    async def call(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("tools"):
            call = SimpleNamespace(
                id=None if self.missing_id else f"call-{len(self.calls)}",
                function=SimpleNamespace(name="memory_add",
                                         arguments={"content": f"memory {len(self.calls)}"}))
            return SimpleNamespace(content="", tool_calls=[call],
                                   reasoning_content=None, thinking_blocks=None)
        return SimpleNamespace(content="<no_intervention/>", tool_calls=[],
                               reasoning_content=None, thinking_blocks=None)


def test_history_independent_receipts_and_reset():
    llm = FakeLLM()
    agent = ContextPredictiveMemoryAgent(llm=llm)
    asyncio.run(agent.process("new window one", 1))
    asyncio.run(agent.process("new window two", 9))
    assert len(llm.calls) == 4
    p1_first, p2_first, p1_second, p2_second = llm.calls
    assert p1_first["system"] == PHASE1_SYSTEM
    assert p2_first["system"] == PHASE2_SYSTEM
    assert p1_first["message_history"] == []
    assert p2_first["message_history"] == []
    p1_history = p1_second["message_history"]
    assert any(m.get("tool_calls") for m in p1_history)
    assert any(m.get("role") == "tool" and m.get("tool_call_id") == "call-1"
               for m in p1_history)
    assert "new window one" in str(p1_history)
    assert "new window two" not in str(p1_history)
    p2_history = p2_second["message_history"]
    assert "new window one" in str(p2_history)
    assert "new window two" not in str(p2_history)
    assert not any(m.get("tool_calls") for m in p2_history)
    assert len(agent.memory.knowledge) == 2
    agent.reset_conversation_history()
    assert agent._phase1_history == agent._phase2_history == []
    assert len(agent.memory.knowledge) == 2  # task reset is separate from the bank


def test_missing_native_id_fails_before_bank_write():
    agent = ContextPredictiveMemoryAgent(llm=FakeLLM(missing_id=True))
    with pytest.raises(GAHistoryIntegrityError):
        asyncio.run(agent.process("task", 1))
    assert not agent.memory.knowledge


def test_installed_litellm_anthropic_transform_keeps_signed_continuation():
    """Exercise the installed Anthropic request translator, without HTTP."""
    from litellm.llms.anthropic.chat.transformation import AnthropicConfig

    messages = [
        {"role": "system", "content": PHASE1_SYSTEM},
        {"role": "user", "content": "previous P1 window"},
        {"role": "assistant", "content": "", "thinking_blocks": [
            {"type": "thinking", "thinking": "synthetic private", "signature": "synthetic-signature"}],
         "tool_calls": [{"id": "tool-1", "type": "function",
                         "function": {"name": "memory_add", "arguments": '{"content":"fact"}'}}]},
        {"role": "tool", "tool_call_id": "tool-1", "content": "saved"},
        {"role": "user", "content": "current P1 window"},
    ]
    data = AnthropicConfig().transform_request(
        model="claude-opus-4-8", messages=messages,
        optional_params={"max_tokens": 1024, "thinking": {"type": "adaptive"}},
        litellm_params={}, headers={})
    assistant = next(row for row in data["messages"] if row["role"] == "assistant")
    assert any(block.get("type") == "thinking" and block.get("signature") == "synthetic-signature"
               for block in assistant["content"])
    assert any(block.get("type") == "tool_use" and block.get("id") == "tool-1"
               for block in assistant["content"])
    assert any(block.get("type") == "tool_result" and block.get("tool_use_id") == "tool-1"
               for row in data["messages"] for block in row["content"])
