"""Offline contracts for decoupled latest revisions, with no model calls."""
from copy import deepcopy
from dataclasses import replace
import json
import unittest

from aligned_evidence_gap_store import AlignedEvidenceGapMemory
from evidence_gap_store import History
from gap_evidence import RenderBlock, SourceRegistry, register_public_source, render_source_blocks, sha256
from gap_evidence_alignment import align_evidence, EvidenceAlignment
from latest_evidence_gap_store import LatestEvidenceGapMemory


class LatestRevisionTests(unittest.TestCase):
    def setUp(self):
        self.bank = LatestEvidenceGapMemory()
        self.cycle = 0

    def context(self, memory_ids=(), text="check passed"):
        self.cycle += 1
        registry = SourceRegistry("latest-test")
        _, source = register_public_source(registry, event_id=f"public-{self.cycle}", role="tool_observation",
            text=text, order=0, field_path="text", record_digest=sha256(text), record_digest_kind="event")
        blocks = [RenderBlock(registry.snapshot(source.source_id))]
        for key in memory_ids:
            source = self.bank.memory_source(registry, key)
            blocks.append(RenderBlock(registry.snapshot(source.source_id)))
        return render_source_blocks(blocks, cycle_id=f"c{self.cycle}")

    def write(self, text, evidence=None, target=None, kind="gap", memory_ids=(), alignment=None):
        parts = self.context(memory_ids)
        draft = self.bank.fork_write_draft()
        draft.retain_manifest(parts)
        aligned = align_evidence(evidence or [], parts.catalog) if alignment is None else alignment
        result = draft.apply_aligned_write(kind, text, aligned, cycle_id=parts.manifest.cycle_id,
                                           op_index=0, memory_id=target)
        self.bank.publish(self.bank.prepare_publication(draft))
        self.bank.validate_bank()
        return result

    def test_same_id_bound_unbound_bound_and_no_ref_inheritance(self):
        key, first, _ = self.write("first", [{"quote": "check passed"}])
        same, second, disposition = self.write("second", target=key)
        self.assertEqual((same, disposition), (key, "unbound"))
        self.assertEqual(self.bank._content(key)[1], "second")
        self.assertEqual(self.bank.revisions[second].previous_revision_id, first)
        self.assertIsNone(self.bank.revisions[second].receipt_id)
        self.assertEqual(json.loads(self.bank.binding(key).alignment_json)["bound_refs"], [])
        same, third, disposition = self.write("third", [{"quote": "check passed"}], key)
        self.assertEqual((same, disposition), (key, "bound"))
        self.assertEqual(self.bank.revisions[third].previous_revision_id, second)
        self.assertEqual(self.bank._content(key)[1], "third")
        self.assertEqual(len(self.bank._gap_entries), 1)
        self.assertFalse(self.bank.pending_proposals)
        self.assertFalse(self.bank.tombstones)
        self.assertEqual(len(self.bank.revisions), 3)

    def test_malformed_binding_error_content_is_latest(self):
        key, first, _ = self.write("first", [{"quote": "check passed"}])
        _, second, disposition = self.write("new content", target=key,
            alignment=EvidenceAlignment("error", "invalid_evidence_item", (), ()))
        self.assertEqual(disposition, "unbound")
        self.assertEqual(self.bank.binding(key).status, "error")
        self.assertEqual(self.bank._content(key)[1], "new content")
        self.assertEqual(self.bank.revisions[second].previous_revision_id, first)
        self.assertIsNone(self.bank.revisions[second].receipt_id)

    def test_raw_candidate_survives_unbound_memory_alternative(self):
        key, _, _ = self.write("check passed")
        other, _, disposition = self.write("new claim", [{"quote": "check passed"}], memory_ids=(key,))
        row = self.bank.binding(other)
        self.assertEqual(disposition, "bound")
        self.assertEqual(row.status, "exact_multiple")
        self.assertEqual(row.provenance_summary, "mixed")
        provenance = json.loads(row.candidate_provenance_json)
        self.assertEqual({r["origin"] for r in provenance}, {"raw", "derived"})
        self.assertEqual(next(r for r in provenance if r["origin"] == "derived")["parent_disposition"], "unbound")

    def test_derived_only_remains_unbound(self):
        key, _, _ = self.write("only derived")
        other, _, disposition = self.write("claim", [{"quote": "only derived"}], memory_ids=(key,))
        self.assertEqual(disposition, "unbound")
        self.assertEqual(self.bank.binding(other).provenance_summary, "derived")

    def test_status_always_replaced(self):
        _, first, _ = self.write("before", [{"quote": "check passed"}], kind="status")
        key, second, _ = self.write("after", kind="status")
        self.assertEqual(key, "status")
        self.assertEqual(self.bank.status, "after")
        self.assertEqual(self.bank.revisions[second].previous_revision_id, first)
        self.assertFalse(self.bank.pending_proposals)

    def test_roundtrip_and_tamper_rejection(self):
        key, _, _ = self.write("claim", [{"quote": "check passed"}])
        self.write("new", target=key)
        data = self.bank.to_dict()
        self.assertEqual(LatestEvidenceGapMemory.from_dict(deepcopy(data)).to_dict(), data)
        self.assertEqual(data["gap_alignment"]["schema"], 2)
        self.assertNotIn("pending_proposals", data["gap_alignment"])
        for mutate in (
            lambda d: d["gap_alignment"].update(schema=1),
            lambda d: d["gap_alignment"]["alignments"].pop(self.bank.active_revisions[key]),
            lambda d: d["gap_alignment"]["alignments"][self.bank.active_revisions[key]].update(provenance_summary="raw"),
            lambda d: d["gap_evidence"]["blobs"].update({next(iter(d["gap_evidence"]["blobs"])): "corrupt"}),
        ):
            corrupted = deepcopy(data)
            mutate(corrupted)
            with self.assertRaises(ValueError):
                LatestEvidenceGapMemory.from_dict(corrupted)

    def test_legacy_policy_not_silently_migrated(self):
        old = AlignedEvidenceGapMemory().to_dict()
        with self.assertRaisesRegex(ValueError, "schema 2"):
            LatestEvidenceGapMemory.from_dict(old)
        self.assertEqual(AlignedEvidenceGapMemory.from_dict(old).to_dict(), old)

    def test_invalid_content_target_or_internal_reference_does_not_publish(self):
        key, _, _ = self.write("first")
        before = self.bank.to_dict()
        for kind, content, target in (("gap", "", key), ("knowledge", "x", key),
                                      ("gap", "x", "missing"), ("bad", "x", None)):
            with self.assertRaises(ValueError):
                self.write(content, target=target, kind=kind)
            self.assertEqual(self.bank.to_dict(), before)
        parts = self.context()
        alignment = align_evidence([{"quote": "check passed"}], parts.catalog)
        bad = replace(alignment.bound_refs[0], snippet_sha256="0" * 64)
        alignment = replace(alignment, bound_refs=(bad,),
            items=(replace(alignment.items[0], candidates=(bad,)),))
        draft = self.bank.fork_write_draft()
        draft.retain_manifest(parts)
        with self.assertRaises(ValueError):
            draft.apply_aligned_write("gap", "bad", alignment, cycle_id=parts.manifest.cycle_id,
                                      op_index=0, memory_id=key)
        self.assertEqual(self.bank.to_dict(), before)

    def test_history_and_manifest_tampering_rejected(self):
        key, first, _ = self.write("first", [{"quote": "check passed"}])
        _, second, _ = self.write("second", target=key)
        data = self.bank.to_dict()
        corrupted = deepcopy(data)
        corrupted["gap_evidence"]["revisions"][first]["previous_revision_id"] = second
        with self.assertRaises(ValueError):
            LatestEvidenceGapMemory.from_dict(corrupted)
        corrupted = deepcopy(data)
        cycle = self.bank.alignments[first].cycle_id
        corrupted["gap_evidence"]["manifests"][cycle]["request_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            LatestEvidenceGapMemory.from_dict(corrupted)
        corrupted = deepcopy(data)
        row = corrupted["gap_alignment"]["alignments"][first]
        value = json.loads(row["alignment_json"])
        value["items"][0]["quote"] = "different quote"
        row["alignment_json"] = json.dumps(value)
        with self.assertRaises(ValueError):
            LatestEvidenceGapMemory.from_dict(corrupted)

    def test_no_same_cycle_memory_parent(self):
        parts = self.context()
        draft = self.bank.fork_write_draft()
        draft.retain_manifest(parts)
        key, revision, _ = draft.apply_aligned_write("gap", "first", align_evidence([], parts.catalog),
            cycle_id=parts.manifest.cycle_id, op_index=0)
        registry = SourceRegistry("same-cycle")
        source = draft.memory_source(registry, key)
        later = render_source_blocks([RenderBlock(registry.snapshot(source.source_id))],
                                     cycle_id=parts.manifest.cycle_id)
        # Even a fabricated manifest listing the revision cannot make an
        # alignment created in this cycle a pre-cycle source.
        draft.manifests = History(rows=((later.manifest.cycle_id, later.manifest),))
        draft._pending_visibility = {v.visibility_ref: v for v in later.catalog.values()}
        with self.assertRaisesRegex(ValueError, "non-pre-cycle"):
            draft.apply_aligned_write("gap", "second", align_evidence([{"quote": "first"}], later.catalog),
                cycle_id=later.manifest.cycle_id, op_index=1)

    def test_binding_error_does_not_hide_corrupt_source_catalog(self):
        parts = self.context()
        draft = self.bank.fork_write_draft()
        draft.retain_manifest(parts)
        ref, visible = next(iter(draft._pending_visibility.items()))
        draft._pending_visibility[ref] = replace(visible, display_transform="forged")
        with self.assertRaises(ValueError):
            draft.apply_aligned_write("gap", "legal content",
                EvidenceAlignment("error", "invalid_evidence", (), ()),
                cycle_id=parts.manifest.cycle_id, op_index=0)
        self.assertFalse(draft.revisions)
        self.assertFalse(self.bank._gap_entries)

    def test_normalized_latest_revision_roundtrip_and_metadata_tamper(self):
        from graded_evidence_alignment import align_graded_evidence
        key, first, _ = self.write("first")
        parts = self.context(text="cc -O0  sqlite3.c")
        draft = self.bank.fork_write_draft()
        draft.retain_manifest(parts)
        aligned = align_graded_evidence([{"quote": "cc -O0 sqlite3.c"}], parts.catalog)
        self.assertEqual(aligned.status, "normalized_unique")
        _, revision, disposition = draft.apply_aligned_write("gap", "compiled", aligned,
            cycle_id=parts.manifest.cycle_id, op_index=0, memory_id=key)
        self.bank.publish(self.bank.prepare_publication(draft))
        self.assertEqual(disposition, "bound")
        self.assertEqual(self.bank.revisions[revision].previous_revision_id, first)
        data = self.bank.to_dict()
        self.assertEqual(LatestEvidenceGapMemory.from_dict(deepcopy(data)).to_dict(), data)
        value = json.loads(data["gap_alignment"]["alignments"][revision]["alignment_json"])
        value["items"][0]["metadata"]["normalization"] = "semantic_equivalence"
        data["gap_alignment"]["alignments"][revision]["alignment_json"] = json.dumps(value)
        with self.assertRaises(ValueError):
            LatestEvidenceGapMemory.from_dict(data)

    def test_fuzzy_latest_revision_is_not_promoted_to_bound(self):
        from graded_evidence_alignment import align_graded_evidence
        key, first, _ = self.write("first", [{"quote": "check passed"}])
        parts = self.context(text="tests not passed")
        draft = self.bank.fork_write_draft()
        draft.retain_manifest(parts)
        aligned = align_graded_evidence([{"quote": "tests passed"}], parts.catalog)
        self.assertEqual(aligned.status, "fuzzy_candidate")
        _, revision, disposition = draft.apply_aligned_write("gap", "new claim", aligned,
            cycle_id=parts.manifest.cycle_id, op_index=0, memory_id=key)
        self.bank.publish(self.bank.prepare_publication(draft))
        self.assertEqual(disposition, "unbound")
        self.assertEqual(self.bank._content(key)[1], "new claim")
        self.assertEqual(self.bank.revisions[revision].previous_revision_id, first)
        self.assertIsNone(self.bank.revisions[revision].receipt_id)
        data = self.bank.to_dict()
        self.assertEqual(LatestEvidenceGapMemory.from_dict(deepcopy(data)).to_dict(), data)

    def test_exact_and_no_ref_metadata_tamper_rejected(self):
        for evidence in ([{"quote": "check passed"}], []):
            key, revision, _ = self.write("claim", evidence)
            data = self.bank.to_dict()
            row = data["gap_alignment"]["alignments"][revision]
            value = json.loads(row["alignment_json"])
            if value["items"]:
                value["items"][0]["metadata"] = {"truth": "proved"}
            else:
                value["items"] = [{"quote": "absent", "source_hint": None,
                    "status": "unbound", "reason": "quote_not_visible", "candidates": [],
                    "metadata": {"truth": "proved"}}]
            row["alignment_json"] = json.dumps(value)
            with self.assertRaises(ValueError):
                LatestEvidenceGapMemory.from_dict(data)

    def test_pristine_upstream_initialization_not_archive_migration(self):
        from memory_agent.memory.universal_memory import UniversalMemory
        upstream = UniversalMemory()
        initialized = LatestEvidenceGapMemory.from_dict(upstream.to_dict())
        self.assertEqual(initialized.to_dict(), LatestEvidenceGapMemory().to_dict())
        upstream.save_knowledge("existing knowledge")
        with self.assertRaisesRegex(ValueError, "schema 2"):
            LatestEvidenceGapMemory.from_dict(upstream.to_dict())
        for extra in ({"gaps": []}, {"history": []}, {"gap_alignment_policy": "old"}):
            data = {**UniversalMemory().to_dict(), **extra}
            with self.assertRaises(ValueError):
                LatestEvidenceGapMemory.from_dict(data)
        upstream = UniversalMemory()
        upstream.update_status("existing status")
        with self.assertRaises(ValueError):
            LatestEvidenceGapMemory.from_dict(upstream.to_dict())

    def test_stale_draft_rejected(self):
        draft = self.bank.fork_write_draft()
        self.write("new")
        with self.assertRaisesRegex(ValueError, "stale"):
            self.bank.prepare_publication(draft)


if __name__ == "__main__":
    unittest.main()
