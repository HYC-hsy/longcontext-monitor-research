import tempfile
from pathlib import Path
import unittest
from paper_archive_coverage import analyze, read_jsonl, usage_totals


class CoverageTests(unittest.TestCase):
    def test_failed_request_missing_usage_not_zero(self):
        progress = [dict(event='request_started', request_id='a'),
                    dict(event='request_started', request_id='b'),
                    dict(event='request_usage', request_id='a', usage=dict(input_tokens=10, output_tokens=2)),
                    dict(event='request_finished', request_id='a', outcome='success')]
        data = analyze(progress, [], [])
        self.assertEqual(data['usage_coverage_fraction'], .5)
        self.assertEqual(data['started_without_finish'], 1)
        self.assertIsNone(data['dollars'])

    def test_duplicate_usage_not_double_counted(self):
        row = dict(event='request_usage', request_id='a', usage=dict(input_tokens=10, output_tokens=2))
        data = analyze([dict(event='request_started', request_id='a'), row, row], [], [])
        self.assertEqual(data['progress_usage']['reported_fields_sum']['input_tokens'], 10)

    def test_conflicting_usage_excluded(self):
        rows = [dict(event='request_started', request_id='a')]
        rows += [dict(event='request_usage', request_id='a', usage=dict(input_tokens=n, output_tokens=1))
                 for n in (10, 20)]
        data = analyze(rows, [], [])
        self.assertEqual(data['conflicting_usage_request_count'], 1)
        self.assertIsNone(data['progress_usage']['reported_fields_sum']['input_tokens'])

    def test_interface_not_uptake(self):
        data = analyze([], [], [dict(kind='intervention', delivery='handed_to_task_interrupt_interface')])
        self.assertEqual(data['interface_handoffs'], 1)
        self.assertEqual(data['handoffs_with_timestamp_field'], 0)
        self.assertIsNone(data['behavioral_uptake'])

    def test_missing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            records, status = read_jsonl(Path(directory) / 'absent.jsonl')
            self.assertFalse(status['present'])
            self.assertEqual(records, [])
        self.assertIsNone(usage_totals([])['reported_fields_sum']['input_tokens'])


if __name__ == '__main__':
    unittest.main()
