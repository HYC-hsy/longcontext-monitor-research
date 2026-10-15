"""Zero-provider checks of the real upstream two-phase process with S2/R2 adapters."""
import asyncio
import copy
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
import litellm
from episode import PMAEpisode, construct_upstream
from source_memory_v2 import SourceMemoryV2
from static_source_screen import MANIFEST_V2, projected_events


def call(name, **kwargs):
    return SimpleNamespace(function=SimpleNamespace(name=name, arguments=kwargs))


class Script:
    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []

    async def __call__(self, *, prompt, system, tools=None):
        self.requests.append({"prompt": prompt, "system": system, "tools": tools})
        if not self.replies:
            raise AssertionError("unexpected provider send")
        return self.replies.pop(0)


class V2Tests(unittest.TestCase):
    def make(self, variant, replies):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        agent = construct_upstream(Path(tmp.name) / "upstream", research_candidate=variant)
        fake = Script(replies)
        agent._memory_llm.call = fake
        return agent, fake, Path(tmp.name)

    @staticmethod
    def receipt_view(prompt, heading):
        return json.loads(prompt.split(heading, 1)[1].strip())

    def test_reconcile_contract_and_safe_feedback_at_real_request_boundary(self):
        agent, fake, _ = self.make("R2", [])
        bank = agent.memory
        old = bank.register_leaf("old", "task_instruction", "Keep the requirement", 1,
                                 "initial_user_content", "1" * 64)
        memory_id = bank.save_sourced("knowledge", "Old active conclusion", "task_requirement",
                                      [{"source_handle": old, "start_line": 1, "end_line": 1}])
        fresh = bank.register_leaf("fresh", "tool_observation", "New observation", 2,
                                   "observation/tool_results/0/content", "2" * 64)
        ref = [{"source_handle": fresh, "start_line": 1, "end_line": 1}]
        bad = call("memory_reconcile", memory_id=memory_id, decision="revise",
                   reason="new observation", evidence_refs=ref,
                   content="Revised conclusion", inherit_source_ref_indices=[0])
        fake.replies.extend([
            LLMResponse(content="", tool_calls=[call("memory_update_status", content="B"), bad]),
            LLMResponse(content="<no_intervention/>"),
            LLMResponse(content="", tool_calls=[]),
            LLMResponse(content="<no_intervention/>")])
        before = bank.to_dict()
        asyncio.run(agent._memory_agent.process("New observation", 2))
        self.assertEqual(bank.status, "B")  # Prior valid operation now survives.
        self.assertEqual([entry.content for entry in bank.knowledge],
                         [entry["content"] for entry in before["knowledge"]])
        schema = next(t["function"] for t in fake.requests[0]["tools"]
                      if t["function"]["name"] == "memory_reconcile")
        self.assertIn("exact active", schema["description"])
        self.assertIn("replacement", schema["parameters"]["properties"]["statement_type"]["description"])
        self.assertNotIn("statement_type", schema["parameters"]["required"])
        self.assertIn("memory_id", fake.requests[0]["system"])
        self.assertIn("one isolated commit per operation", fake.requests[0]["system"])
        self.assertIn("A valid citation establishes provenance, not truth", fake.requests[0]["system"])
        self.assertIn("knowledge/procedural memory use",
                      schema["parameters"]["properties"]["statement_type"]["description"])
        phase2 = self.receipt_view(fake.requests[1]["prompt"],
                                   "## This phase-1 execution result\n")
        self.assertEqual(phase2["transaction"]["status"], "partially_committed")
        self.assertEqual(phase2["receipts"][0]["status"], "committed")
        self.assertEqual(phase2["receipts"][1]["field_path"], "statement_type")
        self.assertEqual(phase2["receipts"][1]["rule_code"], "replacement_type_required")
        self.assertNotIn("Old active conclusion", json.dumps(phase2))
        asyncio.run(agent._memory_agent.process("New observation", 3))
        previous = self.receipt_view(fake.requests[2]["prompt"],
                                     "## Previous phase-1 execution receipts\n")
        self.assertEqual(previous, phase2)

    def test_archived_failed_shapes_and_synthetic_corrected_revision(self):
        archive = HERE / "source_memory_v2_live_batch_20261015_95940c8d" / "raw"
        archive = archive / "source-v2-822ee4349181-04-r2" / "responses.jsonl"
        recorded = {row["logical_call"]: row for line in archive.read_text(encoding="utf-8").splitlines()
                    if (row := json.loads(line))["logical_call"] in (37, 39, 41)}
        self.assertEqual(set(recorded), {37, 39, 41})
        for number, row in recorded.items():
            self.assertEqual(row["phase"], "phase1")
            revisions = [json.loads(item["function"]["arguments"])
                         for item in row["tool_calls"]
                         if item["function"]["name"] == "memory_reconcile"]
            self.assertTrue(revisions)
            for revision in revisions:
                self.assertEqual(revision["decision"], "revise")
                # Preserve the original failed payload: no correction is made here.
                self.assertTrue("statement_type" not in revision or
                                not revision.get("source_refs") and
                                not revision.get("inherit_source_ref_indices"), number)
            # Synthetic bank/source identities, but the archived replacement-field
            # shape is preserved and sent through the actual two-phase process.
            replay, transport, _ = self.make("R2", [])
            bank = replay.memory
            old_handle = bank.register_leaf("old", "task_instruction", "Original", 1,
                                            "initial_user_content", "6" * 64)
            old_id = bank.save_sourced("knowledge", "Original", "task_requirement", [
                {"source_handle": old_handle, "start_line": 1, "end_line": 1}])
            new_handle = bank.register_leaf("new", "tool_observation", "Observed", 2,
                                            "observation/tool_results/0/content", "7" * 64)
            new_ref = [{"source_handle": new_handle, "start_line": 1, "end_line": 1}]
            mapped = []
            for revision in revisions:
                mapped_args = {**revision, "memory_id": old_id, "evidence_refs": new_ref}
                mapped.append(call("memory_reconcile", **mapped_args))
            transport.replies.extend([LLMResponse(content="", tool_calls=[
                call("memory_update_status", content="would roll back"), *mapped]),
                LLMResponse(content="<no_intervention/>")])
            before = bank.to_dict()
            asyncio.run(replay._memory_agent.process("Observed", number))
            self.assertEqual(bank.status, "would roll back")
            self.assertEqual([item.content for item in bank.knowledge],
                             [item["content"] for item in before["knowledge"]])
            visible = self.receipt_view(transport.requests[1]["prompt"],
                                        "## This phase-1 execution result\n")
            self.assertEqual(visible["transaction"]["status"], "partially_committed")
            self.assertEqual(visible["receipts"][0]["status"], "committed")
            self.assertTrue(all(receipt["rule_code"] in
                {"replacement_type_required", "replacement_sources_required"}
                for receipt in visible["receipts"][1:]))
        agent, fake, _ = self.make("R2", [])
        bank = agent.memory
        handle = bank.register_leaf("source", "task_instruction", "Keep evidence", 1,
                                    "initial_user_content", "3" * 64)
        ref = [{"source_handle": handle, "start_line": 1, "end_line": 1}]
        memory_id = bank.save_sourced("knowledge", "Old", "task_requirement", ref)
        # Synthetic correction, not a replay or amendment of the archived requests.
        corrected = call("memory_reconcile", memory_id=memory_id, decision="revise",
                         reason="synthetic_corrected", evidence_refs=ref, content="New",
                         statement_type="task_requirement", inherit_source_ref_indices=[0])
        fake.replies.extend([LLMResponse(content="", tool_calls=[corrected]),
                             LLMResponse(content="<no_intervention/>")])
        asyncio.run(agent._memory_agent.process("Keep evidence", 1))
        self.assertEqual(agent._memory_agent.last_transaction["status"], "committed")
        self.assertIsNone(bank.get(memory_id))
        self.assertEqual(bank.knowledge[0].content, "New")

    def test_reconcile_conditions_and_exact_active_identity(self):
        from source_protocol_v2 import ReconcileArgs
        agent, fake, _ = self.make("R2", [])
        bank = agent.memory
        old = bank.register_leaf("old", "task_instruction", "Old", 1,
                                 "initial_user_content", "4" * 64)
        old_ref = [{"source_handle": old, "start_line": 1, "end_line": 1}]
        memory_id = bank.save_sourced("knowledge", "Active", "task_requirement", old_ref)
        fresh = bank.register_leaf("fresh", "tool_observation", "Fresh", 2,
                                   "observation/tool_results/0/content", "5" * 64)
        ref = [{"source_handle": fresh, "start_line": 1, "end_line": 1}]
        base = {"memory_id": memory_id, "reason": "current evidence", "evidence_refs": ref}
        for decision in ("retain", "retract", "unresolved"):
            ReconcileArgs.model_validate({**base, "decision": decision})
            ReconcileArgs.model_validate({**base, "decision": decision, "content": None})
            with self.assertRaises(ValueError):
                ReconcileArgs.model_validate({**base, "decision": decision, "content": "bad"})
        for sources in ({"source_refs": ref}, {"inherit_source_ref_indices": [0]},
                        {"source_refs": ref, "inherit_source_ref_indices": [0]}):
            args = ReconcileArgs.model_validate({**base, "decision": "revise", "content": "New",
                                                 "statement_type": "task_requirement", **sources})
            self.assertEqual(args.decision, "revise")
        with self.assertRaises(ValueError):
            ReconcileArgs.model_validate({**base, "decision": "revise", "content": "New",
                                          "statement_type": "task_requirement"})
        fake.replies.extend([LLMResponse(content="", tool_calls=[call(
            "memory_reconcile", **{**base, "memory_id": memory_id + " v1",
                                   "decision": "retain"})]),
            LLMResponse(content="<no_intervention/>")])
        asyncio.run(agent._memory_agent.process("Fresh", 2))
        rejected = self.receipt_view(fake.requests[1]["prompt"],
                                     "## This phase-1 execution result\n")["receipts"][0]
        self.assertEqual((rejected["error_code"], rejected["field_path"]),
                         ("memory_not_active", "memory_id"))
        self.assertEqual(bank.get(memory_id).content, "Active")
        fake.replies.extend([LLMResponse(content="", tool_calls=[call(
            "memory_reconcile", **{**base, "decision": []})]),
            LLMResponse(content="<no_intervention/>")])
        asyncio.run(agent._memory_agent.process("Fresh", 3))
        malformed = self.receipt_view(fake.requests[3]["prompt"],
                                      "## This phase-1 execution result\n")["receipts"][0]
        self.assertEqual(malformed["rule_code"], "field_invalid")
        self.assertEqual(malformed["field_path"], "decision")

    def test_archived_old_content_is_not_projected_in_s2_r2_receipts(self):
        marker = "ARCHIVED_ONLY_REVOKED_CONTENT_6C81"
        inherited = "BOUND_INHERITABLE_SOURCE_7D32"
        for variant in ("S2", "R2"):
            with self.subTest(variant=variant):
                agent, fake, _ = self.make(variant, [])
                bank = agent.memory
                old_handle = bank.register_leaf("old", "task_instruction", inherited, 1,
                                                "initial_user_content", "1" * 64)
                old_id = bank.save_sourced("knowledge", marker, "task_requirement", [
                    {"source_handle": old_handle, "start_line": 1, "end_line": 1}])
                for number in range(2, 12):
                    bank.register_leaf(f"recent-{number}", "agent_report", f"recent {number}",
                                       number, "response", "2" * 64)
                bank.current_source_ids = ["recent-11:response"]
                self.assertNotIn(marker, json.dumps(bank.visible_lines()))
                current_handle = bank.sources["recent-11:response"]["handle"]
                if variant == "S2":
                    change = call("memory_delete", memory_id=old_id)
                else:
                    change = call("memory_reconcile", memory_id=old_id, decision="revise",
                                  reason="current report changes the claim",
                                  evidence_refs=[{"source_handle": current_handle,
                                                  "start_line": 1, "end_line": 1}],
                                  content="new active content", statement_type="agent_report",
                                  source_refs=[{"source_handle": current_handle,
                                                "start_line": 1, "end_line": 1}],
                                  inherit_source_ref_indices=[0])
                fake.replies.extend([LLMResponse(content="", tool_calls=[change]),
                                     LLMResponse(content="<no_intervention/>"),
                                     LLMResponse(content="", tool_calls=[]),
                                     LLMResponse(content="<no_intervention/>")])
                asyncio.run(agent._memory_agent.process("current report", 12))
                archived = agent._memory_agent.last_transaction
                self.assertIn(marker, json.dumps(archived["after_bank"]["history"],
                                                 ensure_ascii=False))
                self.assertNotIn(marker, json.dumps([entry.content for entry in bank.knowledge]))
                phase2 = fake.requests[1]["prompt"]
                self.assertNotIn(marker, phase2)
                self.assertEqual(phase2.count('"call_index"'), 1)
                current_view = self.receipt_view(phase2, "## This phase-1 execution result\n")
                self.assertEqual(current_view["transaction"]["status"], "committed")
                self.assertEqual(len(current_view["receipts"]), 1)
                self.assertEqual(set(current_view["transaction"]) &
                                 {"before_bank", "after_bank", "history", "metadata", "receipts"}, set())
                if variant == "R2":
                    self.assertIn("new active content", phase2)
                    self.assertIn(inherited, phase2)  # Explicitly inherited bound excerpt.
                asyncio.run(agent._memory_agent.process("another current report", 13))
                for request, heading in ((fake.requests[2], "## Previous phase-1 execution receipts\n"),
                                         (fake.requests[3], "## This phase-1 execution result\n")):
                    view = self.receipt_view(request["prompt"], heading)
                    self.assertNotIn(marker, json.dumps(view, ensure_ascii=False))
                    self.assertNotIn(marker, request["prompt"])

    def test_receipt_projection_states_and_no_raw_exception(self):
        for variant in ("S2", "R2"):
            with self.subTest(variant=variant):
                agent, fake, _ = self.make(variant, [
                    LLMResponse(content="", tool_calls=[
                        call("memory_update_status", content="B"),
                        call("memory_delete", memory_id="missing")]),
                    LLMResponse(content="<no_intervention/>"),
                    LLMResponse(content="<tool_call", tool_calls=[]),
                    LLMResponse(content="<no_intervention/>")])
                asyncio.run(agent._memory_agent.process("task", 1))
                rollback = self.receipt_view(fake.requests[1]["prompt"],
                                             "## This phase-1 execution result\n")
                self.assertEqual(rollback["transaction"]["status"], "partially_committed")
                self.assertEqual([r["status"] for r in rollback["receipts"]],
                                 ["committed", "rejected"])
                self.assertEqual(rollback["receipts"][1]["error_code"], "memory_not_active")
                self.assertNotIn("error", rollback["receipts"][1])
                self.assertEqual(fake.requests[1]["prompt"].count('"call_index"'), 2)
                asyncio.run(agent._memory_agent.process("task", 2))
                rejected = self.receipt_view(fake.requests[3]["prompt"],
                                             "## This phase-1 execution result\n")
                self.assertEqual(rejected["transaction"]["status"], "format_rejected")
                self.assertEqual(rejected["receipts"][0]["error_code"],
                                 "text_tool_call_forbidden")
                with self.assertRaises(AssertionError):
                    asyncio.run(agent._memory_agent.process("task", 3))
                failure = agent._memory_agent._model_transaction_view(
                    agent._memory_agent.last_transaction, agent._memory_agent.last_receipts)
                self.assertEqual(failure["transaction"]["status"], "phase1_request_failed")
                self.assertEqual(failure["receipts"], [])
                self.assertEqual(len(fake.requests), 5)  # Failed phase 1; no phase 2 send.

    def test_raw_error_and_bank_fields_never_cross_projection(self):
        marker = "ARCHIVED_EXCEPTION_ONLY_4321"
        transaction = {"transaction_id": "txn", "status": "transaction_aborted",
                       "committed": False, "commit_version": "v", "before_bank": {"history": marker},
                       "after_bank": {"metadata": marker}, "receipts": [{"error": marker}]}
        receipts = [{"call_index": 1, "tool_name": "memory_delete", "status": "rejected",
                     "error_code": "memory_not_active", "error": marker, "error_type": marker,
                     "memory_id": "missing", "commit_version": "v"}]
        agent, _, _ = self.make("S2", [])
        view = agent._memory_agent._model_transaction_view(transaction, receipts)
        self.assertNotIn(marker, json.dumps(view))
        self.assertEqual(view["receipts"][0]["reason"],
                         "memory_id must be an exact active memory ID; omit the displayed version label")
        self.assertNotIn("receipts", view["transaction"])

    def test_real_process_schema_transaction_receipts_and_next_phase(self):
        refs = [{"source_handle": "placeholder", "start_line": 1, "end_line": 1}]
        agent, fake, _ = self.make("S2", [])
        bank = agent.memory
        handle = bank.register_leaf("e1", "task_instruction", "Keep WAL.\nNo deletion.", 1,
                                    "initial_user_content", "a" * 64)
        refs[0]["source_handle"] = handle
        fake.replies.extend([
            LLMResponse(content="", tool_calls=[call("memory_save_knowledge", content="Keep WAL",
                statement_type="task_requirement", source_refs=refs)]),
            LLMResponse(content="<no_intervention/>"),
            LLMResponse(content="", tool_calls=[call("memory_delete", memory_id="absent")]),
            LLMResponse(content="<no_intervention/>")])
        asyncio.run(agent._memory_agent.process("Keep WAL.", 1))
        self.assertEqual(len(bank.knowledge), 1)
        transaction = agent._memory_agent.last_transaction
        self.assertEqual(transaction["before_bank"]["knowledge"], [])
        self.assertEqual(len(transaction["after_bank"]["knowledge"]), 1)
        schema = fake.requests[0]["tools"][0]["function"]["parameters"]
        self.assertIn("source_refs", schema["required"])
        self.assertTrue(schema["additionalProperties"] is False)
        self.assertIn("committed", fake.requests[1]["prompt"])
        asyncio.run(agent._memory_agent.process("Keep WAL.", 2))
        self.assertIn("Previous phase-1 execution receipts", fake.requests[2]["prompt"])
        self.assertIn("committed", fake.requests[2]["prompt"])
        self.assertIn("rejected", fake.requests[3]["prompt"])

    def test_delete_survives_invalid_save_in_both_orders(self):
        for first in ("memory_delete", "memory_save_knowledge"):
            with self.subTest(first=first):
                agent, fake, _ = self.make("S2", [])
                bank = agent.memory
                handle = bank.register_leaf("e1", "task_instruction", "Keep WAL.", 1,
                                            "initial_user_content", "b" * 64)
                ref = [{"source_handle": handle, "start_line": 1, "end_line": 1}]
                old = bank.save_sourced("knowledge", "old", "task_requirement", ref)
                prior = bank.to_dict()
                good = call("memory_delete", memory_id=old)
                bad = call("memory_save_knowledge", content="bad", statement_type="task_requirement",
                           source_refs=[{"source_handle": "missing", "start_line": 1, "end_line": 1}])
                calls = [good, bad] if first == "memory_delete" else [bad, good]
                fake.replies.extend([LLMResponse(content="", tool_calls=calls),
                                     LLMResponse(content="<no_intervention/>")])
                asyncio.run(agent._memory_agent.process("Keep WAL.", 1))
                self.assertIsNone(bank.get(old))
                self.assertNotEqual(bank.to_dict(), prior)
                statuses = [r["status"] for r in agent._memory_agent.last_receipts]
                self.assertIn("rejected", statuses)
                self.assertIn("committed", statuses)
                self.assertEqual(agent._memory_agent.collateral_aborts, 0)

    def test_valid_save_survives_invalid_delete_in_both_orders(self):
        for bad_first in (True, False):
            with self.subTest(bad_first=bad_first):
                agent, fake, _ = self.make("S2", [])
                bank = agent.memory
                handle = bank.register_leaf("e1", "task_instruction", "Keep WAL", 1,
                                            "initial_user_content", "b" * 64)
                ref = [{"source_handle": handle, "start_line": 1, "end_line": 1}]
                prior = bank.to_dict()
                good = call("memory_save_knowledge", content="Keep WAL",
                            statement_type="task_requirement", source_refs=ref)
                bad = call("memory_delete", memory_id="missing")
                calls = [bad, good] if bad_first else [good, bad]
                fake.replies.extend([LLMResponse(content="", tool_calls=calls),
                                     LLMResponse(content="<no_intervention/>")])
                asyncio.run(agent._memory_agent.process("Keep WAL", 1))
                self.assertNotEqual(bank.to_dict(), prior)
                self.assertEqual({r["status"] for r in agent._memory_agent.last_receipts},
                                 {"rejected", "committed"})
                self.assertEqual(len(bank.search_knowledge("WAL")), 1)

    def test_status_commit_survives_rejection_and_empty_phase_is_no_operations(self):
        agent, fake, _ = self.make("S2", [])
        bank = agent.memory
        fake.replies.extend([LLMResponse(content="", tool_calls=[
            call("memory_update_status", content="working"),
            call("memory_delete", memory_id="missing")]),
            LLMResponse(content="<no_intervention/>"),
            LLMResponse(content="", tool_calls=[]), LLMResponse(content="<no_intervention/>")])
        asyncio.run(agent._memory_agent.process("task", 1))
        self.assertEqual(bank.status, "working")
        self.assertEqual(agent._memory_agent.last_receipts[0]["status"], "committed")
        asyncio.run(agent._memory_agent.process("task", 2))
        self.assertEqual(agent._memory_agent.last_receipts, [])
        self.assertEqual(agent._memory_agent.last_transaction["status"], "no_operations")

    def test_text_tool_fallback_is_rejected_whole_in_both_orders(self):
        good = "<tool_call><function=memory_update_status><parameter=content>B</parameter></function></tool_call>"
        bad = "<tool_call><function=memory_delete><parameter=memory_id>missing</parameter>"
        for variant in ("S2", "R2"):
            for text in (good + bad, bad + good, bad, good):
                with self.subTest(variant=variant, text=text):
                    agent, fake, _ = self.make(variant, [
                        LLMResponse(content=text, tool_calls=[]),
                        LLMResponse(content="<no_intervention/>")])
                    bank = agent.memory
                    bank.update_status("A")
                    before = bank.to_dict()
                    result = asyncio.run(agent._memory_agent.process("task", 1))
                    self.assertEqual(bank.to_dict(), before)
                    self.assertEqual(len(fake.requests), 2)
                    self.assertFalse(result.operations[0].success)
                    self.assertEqual(agent._memory_agent.last_transaction["status"],
                                     "format_rejected")
                    self.assertEqual(agent._memory_agent.last_receipts[0]["error_code"],
                                     "text_tool_call_forbidden")
        agent, _, _ = self.make("S2", [
            LLMResponse(content="ordinary prose", tool_calls=[]),
            LLMResponse(content="<no_intervention/>")])
        result = asyncio.run(agent._memory_agent.process("task", 1))
        self.assertEqual(result.operations, [])
        self.assertEqual(agent._memory_agent.last_transaction["status"], "no_operations")

    def test_partial_commit_preserves_no_change_and_feedback(self):
        agent, fake, _ = self.make("S2", [
            LLMResponse(content="", tool_calls=[
                call("memory_update_status", content="B"),
                call("memory_update_status", content="B"),
                call("memory_delete", memory_id="absent")]),
            LLMResponse(content="<no_intervention/>"),
            LLMResponse(content="", tool_calls=[]),
            LLMResponse(content="<no_intervention/>")])
        agent.memory.update_status("A")
        result = asyncio.run(agent._memory_agent.process("task", 1))
        self.assertEqual(agent.memory.status, "B")
        self.assertEqual([r["status"] for r in agent._memory_agent.last_receipts],
                         ["committed", "no_change", "rejected"])
        self.assertEqual([op.success for op in result.operations], [True, True, False])
        self.assertEqual(agent._memory_agent.collateral_aborts, 0)
        self.assertIn('"status": "partially_committed"', fake.requests[1]["prompt"])
        self.assertIn('"status": "rejected"', fake.requests[1]["prompt"])
        asyncio.run(agent._memory_agent.process("task", 2))
        self.assertIn('"status": "partially_committed"', fake.requests[2]["prompt"])
        self.assertEqual(agent._memory_agent.last_transaction["status"], "no_operations")

    def test_revise_is_one_atomic_operation_and_old_id_identity_follows_commit(self):
        agent, fake, _ = self.make("R2", [])
        bank = agent.memory
        handle = bank.register_leaf("task", "task_instruction", "keep it", 1,
                                    "initial_user_content", "1" * 64)
        refs = [{"source_handle": handle, "start_line": 1, "end_line": 1}]
        old = bank.save_sourced("knowledge", "old", "task_requirement", refs)
        revise = call("memory_reconcile", memory_id=old, decision="revise",
                      reason="bounded revision", evidence_refs=refs, content="new",
                      statement_type="task_requirement", inherit_source_ref_indices=[0])
        fake.replies.extend([LLMResponse(content="", tool_calls=[
            revise, call("memory_delete", memory_id=old)]),
            LLMResponse(content="<no_intervention/>")])
        asyncio.run(agent._memory_agent.process("task", 1))
        self.assertEqual([r["status"] for r in agent._memory_agent.last_receipts],
                         ["committed", "rejected"])
        self.assertIsNone(bank.get(old))
        self.assertEqual(bank.knowledge[0].content, "new")
        self.assertEqual(bank.metadata[bank.knowledge[0].id]["supersedes"], old)
        self.assertEqual(len([h for h in bank.history if h["action"] == "revise"]), 1)

        # A host exception after staging the old entry's removal cannot publish
        # a half-revision; an earlier independent commit still remains.
        second, fake2, _ = self.make("R2", [])
        second.memory.__dict__.update(copy.deepcopy(bank.__dict__))
        active = second.memory.knowledge[0].id
        bad = call("memory_reconcile", memory_id=active, decision="revise",
                   reason="fault injection", evidence_refs=refs, content="half",
                   statement_type="task_requirement", inherit_source_ref_indices=[0])
        prior = second.memory.to_dict()
        from source_memory_v2 import SourceMemoryV2
        def fail_after_staging(staged, *args, **kwargs):
            staged.history.append({"action": "incomplete"})
            raise RuntimeError("synthetic host fault")
        fake2.replies.append(LLMResponse(content="", tool_calls=[
            call("memory_update_status", content="saved first"), bad]))
        with patch.object(SourceMemoryV2, "revise", fail_after_staging):
            with self.assertRaises(RuntimeError):
                asyncio.run(second._memory_agent.process("task", 2))
        self.assertEqual(second.memory.status, "saved first")
        self.assertEqual(second.memory.knowledge[0].id, active)
        self.assertEqual(second.memory.history, prior["history"])
        self.assertEqual(second._memory_agent.last_transaction["status"], "host_failure")
        self.assertEqual([r["status"] for r in second._memory_agent.last_receipts],
                         ["committed", "integrity_error"])
        self.assertEqual(len(fake2.requests), 1)  # No phase-2 send after host failure.

    def test_failed_revision_does_not_invalidate_old_id_for_later_operation(self):
        agent, fake, _ = self.make("R2", [])
        bank = agent.memory
        handle = bank.register_leaf("task", "task_instruction", "keep it", 1,
                                    "initial_user_content", "1" * 64)
        refs = [{"source_handle": handle, "start_line": 1, "end_line": 1}]
        old = bank.save_sourced("knowledge", "old", "task_requirement", refs)
        fake.replies.extend([LLMResponse(content="", tool_calls=[
            call("memory_reconcile", memory_id=old, decision="revise", reason="bad",
                 evidence_refs=refs, content="new", statement_type="task_requirement",
                 source_refs=[{"source_handle": "missing", "start_line": 1, "end_line": 1}]),
            call("memory_delete", memory_id=old)]),
            LLMResponse(content="<no_intervention/>")])
        asyncio.run(agent._memory_agent.process("task", 1))
        self.assertEqual([r["status"] for r in agent._memory_agent.last_receipts],
                         ["rejected", "committed"])
        self.assertIsNone(bank.get(old))
        self.assertFalse(any(h["action"] == "revise" for h in bank.history))
        self.assertTrue(any(h["action"] == "upstream_delete" for h in bank.history))

    def test_model_visible_partial_commit_sample_in_both_phases(self):
        for variant in ("S2", "R2"):
            with self.subTest(variant=variant):
                agent, fake, _ = self.make(variant, [
                    LLMResponse(content="", tool_calls=[
                        call("memory_update_status", content="kept"),
                        call("memory_delete", memory_id="absent")]),
                    LLMResponse(content="<no_intervention/>"),
                    LLMResponse(content="", tool_calls=[]),
                    LLMResponse(content="<no_intervention/>")])
                asyncio.run(agent._memory_agent.process("public", 1))
                phase2 = self.receipt_view(fake.requests[1]["prompt"],
                                           "## This phase-1 execution result\n")
                asyncio.run(agent._memory_agent.process("public", 2))
                next_phase1 = self.receipt_view(fake.requests[2]["prompt"],
                                                 "## Previous phase-1 execution receipts\n")
                self.assertEqual(phase2, next_phase1)
                self.assertEqual(phase2["transaction"]["status"], "partially_committed")
                self.assertEqual(phase2["transaction"]["committed_count"], 1)
                self.assertEqual(phase2["transaction"]["rejected_count"], 1)
                self.assertEqual([r["status"] for r in phase2["receipts"]],
                                 ["committed", "rejected"])
                self.assertEqual(len(fake.requests), 4)
                print(json.dumps({"variant": variant,
                                  "system_contract": "one isolated commit per operation" in fake.requests[0]["system"],
                                  "statement_schema": fake.requests[0]["tools"][0]["function"]["parameters"]["properties"]["statement_type"]["description"],
                                  "phase2_result": phase2,
                                  "next_phase1_result": next_phase1}, ensure_ascii=False))

    def test_phase1_transport_failure_does_not_reuse_prior_receipts(self):
        agent, fake, _ = self.make("S2", [
            LLMResponse(content="", tool_calls=[call("memory_update_status", content="B")]),
            LLMResponse(content="<no_intervention/>")])
        asyncio.run(agent._memory_agent.process("task", 1))
        self.assertEqual(agent._memory_agent.last_transaction["status"], "committed")
        with self.assertRaises(AssertionError):
            asyncio.run(agent._memory_agent.process("task", 2))
        self.assertEqual(len(fake.requests), 3)
        self.assertEqual(agent._memory_agent.last_receipts, [])
        self.assertEqual(agent._memory_agent.last_transaction["status"],
                         "phase1_request_failed")
        self.assertIn('"status": "committed"', fake.requests[2]["prompt"])

    def test_successful_delete_and_procedural_index_invalidation(self):
        agent, fake, _ = self.make("S2", [])
        bank = agent.memory
        handle = bank.register_leaf("e1", "tool_observation", "compile failed", 1,
                                    "observation/tool_results/0/content", "b" * 64)
        ref = [{"source_handle": handle, "start_line": 1, "end_line": 1}]
        memory_id = bank.save_sourced("procedural", "compile failed", "tool_observation", ref)
        self.assertEqual(bank.search_procedural("compile")[0].id, memory_id)
        fake.replies.extend([LLMResponse(content="", tool_calls=[
            call("memory_delete", memory_id=memory_id)]),
            LLMResponse(content="<no_intervention/>")])
        asyncio.run(agent._memory_agent.process("compile failed", 2))
        self.assertEqual(bank.search_procedural("compile"), [])
        self.assertTrue(any(row["action"] == "upstream_delete" for row in bank.history))
        self.assertEqual(agent._memory_agent.last_receipts[0]["status"], "committed")

    def test_roles_visibility_and_line_ranges(self):
        bank = SourceMemoryV2()
        instruction = bank.register_leaf("e1", "task_instruction", "A\nB\n", 1,
                                         "initial_user_content", "c" * 64)
        report = bank.register_leaf("e2", "agent_report", "I saw success", 2,
                                    "response", "d" * 64)
        tool = bank.register_leaf("e2", "tool_observation", "failed", 2,
                                  "observation/tool_results/0/content", "d" * 64)
        self.assertEqual(bank.excerpt(bank.resolve_refs([{
            "source_handle": instruction, "start_line": 1, "end_line": 2}],
            "task_requirement")[0]), "A\nB")
        with self.assertRaises(ValueError):
            bank.resolve_refs([{"source_handle": report, "start_line": 1, "end_line": 1}],
                              "tool_observation")
        with self.assertRaises(ValueError):
            bank.resolve_refs([{"source_handle": tool, "start_line": 2, "end_line": 3}], "inference")
        bank.current_source_ids = ["e1:initial_user_content"]
        with self.assertRaises(ValueError):
            bank.resolve_refs([{"source_handle": tool, "start_line": 1, "end_line": 1}], "inference")

    def test_unicode_crlf_blank_and_last_line_boundaries(self):
        bank = SourceMemoryV2()
        handle = bank.register_leaf("e1", "task_instruction", "甲\r\n\r\n乙\u2028末行", 1,
                                    "initial_user_content", "c" * 64)
        self.assertEqual(bank.visible_lines()[0]["numbered_lines"],
                         ["1: 甲", "2: ", "3: 乙", "4: 末行"])
        selected = bank.resolve_refs([{"source_handle": handle, "start_line": 3,
                                       "end_line": 4}], "task_requirement")[0]
        self.assertEqual(bank.excerpt(selected), "乙\u2028末行")
        blank = {"source_handle": handle, "start_line": 2, "end_line": 2}
        with self.assertRaises(ValueError):
            bank.resolve_refs([blank], "task_requirement")
        tampered = {**selected, "start_line": 2}
        self.assertFalse(bank.source_ref_valid(tampered))

    def test_old_bound_excerpt_can_be_explicitly_inherited_not_newly_cited(self):
        bank = SourceMemoryV2()
        old_handle = bank.register_leaf("e1", "task_instruction", "Keep WAL", 1,
                                        "initial_user_content", "1" * 64)
        old_ref = [{"source_handle": old_handle, "start_line": 1, "end_line": 1}]
        memory_id = bank.save_sourced("knowledge", "Keep WAL", "task_requirement", old_ref)
        bank.register_leaf("e2", "agent_report", "I checked", 2, "response", "2" * 64)
        bank.current_source_ids = ["e2:response"]
        with self.assertRaises(ValueError):
            bank.resolve_refs(old_ref, "task_requirement")
        evidence_handle = bank.sources["e2:response"]["handle"]
        evidence = bank.resolve_refs([{"source_handle": evidence_handle, "start_line": 1,
                                       "end_line": 1}], "agent_report")
        new_id = bank.revise(memory_id, "Keep WAL, based on original instruction",
                             "task_requirement", [], "retain original source", evidence, [0])
        self.assertEqual(bank.excerpt(bank.metadata[new_id]["source_refs"][0]), "Keep WAL")
        with self.assertRaises(ValueError):
            bank.revise(new_id, "bad", "task_requirement", [], "bad inheritance", evidence, [3])

    def test_actual_episode_splits_working_memory_from_tool_result(self):
        agent, fake, root = self.make("S2", [LLMResponse(content="", tool_calls=[]),
            LLMResponse(content="<no_intervention/>"), LLMResponse(content="", tool_calls=[]),
            LLMResponse(content="<no_intervention/>")])
        episode = PMAEpisode(agent, run_id="r", task_id="t", archive=root / "episode")
        base = {"run_id": "r", "task_id": "t"}
        asyncio.run(episode.handle({**base, "kind": "task_start", "event_id": "e1",
            "sequence": 1, "initial_user_content": "Task text", "source_record_sha256": "e" * 64}))
        asyncio.run(episode.handle({**base, "kind": "before_actor_call", "event_id": "e2",
            "sequence": 2, "actor_attempt": 1}))
        observation = json.dumps({"content": "working memory says pass", "tool_results": [
            {"tool_use_id": "x", "content": "real tool failed"}]})
        asyncio.run(episode.handle({**base, "kind": "actor_step", "event_id": "e3",
            "sequence": 3, "actor_attempt": 1, "step_status": "normal", "response": "checking",
            "commands": [], "observation": observation, "source_record_sha256": "f" * 64}))
        visible = agent.memory.visible_lines()
        self.assertEqual(next(row["role"] for row in visible if "working memory" in str(row)),
                         "agent_report")
        self.assertEqual(next(row["role"] for row in visible if "real tool failed" in str(row)),
                         "tool_observation")
        self.assertIn("real tool failed", fake.requests[2]["prompt"])

    def test_r2_revision_reload_and_pending_reference_invalidation(self):
        agent, fake, root = self.make("R2", [])
        bank = agent.memory
        old_handle = bank.register_leaf("e1", "task_instruction", "Keep WAL", 1,
                                        "initial_user_content", "1" * 64)
        old_ref = [{"source_handle": old_handle, "start_line": 1, "end_line": 1}]
        old_id = bank.save_sourced("knowledge", "Keep WAL", "task_requirement", old_ref)
        agent._memory_agent.last_delivery_status = "selected_validated_not_delivered"
        agent._memory_agent.last_reminder_refs = [{"id": old_id, "version": 1}]
        agent._memory_agent.last_reminder_identities = [agent._memory_agent._memory_identity(old_id)]
        new_handle = bank.register_leaf("e2", "tool_observation", "WAL has been removed", 2,
                                        "observation/tool_results/0/content", "2" * 64)
        new_ref = [{"source_handle": new_handle, "start_line": 1, "end_line": 1}]
        fake.replies.extend([LLMResponse(content="", tool_calls=[call("memory_reconcile",
            memory_id=old_id, decision="revise", reason="new tool observation",
            evidence_refs=new_ref, content="WAL absent", statement_type="tool_observation",
            source_refs=new_ref)]), LLMResponse(content="<no_intervention/>")])
        asyncio.run(agent._memory_agent.process("WAL has been removed", 2))
        self.assertFalse(agent._memory_agent.pending_refs_valid())
        self.assertIsNone(bank.get(old_id))
        new_id = bank.knowledge[0].id
        self.assertEqual(bank.search_knowledge("absent")[0].id, new_id)
        path = root / "bank.json"
        bank.save_to_file(path)
        loaded = SourceMemoryV2.load_from_file(path)
        self.assertEqual(loaded.knowledge[0].id, new_id)
        self.assertEqual(loaded.search_knowledge("absent")[0].id, new_id)
        self.assertTrue(any(h["action"] == "revise" for h in loaded.history))

    def test_bad_json_unknown_tool_and_missing_source_abort_without_mutation(self):
        agent, fake, _ = self.make("S2", [])
        bank = agent.memory
        handle = bank.register_leaf("e1", "task_instruction", "Keep WAL", 1,
                                    "initial_user_content", "3" * 64)
        ref = [{"source_handle": handle, "start_line": 1, "end_line": 1}]
        prior = bank.to_dict()
        fake.replies.extend([LLMResponse(content="", tool_calls=[
            call("memory_save_knowledge", content="Keep WAL", statement_type="task_requirement",
                 source_refs=ref),
            SimpleNamespace(function=SimpleNamespace(name="memory_delete", arguments="{bad-json")),
            call("memory_unknown", content="x")]), LLMResponse(content="<no_intervention/>")])
        asyncio.run(agent._memory_agent.process("Keep WAL", 1))
        self.assertNotEqual(bank.to_dict(), prior)
        self.assertEqual(len(bank.knowledge), 1)
        self.assertEqual([r["status"] for r in agent._memory_agent.last_receipts],
                         ["committed", "rejected", "rejected"])
        self.assertEqual(agent._memory_agent.last_receipts[2]["error_code"], "unknown_tool")

    def test_schema_and_local_validation_both_reject_nested_extra_and_coercion(self):
        agent, fake, _ = self.make("S2", [])
        bank = agent.memory
        handle = bank.register_leaf("e1", "task_instruction", "Keep WAL", 1,
                                    "initial_user_content", "3" * 64)
        bad_refs = [
            [{"source_handle": handle, "start_line": "1", "end_line": 1}],
            [{"source_handle": handle, "start_line": 1, "end_line": 1, "extra": True}],
        ]
        fake.replies.extend([LLMResponse(content="", tool_calls=[
            call("memory_save_knowledge", content="Keep WAL", statement_type="task_requirement",
                 source_refs=refs) for refs in bad_refs]),
            LLMResponse(content="<no_intervention/>")])
        asyncio.run(agent._memory_agent.process("Keep WAL", 1))
        self.assertEqual(bank.knowledge, [])
        self.assertEqual([r["error_code"] for r in agent._memory_agent.last_receipts],
                         ["argument_shape", "argument_shape"])
        nested = fake.requests[0]["tools"][0]["function"]["parameters"]["properties"][
            "source_refs"]["items"]
        self.assertFalse(nested["additionalProperties"])
        self.assertEqual(nested["required"], ["source_handle", "start_line", "end_line"])

    def test_host_integrity_exception_blocks_phase2_and_is_not_model_rejection(self):
        agent, fake, root = self.make("S2", [])
        fake.replies.append(LLMResponse(content="", tool_calls=[call(
            "memory_save_knowledge", content="Keep WAL", statement_type="task_requirement",
            source_refs=[{"source_handle": "irrelevant", "start_line": 1, "end_line": 1}])]))
        episode = PMAEpisode(agent, run_id="r", task_id="t", archive=root / "episode")
        event = {"kind": "task_start", "run_id": "r", "task_id": "t", "event_id": "e1",
                 "sequence": 1, "source_record_sha256": "9" * 64,
                 "initial_user_content": "Keep WAL"}
        handle = "s" + __import__("hashlib").sha256("e1:initial_user_content".encode()).hexdigest()[:12]
        fake.replies[0].tool_calls[0].function.arguments["source_refs"][0]["source_handle"] = handle
        with patch.object(SourceMemoryV2, "save_sourced", side_effect=OSError("disk-like host fault")):
            asyncio.run(episode.handle(event))
        self.assertEqual(len(fake.requests), 1)
        self.assertIsInstance(agent._memory_agent._fatal_error, OSError)
        self.assertEqual(agent.memory.knowledge, [])
        self.assertEqual(agent._memory_agent.last_receipts[0]["status"], "integrity_error")

    def test_real_litellm_serialization_boundary_with_local_only_response(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        profile = {"provider": "anthropic", "api_mode": "messages", "model": "claude-opus-4-8",
            "thinking_type": "adaptive", "reasoning_effort": "high", "temperature": 1,
            "max_tokens": 8192, "read_timeout": 300, "apibase": "https://offline.invalid",
            "apikey": "SENTINEL_DO_NOT_SEND"}
        agent = construct_upstream(Path(tmp.name) / "upstream", memory_profile=profile,
                                   research_candidate="S2")
        sent = []

        async def only_fake(**kwargs):
            sent.append(kwargs)
            if len(sent) > 2:
                raise AssertionError("unexpected model request")
            if len(sent) == 1:
                content_blocks = kwargs["messages"][-1]["content"]
                user_text = (content_blocks if isinstance(content_blocks, str) else
                             "".join(block["text"] for block in content_blocks if block.get("type") == "text"))
                source = next(row for row in json.loads(user_text.split(
                    "## Numbered visible public source leaves\n", 1)[1].split(
                    "\n## Previous phase-1 execution receipts", 1)[0])
                    if row["role"] == "task_instruction")
                args = json.dumps({"content": "Keep WAL", "statement_type": "task_requirement",
                    "source_refs": [{"source_handle": source["source_handle"],
                                     "start_line": 1, "end_line": 1}]})
                tool_calls = [{"id": "local-1", "type": "function", "function": {
                    "name": "memory_save_knowledge", "arguments": args}}]
                content = ""
            else:
                tool_calls = None
                content = "<no_intervention/>"
            return litellm.ModelResponse(model="claude-opus-4-8", choices=[{
                "message": {"content": content, "tool_calls": tool_calls},
                "finish_reason": "stop"}], usage={"prompt_tokens": 2, "completion_tokens": 1})

        episode = PMAEpisode(agent, run_id="r", task_id="t", archive=Path(tmp.name) / "archive")
        event = {"kind": "task_start", "run_id": "r", "task_id": "t", "event_id": "e1",
                 "sequence": 1, "source_record_sha256": "9" * 64,
                 "initial_user_content": "Keep WAL and diagnose recovery."}
        with patch("litellm.acompletion", only_fake):
            asyncio.run(episode.handle(event))
        self.assertEqual(len(sent), 2)
        self.assertEqual(sent[0]["model"], "anthropic/claude-opus-4-8")
        self.assertEqual(sent[0]["max_tokens"], 8192)
        self.assertEqual(sent[0]["thinking"], {"type": "adaptive"})
        self.assertEqual(sent[0]["reasoning_effort"], "high")
        self.assertIn("start_line", json.dumps(sent[0]["tools"]))
        self.assertNotIn("tools", sent[1])
        self.assertIn("committed", json.dumps(sent[1]["messages"][-1]["content"]))
        self.assertEqual(len(agent.memory.knowledge), 1)

    def test_archived_escaped_stdout_is_explicitly_decoded_and_bounded(self):
        case = json.loads(MANIFEST_V2.read_text(encoding="utf-8"))["cases"][0]
        events = projected_events(case, "r")[:3]
        agent, fake, root = self.make("S2", [LLMResponse(content="", tool_calls=[]),
            LLMResponse(content="<no_intervention/>"), LLMResponse(content="", tool_calls=[]),
            LLMResponse(content="<no_intervention/>")])
        episode = PMAEpisode(agent, run_id="r", task_id=case["task"], archive=root / "episode")
        for event in events:
            asyncio.run(episode.handle(event))
        decoded = next(row for row in agent.memory.sources.values()
                       if row.get("field_path") == "observation/tool_results/0/content/stdout")
        self.assertIn("drwx", decoded["text"])
        self.assertIn("\n", decoded["text"])
        self.assertEqual(decoded["raw_sha256"], events[2]["source_record_sha256"])
        selection = {"source_handle": decoded["handle"], "start_line": 1, "end_line": 1}
        ref = agent.memory.resolve_refs([selection], "tool_observation")[0]
        self.assertTrue(agent.memory.source_ref_valid(ref))
        with self.assertRaises(ValueError):
            agent.memory.resolve_refs([{**selection, "source_handle": "wrong"}], "tool_observation")
