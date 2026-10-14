"""Generate full, fake-transport PMA request examples for independent audit."""
import asyncio
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
VENDOR = HERE / "vendor" / "pma_89e5c0d"
sys.path[:0] = [str(VENDOR / "src"), str(VENDOR / "external" / "harbor" / "src")]
from harbor.llms.base import LLMResponse
from episode import construct_upstream


class Fake:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    async def __call__(self, *, prompt, system, tools=None):
        self.requests.append({"system": system, "prompt": prompt, "tools": tools})
        if not self.responses:
            raise AssertionError("unexpected request; no network fallback")
        return self.responses.pop(0)


async def produce(output: Path):
    output.mkdir(parents=True, exist_ok=False)
    with TemporaryDirectory() as temp:
        u = construct_upstream(Path(temp) / "u", research_candidate="U")
        uf = Fake([LLMResponse(content="", tool_calls=[]),
                   LLMResponse(content="<no_intervention/>")])
        u._memory_llm.call = uf
        await u._memory_agent.process("Public task: preserve the audit trail", step_count=1)
        r = construct_upstream(Path(temp) / "r", research_candidate="R")
        bank = r.memory
        bank.register_source("public-task", "task_instruction", "Preserve the AUDIT-TRACE evidence.", 1)
        ref = [{"event_id": "public-task", "role": "task_instruction", "quote": "AUDIT-TRACE"}]
        memory_id = bank.save_sourced("knowledge", "Audit trace is preserved", "task_requirement", ref)
        reconcile = SimpleNamespace(function=SimpleNamespace(name="memory_reconcile", arguments={
            "memory_id": memory_id, "decision": "unresolved", "reason": "Current trace was not checked",
            "evidence_refs": ref}))
        rf = Fake([LLMResponse(content="", tool_calls=[reconcile]),
                   LLMResponse(content="<no_intervention/>"),
                   LLMResponse(content="", tool_calls=[]),
                   LLMResponse(content="<no_intervention/>")])
        r._memory_llm.call = rf
        await r._memory_agent.process("Public observation: trace status unknown", step_count=2)
        await r._memory_agent.process("Later public observation", step_count=3)
        assert "AUDIT-TRACE" in rf.requests[1]["prompt"]
        assert '"decision": "unresolved"' in rf.requests[1]["prompt"]
        assert '"decision": "unresolved"' in rf.requests[2]["prompt"]
        samples = {"U_original_phase1": uf.requests[0],
                   "R_unresolved_phase2": rf.requests[1],
                   "R_unresolved_future_phase1": rf.requests[2]}
        (output / "REQUEST_SAMPLES.json").write_text(
            json.dumps(samples, ensure_ascii=False, indent=2), encoding="utf-8")
        return samples


if __name__ == "__main__":
    samples = asyncio.run(produce(Path(sys.argv[1])))
    print(json.dumps({"actual_fake_requests": 6, "samples": list(samples),
                      "real_provider_attempts": 0}, sort_keys=True))
