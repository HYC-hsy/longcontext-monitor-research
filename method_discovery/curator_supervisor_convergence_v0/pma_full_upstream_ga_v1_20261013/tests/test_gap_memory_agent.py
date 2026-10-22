import asyncio
from copy import deepcopy
import inspect
import json
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from gap_memory_agent import GapMemoryAgent
from gap_prompts import ATTENTION, MAINTENANCE, PHASE2_REPLACEMENTS, phase2_system
from gap_store import GapMemory
from memory_agent.memory.memory_agent import (
    BANK_TOOLS, MemoryAgent, PHASE1_SYSTEM, PHASE2_SYSTEM,
)
from memory_agent.memory.universal_memory import UniversalMemory


def reply(content="", calls=()):
    return NS(content=content, tool_calls=[
        NS(function=NS(name=name, arguments=json.dumps(args))) for name, args in calls])


class ScriptedLLM:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.inputs = []

    async def call(self, **kwargs):
        self.inputs.append(deepcopy(kwargs))
        if not self.responses:
            raise AssertionError("unexpected model call")
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


class GapAgentTests(unittest.TestCase):
    def run_cycle(self, model, bank=None, *, structured=True, observation="PUBLIC_CONTEXT"):
        agent = GapMemoryAgent(task="ORIGINAL_TASK", llm=model, memory=bank,
                               use_structured_tools=structured)
        result = asyncio.run(agent.process(observation, step_count=1))
        self.assertEqual(model.responses, [])
        self.assertEqual(len(model.inputs), 2)
        self.assertEqual(result.user_prompt_phase2, model.inputs[1]["prompt"])
        self.assertEqual(agent.transport_phase, "selection")
        self.assertEqual(agent.last_gap_report["mode"], "direct_two_phase")
        return agent, result

    def test_prompt_contract_is_role_local_and_vendor_is_unchanged(self):
        original = PHASE2_SYSTEM
        model = ScriptedLLM(reply(), reply("<no_intervention/>"))
        self.run_cycle(model)
        self.assertEqual(model.inputs[0]["system"], PHASE1_SYSTEM + MAINTENANCE)
        for heading in ("Test-quality checks:", "Maintain existing gaps:",
                        "Preserve useful resolutions:"):
            self.assertEqual(MAINTENANCE.count(heading), 1)
        self.assertEqual(ATTENTION.count("The gap view is fallible memory"), 1)
        self.assertEqual(model.inputs[1]["system"], phase2_system())
        for old, new in PHASE2_REPLACEMENTS:
            self.assertEqual(original.count(old), 1)
            self.assertNotIn(old, model.inputs[1]["system"])
            self.assertEqual(model.inputs[1]["system"].count(new), 1)
        self.assertEqual(PHASE2_SYSTEM, original)
        self.assertTrue(all(ord(char) < 128 for char in MAINTENANCE + ATTENTION +
                            "".join(part for pair in PHASE2_REPLACEMENTS for part in pair)))

    def test_resolution_can_save_procedural_experience_and_delete_gap(self):
        bank = GapMemory()
        resolved = bank.save_gap("Verification command not yet run")
        model = ScriptedLLM(reply(calls=[
            ("memory_save_procedural", {"content": "Ran the check; observed report; applies to this build"}),
            ("memory_delete", {"memory_id": resolved})]),
            reply("<no_intervention/>"))
        agent, result = self.run_cycle(model, bank)
        self.assertEqual([op.action for op in result.operations], ["save_procedural", "delete_gap"])
        self.assertEqual(bank.entries, [])
        self.assertEqual(len(bank.procedural), 1)
        self.assertNotIn("Verification command not yet run", model.inputs[1]["prompt"])
        self.assertEqual(agent.last_gap_report["formal_gaps"], [])

    def test_partial_resolution_revises_one_gap_without_closing_other(self):
        bank = GapMemory()
        partial = bank.save_gap("Local and remote checks remain")
        other = bank.save_gap("Independent requirement still open")
        model = ScriptedLLM(reply(calls=[
            ("memory_delete", {"memory_id": partial}),
            ("memory_save_gap", {"content": "Remote check remains"})]),
            reply("<no_intervention/>"))
        _, result = self.run_cycle(model, bank)
        self.assertEqual([op.action for op in result.operations], ["delete_gap", "save_gap"])
        self.assertEqual([entry.content for entry in bank.entries],
                         ["Independent requirement still open", "Remote check remains"])
        self.assertEqual(bank.entries[0].id, other)
        self.assertIn("Remote check remains", model.inputs[1]["prompt"])

    def test_duplicate_deletion_does_not_automatically_create_experience(self):
        bank = GapMemory()
        duplicate = bank.save_gap("Duplicate claim")
        model = ScriptedLLM(reply(calls=[("memory_delete", {"memory_id": duplicate})]),
                            reply("<no_intervention/>"))
        self.run_cycle(model, bank)
        self.assertEqual(bank.entries, [])
        self.assertEqual(bank.procedural, [])

    def test_status_only_never_closes_gap(self):
        bank = GapMemory()
        entry = bank.save_gap("Acceptance still unverified")
        model = ScriptedLLM(reply(calls=[("memory_update_status", {"content": "COMPLETE"})]),
                            reply("<no_intervention/>"))
        self.run_cycle(model, bank)
        self.assertEqual(bank.status, "COMPLETE")
        self.assertEqual([gap.id for gap in bank.entries], [entry])

    def test_vendor_process_two_calls_and_updated_phase2(self):
        model = ScriptedLLM(
            reply(calls=[("memory_save_knowledge", {"content": "ordinary fact"}),
                         ("memory_save_gap", {"content": "Acceptance unverified"})]),
            reply("<context_for_action>Check acceptance.</context_for_action>"))
        self.assertIn("vendor/pma_89e5c0d/src/memory_agent",
                      inspect.getfile(MemoryAgent).replace("\\", "/"))
        with patch.object(MemoryAgent, "process", autospec=True,
                          side_effect=MemoryAgent.process) as used:
            agent, result = self.run_cycle(model)
        used.assert_called_once()
        self.assertTrue(result.should_inject)
        self.assertEqual(result.context_for_action, "Check acceptance.")
        self.assertEqual(len(agent.memory.knowledge), 1)
        self.assertIs(agent.gaps, agent.memory)
        self.assertIn("Acceptance unverified", model.inputs[1]["prompt"])
        self.assertEqual([op.action for op in result.operations], ["save_knowledge", "save_gap"])
        self.assertEqual([row["action"] for row in agent.last_gap_report["operations"]],
                         ["save_knowledge", "save_gap"])
        self.assertEqual(agent.last_gap_report["errors"], [])
        self.assertEqual(agent.last_gap_report["actual_phase2_prompt"], model.inputs[1]["prompt"])

    def test_base_u_paired_non_gap_behavior_and_immutable_constants(self):
        before = deepcopy(BANK_TOOLS)
        ordinary_calls = [("memory_save_knowledge", {"content": "fact"}),
                          ("memory_save_procedural", {"content": "lesson"}),
                          ("memory_update_status", {"content": "working"})]
        baseline = ScriptedLLM(reply(calls=ordinary_calls), reply("<no_intervention/>"))
        base_result = asyncio.run(MemoryAgent(llm=baseline).process("PUBLIC_CONTEXT", 1))
        gap = ScriptedLLM(reply(calls=ordinary_calls), reply("<no_intervention/>"))
        agent, gap_result = self.run_cycle(gap)
        self.assertEqual([op.action for op in gap_result.operations],
                         [op.action for op in base_result.operations])
        self.assertEqual(gap_result.should_inject, base_result.should_inject)
        self.assertEqual(agent.memory.status, "working")
        self.assertEqual([e.content for e in agent.memory.knowledge], ["fact"])
        self.assertEqual([e.content for e in agent.memory.procedural], ["lesson"])
        self.assertEqual(BANK_TOOLS, before)
        self.assertEqual(baseline.inputs[0]["tools"], before)
        self.assertEqual(gap.inputs[0]["tools"][:-1], before)
        self.assertEqual(gap.inputs[0]["tools"][-1]["function"]["name"], "memory_save_gap")
        self.assertEqual([x["function"]["name"] for x in gap.inputs[0]["tools"]],
                         [x["function"]["name"] for x in before] + ["memory_save_gap"])
        self.assertEqual(gap.inputs[0]["system"], PHASE1_SYSTEM + MAINTENANCE)
        self.assertEqual(gap.inputs[1]["system"], phase2_system())
        self.assertTrue(phase2_system().endswith(ATTENTION))
        self.assertNotIn("tools", gap.inputs[1])
        self.assertEqual(agent.gaps.entries, [])

    def test_direct_save_then_missing_delete_keeps_save_and_reports_id(self):
        model = ScriptedLLM(
            reply(calls=[("memory_save_gap", {"content": "First saved"}),
                         ("memory_delete", {"memory_id": "gap_missing"}),
                         ("memory_save_knowledge", {"content": "Ordinary once"})]),
            reply("<no_intervention/>"))
        agent, result = self.run_cycle(model)
        self.assertEqual([e.content for e in agent.gaps.entries], ["First saved"])
        self.assertEqual([e.content for e in agent.memory.knowledge], ["Ordinary once"])
        self.assertEqual([op.success for op in result.operations], [True, False, True])
        self.assertEqual(result.operations[1].memory_id, "gap_missing")
        self.assertIn("not found", result.operations[1].error)
        self.assertEqual(agent.last_gap_report["errors"][0]["memory_id"], "gap_missing")

    def test_existing_gap_delete_and_unmentioned_gap_retained(self):
        bank = GapMemory()
        remove = bank.save_gap("Outdated")
        keep = bank.save_gap("Keep")
        ordinary = bank.save_knowledge("Old fact")
        model = ScriptedLLM(reply(calls=[("memory_delete", {"memory_id": remove}),
                                            ("memory_delete", {"memory_id": ordinary}),
                                            ("memory_save_gap", {"content": "Replacement"})]),
                            reply("<no_intervention/>"))
        agent, _ = self.run_cycle(model, bank)
        self.assertEqual([e.id for e in bank.entries][0], keep)
        self.assertEqual([e.content for e in bank.entries], ["Keep", "Replacement"])
        self.assertIsNone(bank.get(ordinary))
        self.assertEqual(agent.last_gap_report["formal_gaps"],
                         [e.to_dict() for e in bank.entries])

    def test_invalid_gap_operation_does_not_block_ordinary_operation(self):
        model = ScriptedLLM(reply(calls=[("memory_save_gap", {"content": ""}),
                                           ("memory_save_knowledge", {"content": "Still applied"})]),
                            reply("<no_intervention/>"))
        agent, result = self.run_cycle(model)
        self.assertEqual([op.success for op in result.operations], [False, True])
        self.assertEqual(agent.gaps.entries, [])
        self.assertEqual(agent.memory.knowledge[0].content, "Still applied")

    def test_xml_mode_uses_vendor_parser_and_two_calls(self):
        raw = ("<tool_call><function=memory_save_gap>"
               "<parameter=content>Unverified coverage</parameter></function></tool_call>"
               "<tool_call><function=memory_save_knowledge>"
               "<parameter=content>Observed fact</parameter></function></tool_call>")
        model = ScriptedLLM(reply(raw), reply("<no_intervention/>"))
        with patch.object(MemoryAgent, "_parse_tool_calls_from_text", autospec=True,
                          side_effect=MemoryAgent._parse_tool_calls_from_text) as parser:
            agent, _ = self.run_cycle(model, structured=False)
        parser.assert_called_once()
        self.assertNotIn("tools", model.inputs[0])
        self.assertEqual(agent.gaps.entries[0].content, "Unverified coverage")
        self.assertEqual(agent.memory.knowledge[0].content, "Observed fact")

    def test_bm25_threshold_counts_ordinary_only(self):
        bank = GapMemory()
        for n in range(60):
            bank.save_gap(f"Gap {n}")
        bank.save_knowledge("needle fact")
        agent = GapMemoryAgent(task="task", memory=bank)
        with patch.object(bank, "search_knowledge", wraps=bank.search_knowledge) as search:
            agent._build_phase2_prompt("needle", 1)
            search.assert_not_called()
            for n in range(50):
                bank.save_knowledge(f"needle fact {n}")
            agent._build_phase2_prompt("needle", 1)
            search.assert_called_once_with("needle", top_k=20)
        self.assertEqual(len(bank), 51)

    def test_phase1_transport_error_preserves_vendor_phase2_path(self):
        model = ScriptedLLM(RuntimeError("maintenance unavailable"), reply("<no_intervention/>"))
        with self.assertLogs("memory_agent.memory.memory_agent", level="ERROR"):
            agent, result = self.run_cycle(model)
        self.assertFalse(result.should_inject)
        self.assertEqual(agent.gaps.entries, [])
        self.assertEqual(result.user_prompt_phase2, model.inputs[1]["prompt"])
        self.assertEqual(agent.last_gap_report["transport_errors"],
                         [{"phase": "maintenance", "type": "RuntimeError"}])

    def test_malformed_gap_arguments_record_failure_without_extra_role(self):
        response = reply(calls=[("memory_save_gap", {"content": "Already saved"}),
                                ("memory_save_gap", {"content": ""})])
        model = ScriptedLLM(response, reply("<no_intervention/>"))
        agent, result = self.run_cycle(model)
        self.assertEqual([op.success for op in result.operations], [True, False])
        self.assertEqual([e.content for e in agent.gaps.entries], ["Already saved"])
        self.assertEqual(agent.last_gap_report["errors"][0]["action"], "memory_save_gap")

    def test_invalid_ordinary_delete_ids_do_not_break_reporting_or_reminder(self):
        for invalid_id in (123, ["gap_x"], {"id": "gap_x"}):
            with self.subTest(invalid_id=invalid_id):
                model = ScriptedLLM(
                    reply(calls=[("memory_save_gap", {"content": "x"}),
                                 ("memory_delete", {"memory_id": invalid_id})]),
                    reply("<context_for_action>Useful reminder.</context_for_action>"))
                agent, result = self.run_cycle(model)
                self.assertTrue(result.should_inject)
                self.assertEqual(result.context_for_action, "Useful reminder.")
                self.assertEqual([e.content for e in agent.gaps.entries], ["x"])
                self.assertEqual([op.success for op in result.operations], [True, False])
                self.assertEqual(result.operations[1].memory_id, invalid_id)
                self.assertEqual(agent.last_gap_report["errors"][0]["memory_id"], invalid_id)
                self.assertEqual(len(agent.last_gap_report["formal_gaps"]), 1)

    def test_vendor_paired_tool_parser_edges(self):
        def raw_call(name, arguments):
            return NS(function=NS(name=name, arguments=arguments))

        for case in ("ordinary_valid", "malformed_json", "non_object",
                     "prior_delete_then_bad", "delete_xml_fallback"):
            with self.subTest(case=case):
                base_bank = UniversalMemory()
                old = base_bank.save_knowledge("old")
                gap_bank = GapMemory.from_dict(base_bank.to_dict())
                if case == "ordinary_valid":
                    phase1 = reply(calls=[("memory_save_knowledge", {"content": "new"}),
                                          ("memory_update_status", {"content": "working"})])
                elif case == "malformed_json":
                    phase1 = NS(content="", tool_calls=[raw_call("memory_save_knowledge", "{")])
                elif case == "non_object":
                    phase1 = NS(content="", tool_calls=[raw_call("memory_save_knowledge", "[1]")])
                elif case == "prior_delete_then_bad":
                    phase1 = NS(content="", tool_calls=[
                        raw_call("memory_delete", json.dumps({"memory_id": old})),
                        raw_call("memory_save_knowledge", "{")])
                else:
                    xml = ("<tool_call><function=memory_save_knowledge>"
                           "<parameter=content>xml fact</parameter></function></tool_call>")
                    phase1 = NS(content=xml, tool_calls=[
                        raw_call("memory_delete", json.dumps({"memory_id": old}))])
                base_llm = ScriptedLLM(deepcopy(phase1), reply("<no_intervention/>"))
                gap_llm = ScriptedLLM(deepcopy(phase1), reply("<no_intervention/>"))
                with self.assertLogs("memory_agent.memory.memory_agent", level="ERROR") if case in {
                    "malformed_json", "non_object", "prior_delete_then_bad"
                } else patch("memory_agent.memory.memory_agent.logger"):
                    base_result = asyncio.run(MemoryAgent(llm=base_llm, memory=base_bank).process("ctx"))
                if case in {"malformed_json", "non_object", "prior_delete_then_bad"}:
                    with self.assertLogs("memory_agent.memory.memory_agent", level="ERROR"):
                        gap_result = asyncio.run(GapMemoryAgent(task="task", llm=gap_llm,
                                            memory=gap_bank).process("ctx"))
                else:
                    gap_result = asyncio.run(GapMemoryAgent(task="task", llm=gap_llm,
                                        memory=gap_bank).process("ctx"))
                self.assertEqual(len(base_llm.inputs), 2)
                self.assertEqual(len(gap_llm.inputs), 2)
                self.assertEqual(base_bank.status, gap_bank.status)
                self.assertEqual([e.content for e in base_bank.knowledge],
                                 [e.content for e in gap_bank.knowledge])
                self.assertEqual([e.content for e in base_bank.procedural],
                                 [e.content for e in gap_bank.procedural])
                self.assertEqual([(op.action, op.success, op.error) for op in base_result.operations],
                                 [(op.action, op.success, op.error) for op in gap_result.operations])
                self.assertEqual(base_result.should_inject, gap_result.should_inject)

    def test_phase2_transport_error_adds_no_review_or_retry(self):
        model = ScriptedLLM(reply(calls=[("memory_save_gap", {"content": "Still formal"})]),
                            RuntimeError("selection unavailable"))
        with self.assertLogs("memory_agent.memory.memory_agent", level="ERROR"):
            agent, result = self.run_cycle(model)
        self.assertFalse(result.should_inject)
        self.assertEqual([e.content for e in agent.gaps.entries], ["Still formal"])
        self.assertEqual(agent.last_gap_report["mode"], "direct_two_phase")
        self.assertEqual(agent.last_gap_report["transport_errors"],
                         [{"phase": "selection", "type": "RuntimeError"}])


if __name__ == "__main__":
    unittest.main()
