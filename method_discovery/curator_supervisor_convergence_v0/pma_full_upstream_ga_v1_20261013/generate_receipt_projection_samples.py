"""Generate offline S2/R2 prompt versus raw-archive examples; no provider transport."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from harbor.llms.base import LLMResponse
from episode import construct_upstream
from test_source_candidate_v2 import Script, call


def generate(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=False)
    for variant in ("S2", "R2"):
        with TemporaryDirectory() as directory:
            agent = construct_upstream(Path(directory) / "upstream", research_candidate=variant)
            bank = agent.memory
            handle = bank.register_leaf("old", "task_instruction", "BOUND_SOURCE_SNIPPET", 1,
                                        "initial_user_content", "1" * 64)
            old_id = bank.save_sourced("knowledge", "ARCHIVED_ONLY_OLD_CLAIM_6C81",
                                       "task_requirement", [{"source_handle": handle,
                                                              "start_line": 1, "end_line": 1}])
            for number in range(2, 12):
                bank.register_leaf(f"recent-{number}", "agent_report", f"recent {number}",
                                   number, "response", "2" * 64)
            bank.current_source_ids = ["recent-11:response"]
            if variant == "S2":
                operation = call("memory_delete", memory_id=old_id)
            else:
                operation = call("memory_reconcile", memory_id=old_id, decision="revise",
                                 reason="new current report", evidence_refs=[{
                                     "source_handle": bank.sources["recent-11:response"]["handle"],
                                     "start_line": 1, "end_line": 1}],
                                 content="new active claim", statement_type="agent_report",
                                 source_refs=[{"source_handle": bank.sources[
                                     "recent-11:response"]["handle"],
                                     "start_line": 1, "end_line": 1}],
                                 inherit_source_ref_indices=[0])
            fake = Script([LLMResponse(content="", tool_calls=[operation]),
                           LLMResponse(content="<no_intervention/>"),
                           LLMResponse(content="", tool_calls=[]),
                           LLMResponse(content="<no_intervention/>")])
            agent._memory_llm.call = fake
            asyncio.run(agent._memory_agent.process("current report", 12))
            raw_transaction = agent._memory_agent.last_transaction
            asyncio.run(agent._memory_agent.process("next current report", 13))
            for index, request in enumerate(fake.requests, 1):
                (output / f"{variant}_request_{index}.txt").write_text(
                    request["prompt"], encoding="utf-8")
            (output / f"{variant}_raw_transaction.json").write_text(
                json.dumps(raw_transaction, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    generate(parser.parse_args().output)
