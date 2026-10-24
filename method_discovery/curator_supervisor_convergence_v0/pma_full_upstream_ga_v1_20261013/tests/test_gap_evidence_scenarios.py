"""Scripted semantic scenarios test wiring, not model reasoning or entailment."""
import asyncio
from copy import deepcopy
import json
import re
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from evidence_gap_agent import EvidenceGapMemoryAgent
from evidence_gap_store import EvidenceGapMemory
from gap_evidence import sha256
from gap_memory_agent import GapMemoryAgent


TASK = "Implement ascending sorting and demonstrate correctness, not just output length."
CODE = "def test_sort():\n    result = sort_values([3, 1, 2])\n    assert len(result) == 3\n"


def source(text, role="task_instruction", event="task"):
    return {"source_id": event, "role": role, "text": text, "order": 0,
            "field_path": "task" if role == "task_instruction" else "tool_result",
            "record_digest": sha256(text), "record_digest_kind": "public_event"}


def response(calls=(), content=""):
    return NS(content=content, tool_calls=[
        NS(function=NS(name=name, arguments=json.dumps(args))) for name, args in calls])


def cite(prompt, role, quote):
    # Resolve only a handle in the submitted visible source block, not a fabricated ID.
    matches = re.finditer(r"\[(s[0-9a-f]+) " + role + r"\b[^\]\n]*\]\n", prompt)
    for match in matches:
        end = re.search(r"\n\[s[0-9a-f]+ ", prompt[match.end():])
        text = prompt[match.end():match.end() + end.start()] if end else prompt[match.end():]
        if quote in text:
            return [{"source": match[1], "quote": quote}]
    raise AssertionError(f"No visible {role} source containing {quote!r}")


class ScriptedModel:
    def __init__(self, plan):
        self.plan = plan
        self.inputs = []

    async def call(self, **kwargs):
        self.inputs.append(deepcopy(kwargs))
        if len(self.inputs) == 1:
            return response(self.plan(kwargs["prompt"]))
        if len(self.inputs) == 2:
            return response(content="<context_for_action>Investigate the open gap.</context_for_action>")
        raise AssertionError("Unexpected model stage")


