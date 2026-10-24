import asyncio
from copy import deepcopy
import json
import re
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from evidence_gap_agent import EvidenceGapMemoryAgent, WRITERS
from evidence_gap_store import EvidenceGapMemory
from gap_evidence import sha256
from gap_memory_agent import GapMemoryAgent
from gap_store import GapMemory
from memory_agent.memory.memory_agent import BANK_TOOLS, MemoryAgent


RAW = "RAW_COMPOUND_CONTEXT (kept only for retrieval and phase 2)"
TEXT = '{"result": "check passed", "exit_code": 0}'


def blocks():
    return [{"source_id": "event-1", "role": "tool_observation", "text": TEXT,
             "order": 1, "field_path": "tool_result", "record_digest": sha256(TEXT),
             "record_digest_kind": "public_event", "tool_call_id": "call-1"}]


def reply(calls=(), content=""):
    return NS(content=content, tool_calls=[NS(function=NS(name=n, arguments=json.dumps(a)))
                                         for n, a in calls])


class Model:
    def __init__(self, plan):
        self.plan = plan
        self.inputs = []

    async def call(self, **kwargs):
        self.inputs.append(deepcopy(kwargs))
        if len(self.inputs) == 1:
            match = re.search(r"\[(s[0-9a-f]+) tool_observation\]", kwargs["prompt"])
            evidence = [{"source": match[1] if match else "unavailable", "quote": "check passed"}]
            return self.plan(evidence)
        if len(self.inputs) == 2:
            return reply(content="<context_for_action>Check the remaining scope.</context_for_action>")
        raise AssertionError("extra model call")


