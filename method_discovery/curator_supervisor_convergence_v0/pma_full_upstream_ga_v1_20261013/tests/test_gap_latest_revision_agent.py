"""Deterministic latest-revision adapter tests, without provider requests."""
import asyncio
from copy import deepcopy
import json
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from gap_evidence import SourceScopeError, sha256
from gap_prompts import MAINTENANCE, phase2_system
from latest_evidence_gap_agent import LatestEvidenceGapMemoryAgent, latest_phase1_system
from latest_evidence_gap_store import LatestEvidenceGapMemory
from memory_agent.memory.memory_agent import MemoryAgent, PHASE1_SYSTEM


RAW = "unchanged retrieval query"
TEXT = "The check passed with all assertions enabled."


def reply(calls=(), content=""):
    return NS(content=content, tool_calls=[NS(function=NS(name=name, arguments=json.dumps(args)))
                                         for name, args in calls])


def block(text=TEXT):
    return [{"source_id": "event-1", "role": "tool_observation", "text": text,
             "order": 1, "field_path": "tool_result", "record_digest": sha256(text),
             "record_digest_kind": "public_event", "tool_call_id": "call-1"}]


class Model:
    def __init__(self, calls):
        self.calls, self.inputs = calls, []

    async def call(self, **kwargs):
        self.inputs.append(deepcopy(kwargs))
        if len(self.inputs) == 1:
            return reply(self.calls)
        if len(self.inputs) == 2:
            return reply(content="<no_intervention/>")
        raise AssertionError("extra model call")