class GapEvidenceScenarioTests(unittest.TestCase):
    def cycle(self, plan, blocks, bank=None):
        bank = EvidenceGapMemory() if bank is None else bank
        raw = "\n".join(block["text"] for block in blocks)
        model = ScriptedModel(plan)
        agent = EvidenceGapMemoryAgent(task=TASK, memory=bank, llm=model,
                                       use_structured_tools=True)
        agent.prepare_visible_context(raw, blocks)
        result = asyncio.run(agent.process(raw, 4))
        self.assertEqual(len(model.inputs), 2)
        self.assertEqual({tool["function"]["name"] for tool in model.inputs[0]["tools"]},
                         {"memory_save_knowledge", "memory_save_procedural",
                          "memory_update_status", "memory_delete", "memory_save_gap"})
        self.assertEqual(len(model.inputs[0]["tools"]), 5)
        self.assertNotIn("tools", model.inputs[1])
        self.assertEqual(model.inputs[1]["prompt"],
                         GapMemoryAgent(task=TASK, memory=bank)._build_phase2_prompt(raw, 4))
        self.assertTrue(result.should_inject)
        bank.validate_bank()
        return agent, result, model

    def test_information_gap_can_be_inferred_from_requirement_without_failure(self):
        task = "Generate a report using the customer's agreed fiscal-year boundary."
        gap = "The fiscal-year boundary has not been supplied; ask before selecting dates."
        agent, result, model = self.cycle(lambda prompt: [("memory_save_gap", {
            "content": gap, "evidence": cite(prompt, "task_instruction", task)})], [source(task)])
        self.assertTrue(result.operations[0].success)
        self.assertEqual([entry.content for entry in agent.gaps.entries], [gap])
        self.assertNotIn(gap, task)  # NL inference is not required to be a source substring.
        receipt = next(iter(agent.memory.receipts.values()))
        self.assertEqual([ref.role for ref in receipt.bound_refs], ["task_instruction"])
        self.assertNotIn("tool_observation", model.inputs[0]["prompt"])
        self.assertIn(gap, model.inputs[1]["prompt"])

    def test_test_quality_gap_cites_visible_code_not_a_failed_result(self):
        gap = "The sorting test only asserts length; ascending order remains untested."
        blocks = [source(TASK), source(CODE, "tool_observation", "read-test-file")]
        agent, result, model = self.cycle(lambda prompt: [("memory_save_gap", {
            "content": gap,
            "evidence": cite(prompt, "tool_observation", "assert len(result) == 3")})], blocks)
        self.assertTrue(result.operations[0].success)
        self.assertEqual(agent.gaps.entries[0].content, gap)
        self.assertNotIn(gap, CODE)
        self.assertIn(CODE, model.inputs[0]["prompt"])
        receipt = next(iter(agent.memory.receipts.values()))
        ref = receipt.bound_refs[0]
        retained = agent.memory.blobs[ref.source_text_sha256]
        self.assertEqual(retained, CODE)
        self.assertEqual(retained[ref.start:ref.end], "assert len(result) == 3")
        self.assertIn(gap, model.inputs[1]["prompt"])

    def test_achievement_gap_revision_and_procedure_retain_deleted_parent(self):
        bank = EvidenceGapMemory()
        old_text = "Sorting correctness still lacks a result assertion."
        self.cycle(lambda prompt: [("memory_save_gap", {"content": old_text,
            "evidence": cite(prompt, "task_instruction", TASK)})], [source(TASK)], bank)
        old = bank.entries[0].id
        parent_revision = bank.active_revisions[old]
        parent_receipt = bank.revisions[parent_revision].receipt_id
        repaired = "assert sort_values([3, 1, 2]) == [1, 2, 3]"
        new_text = "The example now asserts ascending order; duplicate-input behavior is still unverified."
        procedure = "For sorting, assert output values as well as length, and cover duplicates."

        def plan(prompt):
            prior = cite(prompt, "memory_derived", old_text)
            observed = cite(prompt, "tool_observation", repaired)
            return [("memory_delete", {"memory_id": old}),
                    ("memory_save_gap", {"content": new_text, "evidence": prior + observed}),
                    ("memory_save_procedural", {"content": procedure, "evidence": prior + observed})]

        agent, result, model = self.cycle(plan, [source(TASK),
            source(repaired, "tool_observation", "read-repaired-test")], bank)
        self.assertTrue(all(op.success for op in result.operations))
        self.assertEqual([op.action for op in result.operations],
                         ["delete_gap", "save_gap", "save_procedural"])
        self.assertEqual([entry.content for entry in bank.entries], [new_text])
        self.assertEqual([entry.content for entry in bank.procedural], [procedure])
        self.assertNotIn(old, bank.active_revisions)
        self.assertTrue(any(t.revision_id == parent_revision for t in bank.tombstones.values()))
        self.assertIn(parent_receipt, bank.receipts)
        for key in [bank.entries[0].id, bank.procedural[0].id]:
            receipt = bank.receipts[bank.revisions[bank.active_revisions[key]].receipt_id]
            prior = next(ref for ref in receipt.bound_refs if ref.role == "memory_derived")
            self.assertEqual(prior.parent_revision_id, parent_revision)
            self.assertEqual(bank.blobs[bank.revisions[parent_revision].content_sha256], old_text)
        self.assertNotIn(old_text, model.inputs[1]["prompt"])
        self.assertIn(new_text, model.inputs[1]["prompt"])
        restored = EvidenceGapMemory.from_dict(bank.to_dict())
        restored.validate_bank()
        self.assertEqual(restored.to_dict(), bank.to_dict())

    def test_invalid_achievement_gap_replacement_is_atomic_and_phase2_runs(self):
        bank = EvidenceGapMemory()
        old_text = "The requested ascending result has not yet been demonstrated."
        old = bank.save_gap(old_text)
        before = bank.to_dict()

        def plan(prompt):
            evidence = cite(prompt, "task_instruction", TASK)
            evidence[0]["quote"] = "invented observation: all sorting properties verified"
            return [("memory_delete", {"memory_id": old}),
                    ("memory_save_gap", {"content": "Only performance remains.", "evidence": evidence})]

        agent, result, model = self.cycle(plan, [source(TASK)], bank)
        self.assertFalse(agent.last_evidence_report["accepted"])
        self.assertTrue(any(not op.success for op in result.operations))
        self.assertEqual(bank.to_dict(), before)
        self.assertIn(old_text, model.inputs[1]["prompt"])
        self.assertNotIn("Only performance remains.", model.inputs[1]["prompt"])

    def test_all_gap_scenarios_survive_ordinary_bm25_filtering_above_fifty(self):
        bank = EvidenceGapMemory()
        for n in range(52):
            bank.save_knowledge(f"Ordinary unrelated retained fact number {n}.")
        gaps = ["Information gap: the input domain is unspecified.",
                "Achievement gap: requested descending mode has no demonstration.",
                "Test-quality gap: sorting test only asserts length."]
        for gap in gaps:
            bank.save_gap(gap)
        with patch.object(bank, "search_knowledge", return_value=bank.knowledge[:1]) as search, \
                patch.object(bank, "search_procedural", return_value=[]):
            _, _, model = self.cycle(lambda prompt: [], [source(TASK)], bank)
        self.assertTrue(search.called)
        self.assertTrue(all(call.args[0] == TASK for call in search.call_args_list))
        for request in model.inputs:
            self.assertIn(bank.knowledge[0].content, request["prompt"])
            self.assertNotIn(bank.knowledge[-1].content, request["prompt"])
            for gap in gaps:
                self.assertIn(gap, request["prompt"])
        self.assertIn("knowledge 1/52", model.inputs[0]["prompt"])
        self.assertIn("gap 3/3", model.inputs[0]["prompt"])
        self.assertIn("## Separate Gap View", model.inputs[1]["prompt"])


if __name__ == "__main__":
    unittest.main()
