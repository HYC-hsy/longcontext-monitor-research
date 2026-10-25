"""Pinned LCS adapter safety and bounded-work regressions."""
import copy
import dataclasses
import unittest
from unittest.mock import patch

from graded_evidence_alignment import (align_graded_evidence, candidate_grade_valid,
    quote_metadata_valid, FUZZY_WORK_LIMIT)
from vendor.langextract_3a68580.fuzzy import _best_lcs_spans
from test_gap_evidence_alignment import catalog_for


class FuzzyTests(unittest.TestCase):
    def test_fuzzy_never_unique_or_semantic_proof(self):
        for source, quote in [("The check passed with all assertions enabled.",
                               "The check passed with most assertions enabled."),
                              ("The check is not safe today", "The check is safe today"),
                              ("Set the value to 100 now", "Set the value to 10 now"),
                              ("Read the file /app/foo now", "Read the file /app/bar now")]:
            catalog = catalog_for(source)
            result = align_graded_evidence([{"quote": quote}], catalog)
            self.assertEqual(result.status, "fuzzy_candidate")
            self.assertEqual(result.items[0].metadata["candidate_enumeration"], "non_exhaustive")
            resolver = {v.visibility_ref: v for v in catalog.values()}
            self.assertTrue(quote_metadata_valid(dataclasses.asdict(result.items[0]), resolver))
            self.assertTrue(candidate_grade_valid(quote, source, result.status))
            self.assertFalse(candidate_grade_valid(quote, source, "normalized_unique"))

    def test_actual_upstream_called_and_duplicate_span_not_unique(self):
        catalog = catalog_for("one two three four one two three four")
        with patch("graded_evidence_alignment._best_lcs_spans", wraps=_best_lcs_spans) as helper:
            result = align_graded_evidence([{"quote": "one two NEW three four"}], catalog)
        self.assertTrue(helper.called)
        self.assertEqual(result.status, "fuzzy_candidate")
        self.assertEqual(len(result.bound_refs), 1)

    def test_work_limit_is_not_false_miss_or_task_failure(self):
        quote = "one two changed " * 100
        with patch("graded_evidence_alignment._best_lcs_spans") as helper:
            result = align_graded_evidence([{"quote": quote}], catalog_for("one two three " * 1000))
        helper.assert_not_called()
        self.assertEqual(result.items[0].reason, "approximate_work_limit_not_searched")
        self.assertEqual(result.items[0].metadata["fuzzy_search"]["status"], "not_searched")
        self.assertEqual(result.items[0].metadata["fuzzy_search"]["work_used"], 0)

    def test_fuzzy_metadata_tamper_rejected(self):
        catalog = catalog_for("one two three four")
        result = align_graded_evidence([{"quote": "one two NEW three four"}], catalog)
        resolver = {v.visibility_ref: v for v in catalog.values()}
        item = dataclasses.asdict(result.items[0])
        for key, value in [("coverage", 1.0), ("original_excerpt", "forged"), ("matches", 99)]:
            corrupted = copy.deepcopy(item)
            corrupted["metadata"]["candidate_details"][0][key] = value
            self.assertFalse(quote_metadata_valid(corrupted, resolver))

    def test_source_marker_is_not_approximated_across(self):
        result = align_graded_evidence([{"quote": "one two three four"}],
                                       catalog_for("one two [hidden gap] three four"))
        self.assertEqual(result.status, "unbound")

    def test_case_and_stemming_not_normalized(self):
        self.assertEqual(align_graded_evidence([{"quote": "CATS"}], catalog_for("cats")).status, "unbound")
        self.assertEqual(align_graded_evidence([{"quote": "cat"}], catalog_for("dogs")).status, "unbound")


if __name__ == "__main__":
    unittest.main()