class EvidenceAgentTests(unittest.TestCase):
    def run_cycle(self, plan, bank=None, prepare=True, raw=RAW, structured=True):
        bank = EvidenceGapMemory() if bank is None else bank
        model = Model(plan)
        agent = EvidenceGapMemoryAgent(task="task", memory=bank, llm=model,
                                       use_structured_tools=structured)
        if prepare:
            agent.prepare_visible_context(RAW, blocks())
        result = asyncio.run(agent.process(raw, 7))
        self.assertEqual(len(model.inputs), 2)
        self.assertTrue(result.should_inject)
        self.assertIs(agent.memory, bank)
        self.assertIs(agent.gaps, bank)
        expected = GapMemoryAgent(task="task", memory=bank)._build_phase2_prompt(raw, 7)
        self.assertEqual(model.inputs[1]["prompt"], expected)
        return agent, result, model

    def test_all_five_tools_and_exact_phase2(self):
        bank = EvidenceGapMemory(max_status_length=8)
        old = bank.save_gap("old gap")
        def plan(evidence):
            return reply([(name, {"content": kind + " observed", "evidence": evidence})
                          for name, kind in WRITERS.items()] +
                         [("memory_delete", {"memory_id": old})])
        with patch.object(MemoryAgent, "process", autospec=True,
                          side_effect=MemoryAgent.process) as original:
            agent, result, model = self.run_cycle(plan, bank)
        original.assert_called_once()
        self.assertTrue(all(op.success for op in result.operations))
        self.assertEqual(len(result.operations), 5)
        self.assertEqual(len(bank.receipts), 4)
        self.assertEqual(len(bank.tombstones), 1)
        baseline = GapMemory(max_status_length=8)
        baseline.update_status("status observed")
        self.assertEqual(bank.status, baseline.status)
        status = bank.revisions[bank.active_revisions["status"]]
        self.assertEqual(status.content_sha256, sha256(bank.status))
        self.assertEqual(status.proposal_sha256, sha256("status observed"))
        self.assertNotIn(RAW, model.inputs[0]["prompt"])
        self.assertEqual(model.inputs[0]["prompt"].count(TEXT), 1)
        self.assertIn(RAW, model.inputs[1]["prompt"])
        self.assertTrue(agent.last_evidence_report["accepted"])
        bank.validate_bank()

    def test_failed_binding_after_delete_preserves_whole_bank(self):
        bank = EvidenceGapMemory()
        old = bank.save_gap("old gap")
        before = bank.to_dict()
        def plan(evidence):
            evidence[0]["quote"] = "absent quote"
            return reply([("memory_delete", {"memory_id": old}),
                          ("memory_save_gap", {"content": "replacement", "evidence": evidence})])
        agent, result, _ = self.run_cycle(plan, bank)
        self.assertEqual(bank.to_dict(), before)
        self.assertFalse(result.operations[0].success)
        self.assertFalse(agent.last_evidence_report["accepted"])

    def test_preflight_rejects_every_malformed_batch_without_partial_write(self):
        bad_arguments = ["{", "[]", "null"]
        for arguments in bad_arguments:
            with self.subTest(arguments=arguments):
                def plan(evidence):
                    good = reply([("memory_save_gap", {"content": "new", "evidence": evidence})])
                    good.tool_calls.append(NS(function=NS(name="memory_save_gap", arguments=arguments)))
                    return good
                agent, result, _ = self.run_cycle(plan)
                self.assertFalse(result.operations[0].success)
                self.assertEqual(agent.memory.entries, [])
        for name, args in [("unknown", {}), ("memory_delete", {"memory_id": "missing"}),
                           ("memory_delete", {"memory_id": ["bad"]}),
                           ("memory_save_gap", {"content": "missing evidence"})]:
            with self.subTest(name=name, args=args):
                agent, result, _ = self.run_cycle(lambda evidence: reply([
                    ("memory_save_gap", {"content": "new", "evidence": evidence}), (name, args)]))
                self.assertFalse(result.operations[0].success)
                self.assertEqual(agent.memory.entries, [])

    def test_strict_evidence_and_unknown_fields(self):
        for mutate in [lambda e: [], lambda e: [dict(e[0], role="tool_observation")],
                       lambda e: [{"source": "invented", "quote": "check passed"}],
                       lambda e: [{"source": e[0]["source"], "quote": ""}]]:
            agent, result, _ = self.run_cycle(lambda e: reply([
                ("memory_save_knowledge", {"content": "fact", "evidence": mutate(e)})]))
            self.assertFalse(result.operations[0].success)
            self.assertEqual(agent.memory.knowledge, [])

    def test_xml_evidence_and_structured_precedence(self):
        def xml(evidence):
            return reply(content="<tool_call><function=memory_save_gap>"
                         "<parameter=content>bounded gap</parameter>"
                         f"<parameter=evidence>{json.dumps(evidence)}</parameter>"
                         "</function></tool_call>")
        agent, result, model = self.run_cycle(xml, structured=False)
        self.assertEqual(agent.memory.entries[0].content, "bounded gap")
        self.assertTrue(result.operations[0].success)
        self.assertNotIn("tools", model.inputs[0])
        bank = EvidenceGapMemory()
        old = bank.save_gap("delete only")
        def both(evidence):
            response = xml(evidence)
            response.tool_calls = reply([("memory_delete", {"memory_id": old})]).tool_calls
            return response
        agent, result, _ = self.run_cycle(both, bank)
        self.assertEqual(bank.entries, [])
        self.assertEqual(len(result.operations), 1)
        self.assertEqual(len(bank.receipts), 0)

    def test_malformed_xml_never_silently_drops_operation(self):
        for tail in ["<tool_call>", "<tool_call>bad</tool_call>",
                     "<tool_call><function=unknown></function></tool_call>"]:
            def plan(evidence):
                return reply(content="<tool_call><function=memory_save_gap>"
                    "<parameter=content>new</parameter>"
                    f"<parameter=evidence>{json.dumps(evidence)}</parameter>"
                    "</function></tool_call>" + tail)
            agent, result, _ = self.run_cycle(plan)
            self.assertEqual(agent.memory.entries, [])
            self.assertFalse(result.operations[0].success)

    def test_missing_or_stale_preparation_does_not_abort_phase2(self):
        for prepare, raw in [(False, RAW), (True, "different raw")]:
            agent, result, _ = self.run_cycle(lambda e: reply([
                ("memory_save_gap", {"content": "new", "evidence": e})]),
                prepare=prepare, raw=raw)
            self.assertFalse(result.operations[0].success)
            self.assertEqual(agent.memory.entries, [])
            self.assertTrue(agent.last_evidence_report["errors"])

    def test_empty_batch_is_noop_and_legacy_entries_remain_unbound(self):
        bank = EvidenceGapMemory()
        key = bank.save_knowledge("legacy unbound")
        before = bank.to_dict()
        agent, result, _ = self.run_cycle(lambda e: reply(), bank)
        self.assertEqual(result.operations, [])
        self.assertEqual(bank.to_dict(), before)
        self.assertNotIn(key, bank.active_revisions)
        self.assertTrue(agent.last_evidence_report["accepted"])

    def test_derived_precycle_memory_is_citable_and_new_output_is_not(self):
        bank = EvidenceGapMemory()
        bank.save_gap("prior bounded inference")
        model = Model(lambda e: reply())
        async def call(**kwargs):
            model.inputs.append(deepcopy(kwargs))
            if len(model.inputs) == 1:
                handle = re.search(r"\[(s[0-9a-f]+) memory_derived\]", kwargs["prompt"])[1]
                return reply([("memory_save_procedural", {"content": "retained inference",
                    "evidence": [{"source": handle, "quote": "prior bounded inference"}]})])
            return reply(content="<no_intervention/>")
        model.call = call
        agent = EvidenceGapMemoryAgent(task="task", memory=bank, llm=model)
        agent.prepare_visible_context(RAW, blocks())
        result = asyncio.run(agent.process(RAW))
        self.assertTrue(result.operations[0].success)
        receipt = next(iter(bank.receipts.values()))
        self.assertEqual(receipt.bound_refs[0].role, "memory_derived")
        self.assertNotIn("retained inference", model.inputs[0]["prompt"])

    def test_writer_failure_does_not_publish_any_staged_change(self):
        bank = EvidenceGapMemory()
        old = bank.save_gap("keep original")
        before = bank.to_dict()
        def plan(evidence):
            return reply([("memory_delete", {"memory_id": old}),
                ("memory_save_gap", {"content": "first", "evidence": evidence}),
                ("memory_save_procedural", {"content": "second", "evidence": evidence})])
        real = EvidenceGapMemory.apply_bound_write
        def failing(draft, kind, *args, **kwargs):
            if kind == "procedural":
                raise RuntimeError("injected writer failure")
            return real(draft, kind, *args, **kwargs)
        with patch.object(EvidenceGapMemory, "apply_bound_write", failing):
            agent, result, _ = self.run_cycle(plan, bank)
        self.assertEqual(bank.to_dict(), before)
        self.assertFalse(result.operations[0].success)
        self.assertIn("injected writer failure", agent.last_evidence_report["errors"])

    def test_invalid_preparation_and_consumed_preparation_are_nonfatal(self):
        bank = EvidenceGapMemory()
        model = Model(lambda e: reply())
        agent = EvidenceGapMemoryAgent(task="task", memory=bank, llm=model)
        malformed = blocks()
        del malformed[0]["record_digest"]
        agent.prepare_visible_context(RAW, malformed)
        asyncio.run(agent.process(RAW))
        self.assertTrue(agent.last_evidence_report["errors"])
        agent.prepare_visible_context(RAW, blocks())
        model.inputs.clear()
        asyncio.run(agent.process(RAW))
        self.assertEqual(agent.last_evidence_report["errors"], [])
        model.inputs.clear()
        asyncio.run(agent.process(RAW))
        self.assertIn("visible_context_not_prepared", agent.last_evidence_report["errors"])

    def test_bm25_catalog_contains_only_rendered_selected_memories(self):
        bank = EvidenceGapMemory()
        keys = [bank.save_knowledge(f"fact {n}") for n in range(52)]
        agent = EvidenceGapMemoryAgent(task="task", memory=bank)
        agent.prepare_visible_context(RAW, blocks())
        with patch.object(bank, "search_knowledge", return_value=bank.knowledge[:1]), \
                patch.object(bank, "search_procedural", return_value=[]):
            prompt = agent._build_phase1_prompt(RAW, 1)
        self.assertIn(keys[0], prompt)
        self.assertNotIn(keys[-1], prompt)
        derived = [v for v in agent._parts.catalog.values()
                   if v.snapshot.record.role == "memory_derived"]
        self.assertEqual(len(derived), 1)
        self.assertEqual(derived[0].snapshot.blob.text, "fact 0")
        self.assertEqual(agent._parts.manifest.request_sha256, sha256(prompt))
        self.assertEqual(len(bank.active_revisions), 0)

    def test_duplicate_delete_and_new_source_handles_reject_entire_batch(self):
        bank = EvidenceGapMemory()
        old = bank.save_gap("prior")
        before = bank.to_dict()
        _, result, _ = self.run_cycle(lambda e: reply([
            ("memory_delete", {"memory_id": old}),
            ("memory_delete", {"memory_id": old})]), bank)
        self.assertFalse(result.operations[0].success)
        self.assertEqual(bank.to_dict(), before)
        def plan(evidence):
            return reply([("memory_save_gap", {"content": "new", "evidence": evidence}),
                ("memory_save_procedural", {"content": "use new", "evidence": [
                    {"source": "new output", "quote": "new"}]})])
        _, result, _ = self.run_cycle(plan, bank)
        self.assertFalse(result.operations[0].success)
        self.assertEqual(bank.to_dict(), before)

    def test_raw_query_bm25_and_phase2_schema_unchanged(self):
        bank = EvidenceGapMemory()
        for n in range(52):
            bank.save_knowledge(f"fact {n}")
        with patch.object(bank, "search_knowledge", wraps=bank.search_knowledge) as search:
            _, _, model = self.run_cycle(lambda e: reply(), bank)
        self.assertTrue(all(call.args[0] == RAW for call in search.call_args_list))
        self.assertNotIn("tools", model.inputs[1])
        original = deepcopy(BANK_TOOLS)
        agent = EvidenceGapMemoryAgent(task="task", memory=EvidenceGapMemory())
        schema = agent.get_tools_schema()
        self.assertEqual(BANK_TOOLS, original)
        self.assertEqual(next(t for t in schema if t["function"]["name"] == "memory_delete"),
                         next(t for t in BANK_TOOLS if t["function"]["name"] == "memory_delete"))
        with self.assertRaises(TypeError):
            EvidenceGapMemoryAgent(task="task", memory=GapMemory())


if __name__ == "__main__":
    unittest.main()
