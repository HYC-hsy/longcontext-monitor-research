"""Deterministic operation-isolation and stable identity contracts; no provider."""
import unittest
from unittest.mock import patch

from evidence_gap_agent import EvidenceGapMemoryAgent
from evidence_gap_store import EvidenceGapMemory
from test_gap_evidence_agent import RAW, blocks, reply


class OperationRepairTests(unittest.TestCase):
    def prepared(self, bank=None):
        bank = EvidenceGapMemory() if bank is None else bank
        agent = EvidenceGapMemoryAgent(task="task", memory=bank)
        agent.prepare_visible_context(RAW, blocks())
        prompt = agent._build_phase1_prompt(RAW, 1)
        self.assertIsNotNone(agent._parts)
        self.evidence = [{"source": next(k for k, v in agent._parts.catalog.items()
                          if v.snapshot.record.role == "tool_observation"),
                          "quote": "check passed"}]
        return agent, bank, prompt

    def test_memory_has_one_display_identity(self):
        bank = EvidenceGapMemory()
        key = bank.save_gap("old observation")
        agent, bank, prompt = self.prepared(bank)
        visible = agent._parts.catalog[key]
        self.assertIn(f"[{key} memory_derived", prompt)
        self.assertNotIn(visible.snapshot.record.handle, prompt)
        self.assertNotIn(visible.snapshot.record.handle, agent._parts.catalog)
        self.assertEqual(visible.snapshot.record.parent_revision_id,
                         agent._draft.active_revisions[key])

    def write_target(self, bank, key, kind, content):
        from gap_evidence import bind_evidence
        agent, bank, _ = self.prepared(bank)
        draft = agent._draft
        draft.retain_manifest(agent._parts)
        result = draft.apply_bound_write(kind, content,
            bind_evidence(self.evidence, agent._parts.catalog),
            cycle_id=agent._parts.manifest.cycle_id, op_index=0, memory_id=key)
        bank.publish(bank.prepare_publication(draft))
        return result

    def test_store_updates_preserve_identity_metadata_and_history(self):
        for kind in ("knowledge", "procedural", "gap"):
            with self.subTest(kind=kind):
                bank = EvidenceGapMemory()
                key = getattr(bank, "save_" + kind)("original")
                original = next(e for e in bank._knowledge + bank._procedural + bank._gap_entries
                                if e.id == key)
                metadata = original.to_dict()
                updated, revision_id = self.write_target(bank, key, kind, "revised")
                self.assertEqual(updated, key)
                self.assertEqual(original.content, "original")
                current = next(e for e in bank._knowledge + bank._procedural + bank._gap_entries
                               if e.id == key)
                self.assertEqual(current.to_dict(), dict(metadata, content="revised"))
                revision = bank.revisions[revision_id]
                prior = bank.revisions[revision.previous_revision_id]
                self.assertEqual(bank.blobs[prior.content_sha256], "original")
                self.assertEqual(bank._content(key), (kind, "revised"))
                restored = EvidenceGapMemory.from_dict(bank.to_dict())
                self.assertEqual(restored.to_dict(), bank.to_dict())

    def test_store_unknown_wrong_category_and_failure_preserve_owner(self):
        for target, kind in (("missing", "gap"), (None, "procedural")):
            bank = EvidenceGapMemory()
            key = bank.save_gap("original")
            before = bank.to_dict()
            with self.assertRaises(ValueError):
                self.write_target(bank, target or key, kind, "rejected")
            self.assertEqual(bank.to_dict(), before)
        bank = EvidenceGapMemory()
        key = bank.save_gap("original")
        before = bank.to_dict()
        with patch.object(bank, "publish", side_effect=RuntimeError("failure")):
            with self.assertRaises(RuntimeError):
                self.write_target(bank, key, "gap", "rejected")
        self.assertEqual(bank.to_dict(), before)

    def test_loader_rejects_restored_old_revision_even_with_matching_content(self):
        bank = EvidenceGapMemory()
        key = bank.save_gap("original")
        _, revision_id = self.write_target(bank, key, "gap", "revised")
        saved = bank.to_dict()
        prior = bank.revisions[revision_id].previous_revision_id
        saved["gap_evidence"]["active_revisions"][key] = prior
        saved["gaps"][0]["content"] = "original"
        with self.assertRaisesRegex(ValueError, "latest"):
            EvidenceGapMemory.from_dict(saved)

    def test_existing_save_tool_updates_target_in_place(self):
        bank = EvidenceGapMemory()
        key = bank.save_gap("old observation")
        agent, bank, _ = self.prepared(bank)
        result = agent._execute_tool_calls(reply([("memory_save_gap", {
            "memory_id": key, "content": "updated", "evidence": self.evidence})]))
        self.assertTrue(result[0].success)
        self.assertEqual(result[0].memory_id, key)
        self.assertEqual([(e.id, e.content) for e in bank.entries], [(key, "updated")])
        self.assertEqual(len(bank.tombstones), 0)

    def test_bad_middle_structured_call_does_not_discard_neighbors(self):
        from types import SimpleNamespace as NS
        agent, bank, _ = self.prepared()
        response = reply([("memory_save_gap", {"content": "first", "evidence": self.evidence}),
                          ("memory_save_gap", {"content": "last", "evidence": self.evidence})])
        response.tool_calls.insert(1, NS(function=NS(name="memory_save_gap", arguments="{")))
        result = agent._execute_tool_calls(response)
        self.assertEqual([op.success for op in result], [True, False, True])
        self.assertEqual([e.content for e in bank.entries], ["first", "last"])
        self.assertFalse(agent.last_evidence_report["accepted"])
        self.assertTrue(agent.last_evidence_report["partial_success"])
        self.assertEqual(agent.last_evidence_report["succeeded"], 2)
        self.assertEqual(agent.last_evidence_report["failed"], 1)
        self.assertEqual(sorted(r.op_index for r in bank.receipts.values()), [0, 2])
        self.assertEqual(len(bank.manifests), 1)
        bank.validate_bank()

    def test_xml_bad_operation_between_good_calls_is_isolated(self):
        import json
        for bad in ("<tool_call>bad</tool_call>", "</tool_call>"):
            with self.subTest(bad=bad):
                agent, bank, _ = self.prepared()
                xml = ("<tool_call><function=memory_save_gap><parameter=content>good</parameter>"
                       f"<parameter=evidence>{json.dumps(self.evidence)}</parameter>"
                       "</function></tool_call>")
                result = agent._execute_tool_calls(reply(content=xml + bad + xml))
                self.assertEqual([op.success for op in result], [True, False, True])
                self.assertEqual(len(bank.entries), 2)

    def test_deleted_memory_is_citable_from_fixed_p1_snapshot(self):
        bank = EvidenceGapMemory()
        key = bank.save_gap("old observation")
        agent, bank, _ = self.prepared(bank)
        result = agent._execute_tool_calls(reply([
            ("memory_delete", {"memory_id": key}),
            ("memory_save_knowledge", {"content": "historical inference", "evidence": [
                {"source": key, "quote": "old observation"}]})]))
        self.assertTrue(all(op.success for op in result))
        self.assertEqual(bank.entries, [])
        parent = next(iter(bank.receipts.values())).bound_refs[0].parent_revision_id
        self.assertEqual(bank.revisions[parent].memory_id, key)
        self.assertEqual(EvidenceGapMemory.from_dict(bank.to_dict()).to_dict(), bank.to_dict())

    def test_two_updates_cite_original_snapshot_not_intermediate_revision(self):
        bank = EvidenceGapMemory()
        key = bank.save_gap("old observation")
        agent, bank, _ = self.prepared(bank)
        original = agent._draft.active_revisions[key]
        result = agent._execute_tool_calls(reply([
            ("memory_save_gap", {"memory_id": key, "content": text, "evidence": [
                {"source": key, "quote": "old observation"}]}) for text in ("first", "last")]))
        self.assertTrue(all(op.success for op in result))
        self.assertEqual(bank.entries[0].content, "last")
        self.assertEqual({r.bound_refs[0].parent_revision_id for r in bank.receipts.values()}, {original})
        self.assertEqual(EvidenceGapMemory.from_dict(bank.to_dict()).to_dict(), bank.to_dict())

    def test_failed_update_preserves_target_and_other_successes(self):
        bank = EvidenceGapMemory()
        key = bank.save_gap("original")
        agent, bank, _ = self.prepared(bank)
        real = EvidenceGapMemory.apply_bound_write
        def fail_after_mutation(draft, kind, content, *args, **kwargs):
            result = real(draft, kind, content, *args, **kwargs)
            if content == "rejected":
                raise RuntimeError("after mutation")
            return result
        with patch.object(EvidenceGapMemory, "apply_bound_write", fail_after_mutation):
            result = agent._execute_tool_calls(reply([
                ("memory_save_gap", {"content": "independent", "evidence": self.evidence}),
                ("memory_save_gap", {"memory_id": key, "content": "rejected", "evidence": self.evidence})]))
        self.assertEqual([op.success for op in result], [True, False])
        self.assertEqual([e.content for e in bank.entries], ["original", "independent"])
        self.assertEqual(len(bank.receipts), 1)
        self.assertNotIn("rejected", bank.blobs.values())

    def test_next_cycle_feedback_is_bounded_host_diagnostic_not_evidence(self):
        agent, bank, _ = self.prepared()
        agent._execute_tool_calls(reply([("unknown" + "secret" * 100, {})] * 5))
        agent.prepare_visible_context(RAW, blocks())
        prompt = agent._build_phase1_prompt(RAW, 2)
        self.assertIn("total failed=5", prompt)
        self.assertEqual(prompt.count("invalid_memory_operation: unknown_memory_operation"), 3)
        self.assertNotIn("secret", prompt)
        self.assertFalse(any("Previous maintenance errors" in v.snapshot.blob.text
                             for v in agent._parts.catalog.values()))

    def test_nested_xml_cannot_salvage_an_action_from_malformed_outer_argument(self):
        import json
        for closing in ("</parameter></function></tool_call>", ""):
            with self.subTest(closing=closing):
                agent, bank, _ = self.prepared()
                xml = ("<tool_call><function=memory_save_gap><parameter=content>nested</parameter>"
                       f"<parameter=evidence>{json.dumps(self.evidence)}</parameter>"
                       "</function></tool_call>")
                malformed = "<tool_call><function=unknown><parameter=content>" + xml + closing
                result = agent._execute_tool_calls(reply(content=malformed))
                self.assertEqual([op.success for op in result], [False])
                self.assertEqual(bank.entries, [])
                self.assertEqual(len(bank.receipts), 0)

    def test_malformed_tool_name_does_not_abort_later_calls(self):
        from types import SimpleNamespace as NS
        agent, bank, _ = self.prepared()
        response = reply([("memory_save_gap", {"content": "later", "evidence": self.evidence})])
        response.tool_calls.insert(0, NS(function=NS(name=["invalid"], arguments="{}")))
        result = agent._execute_tool_calls(response)
        self.assertEqual([op.success for op in result], [False, True])
        self.assertEqual([e.content for e in bank.entries], ["later"])