class LatestRevisionAgentTests(unittest.TestCase):
    def cycle(self, calls=(), bank=None, text=TEXT, structured=True):
        bank = bank if bank is not None else LatestEvidenceGapMemory()
        model = Model(calls)
        agent = LatestEvidenceGapMemoryAgent(task="task", memory=bank, llm=model,
                                             use_structured_tools=structured)
        agent.prepare_visible_context(RAW, block(text))
        result = asyncio.run(agent.process(RAW, 2))
        self.assertEqual(len(model.inputs), 2)
        self.assertEqual(model.inputs[1]["system"], phase2_system())
        self.assertNotIn("Pending unbound proposals", model.inputs[1]["prompt"])
        bank.validate_bank()
        return agent, result, model

    def test_bound_to_unbound_becomes_latest_in_both_phases(self):
        bank = LatestEvidenceGapMemory()
        self.cycle([("memory_save_gap", {"content": "original gap", "evidence": [{"quote": TEXT}]})], bank)
        key = bank.entries[0].id
        old_revision = bank.active_revisions[key]
        agent, result, model = self.cycle([
            ("memory_save_gap", {"memory_id": key, "content": "latest uncertain gap"})], bank)
        self.assertTrue(result.operations[0].success)
        self.assertEqual(bank.entries[0].id, key)
        self.assertEqual(bank.entries[0].content, "latest uncertain gap")
        self.assertNotEqual(bank.active_revisions[key], old_revision)
        self.assertEqual(bank.binding(key).status, "unbound")
        self.assertEqual(bank.pending_proposals, {})
        self.assertEqual(len(bank.tombstones), 0)
        self.assertIn("latest uncertain gap", model.inputs[1]["prompt"])
        _, _, next_model = self.cycle(bank=bank)
        self.assertIn("latest uncertain gap", next_model.inputs[0]["prompt"])
        self.assertIn("binding_status=unbound", next_model.inputs[0]["prompt"])
        self.assertNotIn("original gap", next_model.inputs[0]["prompt"])
        outcome = agent.last_evidence_report["operations"][0]
        self.assertEqual(outcome["content_status"], "committed")
        self.assertIsNone(outcome["binding_error"])

    def test_malformed_evidence_commits_content_but_invalid_target_rejects(self):
        for evidence in (None, "bad", [None], [{"quote": 3}]):
            with self.subTest(evidence=evidence):
                agent, result, _ = self.cycle([
                    ("memory_save_gap", {"content": "retained", "evidence": evidence}),
                    ("memory_save_gap", {"memory_id": "missing", "content": "bad target", "evidence": evidence}),
                    ("memory_save_knowledge", {"content": "sibling"})])
                self.assertEqual([op.success for op in result.operations], [True, False, True])
                self.assertEqual([entry.content for entry in agent.memory.entries], ["retained"])
                self.assertEqual(agent.memory.binding(agent.memory.entries[0].id).status, "error")
                outcome = agent.last_evidence_report["operations"][0]
                self.assertEqual(outcome["content_status"], "committed")
                self.assertIn(outcome["binding_error"], {"invalid_evidence", "invalid_evidence_item"})
                self.assertTrue(agent.last_evidence_report["partial_success"])

    def test_target_and_content_are_validated_before_matching(self):
        bank = LatestEvidenceGapMemory()
        key = bank.save_knowledge("knowledge")
        with patch("latest_evidence_gap_agent.align_graded_evidence") as matcher:
            _, result, _ = self.cycle([
                ("memory_save_gap", {"content": "wrong category", "memory_id": key}),
                ("memory_save_gap", {"content": "  "})], bank)
        matcher.assert_not_called()
        self.assertFalse(any(op.success for op in result.operations))

    def test_catalog_integrity_failure_never_becomes_binding_error_commit(self):
        with patch("latest_evidence_gap_agent.align_graded_evidence",
                   side_effect=SourceScopeError("invalid_source_snapshot")):
            agent, result, _ = self.cycle([("memory_save_gap", {"content": "not committed"})])
        self.assertFalse(result.operations[0].success)
        self.assertEqual(agent.memory.entries, [])

    def test_malformed_evidence_does_not_mask_corrupt_catalog(self):
        with patch("latest_evidence_gap_agent._validate_catalog",
                   side_effect=SourceScopeError("invalid_source_snapshot")):
            agent, result, _ = self.cycle([("memory_save_gap", {
                "content": "not committed", "evidence": None})])
        self.assertFalse(result.operations[0].success)
        self.assertEqual(agent.memory.entries, [])

    def test_status_bound_to_unbound_latest_is_shown_in_both_phases(self):
        bank = LatestEvidenceGapMemory()
        self.cycle([("memory_update_status", {"content": "old status",
                     "evidence": [{"quote": TEXT}]})], bank)
        _, _, model = self.cycle([("memory_update_status", {"content": "new uncertain status"})], bank)
        self.assertEqual(bank.status, "new uncertain status")
        self.assertEqual(bank.binding("status").status, "unbound")
        self.assertIn("new uncertain status", model.inputs[1]["prompt"])
        _, _, later = self.cycle(bank=bank)
        self.assertIn("new uncertain status", later.inputs[0]["prompt"])
        self.assertNotIn("old status", later.inputs[0]["prompt"])
        self.assertEqual(bank.pending_proposals, {})

    def test_xml_parser_is_reused_for_optional_evidence(self):
        model = Model([])
        original_call = model.call
        async def xml_call(**kwargs):
            response = await original_call(**kwargs)
            if len(model.inputs) == 1:
                response = reply(content=("<tool_call><function=memory_save_gap>"
                    "<parameter=content>XML latest</parameter>"
                    "<parameter=evidence>not json</parameter></function></tool_call>"))
            return response
        model.call = xml_call
        bank = LatestEvidenceGapMemory()
        agent = LatestEvidenceGapMemoryAgent(task="task", memory=bank, llm=model,
                                             use_structured_tools=False)
        agent.prepare_visible_context(RAW, block())
        result = asyncio.run(agent.process(RAW, 2))
        self.assertTrue(result.operations[0].success)
        self.assertEqual(bank.entries[0].content, "XML latest")
        self.assertEqual(bank.binding(bank.entries[0].id).status, "error")
        self.assertEqual(len(model.inputs), 2)
        self.assertNotIn("tools", model.inputs[0])
        bank.validate_bank()

    def test_original_five_tools_two_calls_and_effective_revision_prompts(self):
        for structured in (True, False):
            with self.subTest(structured=structured):
                bank = LatestEvidenceGapMemory()
                old = bank.save_gap("retire this")
                calls = [(name, {"content": name}) for name in (
                    "memory_save_gap", "memory_save_knowledge", "memory_save_procedural", "memory_update_status")]
                calls.append(("memory_delete", {"memory_id": old}))
                with patch.object(MemoryAgent, "process", autospec=True,
                                  side_effect=MemoryAgent.process) as process:
                    agent, result, model = self.cycle(calls, bank, structured=structured)
                process.assert_called_once()
                self.assertTrue(all(op.success for op in result.operations))
                self.assertEqual({tool["function"]["name"] for tool in agent.get_tools_schema()},
                                 {name for name, _ in calls})
                sent = model.inputs[0]["system"]
                self.assertEqual(sent, latest_phase1_system())
                self.assertNotIn("To revise, delete", sent)
                self.assertNotIn("delete-and-save", sent)
                self.assertNotIn("Delete entries that are superseded", sent)
                self.assertNotIn("An unbound replacement cannot overwrite", sent)
                self.assertIn("Every valid save becomes the latest content", sent)
                self.assertIn("optional evidence", sent)
                self.assertIn("content_status=committed; binding_status=unbound", model.inputs[1]["prompt"])
                self.assertIn("Status binding:", model.inputs[1]["prompt"])
                _, _, later = self.cycle(bank=bank)
                self.assertIn("status (status; derived memory)", later.inputs[0]["prompt"])
        self.assertIn("Delete entries that are superseded", PHASE1_SYSTEM)
        self.assertIn("delete-and-save", MAINTENANCE)

    def test_nonexact_source_excerpt_is_not_the_model_quote(self):
        cases = [("The  check passed with all assertions enabled.", "normalized_unique"),
                 ("The check passed with most assertions enabled.", "fuzzy_candidate")]
        for quote, expected in cases:
            with self.subTest(expected=expected):
                agent, _, model = self.cycle([("memory_save_gap", {
                    "content": "interpretation", "evidence": [{"quote": quote}]})])
                key = agent.memory.entries[0].id
                self.assertEqual(agent.memory.binding(key).status, expected)
                rendered = model.inputs[1]["prompt"]
                self.assertIn('model-supplied quote=' + json.dumps(quote), rendered)
                self.assertIn('actual source excerpt=' + json.dumps(TEXT), rendered)
                self.assertNotIn('actual source excerpt=' + json.dumps(quote), rendered)
                self.assertIn("NOT truth probabilities", rendered)
                self.assertIn("tool_observation", rendered)

    def test_cycle_metrics_count_committed_writes_not_deletes_or_claim_truth(self):
        bank = LatestEvidenceGapMemory()
        retire = bank.save_gap("retire")
        target = bank.save_knowledge("revise twice")
        agent, result, _ = self.cycle([
            ("memory_save_knowledge", {"memory_id": target, "content": "exact revision",
                                       "evidence": [{"quote": TEXT}]}),
            ("memory_save_knowledge", {"memory_id": target, "content": "error revision",
                                       "evidence": None}),
            ("memory_save_gap", {"content": "approximate claim", "evidence": [
                {"quote": "The check passed with most assertions enabled."}]}),
            ("memory_save_procedural", {"content": "uncited claim"}),
            ("memory_save_gap", {"memory_id": "missing", "content": "invalid target"}),
            ("memory_delete", {"memory_id": retire})], bank)
        report = agent.last_evidence_report
        self.assertEqual([op.success for op in result.operations], [True, True, True, True, False, True])
        self.assertEqual(report["content_writes_committed"], 4)
        self.assertEqual(report["binding_errors"], 1)
        self.assertEqual(report["binding_grade_counts"], {
            "exact_unique": 1, "exact_multiple": 0, "normalized_unique": 0,
            "normalized_multiple": 0, "fuzzy_candidate": 1, "unbound": 1, "error": 1})
        self.assertEqual(report["provenance_disposition_counts"], {
            "raw": {"bound": 1, "unbound": 1}, "derived": {"bound": 0, "unbound": 0},
            "mixed": {"bound": 0, "unbound": 0}, "none": {"bound": 0, "unbound": 2}})
        self.assertEqual(report["operations"][0]["provenance_summary"], "raw")
        self.assertEqual(report["operations"][1]["provenance_summary"], "none")
        empty, _, _ = self.cycle(bank=bank)
        self.assertEqual(empty.last_evidence_report["content_writes_committed"], 0)
        self.assertEqual(sum(empty.last_evidence_report["binding_grade_counts"].values()), 0)

    def test_effective_tool_schema_requires_only_content_and_optional_quote_hint(self):
        agent, _, _ = self.cycle()
        for tool in agent.get_tools_schema():
            function = tool["function"]
            params = function["parameters"]
            if function["name"] == "memory_delete":
                self.assertEqual(params["required"], ["memory_id"])
                continue
            self.assertEqual(params["required"], ["content"])
            evidence = params["properties"]["evidence"]
            self.assertNotIn("minItems", evidence)
            self.assertEqual(evidence["items"]["required"], ["quote"])
            self.assertEqual(set(evidence["items"]["properties"]), {"source", "quote"})
            self.assertNotIn("minLength", evidence["items"]["properties"]["quote"])
            self.assertNotIn("unique", function["description"].lower())
            self.assertNotIn("required evidence", function["description"].lower())

    def test_derived_memory_match_is_not_semantic_proof(self):
        bank = LatestEvidenceGapMemory()
        self.cycle([("memory_save_gap", {"content": "fallible prior claim"})], bank)
        agent, _, model = self.cycle([("memory_save_knowledge", {
            "content": "derived claim", "evidence": [{"quote": "fallible prior claim"}]})], bank)
        self.assertIn("derived memory [", model.inputs[1]["prompt"])
        self.assertIn("not independent observation", model.inputs[1]["prompt"])
        self.assertIn("NOT semantic proof", model.inputs[1]["prompt"])
        self.assertEqual(agent.memory.binding(bank.knowledge[0].id).status, "exact_unique")


if __name__ == "__main__":
    unittest.main()
