"""Zero-model tests for opt-in S/R, using the real pinned upstream process."""
import asyncio
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

HERE = Path(__file__).resolve().parent
VENDOR = HERE / "vendor" / "pma_89e5c0d"
sys.path.insert(0, str(VENDOR / "src"))
sys.path.insert(0, str(VENDOR / "external" / "harbor" / "src"))
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"

from harbor.llms.base import LLMResponse
from episode import PMAEpisode, construct_upstream
from source_memory import SourceMemory


def call(name, **kwargs):
    return SimpleNamespace(function=SimpleNamespace(name=name, arguments=kwargs))


class ScriptedTransport:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.requests = []

    async def __call__(self, *, prompt, system, tools=None):
        self.requests.append({"prompt": prompt, "system": system, "tools": tools})
        if not self.outputs:
            raise AssertionError("unscripted provider request: no real fallback")
        return self.outputs.pop(0)


class SourceCandidateTests(unittest.TestCase):
    def make(self, variant, outputs):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        agent = construct_upstream(Path(temp.name) / "upstream", research_candidate=variant)
        fake = ScriptedTransport(outputs)
        agent._memory_llm.call = fake
        return agent, fake, Path(temp.name)

    def test_default_u_is_original_classes_and_schema(self):
        agent, fake, root = self.make("U", [
            LLMResponse(content="", tool_calls=[]),
            LLMResponse(content="<no_intervention/>")])
        from memory_agent.memory.memory_agent import MemoryAgent, BANK_TOOLS, PHASE1_SYSTEM, PHASE2_SYSTEM
        from memory_agent.memory.universal_memory import UniversalMemory
        self.assertIs(type(agent._memory_agent), MemoryAgent)
        self.assertIs(type(agent.memory), UniversalMemory)
        self.assertEqual(agent._memory_agent.get_tools_schema(), BANK_TOOLS)
        self.assertFalse(hasattr(agent, "_research_candidate"))
        episode = PMAEpisode(agent, run_id="u", task_id="task", archive=root / "archive")
        result = asyncio.run(episode.handle({"event_id": "u1", "sequence": 1,
            "run_id": "u", "task_id": "task", "kind": "task_start",
            "initial_user_content": "Original public request"}))
        self.assertTrue(result["triggered"])
        self.assertEqual([r["system"] for r in fake.requests], [PHASE1_SYSTEM, PHASE2_SYSTEM])
        self.assertEqual(fake.requests[0]["tools"], BANK_TOOLS)
        self.assertFalse((root / "archive" / "candidate_audit.jsonl").exists())

    def test_source_validation_save_reload_and_active_bm25(self):
        bank = SourceMemory()
        bank.register_source("start", "task_instruction", "Retain WAL files.", 1)
        ref = [{"event_id": "start", "role": "task_instruction", "quote": "Retain WAL files."}]
        old = bank.save_sourced("knowledge", "Keep WAL", "task_requirement", ref)
        self.assertEqual(bank.search_knowledge("WAL")[0].id, old)
        with self.assertRaisesRegex(ValueError, "Task report"):
            bank.resolve_refs(ref, "tool_observation")
        with self.assertRaisesRegex(ValueError, "visible"):
            bank.resolve_refs([{"event_id": "future", "role": "tool_observation", "quote": "x"}], "inference")
        bank.register_source("tool", "tool_observation", "WAL now absent", 2)
        new_ref = [{"event_id": "tool", "role": "tool_observation", "quote": "WAL now absent"}]
        evidence = bank.resolve_refs(new_ref, "tool_observation")
        with self.assertRaises(ValueError):
            bank.revise(old, "bad", "tool_observation", [], "reason", evidence)
        self.assertIsNotNone(bank.get(old))
        new = bank.revise(old, "WAL absent", "tool_observation", new_ref, "new observation", evidence)
        self.assertIsNone(bank.get(old))
        self.assertEqual(bank.search_knowledge("WAL")[0].id, new)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "bank.json"
            bank.save_to_file(path)
            loaded = SourceMemory.load_from_file(path)
            self.assertEqual(loaded.metadata[new]["version"], 2)
            self.assertEqual(loaded.search_knowledge("WAL")[0].id, new)
            self.assertEqual(loaded.history[0]["entry"]["id"], old)
            self.assertTrue(loaded.retract(new, "withdraw", evidence))
            self.assertTrue(loaded.retract(new, "repeat", evidence))
            self.assertEqual(loaded.search_knowledge("WAL"), [])
            loaded.save_to_file(path)
            final = SourceMemory.load_from_file(path)
            self.assertEqual(final.knowledge, [])
            self.assertEqual(len(final.history), 2)

    def test_s_two_phase_free_reminder_and_invalid_ref_silence(self):
        agent, fake, root = self.make("S", [])
        episode = PMAEpisode(agent, run_id="run", task_id="task", archive=root / "archive")
        phase1 = LLMResponse(content="", tool_calls=[call("memory_save_knowledge",
            content="Retain WAL", statement_type="task_requirement",
            source_refs=[{"event_id": "e1", "role": "task_instruction", "quote": "Retain WAL"}])])
        fake.outputs.extend([phase1, LLMResponse(content="<no_intervention/>")])
        start = {"event_id": "e1", "sequence": 1, "run_id": "run", "task_id": "task",
                 "kind": "task_start", "initial_user_content": "Retain WAL"}
        asyncio.run(episode.handle(start))
        memory_id = agent.memory.knowledge[0].id
        self.assertIn("source_refs", fake.requests[0]["tools"][0]["function"]["parameters"]["required"])
        self.assertIn("e1", fake.requests[0]["prompt"])
        self.assertEqual(agent._memory_agent.last_delivery_status, "deliberate_silence")
        fake.outputs.extend([LLMResponse(content="", tool_calls=[]), LLMResponse(content=(
            '<context_for_action>Consider keeping WAL before recovery; this is a bounded reminder.</context_for_action>'
            f'<memory_refs>[{{"id":"{memory_id}","version":1}}]</memory_refs>'))])
        before = {"event_id": "e2", "sequence": 2, "run_id": "run", "task_id": "task",
                  "kind": "before_actor_call", "actor_attempt": 1}
        asyncio.run(episode.handle(before))
        step = {"event_id": "e3", "sequence": 3, "run_id": "run", "task_id": "task",
                "kind": "actor_step", "actor_attempt": 1, "step_status": "normal",
                "response": "I will inspect the journal", "analysis": "PRIVATE_NOT_PUBLIC",
                "observation": "WAL is present", "commands": ["ls"]}
        asyncio.run(episode.handle(step))
        self.assertEqual(agent._memory_agent.last_delivery_status, "selected_validated_not_delivered")
        self.assertIn("Consider keeping WAL", agent._pending_injection)
        self.assertIn("e3:observation", fake.requests[2]["prompt"])
        self.assertNotIn("PRIVATE_NOT_PUBLIC", fake.requests[2]["prompt"])
        self.assertEqual(fake.outputs, [])
        text = agent._memory_agent._parse_phase2_response(
            '<context_for_action>Wrong</context_for_action>'
            '<memory_refs>[{"id":"absent","version":1}]</memory_refs>')
        self.assertIsNone(text)
        self.assertEqual(agent._memory_agent.last_delivery_status, "invalid_reference_no_delivery")

    def test_r_reconcile_and_no_old_version_resurrection(self):
        agent, fake, _ = self.make("R", [])
        bank = agent.memory
        bank.register_source("task", "task_instruction", "Keep audit trail", 1)
        old_ref = [{"event_id": "task", "role": "task_instruction", "quote": "audit trail"}]
        old = bank.save_sourced("knowledge", "Keep trail", "task_requirement", old_ref)
        bank.register_source("observation", "tool_observation", "trail now absent", 2)
        evidence = [{"event_id": "observation", "role": "tool_observation", "quote": "trail now absent"}]
        fake.outputs.extend([LLMResponse(content="", tool_calls=[call("memory_reconcile",
            memory_id=old, decision="revise", reason="Observed state changed",
            evidence_refs=evidence, content="Trail absent", statement_type="tool_observation",
            source_refs=evidence)]), LLMResponse(content="<no_intervention/>")])
        result = asyncio.run(agent._memory_agent.process("Task and observation", step_count=2))
        self.assertEqual([op.action for op in result.operations], ["revise"])
        self.assertIsNone(bank.get(old))
        self.assertEqual(len(bank.knowledge), 1)
        self.assertEqual(bank.metadata[bank.knowledge[0].id]["version"], 2)
        self.assertIn("memory_reconcile", str(fake.requests[0]["tools"]))
        self.assertIn("selective attention", fake.requests[1]["system"].lower())
        self.assertIsNone(agent._memory_agent._parse_phase2_response(
            '<context_for_action>Old error</context_for_action>'
            f'<memory_refs>[{{"id":"{old}","version":1}}]</memory_refs>'))
        self.assertEqual(agent._memory_agent.last_delivery_status, "invalid_reference_no_delivery")

    def test_visible_boundary_report_and_mixed_invalid_refs(self):
        agent, fake, root = self.make("S", [])
        episode = PMAEpisode(agent, run_id="r", task_id="t", archive=root / "archive")
        fake.outputs.extend([LLMResponse(content="", tool_calls=[]),
                             LLMResponse(content="<no_intervention/>")])
        asyncio.run(episode.handle({"kind": "task_start", "event_id": "s1", "sequence": 1,
                                    "run_id": "r", "task_id": "t",
                                    "initial_user_content": "Public task"}))
        bank = agent.memory
        bank.register_source("report", "agent_report", "Task says build passed", 2)
        report = [{"event_id": "report", "role": "agent_report", "quote": "build passed"}]
        with self.assertRaisesRegex(ValueError, "Task report"):
            bank.save_sourced("knowledge", "build passed", "tool_observation", report)
        bank.register_source("truncated", "tool_observation", "shown prefix", 3)
        with self.assertRaisesRegex(ValueError, "exactly once"):
            bank.save_sourced("knowledge", "hidden tail", "tool_observation",
                [{"event_id": "truncated", "role": "tool_observation", "quote": "hidden tail"}])
        bank.current_source_ids = ["s1"]
        with self.assertRaisesRegex(ValueError, "visible"):
            bank.save_sourced("knowledge", "future report", "agent_report", report)
        memory_id = bank.save_sourced("knowledge", "Public task", "task_requirement",
            [{"event_id": "s1", "role": "task_instruction", "quote": "Public task"}])
        mixed = ('<context_for_action>Free synthesis</context_for_action><memory_refs>'
                 f'[{{"id":"{memory_id}","version":1}},{{"id":"invalid","version":1}}]'
                 '</memory_refs>')
        self.assertIsNone(agent._memory_agent._parse_phase2_response(mixed))
        self.assertEqual(agent._memory_agent.last_delivery_status, "invalid_reference_no_delivery")
        self.assertEqual(fake.requests.__len__(), 2)

    def test_r_unresolved_retain_and_retraction_require_current_source(self):
        agent, _, _ = self.make("R", [])
        bank = agent.memory
        bank.register_source("task", "task_instruction", "Output JSON", 1)
        refs = [{"event_id": "task", "role": "task_instruction", "quote": "Output JSON"}]
        memory_id = bank.save_sourced("knowledge", "Output JSON", "task_requirement", refs)
        for decision in ("retain", "unresolved"):
            result = agent._memory_agent._reconcile({"memory_id": memory_id,
                "decision": decision, "reason": "No contrary evidence", "evidence_refs": refs})
            self.assertTrue(result.success)
            self.assertIsNotNone(bank.get(memory_id))
        with self.assertRaises(ValueError):
            agent._memory_agent._reconcile({"memory_id": memory_id,
                "decision": "retract", "reason": "", "evidence_refs": refs})
        self.assertIsNotNone(bank.get(memory_id))


if __name__ == "__main__":
    unittest.main()
