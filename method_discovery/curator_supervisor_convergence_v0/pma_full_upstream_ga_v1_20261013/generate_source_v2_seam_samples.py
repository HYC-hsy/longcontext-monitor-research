"""Offline-only audit samples from the actual v2 process and host send guard."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from unittest.mock import patch

from harbor.llms.base import LLMResponse
from episode import construct_upstream
from static_source_live import run_authorized
from test_source_candidate_v2 import Script, call
from test_static_source_live_v2 import V2EntryTests


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str),
                    encoding="utf-8")


def generate(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=False)
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        agent = construct_upstream(root / "source", research_candidate="S2")
        fake = Script([
            LLMResponse(content="", tool_calls=[
                call("memory_update_status", content="B"),
                call("memory_update_status", content="B"),
                call("memory_delete", memory_id="absent")]),
            LLMResponse(content="<no_intervention/>"),
        ])
        agent._memory_llm.call = fake
        agent.memory.update_status("A")
        result = asyncio.run(agent._memory_agent.process("public task", 1))
        write(output / "transaction_rollback.json", {
            "phase1_request": fake.requests[0], "phase2_request": fake.requests[1],
            "transaction": agent._memory_agent.last_transaction,
            "operations": [vars(operation) for operation in result.operations],
            "final_status": agent.memory.status,
            "collateral_aborts": agent._memory_agent.collateral_aborts,
        })

        agent = construct_upstream(root / "failure", research_candidate="S2")
        fake = Script([
            LLMResponse(content="", tool_calls=[call("memory_update_status", content="B")]),
            LLMResponse(content="<no_intervention/>"),
        ])
        agent._memory_llm.call = fake
        asyncio.run(agent._memory_agent.process("public task", 1))
        try:
            asyncio.run(agent._memory_agent.process("public task", 2))
        except AssertionError:
            pass
        write(output / "later_phase1_failure.json", {
            "requests": fake.requests,
            "current_transaction": agent._memory_agent.last_transaction,
            "current_receipts": agent._memory_agent.last_receipts,
            "phase2_sent_for_second_process": len(fake.requests) > 3,
        })

        fixture = V2EntryTests()
        host_root = root / "host"
        host_root.mkdir()
        manifest, authorization, profile, run_root = fixture.fixture(host_root)
        attempts = []

        async def failing_call(*, prompt, system, tools=None):
            attempts.append("phase1" if tools is not None else "phase2")
            raise RuntimeError("scripted final transport failure")

        async def forbidden_wire(**_kwargs):
            raise AssertionError("real provider boundary was not intercepted")

        with patch("litellm.acompletion", forbidden_wire):
            rows = asyncio.run(run_authorized(
                manifest, authorization, profile, run_root,
                fake_transport_factory=lambda _variant, _slot: failing_call))
        slot = run_root / rows[0]["run_id"]
        for name in ("requests.jsonl", "responses.jsonl", "blocked_requests.jsonl",
                     "result.json"):
            shutil.copyfile(slot / name, output / ("host_" + name))
        write(output / "host_counts.json", {
            "actual_fake_calls": attempts, "slots_started": len(rows),
            "authorization_removed": not authorization.exists(),
            "next_slot_absent": not (run_root / "new-v2-2").exists(),
            "real_provider_calls": 0,
        })


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    generate(args.output)
