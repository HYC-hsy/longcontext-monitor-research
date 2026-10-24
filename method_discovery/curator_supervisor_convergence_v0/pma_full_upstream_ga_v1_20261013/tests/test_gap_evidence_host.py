"""Actual pinned host objects with fake auxiliary responses, never Task inference."""
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
from evidence_gap_context import event_identity, prepare_context
from evidence_gap_store import EvidenceGapMemory


def event(kind, number, **fields):
    return dict(kind=kind, sequence=number, event_id=f"event-{number}",
                run_id="evidence-test", task_id="synthetic", **fields)


class EvidenceHostTests(unittest.TestCase):
    def test_real_host_two_cycles_delivery_and_final_bank(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            wrapper = construct_upstream(root / "upstream", research_candidate="pma_gap_evidence_v1")
            bank, phases, requests = wrapper._memory, [], []
            self.assertIsInstance(bank, EvidenceGapMemory)
            self.assertIs(bank, wrapper._memory_agent.memory)
            self.assertIs(bank, wrapper._memory_agent.gaps)
            self.assertFalse(hasattr(bank, "register_source"))

            async def fake(**kwargs):
                agent = wrapper._memory_agent
                phases.append(agent.transport_phase)
                requests.append(kwargs)
                if agent.transport_phase == "selection":
                    return LLMResponse(content=("<context_for_action>Verify output.</context_for_action>"
                        if len(phases) == 2 else "<no_intervention/>"))
                catalog = agent._parts.catalog
                role = "task_instruction" if len(phases) == 1 else "tool_observation"
                source = next(row for row in catalog.values() if row.snapshot.record.role == role)
                name = "memory_save_gap" if len(phases) == 1 else "memory_save_knowledge"
                body = "Verify output" if len(phases) == 1 else "The tool reported result ready."
                args = {"content": body, "evidence": [{"source": source.snapshot.record.handle,
                        "quote": source.snapshot.blob.text}]}
                call = NS(function=NS(name=name, arguments=json.dumps(args)))
                return LLMResponse(content="", tool_calls=[call])

            wrapper._memory_llm.call = fake
            episode = PMAEpisode(wrapper, run_id="evidence-test", task_id="synthetic", archive=root / "archive")
            async def run():
                await episode.handle(event("task_start", 1, initial_user_content="Original task"))
                reminder = await episode.handle(event("before_actor_call", 2, actor_attempt=1))
                self.assertIn("Verify output.", reminder["reminder"])
                observation = json.dumps({"content": "checked", "tool_results": [
                    {"tool_use_id": "real-tool-id", "content": "result ready"}]})
                await episode.handle(event("actor_step", 3, actor_attempt=1, step_status="normal",
                    response="checked", analysis="PRIVATE NOT A PUBLIC SOURCE", plan="PRIVATE NOT A PUBLIC SOURCE", commands=["check()"],
                    observation=observation))
                silent = await episode.handle(event("before_actor_call", 4, actor_attempt=2))
                self.assertEqual(silent["status"], "silent")
                await episode.handle(event("actor_step", 5, actor_attempt=2, step_status="completed"))
                return await episode.handle(event("task_end", 6, terminal={"result": "done"}))
            self.assertEqual(asyncio.run(run())["status"], "saved")
            self.assertEqual(phases, ["maintenance", "selection"] * 2)
            self.assertIs(wrapper._memory, bank)
            self.assertEqual(len(bank.entries), 1)
            self.assertEqual(len(bank.knowledge), 1)
            self.assertIn("event_order=3", requests[2]["prompt"])
            self.assertIn("field=observation/tool_results/0/content", requests[2]["prompt"])
            self.assertTrue(all("PRIVATE NOT" not in request["prompt"] for request in requests))
            saved = json.loads((root / "archive/memory.json").read_text())
            loaded = EvidenceGapMemory.from_dict(saved)
            self.assertEqual(len(loaded.entries), 1)
            tool_sources = [s for s in loaded.sources.values() if s.role == "tool_observation"]
            self.assertEqual(tool_sources[0].tool_call_id, "real-tool-id")
            cycles = [json.loads(line) for line in (root / "archive/gap_cycle.jsonl").read_text().splitlines()]
            self.assertEqual(len(cycles), 2)
            self.assertTrue(all(row["evidence_report"]["accepted"] for row in cycles))
            self.assertTrue(all("provenance" not in row for row in cycles))

    def test_unknown_observation_does_not_stop_task(self):
        with TemporaryDirectory() as tmp:
            wrapper = construct_upstream(Path(tmp)/"upstream", research_candidate="pma_gap_evidence_v1")
            phases = []
            async def fake(**kwargs):
                phases.append(wrapper._memory_agent.transport_phase)
                return LLMResponse(content="<no_intervention/>")
            wrapper._memory_llm.call = fake
            ep = PMAEpisode(wrapper, run_id="evidence-test", task_id="synthetic", archive=Path(tmp)/"archive")
            async def run():
                await ep.handle(event("task_start", 1, initial_user_content="Task"))
                await ep.handle(event("before_actor_call", 2, actor_attempt=1))
                return await ep.handle(event("actor_step", 3, actor_attempt=1, step_status="normal",
                    response="public", commands=[], observation="not a valid envelope"))
            self.assertEqual(asyncio.run(run())["status"], "observed")
            self.assertEqual(phases, ["maintenance", "selection"] * 2)
            self.assertTrue(wrapper._memory_agent.last_evidence_report["errors"])

    def test_projector_window_one_commands_and_no_hidden_fields(self):
        captured = []
        task_identity = event_identity(event("task_start", 1, initial_user_content="task"))
        def step(n):
            return {"step": n, "analysis": f"report {n}", "plan": None,
                    "commands": [f"command-{i}" for i in range(7)],
                    "observation": json.dumps({"content": f"report {n}", "tool_results": []}),
                    "_evidence_identity": event_identity(event("actor_step", n, response=f"report {n}"))}
        agent = NS(prepare_visible_context=lambda raw, blocks: captured.append((raw, blocks)))
        wrapper = NS(_memory_agent=agent, _get_memory_agent_context=lambda: "raw query",
            _task_description="task", _evidence_task_identity=task_identity,
            _sliding_window_size=1, _accumulated_observations=[{}, step(2), step(3)])
        prepare_context(wrapper)
        raw, blocks = captured[0]
        self.assertEqual(raw, "raw query")
        self.assertEqual({b["source_id"] for b in blocks}, {"event-1", "event-3"})
        self.assertEqual(len([b for b in blocks if b["role"] == "tool_command"]), 5)
        self.assertFalse(any("command-5" in b["text"] for b in blocks))
        a = event_identity(event("actor_step", 8, response="visible", analysis="secret 1"))
        b = event_identity(event("actor_step", 8, response="visible", analysis="secret 2"))
        self.assertEqual(a, b)

    def test_baseline_keeps_original_classes_and_schemas(self):
        with TemporaryDirectory() as tmp:
            from gap_memory_agent import GapMemoryAgent
            from gap_store import GapMemory
            wrapper = construct_upstream(Path(tmp), research_candidate="pma_gap_memory_v0")
            self.assertIs(type(wrapper._memory), GapMemory)
            self.assertIs(type(wrapper._memory_agent), GapMemoryAgent)
            self.assertFalse(hasattr(wrapper._memory, "register_source"))
            for tool in wrapper._memory_agent.get_tools_schema():
                self.assertNotIn("evidence", tool["function"]["parameters"]["properties"])


if __name__ == "__main__":
    unittest.main()
