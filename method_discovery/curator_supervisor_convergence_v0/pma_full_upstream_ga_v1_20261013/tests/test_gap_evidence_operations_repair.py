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
