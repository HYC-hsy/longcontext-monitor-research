"""Historical public references and adversarial alignment boundary regressions."""
from collections import Counter
import importlib.util
from pathlib import Path
import unittest

from gap_evidence import RenderBlock, SourceRegistry, excerpt, register_public_source, render_source_blocks, sha256
from gap_evidence_alignment import align_evidence

D = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('alignment_replay', D / 'alignment_v2_offline/replay_historical.py')
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)


def catalog(entries):
    registry, blocks = SourceRegistry('alignment-boundary-tests'), []
    for number, (role, text, spans) in enumerate(entries):
        _, row = register_public_source(registry, event_id=str(number), role=role,
            text=text, order=number, field_path='content', record_digest=sha256(text),
            record_digest_kind='test_public')
        blocks.append(RenderBlock(registry.snapshot(row.source_id), spans))
    return render_source_blocks(blocks, cycle_id='boundary-test').catalog


class HistoricalAlignmentReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = replay.replay()

    def test_archived_fixture_is_unchanged_and_regenerates(self):
        self.assertEqual(replay.extractor.extract(), replay.FIXTURE)
        for case, row in zip(replay.FIXTURE['cases'], self.rows):
            self.assertEqual(row['quote'], case['quote'])
            self.assertEqual(row['original_hint'], replay.FIXTURE['sources'][case['source_key']]['old_handle'])
            self.assertFalse(row['original_hint_present_in_new_catalog'])

    def test_actual_quotes_with_original_stale_hints(self):
        self.assertEqual(Counter(r['status'] for r in self.rows),
                         {'exact_unique': 26, 'exact_multiple': 4, 'unbound': 2})
        for row in self.rows:
            with self.subTest(case=row['case_id']):
                if row['historical_category'] == 'noncontiguous':
                    self.assertEqual(row['status'], 'unbound')
                    self.assertEqual(row['candidates'], [])
                else:
                    self.assertTrue(row['candidates'])
                for candidate in row['candidates']:
                    self.assertEqual(candidate['snippet_sha256'], row['quote_sha256'])
                    self.assertEqual(candidate['source_kind'], 'public')

    def test_wrong_hint_finds_actual_same_prompt_source(self):
        row = next(r for r in self.rows if r['historical_category'] == 'wrong_source')
        self.assertEqual(row['status'], 'exact_unique')
        self.assertNotEqual(row['candidates'][0]['historical_event_handle'], row['original_hint'])
        case = next(c for c in replay.FIXTURE['cases'] if c['case_id'] == row['case_id'])
        self.assertEqual(row['candidates'][0]['historical_event_handle'],
                         case['wrong_source_witness']['old_handle'])

    def test_full_catalog_exposes_additional_real_ambiguity(self):
        row = next(r for r in self.rows if r['case_id'] == 'sqlite-C9-op4-ref1')
        self.assertEqual(row['status'], 'exact_multiple')
        self.assertEqual(len({c['source_id'] for c in row['candidates']}), 2)
        self.assertTrue(all(c['role'] == 'tool_command' for c in row['candidates']))
        for row in self.rows:
            self.assertGreaterEqual(row['public_source_count'], 1)
            self.assertGreaterEqual(row['projected_catalog_count'], row['public_source_count'])
            self.assertIn('memory_derived', row['omitted_prompt_source_counts'])

    def test_invalid_and_wrong_existing_hints_do_not_filter(self):
        sources = catalog([('tool_observation', 'valid quote', None),
                           ('agent_report', 'something else', None)])
        expected = align_evidence([{'quote': 'valid quote'}], sources)
        wrong = next(h for h, v in sources.items() if v.snapshot.record.role == 'agent_report')
        for hint in ('nonexistent-source', wrong):
            result = align_evidence([{'quote': 'valid quote', 'source': hint}], sources)
            self.assertEqual(result.status, 'exact_unique')
            self.assertEqual(result.bound_refs, expected.bound_refs)
            self.assertEqual(result.items[0].source_hint, hint)

    def test_repetition_same_source_and_across_roles_keeps_all(self):
        sources = catalog([('tool_observation', 'same quote / same quote', None),
                           ('agent_report', 'same quote', None),
                           ('tool_command', 'same quote', None)])
        result = align_evidence([{'quote': 'same quote'}], sources)
        self.assertEqual(result.status, 'exact_multiple')
        self.assertEqual(len(result.bound_refs), 4)
        self.assertEqual(Counter(r.role for r in result.bound_refs),
                         {'tool_observation': 2, 'agent_report': 1, 'tool_command': 1})
        resolver = {v.visibility_ref: v for v in sources.values()}
        self.assertTrue(all(excerpt(ref, resolver) == 'same quote' for ref in result.bound_refs))

    def test_hidden_marker_and_cross_span_quote_stay_unbound(self):
        sources = catalog([('tool_observation', 'visible SECRET tail', ((0, 7), (15, 19)))])
        for quote in ('SECRET', 'visible SECRET tail', 'visible  tail'):
            result = align_evidence([{'quote': quote}], sources)
            self.assertEqual(result.status, 'unbound')
            self.assertEqual(result.bound_refs, ())

    def test_fuzzy_case_whitespace_and_noncontiguous_not_promoted(self):
        sources = catalog([('tool_observation', 'Exact quote\nfirst\nmiddle\nlast', None)])
        for quote in ('exact quote', 'Exact  quote', 'Exact quote!', 'first\nlast'):
            result = align_evidence([{'quote': quote}], sources)
            self.assertEqual(result.status, 'unbound')
            self.assertEqual(result.bound_refs, ())


if __name__ == '__main__':
    unittest.main()
