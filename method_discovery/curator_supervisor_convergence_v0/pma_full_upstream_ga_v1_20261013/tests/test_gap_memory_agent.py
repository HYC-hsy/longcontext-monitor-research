import asyncio
from copy import deepcopy
import inspect
import json
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from gap_memory_agent import GapMemoryAgent
from gap_store import GapMemory
from memory_agent.memory.memory_agent import BANK_TOOLS, MemoryAgent, PHASE2_SYSTEM


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
        return response(kwargs) if callable(response) else response


class GapAgentTests(unittest.TestCase):
    def run_cycle(self, model, bank=None, observation="CURRENT_PUBLIC_MATERIAL"):
        agent = GapMemoryAgent(task="ORIGINAL_TASK", llm=model, memory=bank)
        result = asyncio.run(agent.process(observation, step_count=1))
        self.assertEqual(model.responses, [])
        return agent, result

    def test_minimal_complete_cycle_uses_vendor_and_actual_phase2_prompt(self):
        model = ScriptedLLM(
            reply(calls=[("memory_save_knowledge", {"content": "ordinary fact"}),
                         ("memory_save_gap", {"content": "Acceptance not yet verified"})]),
            reply("ACCEPT: Grounded acceptance expectation."),
            reply("<context_for_action>Relevant acceptance expectation.</context_for_action>"))
        source = Path(inspect.getfile(MemoryAgent)).as_posix()
        self.assertIn("vendor/pma_89e5c0d/src/memory_agent", source)
        original_process = MemoryAgent.process
        with patch.object(MemoryAgent, "process", autospec=True, side_effect=original_process) as used:
            agent, result = self.run_cycle(model)
        self.assertEqual(used.call_count, 1)
        self.assertTrue(result.should_inject)
        self.assertEqual(result.context_for_action, "Relevant acceptance expectation.")
        self.assertEqual(agent.last_gap_report["status"], "accepted")
        self.assertEqual(len(agent.memory.knowledge), 1)
        self.assertEqual(len(agent.gaps.entries), 1)
        self.assertIs(agent.gaps, agent.memory)
        self.assertEqual(result.user_prompt_phase2, model.inputs[-1]["prompt"])
        self.assertIn("Acceptance not yet verified", result.user_prompt_phase2)
        self.assertIn("(accepted)", result.user_prompt_phase2)
        self.assertNotIn("tools", model.inputs[-1])
        review = json.loads(model.inputs[1]["prompt"])
        self.assertEqual(review["original_task"], "ORIGINAL_TASK")
        self.assertEqual(review["current_cycle_actual_material"], "CURRENT_PUBLIC_MATERIAL")

    def test_base_u_constants_and_tools_are_unchanged(self):
        before = deepcopy(BANK_TOOLS)
        agent = GapMemoryAgent(task="task")
        schema = agent.get_tools_schema()
        schema[0]["function"]["name"] = "mutated"
        self.assertEqual(BANK_TOOLS, before)
        model = ScriptedLLM(reply(), reply("<no_intervention/>"))
        result = asyncio.run(MemoryAgent(llm=model).process("task"))
        self.assertFalse(result.should_inject)
        self.assertEqual(model.inputs[0]["tools"], before)
        self.assertEqual(model.inputs[1]["system"], PHASE2_SYSTEM)
        self.assertEqual(len(model.inputs), 2)

    def seeded_bank(self):
        bank = GapMemory()
        bank.begin()
        old = bank.stage_save("Unverified task acceptance")
        keep = bank.stage_save("Unchanged input contract gap")
        bank.commit()
        return bank, old, keep

    def test_one_gap_only_repair_never_replays_ordinary_writes(self):
        bank, old, keep = self.seeded_bank()

        def repair(kwargs):
            material = json.loads(kwargs["prompt"].split("\nReview feedback:")[0])
            proposed = material["candidate_gaps"][-1]["id"]
            return reply(calls=[("memory_delete", {"memory_id": proposed}),
                                ("memory_save_gap", {"content": "Valid test failed: functional gap"})])

        model = ScriptedLLM(
            reply(calls=[("memory_save_knowledge", {"content": "ordinary fact"}),
                         ("memory_update_status", {"content": "COMPLETE"}),
                         ("memory_delete", {"memory_id": old}),
                         ("memory_save_gap", {"content": "Test failure means defective test"})]),
            reply("REVISE: Distinguish a valid failing test from a defective test."),
            repair, reply("ACCEPT: The functional gap is supported."),
            reply("<no_intervention/>"))
        agent, result = self.run_cycle(model, bank)
        self.assertEqual(len(bank.knowledge), 1)
        self.assertEqual(bank.status, "COMPLETE")
        self.assertEqual([e.content for e in bank.entries],
                         ["Unchanged input contract gap", "Valid test failed: functional gap"])
        self.assertEqual(bank.entries[0].id, keep)
        self.assertEqual(agent.last_gap_report["repair_count"], 1)
        self.assertEqual(len(agent.last_gap_report["reviews"]), 2)
        self.assertEqual(len(model.inputs), 5)
        self.assertEqual(result.user_prompt_phase2, model.inputs[-1]["prompt"])
        first_review = json.loads(model.inputs[1]["prompt"])
        self.assertEqual(len(first_review["old_gaps"]), 2)
        self.assertIn(keep, [row["id"] for row in first_review["candidate_gaps"]])
        self.assertIn("unchanged old gaps", model.inputs[1]["system"])
        self.assertEqual({t["function"]["name"] for t in model.inputs[2]["tools"]},
                         {"memory_save_gap", "memory_delete"})

    def test_repair_cannot_write_or_delete_ordinary_memory(self):
        for forbidden in ("memory_save_knowledge", "memory_save_procedural",
                          "memory_update_status", "memory_delete"):
            with self.subTest(forbidden=forbidden):
                bank, old, keep = self.seeded_bank()
                ordinary = bank.save_knowledge("Preserve ordinary entry")
                before = bank.to_dict()
                args = {"memory_id": ordinary} if forbidden == "memory_delete" else {"content": "Forbidden"}
                model = ScriptedLLM(
                    reply(calls=[("memory_delete", {"memory_id": old})]),
                    reply("REVISE: Retain the unsupported closure."),
                    reply(calls=[("memory_save_gap", {"content": "Staged before error"}),
                                 (forbidden, args)]), reply("<no_intervention/>"))
                agent, result = self.run_cycle(model, bank)
                self.assertEqual(bank.to_dict(), before)
                self.assertEqual(agent.last_gap_report["status"], "stale")
                self.assertFalse(result.should_inject)
                self.assertEqual(len(model.inputs), 4)

    def test_invalid_reviews_and_refusals_never_accept(self):
        invalid = ("", "ACCEPT:", "accept: fine", "I cannot review this.",
                   "REVISE", "REVISE: \n ", "Prefix ACCEPT: fine",
                   "ACCEPT\nExtra text", "ACCEPT: fine\nREVISE",
                   "REVISE: restore gaps\nACCEPT", "ACCEPT: fine REVISE: actually wrong",
                   "<think>ok</think>ACCEPT: fine")
        for raw in invalid:
            with self.subTest(raw=raw):
                bank, old, keep = self.seeded_bank()
                before = bank.to_dict()
                model = ScriptedLLM(
                    reply(calls=[("memory_delete", {"memory_id": old})]),
                    reply(raw), reply("<no_intervention/>"))
                agent, result = self.run_cycle(model, bank)
                self.assertEqual(bank.to_dict(), before)
                self.assertEqual(agent.last_gap_report["status"], "stale")
                self.assertIn("(stale)", result.user_prompt_phase2)
                self.assertEqual(result.user_prompt_phase2, model.inputs[-1]["prompt"])

    def test_tool_call_in_review_is_invalid_and_never_executed(self):
        model = ScriptedLLM(reply(), reply("ACCEPT: Fine.", calls=[
            ("memory_save_knowledge", {"content": "Unauthorized review write"})]),
            reply("<no_intervention/>"))
        agent, _ = self.run_cycle(model)
        self.assertEqual(agent.memory.knowledge, [])
        self.assertEqual(agent.last_gap_report["status"], "stale")

    def test_second_revise_retains_old_group_and_continues_phase2(self):
        bank, old, keep = self.seeded_bank()
        before = bank.entries
        model = ScriptedLLM(
            reply(calls=[("memory_delete", {"memory_id": old}),
                         ("memory_save_knowledge", {"content": "Ordinary stays"})]),
            reply("REVISE: Restore acceptance uncertainty."),
            reply(calls=[("memory_save_gap", {"content": "Still inadequate"})]),
            reply("REVISE: Still missing material expectations."),
            reply("<context_for_action>Current useful note.</context_for_action>"))
        agent, result = self.run_cycle(model, bank)
        self.assertEqual(bank.entries, before)
        self.assertEqual(len(bank.knowledge), 1)
        self.assertEqual(agent.last_gap_report["repair_count"], 1)
        self.assertTrue(result.should_inject)
        self.assertEqual(len(model.inputs), 5)

    def test_unchanged_candidate_is_reviewed_for_omissions(self):
        bank, old, keep = self.seeded_bank()
        model = ScriptedLLM(reply(), reply("ACCEPT: Existing gaps remain justified."),
                            reply("<no_intervention/>"))
        agent, _ = self.run_cycle(model, bank)
        material = json.loads(model.inputs[1]["prompt"])
        self.assertEqual(material["changes"], [])
        self.assertEqual(material["old_gaps"], material["candidate_gaps"])
        self.assertEqual(agent.last_gap_report["status"], "accepted")

    def test_original_xml_fallback_and_normal_delete_are_used(self):
        bank = GapMemory()
        ordinary = bank.save_knowledge("Obsolete ordinary fact")
        raw = ("<tool_call><function=memory_save_gap>"
               "<parameter=content>Coverage is unverified</parameter></function></tool_call>"
               "<tool_call><function=memory_delete><parameter=memory_id>"
               + ordinary + "</parameter></function></tool_call>")
        model = ScriptedLLM(reply(raw), reply("ACCEPT: Relevant uncertainty."),
                            reply("<no_intervention/>"))
        with patch.object(MemoryAgent, "_parse_tool_calls_from_text",
                          autospec=True, side_effect=MemoryAgent._parse_tool_calls_from_text) as parser:
            agent, _ = self.run_cycle(model, bank)
        self.assertEqual(parser.call_count, 1)
        self.assertIsNone(bank.get(ordinary))
        self.assertEqual(bank.entries[0].content, "Coverage is unverified")

    def test_review_and_commit_errors_preserve_old_and_continue(self):
        for failure in ("review", "commit"):
            with self.subTest(failure=failure):
                bank, old, keep = self.seeded_bank()
                before = bank.entries
                model = ScriptedLLM(
                    reply(calls=[("memory_delete", {"memory_id": old})]),
                    RuntimeError("review fixture") if failure == "review" else reply("ACCEPT: Fine."),
                    reply("<no_intervention/>"))
                if failure == "commit":
                    with patch.object(bank, "commit", side_effect=RuntimeError("commit fixture")):
                        agent, _ = self.run_cycle(model, bank)
                else:
                    agent, _ = self.run_cycle(model, bank)
                self.assertEqual(bank.entries, before)
                self.assertEqual(agent.last_gap_report["status"], "stale")

    def test_cancellation_and_process_termination_propagate(self):
        for error in (asyncio.CancelledError(), KeyboardInterrupt(), SystemExit()):
            with self.subTest(error=type(error).__name__):
                bank, old, keep = self.seeded_bank()
                before = bank.entries
                model = ScriptedLLM(reply(calls=[("memory_delete", {"memory_id": old})]), error)
                agent = GapMemoryAgent(task="task", memory=bank, llm=model)
                with self.assertRaises(type(error)):
                    asyncio.run(agent.process("current"))
                self.assertEqual(bank.entries, before)
                self.assertIsNone(bank.candidate)
                self.assertEqual(len(model.inputs), 2)

    def test_gap_count_does_not_change_bm25_threshold(self):
        bank = GapMemory()
        bank.save_knowledge("needle fact")
        bank.begin()
        for n in range(60):
            bank.stage_save(f"Gap {n}")
        bank.commit()
        agent = GapMemoryAgent(task="task", memory=bank)
        with patch.object(bank, "search_knowledge", wraps=bank.search_knowledge) as search:
            agent._build_phase2_prompt("needle", 1)
            self.assertEqual(search.call_count, 0)
            for n in range(50):
                bank.save_knowledge(f"needle fact {n}")
            agent._build_phase2_prompt("needle", 1)
            search.assert_called_once_with("needle", top_k=20)
        self.assertEqual(len(bank), 51)

    def test_phase2_additions_replace_only_three_original_rules(self):
        from gap_prompts import ATTENTION, phase2_system
        actual = phase2_system()
        self.assertTrue(actual.endswith(ATTENTION))
        self.assertNotIn("Don't include information already visible", actual)
        self.assertIn("Visible information may be repeated", actual)
        self.assertIn("not a command to remind at every step", actual)
        self.assertIn("status such as COMPLETE", actual)
        self.assertIn("Your DEFAULT is <no_intervention/>", actual)
        self.assertEqual(PHASE2_SYSTEM.count("Don't include information already visible"), 1)

    def test_phase1_failure_still_runs_original_phase2(self):
        model = ScriptedLLM(RuntimeError("phase1 fixture"), reply("<no_intervention/>"))
        with self.assertLogs("memory_agent.memory.memory_agent", level="ERROR"):
            agent, result = self.run_cycle(model)
        self.assertEqual(agent.last_gap_report["status"], "stale")
        self.assertEqual(len(model.inputs), 2)
        self.assertEqual(result.user_prompt_phase2, model.inputs[-1]["prompt"])

    def test_prompt_helper_failure_uses_original_phase2_and_records_actual_input(self):
        model = ScriptedLLM(reply(), reply("ACCEPT: No missing task-grounded gaps."),
                            reply("<no_intervention/>"))
        with patch("gap_memory_agent.phase2_system", side_effect=RuntimeError("prompt fixture")):
            agent, result = self.run_cycle(model)
        self.assertEqual(model.inputs[-1]["system"], PHASE2_SYSTEM)
        self.assertEqual(result.user_prompt_phase2, model.inputs[-1]["prompt"])
        self.assertIn("unavailable/stale", result.user_prompt_phase2)

    def test_invalid_gap_does_not_block_subsequent_ordinary_operations(self):
        model = ScriptedLLM(reply(calls=[
            ("memory_save_gap", {"content": ""}),
            ("memory_save_knowledge", {"content": "Still applied"})]),
            reply("<no_intervention/>"))
        agent, _ = self.run_cycle(model)
        self.assertEqual(agent.memory.knowledge[0].content, "Still applied")
        self.assertEqual(agent.gaps.entries, [])
        self.assertEqual(agent.last_gap_report["status"], "stale")

    def test_broken_structured_arguments_do_not_approve_partial_gap_group(self):
        response = reply(calls=[("memory_save_gap", {"content": "Candidate"})])
        response.tool_calls.insert(0, NS(function=NS(name="memory_save_gap", arguments="{")))
        model = ScriptedLLM(response, reply("<no_intervention/>"))
        agent, _ = self.run_cycle(model)
        self.assertEqual(agent.gaps.entries, [])
        self.assertEqual(agent.last_gap_report["status"], "stale")

    def test_accept_without_reason_and_multiline_reason_are_valid(self):
        for raw in ("ACCEPT", "ACCEPT: Grounded.\nNo omitted task requirements.",
                    "ACCEPT:\nGrounded current gaps."):
            with self.subTest(raw=raw):
                model = ScriptedLLM(reply(calls=[("memory_save_gap", {"content": "Gap"})]),
                                    reply(raw), reply("<no_intervention/>"))
                agent, _ = self.run_cycle(model)
                self.assertEqual(agent.last_gap_report["status"], "accepted")
                self.assertEqual(len(agent.gaps.entries), 1)

    def test_xml_repair_without_structured_tools_and_multiline_feedback(self):
        bank, old, keep = self.seeded_bank()
        raw = ("<tool_call><function=memory_delete><parameter=memory_id>"
               + old + "</parameter></function></tool_call>"
               "<tool_call><function=memory_save_gap><parameter=content>"
               "Valid failing test confirms functional gap</parameter></function></tool_call>")
        feedback = "REVISE:\nReplace the unsupported old interpretation.\nKeep unrelated gaps."
        model = ScriptedLLM(reply(), reply(feedback), reply(raw), reply("ACCEPT"),
                            reply("<no_intervention/>"))
        agent = GapMemoryAgent(task="task", llm=model, memory=bank, use_structured_tools=False)
        result = asyncio.run(agent.process("current material"))
        self.assertEqual(model.responses, [])
        self.assertTrue(all("tools" not in item for item in model.inputs))
        self.assertIn("Keep unrelated gaps.", model.inputs[2]["prompt"])
        self.assertEqual(agent.last_gap_report["repair_count"], 1)
        self.assertEqual(agent.last_gap_report["status"], "accepted")
        self.assertEqual([e.content for e in bank.entries],
                         ["Unchanged input contract gap", "Valid failing test confirms functional gap"])
        self.assertEqual(bank.entries[0].id, keep)
        self.assertEqual(result.user_prompt_phase2, model.inputs[-1]["prompt"])

    def test_review_uses_original_bm25_projection_without_replaying_writes(self):
        bank = GapMemory()
        for n in range(51):
            bank.save_knowledge(f"needle ordinary fact {n}")
        model = ScriptedLLM(
            reply(calls=[("memory_save_knowledge", {"content": "needle new fact"})]),
            reply("REVISE: Add the omitted gap."),
            reply(calls=[("memory_save_gap", {"content": "Task acceptance unverified"})]),
            reply("ACCEPT"), reply("<no_intervention/>"))
        agent = GapMemoryAgent(task="task", llm=model, memory=bank)
        expected_projection = MemoryAgent._format_memory_bank
        with patch.object(bank, "save_knowledge", wraps=bank.save_knowledge) as save:
            asyncio.run(agent.process("needle"))
            save.assert_called_once_with("needle new fact")
        self.assertEqual(model.responses, [])
        for index in (1, 3):
            material = json.loads(model.inputs[index]["prompt"])
            self.assertEqual(material["ordinary_memory_projection"],
                             expected_projection(agent, "needle"))
            self.assertIn("showing top 20 of 52", material["ordinary_memory_projection"])
            self.assertNotIn("Task acceptance unverified", material["ordinary_memory_projection"])
        self.assertIn("never to override the task or actual observations", model.inputs[1]["system"])


if __name__ == "__main__":
    unittest.main()
