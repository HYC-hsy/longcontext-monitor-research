"""Synthetic engineering tests, not evidence of monitor effectiveness."""
import unittest
from paper_protocol_audit import inventory, paired_summary


def result(task, condition, success=None, status='evaluated'):
    return dict(task_id=task, condition=condition, success=success, status=status)


class ProtocolTests(unittest.TestCase):
    def test_static_panel_and_frozen_splits(self):
        report = inventory()
        self.assertEqual(report['split_counts'], {
            'method_dev': 60, 'stage_validation': 30, 'final_holdout': 30})
        self.assertEqual(len(report['panel']), 6)
        self.assertTrue(all(r['split'] == 'method_dev' for r in report['panel']))
        self.assertEqual(sum(r['historical_evaluation_available']
                             for r in report['source_counts'].values()), 75)

    def test_win_loss_tie(self):
        rows = [result('a', 'G0', False), result('a', 'G1', True),
                result('b', 'G0', True), result('b', 'G1', False),
                result('c', 'G0', True), result('c', 'G1', True)]
        summary = paired_summary(rows, 'G0', 'G1')
        self.assertEqual([summary[k] for k in ('wins', 'losses', 'ties')], [1, 1, 1])
        self.assertEqual(summary['paired_success_delta'], 0)

    def test_missing_and_infrastructure_failure_are_visible(self):
        rows = [result('a', 'G0', True), result('b', 'G0', False),
                result('b', 'G1', status='infrastructure_failure')]
        summary = paired_summary(rows, 'G0', 'G1')
        self.assertEqual(len(summary['incomplete_pairs']), 2)
        self.assertIsNone(summary['paired_success_delta'])

    def test_partial_reward_is_not_success(self):
        with self.assertRaises(ValueError):
            paired_summary([result('a', 'G0', 0.8)], 'G0', 'G1')

    def test_duplicate_and_same_condition_rejected(self):
        with self.assertRaises(ValueError):
            paired_summary([result('a', 'G0', True)] * 2, 'G0', 'G1')
        with self.assertRaises(ValueError):
            paired_summary([], 'G0', 'G0')


if __name__ == '__main__':
    unittest.main()
