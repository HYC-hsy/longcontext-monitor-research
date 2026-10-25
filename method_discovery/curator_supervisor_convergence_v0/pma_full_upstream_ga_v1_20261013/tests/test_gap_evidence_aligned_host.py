"""Pinned real host with fake responses: no provider or task-actor inference."""
import asyncio
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest

os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
from harbor.llms.base import LLMResponse
from episode import PMAEpisode, construct_upstream
from latest_evidence_gap_agent import LatestEvidenceGapMemoryAgent as AlignedEvidenceGapMemoryAgent
from latest_evidence_gap_store import LatestEvidenceGapMemory as AlignedEvidenceGapMemory
from gap_memory_agent import GapMemoryAgent
from gap_store import GapMemory
from memory_agent.memory.memory_agent import MemoryAgent
from memory_agent.memory.universal_memory import UniversalMemory
from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.single_run_certification import (
    EVIDENCE_GAP_SOURCE_FILES, require_bound_gap_memory,
)


class AlignedEvidenceHostTests(unittest.TestCase):
    def test_existing_candidate_two_phases_and_unbound_claim_reaches_selection(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            host = construct_upstream(root / "upstream", research_candidate="pma_gap_evidence_v1")
            bank, agent, calls = host._memory, host._memory_agent, []
            self.assertIs(type(bank), AlignedEvidenceGapMemory)
            self.assertIs(type(agent), AlignedEvidenceGapMemoryAgent)
            self.assertIs(bank, agent.memory)
            self.assertIs(bank, agent.gaps)
            self.assertEqual({t["function"]["name"] for t in agent.get_tools_schema()}, {
                "memory_save_knowledge", "memory_save_procedural", "memory_update_status",
                "memory_save_gap", "memory_delete"})

            async def fake(**kwargs):
                calls.append((agent.transport_phase, kwargs))
                if agent.transport_phase == "maintenance":
                    args = {"content": "Investigate the missing check.",
                            "evidence": [{"quote": "not present in the observation"}]}
                    return LLMResponse(content="", tool_calls=[NS(function=NS(
                        name="memory_save_gap", arguments=json.dumps(args)))])
                return LLMResponse(content="<no_intervention/>")

            host._memory_llm.call = fake
            episode = PMAEpisode(host, run_id="aligned-test", task_id="synthetic",
                                 archive=root / "archive")
            def event(kind, sequence, **kwargs):
                return dict(kind=kind, sequence=sequence, event_id=f"event-{sequence}",
                            run_id="aligned-test", task_id="synthetic", **kwargs)
            async def run():
                await episode.handle(event("task_start", 1, initial_user_content="Original task"))
                return await episode.handle(event("task_end", 2, terminal={"result": "done"}))
            self.assertEqual(asyncio.run(run())["status"], "saved")
            self.assertEqual([phase for phase, _ in calls], ["maintenance", "selection"])
            self.assertIn("Investigate the missing check.", calls[1][1]["prompt"])
            self.assertIn("binding_status=unbound", calls[1][1]["prompt"])
            self.assertIs(host._memory, bank)
            self.assertEqual(len(bank.entries), 1)
            self.assertEqual(bank.binding(bank.entries[0].id).disposition, "unbound")
            self.assertEqual(len(bank.receipts), 0)
            self.assertEqual(host._llm.calls, 0)
            cycle = json.loads((root / "archive/gap_cycle.jsonl").read_text().splitlines()[0])
            self.assertEqual(cycle["alignment_policy"], agent.expected_alignment_policy)
            saved = json.loads((root / "archive/memory.json").read_text())
            loaded = AlignedEvidenceGapMemory.from_dict(saved)
            self.assertEqual(loaded.entries[0].content, bank.entries[0].content)

    def test_latest_revision_survives_binding_error_and_next_cycle(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            host = construct_upstream(root / "upstream", research_candidate="pma_gap_evidence_v1")
            bank, agent, calls = host._memory, host._memory_agent, []
            key = None
            maintenance_count = 0

            async def fake(**kwargs):
                nonlocal key, maintenance_count
                calls.append((agent.transport_phase, kwargs))
                if agent.transport_phase == "selection":
                    return LLMResponse(content="<no_intervention/>")
                maintenance_count += 1
                if maintenance_count == 1:
                    args = {"content": "Old gap", "evidence": [{"quote": "Original task"}]}
                elif maintenance_count == 2:
                    key = bank.entries[0].id
                    args = {"content": "Latest gap despite malformed evidence", "memory_id": key,
                            "evidence": "not an evidence array"}
                else:
                    self.assertIn("Latest gap despite malformed evidence", kwargs["prompt"])
                    self.assertNotIn("PENDING UNBOUND replacement", kwargs["prompt"])
                    return LLMResponse(content="")
                return LLMResponse(content="", tool_calls=[NS(function=NS(
                    name="memory_save_gap", arguments=json.dumps(args)))])

            host._memory_llm.call = fake
            ep = PMAEpisode(host, run_id="latest-host", task_id="synthetic", archive=root / "archive")
            def event(kind, n, **kwargs):
                return dict(kind=kind, sequence=n, event_id=f"latest-{n}",
                            run_id="latest-host", task_id="synthetic", **kwargs)
            async def run():
                await ep.handle(event("task_start", 1, initial_user_content="Original task"))
                for attempt, sequence in [(1, 2), (2, 4)]:
                    await ep.handle(event("before_actor_call", sequence, actor_attempt=attempt))
                    await ep.handle(event("actor_step", sequence + 1, actor_attempt=attempt,
                        step_status="normal", response="public observation", commands=[],
                        observation=json.dumps({"content": "public observation", "tool_results": []})))
                await ep.handle(event("task_end", 6, terminal={"result": "done"}))
            asyncio.run(run())
            self.assertEqual([phase for phase, _ in calls], ["maintenance", "selection"] * 3)
            self.assertEqual(bank.entries[0].id, key)
            self.assertEqual(bank.entries[0].content, "Latest gap despite malformed evidence")
            self.assertEqual(bank.binding(key).status, "error")
            self.assertFalse(bank.pending_proposals)
            self.assertIn("binding_status=error", calls[3][1]["prompt"])
            self.assertIn("Latest gap despite malformed evidence", calls[3][1]["prompt"])
            cycles = [json.loads(line) for line in (root / "archive/gap_cycle.jsonl").read_text().splitlines()]
            self.assertEqual(cycles[1]["evidence_report"]["binding_errors"], 1)
            self.assertEqual(cycles[1]["evidence_report"]["content_writes_committed"], 1)
            saved = json.loads((root / "archive/memory.json").read_text())
            self.assertEqual(json.loads(json.dumps(AlignedEvidenceGapMemory.from_dict(saved).to_dict())), saved)
            self.assertEqual(host._llm.calls, 0)

    def test_old_bank_readability_and_new_source_hash_coverage(self):
        stage = Path(__file__).resolve().parents[1]
        require_bound_gap_memory(stage / "cert_evidence_gap_v1_final_20261025/B/memory.json")
        expected = {"aligned_evidence_gap_agent.py", "aligned_evidence_gap_store.py",
                    "gap_evidence_alignment.py", "evidence_requirements.txt",
                    "vendor/langextract_3a68580/__init__.py",
                    "vendor/langextract_3a68580/alignment.py",
                    "vendor/langextract_3a68580/tokenizer.py",
                    "vendor/langextract_3a68580/requirements.txt"}
        self.assertTrue(all(any(path.endswith("/" + name) for path in EVIDENCE_GAP_SOURCE_FILES)
                            for name in expected))
        # This checks historical readability, not certification of changed code.

    def test_ordinary_upstream_and_gap_classes_remain_exact(self):
        for candidate, memory_type, agent_type in [
            ("U", UniversalMemory, MemoryAgent),
            ("pma_gap_memory_v0", GapMemory, GapMemoryAgent),
        ]:
            with self.subTest(candidate=candidate), TemporaryDirectory() as temporary:
                host = construct_upstream(Path(temporary), research_candidate=candidate)
                self.assertIs(type(host._memory), memory_type)
                self.assertIs(type(host._memory_agent), agent_type)
                self.assertFalse(hasattr(host._memory_agent, "expected_alignment_policy"))


if __name__ == "__main__":
    unittest.main()
