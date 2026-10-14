"""Zero-model tests for opt-in S/R, using the real pinned upstream process."""
import asyncio
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

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
        audit_rows = [json.loads(line) for line in
                      (root / "archive" / "candidate_audit.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(audit_rows[-1]["reminder_memory_refs"],
                         [{"id": memory_id, "version": 1}])
        self.assertEqual(audit_rows[-1]["reminder_source_refs"][0][0]["event_id"], "e1")
        agent.memory.sources["e1"]["text"] = "tampered after selection"
        later = {"event_id": "e4", "sequence": 4, "run_id": "run", "task_id": "task",
                 "kind": "before_actor_call", "actor_attempt": 2}
        self.assertEqual(asyncio.run(episode.handle(later))["status"], "silent")
        self.assertEqual(agent._memory_agent.last_delivery_status, "invalid_reference_no_delivery")
        self.assertEqual(len(fake.requests), 4)
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

    def test_unresolved_is_in_phase2_future_phase1_and_reload(self):
        agent, fake, root = self.make("R", [])
        bank = agent.memory
        bank.register_source("task", "task_instruction", "Preserve a precise audit trail.", 1)
        refs = [{"event_id": "task", "role": "task_instruction", "quote": "precise audit trail"}]
        memory_id = bank.save_sourced("knowledge", "Audit trail is preserved", "task_requirement", refs)
        fake.outputs.extend([LLMResponse(content="", tool_calls=[call("memory_reconcile",
            memory_id=memory_id, decision="unresolved", reason="Need to inspect the current trail",
            evidence_refs=refs)]), LLMResponse(content="<no_intervention/>")])
        asyncio.run(agent._memory_agent.process("Current public observation", step_count=2))
        self.assertIn('"decision": "unresolved"', fake.requests[1]["prompt"])
        self.assertIn("Need to inspect the current trail", fake.requests[1]["prompt"])
        self.assertIn("precise audit trail", fake.requests[1]["prompt"])
        self.assertEqual(bank.metadata[memory_id]["coordination"]["decision"], "unresolved")
        path = root / "bank.json"
        bank.save_to_file(path)
        loaded = SourceMemory.load_from_file(path)
        agent._memory = loaded
        agent._memory_agent.memory = loaded
        fake.outputs.extend([LLMResponse(content="", tool_calls=[]),
                             LLMResponse(content="<no_intervention/>")])
        asyncio.run(agent._memory_agent.process("Later observation", step_count=3))
        self.assertIn('"decision": "unresolved"', fake.requests[2]["prompt"])
        self.assertIn("Need to inspect the current trail", fake.requests[2]["prompt"])

    def test_window_old_bound_excerpt_and_no_unbound_citation(self):
        agent, fake, root = self.make("S", [])
        episode = PMAEpisode(agent, run_id="window", task_id="t", archive=root / "archive")
        task = "Preserve uncommon token NORTHSTAR-BOUND while repairing."
        fake.outputs.extend([LLMResponse(content="", tool_calls=[]),
                             LLMResponse(content="<no_intervention/>")])
        asyncio.run(episode.handle({"kind": "task_start", "event_id": "s1", "sequence": 1,
                                    "run_id": "window", "task_id": "t", "initial_user_content": task}))
        for attempt in range(1, 11):
            seq = attempt * 2
            asyncio.run(episode.handle({"kind": "before_actor_call", "event_id": f"b{attempt}",
                "sequence": seq, "run_id": "window", "task_id": "t", "actor_attempt": attempt}))
            first = [call("memory_save_knowledge", content="Retain the uncommon token",
                statement_type="agent_report", source_refs=[{"event_id": "a1:response",
                    "role": "agent_report", "quote": "NORTHSTAR-BOUND"}])] if attempt == 1 else []
            fake.outputs.extend([LLMResponse(content="", tool_calls=first),
                                 LLMResponse(content="<no_intervention/>")])
            asyncio.run(episode.handle({"kind": "actor_step", "event_id": f"a{attempt}",
                "sequence": seq + 1, "run_id": "window", "task_id": "t", "actor_attempt": attempt,
                "step_status": "normal", "response": (
                    "Public reply NORTHSTAR-BOUND" if attempt == 1 else f"Public reply {attempt}"),
                "observation": f"Observed tool result {attempt}", "commands": ["true"]}))
        prompt = fake.requests[-2]["prompt"]
        self.assertIn('"excerpt": "NORTHSTAR-BOUND"', prompt)
        self.assertNotIn("Public reply NORTHSTAR-BOUND", prompt)
        self.assertGreater(agent._memory_agent.evidence_chars_by_phase["phase1"], 0)
        bank = agent.memory
        bank.register_source("unbound", "tool_observation", "PRIVATE-UNBOUND", 99)
        bank.current_source_ids.remove("unbound")
        with self.assertRaises(ValueError):
            bank.revise(bank.knowledge[0].id, "new", "inference",
                [{"event_id": "unbound", "role": "tool_observation", "quote": "PRIVATE-UNBOUND"}],
                "reason", bank.metadata[bank.knowledge[0].id]["source_refs"], [0])

    def test_revision_dispatch_failure_is_atomic_and_collision_safe(self):
        agent, _, _ = self.make("R", [])
        bank = agent.memory
        bank.register_source("task", "task_instruction", "Keep ORIGINAL-BOUND", 1)
        refs = [{"event_id": "task", "role": "task_instruction", "quote": "ORIGINAL-BOUND"}]
        old = bank.save_sourced("procedural", "old procedure", "task_requirement", refs)
        before = json.dumps(bank.to_dict(), sort_keys=True)
        before_search = [e.id for e in bank.search_procedural("procedure")]
        for bad in (42, [], {}, "", "  "):
            result = agent._memory_agent._execute_tool_calls(SimpleNamespace(tool_calls=[call(
                "memory_reconcile", memory_id=old, decision="revise",
                reason="new source", evidence_refs=refs, content=bad,
                statement_type="task_requirement", source_refs=[],
                inherit_source_ref_indices=[0])], content=""))[0]
            self.assertFalse(result.success)
            self.assertEqual(json.dumps(bank.to_dict(), sort_keys=True), before)
            self.assertEqual([e.id for e in bank.search_procedural("procedure")], before_search)
        from memory_agent.memory.universal_memory import UniversalMemory
        with patch.object(UniversalMemory, "_generate_id", return_value=old):
            result = agent._memory_agent._execute_tool_calls(SimpleNamespace(tool_calls=[call(
                "memory_reconcile", memory_id=old, decision="revise",
                reason="updated", evidence_refs=refs, content="new procedure",
                statement_type="task_requirement", source_refs=[],
                inherit_source_ref_indices=[0])], content=""))[0]
        self.assertTrue(result.success)
        self.assertNotEqual(result.memory_id, old)
        self.assertIsNone(bank.get(old))
        self.assertEqual(bank.search_procedural("procedure")[0].id, result.memory_id)

    def test_s_r_valid_reminder_is_returned_not_delivered(self):
        for variant in ("S", "R"):
            with self.subTest(variant=variant):
                agent, fake, root = self.make(variant, [])
                episode = PMAEpisode(agent, run_id="r", task_id="t", archive=root / "archive")
                fake.outputs.extend([LLMResponse(content="", tool_calls=[call(
                    "memory_save_knowledge", content="Keep public scope", statement_type="task_requirement",
                    source_refs=[{"event_id": "s1", "role": "task_instruction", "quote": "public scope"}])]),
                    LLMResponse(content="<no_intervention/>")])
                asyncio.run(episode.handle({"kind": "task_start", "event_id": "s1", "sequence": 1,
                    "run_id": "r", "task_id": "t", "initial_user_content": "Keep public scope"}))
                memory_id = agent.memory.knowledge[0].id
                fake.outputs.extend([LLMResponse(content="", tool_calls=[]), LLMResponse(content=(
                    "<context_for_action>Remember the public scope.</context_for_action>"
                    f'<memory_refs>[{{"id":"{memory_id}","version":1}}]</memory_refs>'))])
                asyncio.run(episode.handle({"kind": "before_actor_call", "event_id": "b1",
                    "sequence": 2, "run_id": "r", "task_id": "t", "actor_attempt": 1}))
                asyncio.run(episode.handle({"kind": "actor_step", "event_id": "a1",
                    "sequence": 3, "run_id": "r", "task_id": "t", "actor_attempt": 1,
                    "step_status": "normal", "response": "Inspecting public information",
                    "observation": "Visible result", "commands": ["read"]}))
                receipt = asyncio.run(episode.handle({"kind": "before_actor_call", "event_id": "b2",
                    "sequence": 4, "run_id": "r", "task_id": "t", "actor_attempt": 2}))
                self.assertEqual(receipt["status"], "reminder")
                self.assertIn("Remember the public scope", receipt["reminder"])
                self.assertEqual(receipt["delivery"], "returned_not_confirmed_in_ga_request")
                self.assertIn('"excerpt": "public scope"', fake.requests[2]["prompt"])
                self.assertEqual(len(fake.requests), 4)

    def test_load_and_presend_reject_invalid_bank(self):
        agent, _, root = self.make("S", [])
        bank = agent.memory
        bank.register_source("s", "task_instruction", "Keep public scope", 1)
        memory_id = bank.save_sourced("knowledge", "scope", "task_requirement",
            [{"event_id": "s", "role": "task_instruction", "quote": "public scope"}])
        good = bank.to_dict()
        for mutation in ("missing_meta", "empty_refs", "bad_version", "retired_active"):
            data = json.loads(json.dumps(good))
            if mutation == "missing_meta":
                del data["metadata"][memory_id]
            elif mutation == "empty_refs":
                data["metadata"][memory_id]["source_refs"] = []
            elif mutation == "bad_version":
                data["metadata"][memory_id]["version"] = 0
            else:
                data["history"].append({"action": "retract", "id": memory_id})
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                SourceMemory.from_dict(data)
        bank.metadata[memory_id]["source_refs"] = []
        self.assertIsNone(agent._memory_agent._parse_phase2_response(
            '<context_for_action>Bad</context_for_action>'
            f'<memory_refs>[{{"id":"{memory_id}","version":1}}]</memory_refs>'))
        self.assertEqual(agent._memory_agent.last_delivery_status, "invalid_reference_no_delivery")


if __name__ == "__main__":
    unittest.main()
