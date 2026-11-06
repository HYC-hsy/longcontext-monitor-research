"""Synthetic signed-history audit must not persist provider-private blocks."""

import asyncio
import json
from types import SimpleNamespace

from worker_main import install_transport_audit


def test_signed_history_forwarded_but_not_written(tmp_path):
    received = []

    async def call(**kwargs):
        received.append(kwargs)
        return SimpleNamespace(content="<no_intervention/>")

    agent = SimpleNamespace(
        _memory_llm=SimpleNamespace(call=call),
        _memory_agent=SimpleNamespace(_history_transforms=[{"phase": "P2"}]),
        _research_candidate="pma_predictive_context_v1")
    install_transport_audit(agent, tmp_path)
    history = [{"role": "assistant", "content": "public",
                "thinking_blocks": [{"type": "thinking", "signature": "SYNTHETIC_PRIVATE_SIGNATURE"}]}]
    asyncio.run(agent._memory_llm.call(
        prompt="current", system="system", message_history=history))
    assert received[0]["message_history"] == history
    payload = (tmp_path / "memory_payload.jsonl").read_text(encoding="utf-8")
    assert "SYNTHETIC_PRIVATE_SIGNATURE" not in payload
    row = json.loads(payload)
    assert row["message_history"][0]["thinking_blocks"] == "[provider-private blocks excluded]"
