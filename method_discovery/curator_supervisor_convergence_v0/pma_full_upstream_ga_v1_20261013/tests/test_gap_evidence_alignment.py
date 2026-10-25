"""Offline adapter contract tests; no model or provider calls."""
import dataclasses
import unittest
from unittest.mock import patch

from gap_evidence import (RenderBlock, SourceRegistry, SourceScopeError,
                          TextBlob, bound_ref_valid, register_memory_source,
                          register_public_source, render_source_blocks, sha256)
from gap_evidence_alignment import align_evidence
from vendor.langextract_3a68580.alignment import _find_token_occurrences


def catalog_for(*texts, roles=None, spans=None, memory=False):
    registry = SourceRegistry("alignment-test")
    blocks = []
    for index, text in enumerate(texts):
        if memory:
            _, row = register_memory_source(registry, revision_id=f"r{index}", text=text)
        else:
            _, row = register_public_source(registry, event_id=f"e{index}",
                role=roles[index] if roles else "tool_observation", text=text,
                order=index, field_path="text", record_digest=sha256(text),
                record_digest_kind="event")
        blocks.append(RenderBlock(registry.snapshot(row.source_id),
                                  None if spans is None else spans[index]))
    return render_source_blocks(blocks, cycle_id="c1").catalog


class AlignmentTests(unittest.TestCase):
    def test_optional_hint_does_not_filter_or_resolve(self):
        catalog = catalog_for("same", "same", roles=["agent_report", "tool_observation"])
        for hint in (None, next(iter(catalog)), "wrong-hint"):
            item = {"quote": "same"}
            if hint is not None:
                item["source"] = hint
            aligned = align_evidence([item], catalog)
            self.assertEqual(aligned.status, "exact_multiple")
            self.assertEqual({r.role for r in aligned.bound_refs}, {"agent_report", "tool_observation"})
            self.assertEqual(aligned.items[0].source_hint, hint)

    def test_all_candidates_are_valid(self):
        catalog = catalog_for("same same", "same")
        result = align_evidence([{"quote": "same"}], catalog)
        resolver = {v.visibility_ref: v for v in catalog.values()}
        self.assertEqual(len(result.bound_refs), 3)
        self.assertTrue(all(bound_ref_valid(r, resolver) for r in result.bound_refs))

    def test_no_evidence_and_partial_are_not_errors(self):
        catalog = catalog_for("present")
        self.assertEqual(align_evidence([], catalog).reason, "no_evidence")
        result = align_evidence([{"quote": "present"}, {"quote": "absent"}], catalog)
        self.assertEqual(result.status, "unbound")
        self.assertEqual(len(result.bound_refs), 1)
        self.assertEqual(result.items[1].reason, "quote_not_visible")
        self.assertEqual(align_evidence([{"quote": ""}], catalog).items[0].reason, "empty_quote")

    def test_overlapping_subtoken_and_punctuation(self):
        for text, quote, starts in [("aaaa", "aa", [0, 1, 2]), ("!!!!", "!!", [0, 1, 2]),
                                    ("banana", "ana", [1, 3])]:
            result = align_evidence([{"quote": quote}], catalog_for(text))
            self.assertEqual([r.start for r in result.bound_refs], starts)

    def test_whitespace_and_unicode(self):
        for text, quote, starts in [("x  y", " ", [1, 2]), ("x\ny", "\n", [1]),
                                    ("😀中文 e\u0301 😀", "😀", [0, 7]),
                                    ("a  b", "a  b", [0]), (" x ", " x ", [0])]:
            result = align_evidence([{"quote": quote}], catalog_for(text))
            self.assertEqual([r.start for r in result.bound_refs], starts)

    def test_no_normalized_or_fuzzy_binding(self):
        for text, quote in [("Aspirin   daily", "aspirin daily"), ("é", "e\u0301"),
                            ("hello brave world", "hello world"), ("cats", "catS")]:
            self.assertEqual(align_evidence([{"quote": quote}], catalog_for(text)).status, "unbound")

    def test_hidden_gap_and_adjacent_rendered_spans_never_join(self):
        for spans in [((0, 2), (4, 6)), ((0, 3), (3, 6))]:
            catalog = catalog_for("abcdef", spans=[spans])
            for quote in ["abcdef", "cde", "[hidden gap]"]:
                self.assertEqual(align_evidence([{"quote": quote}], catalog).status, "unbound")

    def test_chunk_offsets_and_overlapping_visible_windows(self):
        result = align_evidence([{"quote": "abc"}], catalog_for("xxabcxx", spans=[((2, 5), (1, 6))]))
        self.assertEqual(result.status, "exact_unique")
        self.assertEqual((result.bound_refs[0].start, result.bound_refs[0].end), (2, 5))

    def test_derived_memory_is_not_public(self):
        result = align_evidence([{"quote": "same"}], catalog_for("same", memory=True))
        self.assertEqual(result.bound_refs[0].source_kind, "memory")
        self.assertEqual(result.bound_refs[0].role, "memory_derived")
        self.assertEqual(result.bound_refs[0].parent_revision_id, "r0")

    def test_bad_shape_remains_error(self):
        catalog = catalog_for("text")
        for evidence in [None, {}, ["text"], [{"quote": 3}], [{"quote": "text", "source": None}],
                         [{"quote": "text", "extra": True}], [{"source": "x"}]]:
            with self.assertRaises(SourceScopeError):
                align_evidence(evidence, catalog)

    def test_integrity_checked_even_unmatched_or_no_evidence(self):
        catalog = catalog_for("text")
        handle, visible = next(iter(catalog.items()))
        corrupt = [dataclasses.replace(visible, visibility_ref="bad"),
                   dataclasses.replace(visible, visible_spans=((0, 999),)),
                   dataclasses.replace(visible, display_transform="normalized"),
                   dataclasses.replace(visible, snapshot=dataclasses.replace(visible.snapshot,
                       blob=TextBlob(visible.snapshot.blob.text_sha256, "forged")))]
        for row in corrupt:
            for evidence in [[], [{"quote": "absent"}]]:
                with self.assertRaises(SourceScopeError):
                    align_evidence(evidence, {handle: row})

    def test_upstream_candidate_helper_is_executed(self):
        with patch("gap_evidence_alignment._find_token_occurrences", wraps=_find_token_occurrences) as helper:
            self.assertEqual(align_evidence([{"quote": "word"}], catalog_for("word")).status, "exact_unique")
            self.assertEqual(helper.call_count, 2)
            helper.assert_any_call(["word"], ["word"])
            helper.assert_any_call("word", "word")

    def test_no_candidate_cap(self):
        result = align_evidence([{"quote": "x"}], catalog_for("x " * 1001))
        self.assertEqual(len(result.bound_refs), 1001)


if __name__ == "__main__":
    unittest.main()
