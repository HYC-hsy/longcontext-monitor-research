"""Ranked visible windows reuse pinned chunk boundaries and preserve provenance."""
import copy
import dataclasses
import unittest
from unittest.mock import patch

from fuzzy_candidate_windows import ranked_windows
from graded_evidence_alignment import (align_graded_evidence, _tokens,
    quote_metadata_valid)
from vendor.langextract_3a68580.chunking import (
    iter_fragment_intervals, get_char_interval)
from vendor.langextract_3a68580.tokenizer import RegexTokenizer
from test_gap_evidence_alignment import catalog_for


class RankedWindowTests(unittest.TestCase):
    def test_upstream_documented_fragment_and_long_token_examples(self):
        cases = [
            ('No man is an island,\nEntire of itself,\nEvery man is a piece of the continent,\nA part of the main.', 40,
             ['No man is an island,\nEntire of itself,', 'Every man is a piece of the continent,', 'A part of the main.']),
            ('This is antidisestablishmentarianism.', 20,
             ['This is', 'antidisestablishmentarianism', '.']),
        ]
        for text, limit, expected in cases:
            tokenized = RegexTokenizer().tokenize(text)
            slices = [get_char_interval(tokenized, x)
                      for x in iter_fragment_intervals(tokenized, limit)]
            self.assertEqual([text[x.start_pos:x.end_pos] for x in slices], expected)

    def test_relevant_source_first_regardless_of_catalog_order(self):
        quote = 'alpha beta gamma delta epsilon zeta eta theta'
        source = 'alpha beta gamma NEW delta epsilon zeta eta theta'
        distractor = 'theta eta zeta epsilon delta gamma beta alpha ' * 8
        catalog = catalog_for(*([distractor] * 8), 'unrelated noise ' * 300, source)
        with patch('graded_evidence_alignment.FUZZY_WORK_LIMIT', 4300):
            a = align_graded_evidence([{'quote': quote}], catalog)
            b = align_graded_evidence([{'quote': quote}], dict(reversed(list(catalog.items()))))
        self.assertEqual(a, b)
        self.assertEqual(a.status, 'fuzzy_candidate')
        self.assertEqual(a.items[0].metadata['fuzzy_search']['status'], 'partial')
        self.assertEqual(a.items[0].metadata['fuzzy_search']['skipped_chunks'], 8)
        self.assertGreater(a.items[0].metadata['candidate_selection']['lexically_pruned_windows'], 0)

    def test_multiset_upper_bound_does_not_count_repeated_tokens_as_unique(self):
        target, _ = _tokens('one one one one two two two two')
        windows, meta = ranked_windows(target, catalog_for('one two plus noise'))
        self.assertFalse(windows)
        self.assertEqual(meta['lexically_pruned_windows'], 1)

    def test_long_quote_and_chunk_boundary_preserve_original_offsets(self):
        words = [chr(97 + i) * 180 for i in range(8)]
        source = ' '.join(words)
        quote = ' '.join(words[:4] + ['changed'] + words[5:])
        self.assertGreater(len(quote), 1000)
        text = 'irrelevant\n' * 150 + source + '\ntrailer ' * 150
        catalog = catalog_for(text)
        result = align_graded_evidence([{'quote': quote}], catalog)
        self.assertEqual(result.status, 'fuzzy_candidate')
        self.assertTrue(any(text[r.start:r.end].startswith(words[0]) and
                            text[r.start:r.end].endswith(words[-1]) for r in result.bound_refs))
        resolver = {v.visibility_ref: v for v in catalog.values()}
        self.assertTrue(quote_metadata_valid(dataclasses.asdict(result.items[0]), resolver))

    def test_two_sources_keep_multiple_candidates_and_hidden_spans_never_join(self):
        text = 'one two INSERT three four five six'
        result = align_graded_evidence([{'quote': 'one two three four five six'}], catalog_for(text, text))
        self.assertEqual(result.status, 'fuzzy_candidate')
        self.assertEqual(len(result.bound_refs), 2)
        catalog = catalog_for('one two three four five six', spans=[((0, 7), (8, 26))])
        result = align_graded_evidence([{'quote': 'one two three four five six'}], catalog)
        self.assertEqual(result.status, 'unbound')

    def test_selection_metadata_count_tamper_rejected_and_legacy_accepted(self):
        catalog = catalog_for('one two INSERT three four five six')
        result = align_graded_evidence([{'quote': 'one two three four five six'}], catalog)
        resolver = {v.visibility_ref: v for v in catalog.values()}
        item = dataclasses.asdict(result.items[0])
        self.assertTrue(quote_metadata_valid(item, resolver))
        altered = copy.deepcopy(item)
        altered['metadata']['candidate_selection']['generated_windows'] += 1
        self.assertFalse(quote_metadata_valid(altered, resolver))
        legacy = copy.deepcopy(item)
        del legacy['metadata']['candidate_selection']
        self.assertTrue(quote_metadata_valid(legacy, resolver))

    def test_linenumber_source_is_ranked_before_distracting_memory(self):
        quote = '<div class="safe">\n  <a href="">Link</a>\n</div>'
        source = '27|<div class="safe">\n28|  <a href="">Link</a>\n29|</div>'
        distractor = 'An earlier conclusion says the task is complete. ' * 50
        catalog = catalog_for(*([distractor] * 8), source)
        aligned = align_graded_evidence([{'quote': quote}], catalog)
        self.assertEqual(aligned.status, 'fuzzy_candidate')
        ref = aligned.bound_refs[0]
        self.assertIn('28|', source[ref.start:ref.end])
        self.assertEqual(aligned, align_graded_evidence([{'quote': quote}],
                         dict(reversed(list(catalog.items())))))

    def test_ranked_fuzzy_metadata_survives_real_bank_roundtrip(self):
        from test_gap_latest_revision_store import LatestRevisionTests
        from latest_evidence_gap_store import LatestEvidenceGapMemory
        case = LatestRevisionTests()
        case.setUp()
        parts = case.context(text='one two INSERT three four five six')
        aligned = align_graded_evidence([{'quote': 'one two three four five six'}], parts.catalog)
        draft = case.bank.fork_write_draft()
        draft.retain_manifest(parts)
        key, revision, disposition = draft.apply_aligned_write(
            'gap', 'This is only a candidate', aligned,
            cycle_id=parts.manifest.cycle_id, op_index=0)
        case.bank.publish(case.bank.prepare_publication(draft))
        self.assertEqual(disposition, 'unbound')
        self.assertIsNone(case.bank.revisions[revision].receipt_id)
        self.assertEqual(LatestEvidenceGapMemory.from_dict(case.bank.to_dict()).to_dict(),
                         case.bank.to_dict())

    def test_exact_and_normalized_paths_have_no_window_metadata(self):
        for source, quote, expected in [('one two', 'one two', 'exact_unique'),
                                        ('one\ntwo', 'one two', 'normalized_unique')]:
            result = align_graded_evidence([{'quote': quote}], catalog_for(source))
            self.assertEqual(result.status, expected)
            self.assertNotIn('candidate_selection', result.items[0].metadata)


if __name__ == '__main__':
    unittest.main()
