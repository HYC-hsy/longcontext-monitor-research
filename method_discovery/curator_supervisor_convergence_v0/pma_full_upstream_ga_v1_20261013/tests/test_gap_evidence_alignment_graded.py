"""Offline source association checks, never semantic proof or model tests."""
import dataclasses
import unittest

from gap_evidence import bound_ref_valid, sha256
from gap_evidence_alignment import align_evidence
from graded_evidence_alignment import (align_graded_evidence, candidate_grade_valid,
                                       normalize_formatting)
from test_gap_evidence_alignment import catalog_for


class GradedNormalizationTests(unittest.TestCase):
    def test_legacy_and_exact_precedence(self):
        catalog = catalog_for("a b", "a  b")
        old = align_evidence([{"quote": "a b"}], catalog)
        new = align_graded_evidence([{"quote": "a b"}], catalog)
        self.assertEqual(new.status, "exact_unique")
        self.assertEqual(new.bound_refs, old.bound_refs)
        self.assertEqual(new.items[0].metadata, {})
        self.assertNotIn("metadata", dataclasses.asdict(old.items[0]))

    def test_continuation_unicode_crlf_offsets_and_source_hash(self):
        source = "前😀 prefix cc -g \\\r\n\tfile.c\r\nend"
        result = align_graded_evidence([{"quote": "cc -g file.c"}], catalog_for(source))
        self.assertEqual(result.status, "normalized_unique")
        ref = result.bound_refs[0]
        self.assertEqual(source[ref.start:ref.end], "cc -g \\\r\n\tfile.c")
        self.assertEqual(ref.snippet_sha256, sha256(source[ref.start:ref.end]))
        self.assertNotEqual(ref.snippet_sha256, sha256(result.items[0].quote))
        resolver = {v.visibility_ref: v for v in catalog_for(source).values()}
        self.assertTrue(bound_ref_valid(ref, resolver))
        self.assertTrue(candidate_grade_valid(result.items[0].quote,
                                              source[ref.start:ref.end], result.status))

    def test_all_normalized_duplicates_and_hints(self):
        catalog = catalog_for("a  b a\tb", "a\nb", roles=["agent_report", "tool_observation"])
        result = align_graded_evidence([{"quote": "a b", "source": "wrong"}], catalog)
        self.assertEqual(result.status, "normalized_multiple")
        self.assertEqual(len(result.bound_refs), 3)
        self.assertEqual(len(result.items[0].metadata["candidate_details"]), 3)

    def test_no_join_and_omission_refusal(self):
        for spans in [((0, 2), (4, 7)), ((0, 3), (3, 7))]:
            result = align_graded_evidence([{"quote": "ab cd"}],
                                           catalog_for("ab   cd", spans=[spans]))
            self.assertEqual(result.status, "unbound")
        result = align_graded_evidence([{"quote": "a [hidden gap] b"}], catalog_for("a  b"))
        self.assertEqual(result.items[0].reason, "omission_marker_approximation_refused")

    def test_no_semantic_normalization_or_escape_decoding(self):
        for quote, excerpt in [("not safe", "safe"), ("value 10", "value 100"),
                               ("/app/foo", "/app/bar"), ("cats", "catS"),
                               ("é", "e\u0301"), (r"a \n\tb", "a\n\tb")]:
            self.assertFalse(candidate_grade_valid(quote, excerpt, "normalized_unique"))
        self.assertEqual(normalize_formatting(r"C:\new\test")[0], r"C:\new\test")


if __name__ == "__main__":
    unittest.main()
