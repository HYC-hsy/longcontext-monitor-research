"""Offline replay of the archived R2 rejections; no provider endpoint is used."""
import asyncio
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from harbor.llms.base import LLMResponse

from episode import construct_upstream
from source_memory_v2 import SourceMemoryV2, SourceSelectionError
from test_source_candidate_v2 import Script, call


HERE = Path(__file__).resolve().parent
RAW = (HERE / "source_memory_v3_single_r2_archive_20261015" / "raw" /
       "source-v2-59f53dcd1a87-01-r2")
FAILURES = {15: {3: "invalid_range"}, 17: {3: "invalid_range"},
            21: {11: "invalid_range"}, 23: {12: "invalid_range"},
            25: {3: "invalid_range", 4: "invalid_range", 10: "invalid_range"},
            27: {2: "role_mismatch"}}


def records(name):
    return [json.loads(line) for line in (RAW / name).read_text(encoding="utf-8").splitlines()]


def archived_stage(logical_call):
    request = next(row for row in records("requests.jsonl") if row["logical_call"] == logical_call)
    response = next(row for row in records("responses.jsonl") if row["logical_call"] == logical_call)
    bank_row = next(row for row in records("bank_states.jsonl") if row["sequence"] == logical_call)
    bank = SourceMemoryV2.from_dict(bank_row["memory"])
    leaves = json.loads(request["prompt"].split(
        "## Numbered visible public source leaves\n", 1)[1].split(
        "\n## Previous phase-1 execution receipts", 1)[0])
    handles = {leaf["source_handle"] for leaf in leaves}
    bank.current_source_ids = [key for key, value in bank.sources.items()
                               if value.get("handle") in handles]
    calls = [call(item["function"]["name"], **json.loads(item["function"]["arguments"]))
             for item in response["tool_calls"]]
    return bank, leaves, calls


