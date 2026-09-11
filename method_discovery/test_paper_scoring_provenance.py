"""Synthetic post-hoc score mapping tests; no tasks or APIs run."""
import unittest
from paper_scoring_provenance import normalize_reward, snapshot


class ScoringTests(unittest.TestCase):
    def test_all_six_wrappers(self):
        data = snapshot()
        self.assertEqual([r['total_phases'] for r in data['scoring'].values()],
                         [12, 7, 6, 6, 6, 7])
        self.assertFalse(data['complete_runnable_snapshot'])

    def test_full_and_partial(self):
        self.assertTrue(normalize_reward(dict(reward=1, phases_passed=7,
                                             total_phases=7), 7)['success'])
        self.assertFalse(normalize_reward(dict(reward=10/11, phases_passed=6,
                                              total_phases=7), 7)['success'])

    def test_invalid_scores(self):
        for reward in (None, True, float('nan'), float('inf'), -1, 2, '1'):
            with self.subTest(reward=reward), self.assertRaises(ValueError):
                normalize_reward(dict(reward=reward, phases_passed=7, total_phases=7), 7)

    def test_disagreement_and_wrong_version(self):
        for record in (dict(reward=1, phases_passed=6, total_phases=7),
                       dict(reward=.9, phases_passed=7, total_phases=7),
                       dict(reward=1, phases_passed=6, total_phases=6)):
            with self.assertRaises(ValueError):
                normalize_reward(record, 7)


if __name__ == '__main__':
    unittest.main()
