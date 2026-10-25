"""Offline integration contracts: retained uncertainty, provenance and two phases."""
import asyncio
from copy import deepcopy
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from aligned_evidence_gap_agent import AlignedEvidenceGapMemoryAgent
from aligned_evidence_gap_store import AlignedEvidenceGapMemory
from evidence_gap_store import History
from test_gap_evidence_agent import RAW, blocks, reply, Model


class AlignmentIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.bank = AlignedEvidenceGapMemory()

    def agent(self, blocks_override=None):
        agent = AlignedEvidenceGapMemoryAgent(task="task", memory=self.bank)
        agent.prepare_visible_context(RAW, blocks() if blocks_override is None else blocks_override)
        prompt = agent._build_phase1_prompt(RAW, 1)
        self.assertIsNotNone(agent._parts)
        return agent, prompt

    def execute(self, calls):
        agent, _ = self.agent()
        ops = agent._execute_tool_calls(reply(calls))
        self.bank.validate_bank()
        saved = self.bank.to_dict()
        self.assertEqual(AlignedEvidenceGapMemory.from_dict(saved).to_dict(), saved)
        return ops, agent

    def save(self, content="grounded claim", evidence=True, target=None, kind="gap"):
        args = {"content": content}
        if evidence is True:
            args["evidence"] = [{"quote": "check passed"}]
        elif evidence is not False:
            args["evidence"] = evidence
        if target:
            args["memory_id"] = target
        ops, agent = self.execute([("memory_update_status" if kind == "status" else "memory_save_" + kind, args)])
        self.assertTrue(ops[0].success, ops[0].error)
        return ops[0], agent

    def test_no_evidence_survives_both_views_and_roundtrip(self):
        op, agent = self.save("possible failure", False)
        self.assertEqual(op.write_outcome, "retained_unbound")
        self.assertEqual(agent.last_evidence_report["retained_unbound"], 1)
        self.assertEqual(agent.last_evidence_report["bound_writes"], 0)
        self.assertIn("possible failure", agent._build_phase2_prompt(RAW, 1))
        self.assertIn("disposition=unbound", agent._build_phase2_prompt(RAW, 1))
        _, prompt = self.agent()
        self.assertIn("possible failure", prompt)
        self.assertIn("disposition=unbound", prompt)
        self.assertIsNone(self.bank.revisions[self.bank.active_revisions[op.memory_id]].receipt_id)

    def test_optional_wrong_hint_is_not_authority(self):
        op, _ = self.save(evidence=[{"source": "invented hint", "quote": "check passed"}])
        self.assertEqual(op.binding_status, "exact_unique")
        self.assertEqual(op.binding_disposition, "bound")

    def test_empty_and_unmatched_quotes_retained(self):
        for evidence in ([], [{"quote": ""}], [{"quote": "not visible"}]):
            with self.subTest(evidence=evidence):
                op, _ = self.save(evidence=evidence)
                self.assertEqual(op.binding_disposition, "unbound")

    def test_partial_evidence_retains_found_sources_without_receipt(self):
        op, _ = self.save(evidence=[{"quote": "check passed"}, {"quote": "not visible"}])
        row = self.bank.binding(op.memory_id)
        value = json.loads(row.alignment_json)
        self.assertEqual(row.status, "unbound")
        self.assertEqual(len(value["bound_refs"]), 1)
        self.assertTrue(self.bank.sources)
        self.assertFalse(self.bank.receipts)

    def test_multiple_matches_are_alternatives_in_both_views(self):
        self.save("check passed", True)
        op, agent = self.save("repeated matching", [{"quote": "check passed"}])
        self.assertEqual(op.binding_status, "exact_multiple")
        self.assertIn("alternatives, not independent proof", agent._build_phase2_prompt(RAW, 1))
        _, prompt = self.agent()
        self.assertIn("literal_binding=exact_multiple", prompt)

    def test_protected_target_pending_revised_then_resolved(self):
        original, _ = self.save()
        original_revision = self.bank.active_revisions[original.memory_id]
        pending, _ = self.save("unsupported alternative", False, original.memory_id)
        self.assertEqual(self.bank.active_revisions[original.memory_id], original_revision)
        self.assertEqual(self.bank._content(original.memory_id)[1], "grounded claim")
        revised, _ = self.save("revised alternative", False, pending.memory_id)
        self.assertEqual(revised.memory_id, pending.memory_id)
        self.assertEqual(len(self.bank.pending_proposals), 1)
        _, prompt = self.agent()
        self.assertIn("PENDING UNBOUND replacement for " + original.memory_id, prompt)
        resolved, _ = self.save("new supported claim", True, pending.memory_id)
        self.assertEqual(resolved.memory_id, original.memory_id)
        self.assertFalse(self.bank.pending_proposals)
        self.assertIn(pending.memory_id, self.bank._retired_ids)
        historical = [r for r in self.bank.alignments.values() if r.target_id == original.memory_id]
        self.assertEqual(len(historical), 2)
        self.assertTrue(all(r.target_revision_id == original_revision for r in historical))

    def test_target_deletion_closes_pending_and_proposal_delete_keeps_original(self):
        original, _ = self.save()
        pending, _ = self.save("alternative", False, original.memory_id)
        ops, _ = self.execute([("memory_delete", {"memory_id": pending.memory_id})])
        self.assertTrue(ops[0].success)
        self.assertEqual(self.bank._content(original.memory_id)[1], "grounded claim")
        self.save("another alternative", False, original.memory_id)
        ops, _ = self.execute([("memory_delete", {"memory_id": original.memory_id})])
        self.assertTrue(ops[0].success)
        self.assertFalse(self.bank.pending_proposals)
        self.assertFalse(self.bank.entries)

    def test_unbound_target_revision_does_not_create_pending(self):
        op, _ = self.save("initial", False)
        revised, _ = self.save("revision", False, op.memory_id)
        self.assertEqual(op.memory_id, revised.memory_id)
        self.assertFalse(self.bank.pending_proposals)
        self.assertEqual(len(self.bank.entries), 1)

    def test_status_unbound_visible_but_cannot_replace_bound_status(self):
        op, agent = self.save("possible status", False, kind="status")
        self.assertEqual(self.bank.status, "")
        self.assertIn("possible status", agent._build_phase2_prompt(RAW, 1))
        self.assertEqual(self.bank.pending_proposals[op.memory_id].target_id, "status")
        self.save("supported status", True, kind="status")
        self.assertEqual(self.bank.status, "supported status")
        self.assertFalse(self.bank.pending_proposals)
        self.save("unsupported overwrite", False, kind="status")
        self.assertEqual(self.bank.status, "supported status")
        self.assertEqual(len(self.bank.pending_proposals), 1)

    def test_unbound_and_legacy_derived_claims_do_not_launder(self):
        first, _ = self.save("unproven observation", False)
        second, _ = self.save("derived assertion", [{"quote": "unproven observation"}])
        self.assertEqual(second.binding_status, "exact_unique")
        self.assertEqual(second.binding_disposition, "unbound")
        third, _ = self.save("derived twice", [{"quote": "derived assertion"}])
        self.assertEqual(third.binding_disposition, "unbound")
        self.bank.save_knowledge("legacy unsupported observation")
        legacy, _ = self.save("derived legacy", [{"quote": "legacy unsupported observation"}])
        self.assertEqual(legacy.binding_disposition, "unbound")
        self.assertEqual(self.bank.binding(legacy.memory_id).reason, "derived_from_unbound_memory")

    def test_malformed_args_unknown_targets_and_unknown_tool_still_reject(self):
        bad = [
            ("memory_save_gap", {"content": "bad", "memory_id": "missing"}),
            ("memory_save_gap", {"content": "bad", "evidence": None}),
            ("memory_save_gap", {"content": "bad", "evidence": [{"quote": 1}]}),
            ("memory_save_gap", {"content": "bad", "evidence": [{"quote": "x", "offset": 1}]}),
            ("memory_save_gap", {"content": "bad", "extra": True}),
            ("unknown_tool", {"content": "bad"}),
        ]
        before = self.bank.to_dict()
        ops, _ = self.execute(bad)
        self.assertTrue(all(not op.success for op in ops))
        self.assertEqual(self.bank.to_dict(), before)

    def test_integrity_failure_does_not_downgrade_to_unbound(self):
        agent, _ = self.agent()
        first = next(iter(agent._parts.catalog))
        visible = agent._parts.catalog[first]
        # replace the host-visible immutable snapshot, not user supplied evidence
        catalog = dict(agent._parts.catalog)
        catalog[first] = replace(visible, visibility_ref="corrupt")
        agent._parts = replace(agent._parts, catalog=catalog)
        before = self.bank.to_dict()
        ops = agent._execute_tool_calls(reply([("memory_save_gap", {"content": "no evidence"})]))
        self.assertFalse(ops[0].success)
        self.assertEqual(before, self.bank.to_dict())

    def test_corrupt_alignment_and_pending_roundtrip_rejected(self):
        original, _ = self.save()
        pending, _ = self.save("alternative", False, original.memory_id)
        saved = self.bank.to_dict()
        bad = deepcopy(saved)
        bad["gap_alignment"]["pending_proposals"][pending.memory_id]["target_id"] = "missing"
        with self.assertRaises(ValueError):
            AlignedEvidenceGapMemory.from_dict(bad)
        bad = deepcopy(saved)
        bad["gap_alignment"] = None
        with self.assertRaises(ValueError):
            AlignedEvidenceGapMemory.from_dict(bad)
        bad = deepcopy(saved)
        rid = self.bank.active_revisions[pending.memory_id]
        bad["gap_alignment"]["alignments"][rid]["disposition"] = "bound"
        with self.assertRaises(ValueError):
            AlignedEvidenceGapMemory.from_dict(bad)

    def test_wrong_precycle_alignment_parent_rejected(self):
        parent, _ = self.save("unbound parent", False)
        child, _ = self.save("child", [{"quote": "unbound parent"}])
        saved = self.bank.to_dict()
        record = saved["gap_alignment"]["alignments"][self.bank.active_revisions[child.memory_id]]
        manifest = saved["gap_evidence"]["manifests"][record["cycle_id"]]
        manifest["pre_cycle_revision_refs"] = ()
        with self.assertRaisesRegex(ValueError, "pre-cycle"):
            AlignedEvidenceGapMemory.from_dict(saved)

    def test_mixed_raw_and_unbound_memory_keeps_candidates_unbound(self):
        self.save("check passed", False)
        op, _ = self.save("mixed provenance", [{"quote": "check passed"}])
        self.assertEqual(op.binding_status, "exact_multiple")
        self.assertEqual(op.binding_disposition, "unbound")
        alignment = json.loads(self.bank.binding(op.memory_id).alignment_json)
        self.assertEqual(len(alignment["bound_refs"]), 2)
        self.assertEqual({r["source_kind"] for r in alignment["bound_refs"]}, {"memory", "public"})

    def test_removing_unbound_metadata_cannot_restore_as_legacy(self):
        op, _ = self.save("unbound", False)
        saved = self.bank.to_dict()
        for remove_marker in (False, True):
            bad = deepcopy(saved)
            bad.pop("gap_alignment")
            if remove_marker:
                bad.pop("gap_alignment_policy")
            with self.assertRaises(ValueError):
                AlignedEvidenceGapMemory.from_dict(bad)
        bad = deepcopy(saved)
        bad["gap_alignment"]["alignments"].clear()
        with self.assertRaisesRegex(ValueError, "missing unbound"):
            AlignedEvidenceGapMemory.from_dict(bad)

    def test_pending_cannot_shadow_native_identity(self):
        original, _ = self.save(kind="knowledge")
        pending, _ = self.save("alternative", False, original.memory_id, kind="knowledge")
        bad = deepcopy(self.bank.to_dict())
        entry = deepcopy(bad["knowledge"][0])
        entry["id"], entry["content"] = pending.memory_id, "alternative"
        bad["knowledge"].append(entry)
        with self.assertRaisesRegex(ValueError, "shadows"):
            AlignedEvidenceGapMemory.from_dict(bad)

    def test_status_pending_revision_delete_and_p1_visibility(self):
        pending, _ = self.save("status guess", False, kind="status")
        revised, _ = self.save("status guess revised", False, kind="status")
        self.assertEqual(pending.memory_id, revised.memory_id)
        _, prompt = self.agent()
        self.assertIn("status guess revised", prompt)
        self.assertIn("PENDING UNBOUND replacement for status", prompt)
        ops, agent = self.execute([("memory_delete", {"memory_id": revised.memory_id})])
        self.assertTrue(ops[0].success)
        self.assertFalse(self.bank.pending_proposals)
        self.assertNotIn("status guess revised", agent._build_phase2_prompt(RAW, 1))

    def test_binding_presentation_does_not_expose_internal_ids(self):
        op, agent = self.save()
        text = agent._binding_text(op.memory_id)
        self.assertIn("tool_observation, event order 1, field tool_result", text)
        self.assertIn("check passed", text)
        for source_id in self.bank.sources:
            self.assertNotIn(source_id, text)
        for revision_id in self.bank.revisions:
            self.assertNotIn(revision_id, text)

    def test_all_native_categories_keep_unbound_and_later_bind_in_place(self):
        for kind in ("knowledge", "procedural", "gap"):
            with self.subTest(kind=kind):
                unbound, _ = self.save("initial " + kind, False, kind=kind)
                self.assertEqual(self.bank._content(unbound.memory_id)[0], kind)
                bound, _ = self.save("supported " + kind, True, unbound.memory_id, kind)
                self.assertEqual(bound.memory_id, unbound.memory_id)
                self.assertEqual(bound.binding_disposition, "bound")
                self.assertFalse(self.bank.pending_proposals)

    def test_xml_quote_only_and_missing_evidence_use_same_path(self):
        agent, _ = self.agent()
        xml = ('<tool_call><function=memory_save_gap>'
               '<parameter=content>quote only XML</parameter>'
               '<parameter=evidence>[{"quote":"check passed"}]</parameter>'
               '</function></tool_call>'
               '<tool_call><function=memory_save_knowledge>'
               '<parameter=content>no evidence XML</parameter>'
               '</function></tool_call>')
        ops = agent._execute_tool_calls(reply(content=xml))
        self.assertEqual([op.binding_disposition for op in ops], ["bound", "unbound"])
        self.assertEqual(agent.last_evidence_report["bound_writes"], 1)
        self.assertEqual(agent.last_evidence_report["retained_unbound"], 1)
        saved = self.bank.to_dict()
        self.assertEqual(AlignedEvidenceGapMemory.from_dict(saved).to_dict(), saved)

    def test_snapshot_cache_is_scoped_and_does_not_hide_tampering(self):
        import gap_evidence
        from gap_evidence import cached_source_validation, _snapshot_valid
        agent, _ = self.agent()
        snapshot = next(iter(agent._parts.catalog.values())).snapshot
        bad = replace(snapshot, blob=replace(snapshot.blob, text=snapshot.blob.text + "tampered"))
        @cached_source_validation
        def check():
            self.assertTrue(_snapshot_valid(snapshot))
            self.assertTrue(_snapshot_valid(snapshot))
            self.assertFalse(_snapshot_valid(bad))
            self.assertFalse(_snapshot_valid(bad))
        with patch.object(gap_evidence, "_snapshot_valid_uncached", wraps=gap_evidence._snapshot_valid_uncached) as validate:
            check()
            self.assertEqual(validate.call_count, 2)
            check()
            self.assertEqual(validate.call_count, 4)
            self.assertTrue(_snapshot_valid(snapshot))
            self.assertTrue(_snapshot_valid(snapshot))
            self.assertEqual(validate.call_count, 6)

    def test_repeated_source_operation_validates_snapshot_once(self):
        import gap_evidence
        text = "check passed; " * 200
        block = dict(blocks()[0], text=text, record_digest=gap_evidence.sha256(text))
        agent, _ = self.agent([block])
        with patch.object(gap_evidence, "_snapshot_valid_uncached", wraps=gap_evidence._snapshot_valid_uncached) as validate:
            ops = agent._execute_tool_calls(reply([("memory_save_gap", {
                "content": "repeated observation", "evidence": [{"quote": "check passed"}]})]))
            self.assertTrue(ops[0].success, ops[0].error)
            self.assertEqual(validate.call_count, 1)
        value = json.loads(self.bank.binding(ops[0].memory_id).alignment_json)
        self.assertEqual(len(value["bound_refs"]), 200)
        saved = self.bank.to_dict()
        with patch.object(gap_evidence, "_snapshot_valid_uncached", wraps=gap_evidence._snapshot_valid_uncached) as validate:
            restored = AlignedEvidenceGapMemory.from_dict(saved)
            self.assertEqual(validate.call_count, 1)
        self.assertEqual(restored.to_dict(), saved)

    def test_p1_does_not_show_ineligible_historical_quotes_but_p2_does(self):
        from gap_evidence import sha256
        from gap_evidence_alignment import align_evidence
        op, _ = self.save("stored conclusion", True)
        new_text = "unrelated recent observation"
        block = dict(blocks()[0], source_id="event-2", text=new_text,
                     record_digest=sha256(new_text), order=2)
        agent, prompt = self.agent([block])
        self.assertNotIn("check passed", prompt)
        self.assertEqual(align_evidence([{"quote": "check passed"}], agent._parts.catalog).status, "unbound")
        self.assertIn("check passed", agent._build_phase2_prompt(RAW, 1))
        self.assertIn("source excerpt=", agent._build_phase2_prompt(RAW, 1))
        self.save("uncertain conclusion", [{"quote": "unseen attempted citation"}])
        agent, prompt = self.agent([block])
        self.assertNotIn("unseen attempted citation", prompt)
        self.assertIn('model-attempted quote, NOT source evidence="unseen attempted citation"',
                      agent._build_phase2_prompt(RAW, 1))

    def test_exactly_five_tools_and_two_model_calls(self):
        model = Model(lambda evidence: reply([("memory_save_gap", {"content": "retained no evidence"})]))
        agent = AlignedEvidenceGapMemoryAgent(task="task", memory=self.bank, llm=model, use_structured_tools=True)
        self.assertEqual(len(agent.get_tools_schema()), 5)
        for tool in agent.get_tools_schema():
            if tool["function"]["name"] != "memory_delete":
                self.assertEqual(tool["function"]["parameters"]["required"], ["content"])
        agent.prepare_visible_context(RAW, blocks())
        result = asyncio.run(agent.process(RAW, 1))
        self.assertEqual(len(model.inputs), 2)
        self.assertIn("retained no evidence", model.inputs[1]["prompt"])
        self.assertIn("disposition=unbound", model.inputs[1]["prompt"])
        self.assertEqual(agent.last_evidence_report["retained_unbound"], 1)
        self.assertTrue(result.operations[0].success)


if __name__ == "__main__":
    unittest.main()