class ArchivedCoordinateTests(unittest.TestCase):
    def agent(self, variant="R2"):
        from tempfile import TemporaryDirectory
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return construct_upstream(Path(tmp.name) / "upstream", research_candidate=variant)

    def test_eight_original_rejections_and_six_atomic_rollbacks(self):
        total_rejected = total_collateral = 0
        for logical_call, expected in FAILURES.items():
            with self.subTest(logical_call=logical_call):
                bank, leaves, calls = archived_stage(logical_call)
                agent = self.agent()
                agent._memory = bank
                engine = agent._memory_agent
                engine.memory = bank
                engine._phase_step = (logical_call + 1) // 2
                before = copy.deepcopy(bank.to_dict())
                engine._execute_tool_calls(LLMResponse(content="", tool_calls=calls))
                self.assertEqual(bank.to_dict(), before)
                self.assertEqual(engine.last_transaction["status"], "transaction_aborted")
                self.assertFalse(engine.last_transaction["committed"])
                rejected = {row["call_index"]: row for row in engine.last_receipts
                            if row["status"] == "rejected"}
                self.assertEqual({index: row["error_code"] for index, row in rejected.items()},
                                 expected)
                total_rejected += len(rejected)
                total_collateral += sum(row["status"] == "transaction_aborted"
                                        for row in engine.last_receipts)
                for index, code in expected.items():
                    row = rejected[index]
                    self.assertEqual(row["call_index"], index)  # one-based tool call
                    self.assertTrue(row["argument_path"].startswith(
                        ("source_refs", "evidence_refs")))
                    if code == "invalid_range":
                        self.assertEqual(row["total_lines"], 1)
                        self.assertEqual(row["legal_line_range"], "1..1")
                        leaf = next(leaf for leaf in leaves
                                    if leaf["source_handle"] == row["source_handle"])
                        self.assertEqual(leaf["field_path"].split("/")[-1], "content")
                        self.assertTrue(row["decoded_source_handles"])
                        self.assertTrue(any(leaf.get("decoded_from") == row["source_handle"]
                                            for leaf in bank.visible_lines()))
                    else:
                        self.assertEqual(row["required_role"], "agent_report")
                        self.assertEqual(row["actual_roles"], ["tool_observation"])
                if logical_call == 23:
                    self.assertEqual(engine.last_receipts[11]["status"], "rejected")
                    self.assertTrue(any(row["status"] == "transaction_aborted" for row in engine.last_receipts))
                if logical_call == 27:
                    self.assertTrue(any(row["status"] == "transaction_aborted" for row in engine.last_receipts))
        self.assertEqual((total_rejected, total_collateral), (8, 65))

    def test_synthetic_corrected_coordinates_and_roles(self):
        corrected = 0
        for logical_call, expected in FAILURES.items():
          for index in expected:
            with self.subTest(logical_call=logical_call, call_index=index):
                bank, leaves, calls = archived_stage(logical_call)
                args = calls[index - 1].function.arguments
                if logical_call == 27:
                    args["statement_type"] = "tool_observation"
                else:
                    key = "source_refs" if "source_refs" in args else "evidence_refs"
                    original = args[key][0]["source_handle"]
                    child = next(leaf for leaf in bank.visible_lines()
                                 if leaf.get("decoded_from") == original)
                    args[key][0] = {"source_handle": child["source_handle"],
                                    "start_line": 1, "end_line": 1}
                    if logical_call == 25 and index == 3:
                        args["statement_type"] = "tool_observation"
                agent = self.agent()
                agent._memory = bank
                engine = agent._memory_agent
                engine.memory = bank
                engine._phase_step = (logical_call + 1) // 2
                # This isolated operation is synthetic_corrected, not the historical stage.
                engine._execute_tool_calls(LLMResponse(content="", tool_calls=[calls[index - 1]]))
                self.assertTrue(engine.last_transaction["committed"])
                corrected += 1
        self.assertEqual(corrected, 8)

    def test_display_and_safe_feedback_in_two_real_processes(self):
        for variant in ("S2", "R2"):
            with self.subTest(variant=variant):
                agent = self.agent(variant)
                bank = agent.memory
                wrapper = json.dumps({"status": "ok", "stdout": "alpha\nbeta"})
                parent = bank.register_leaf("e", "tool_observation", wrapper, 1,
                    "observation/tool_results/0/content", "a" * 64)
                child = bank.register_leaf("e", "tool_observation", "alpha\nbeta", 1,
                    "observation/tool_results/0/content/stdout", "a" * 64)
                fake = Script([LLMResponse(content="", tool_calls=[call(
                    "memory_save_knowledge", content="bad", statement_type="tool_observation",
                    source_refs=[{"source_handle": parent, "start_line": 2, "end_line": 2}])]),
                    LLMResponse(content="<no_intervention/>"),
                    LLMResponse(content="", tool_calls=[]),
                    LLMResponse(content="<no_intervention/>")])
                agent._memory_llm.call = fake
                asyncio.run(agent._memory_agent.process("public", 1))
                asyncio.run(agent._memory_agent.process("public", 2))
                self.assertEqual(len(fake.requests), 4)
                leaves = bank.visible_lines()
                self.assertEqual(next(r for r in leaves if r["source_handle"] == parent)["total_lines"], 1)
                self.assertEqual(next(r for r in leaves if r["source_handle"] == child)["total_lines"], 2)
                self.assertEqual(next(r for r in leaves if r["source_handle"] == child)["decoded_from"], parent)
                self.assertIn('"total_lines": 1', fake.requests[0]["prompt"])
                self.assertIn('"decoded_from": "' + parent + '"', fake.requests[0]["prompt"])
                for pos in (1, 2):
                    self.assertIn('"invalid_range"', fake.requests[pos]["prompt"])
                    self.assertIn('"legal_line_range": "1..1"', fake.requests[pos]["prompt"])

    def test_role_mismatch_feedback_is_bounded_in_both_following_requests(self):
        agent = self.agent("R2")
        bank = agent.memory
        handle = bank.register_leaf("e", "tool_observation", "VISIBLE TOOL RESULT", 1,
                                    "observation/tool_results/0/content", "a" * 64)
        hidden = bank.register_leaf("old", "agent_report", "HIDDEN_SENTINEL", 0,
                                    "response", "b" * 64)
        bank.current_source_ids = ["e:observation/tool_results/0/content"]
        fake = Script([LLMResponse(content="", tool_calls=[call(
            "memory_save_procedural", content="claim", statement_type="agent_report",
            source_refs=[{"source_handle": handle, "start_line": 1, "end_line": 1}])]),
            LLMResponse(content="<no_intervention/>"),
            LLMResponse(content="", tool_calls=[]),
            LLMResponse(content="<no_intervention/>")])
        agent._memory_llm.call = fake
        asyncio.run(agent._memory_agent.process("public", 1))
        asyncio.run(agent._memory_agent.process("public", 2))
        for pos in (1, 2):
            payload = fake.requests[pos]["prompt"]
            self.assertIn('"role_mismatch"', payload)
            self.assertIn('"required_role": "agent_report"', payload)
            self.assertIn('"actual_roles": ["tool_observation"]', payload)
            self.assertNotIn(hidden, payload)
            self.assertNotIn("HIDDEN_SENTINEL", payload)
            self.assertNotIn("VISIBLE TOOL RESULT", payload.split("## This phase-1 execution result")[-1]
                             if pos == 1 else payload.split("## Previous phase-1 execution receipts")[-1])
        self.assertEqual(len(fake.requests), 4)

    def test_hidden_unknown_mixed_roles_and_semantic_non_guarantee(self):
        bank = SourceMemoryV2()
        report = bank.register_leaf("r", "agent_report", "Task says changed", 1, "response", "a" * 64)
        tool = bank.register_leaf("r", "tool_observation", "old code", 1,
                                  "observation/tool_results/0/content", "a" * 64)
        refs = [{"source_handle": report, "start_line": 1, "end_line": 1},
                {"source_handle": tool, "start_line": 1, "end_line": 1}]
        self.assertEqual(len(bank.resolve_refs(refs, "agent_report")), 2)
        self.assertEqual(len(bank.resolve_refs(refs, "tool_observation")), 2)
        self.assertEqual(bank.excerpt(bank.resolve_refs(refs[1:], "tool_observation")[0]), "old code")
        # A valid range can still support the wrong temporal or causal interpretation.
        with self.assertRaises(SourceSelectionError) as unknown:
            bank.resolve_refs([{"source_handle": "hidden-sentinel", "start_line": 1,
                                "end_line": 1}], "inference")
        self.assertEqual(unknown.exception.code, "unknown_source")
        bank.current_source_ids = []
        with self.assertRaises(SourceSelectionError) as invisible:
            bank.resolve_refs(refs[:1], "inference")
        self.assertEqual(invisible.exception.code, "window_invisible")

    def test_wrapper_without_visible_decoded_child_remains_citable(self):
        bank = SourceMemoryV2()
        wrapper = json.dumps({"status": "ok", "stdout": "first\nsecond"})
        parent = bank.register_leaf("e", "tool_observation", wrapper, 1,
                                    "observation/tool_results/0/content", "a" * 64)
        child = bank.register_leaf("e", "tool_observation", "first\nsecond", 1,
                                   "observation/tool_results/0/content/stdout", "a" * 64)
        bank.current_source_ids = ["e:observation/tool_results/0/content"]
        rows = bank.visible_lines()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["total_lines"], 1)
        self.assertNotIn("decoded_from", rows[0])
        self.assertEqual(bank.excerpt(bank.resolve_refs([{"source_handle": parent,
            "start_line": 1, "end_line": 1}], "tool_observation")[0]), wrapper)
        with self.assertRaises(SourceSelectionError) as failure:
            bank.resolve_refs([{"source_handle": child, "start_line": 1,
                                "end_line": 1}], "tool_observation")
        self.assertEqual(failure.exception.code, "window_invisible")


if __name__ == "__main__":
    unittest.main()
