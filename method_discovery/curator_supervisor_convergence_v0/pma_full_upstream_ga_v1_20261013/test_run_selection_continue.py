"""Serial failure continuation requires an ended and cleaned slot."""

import json
from pathlib import Path
import tempfile
import unittest

from .run_selection import execute_serial


class ContinueTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'selection'
        self.slots = [{'task': 'first'}, {'task': 'second'}]
        self.calls = []

    def prepare(self, directory, row):
        directory.mkdir()
        return {'task': row['task']}

    def fixture(self, *, cleanup=True, missing_identity=False):
        execute_serial(self.slots, self.root, 'prepare', self.prepare, None,
                       lambda order, row: f'{order:02d}-{row["task"]}')
        for slot in self.root.iterdir():
            if slot.is_dir():
                (slot / 'authorization.json').write_text('{}')

        def run(directory, row, authorization):
            self.calls.append(row['task'])
            run_id = row['task']
            run_root = directory / 'run'
            (run_root / 'archive').mkdir(parents=True)
            if not missing_identity:
                (run_root / 'archive/agent_start_identity.json').write_text(
                    json.dumps({'run_id': run_id}))
            (run_root / 'archive/agent_end_native.json').write_text(
                json.dumps({'run_id': run_id, 'writers_stopped': True}))
            if row['task'] == 'second':
                return {'stop_reason': None, 'arm': {'disposition': 'completed'}}
            status = {'run_id': run_id, 'primary_failure': None,
                      'cleanup_confirmed': cleanup, 'remaining_containers': [],
                      'cleanup_errors': [], 'owned_volume_clearance': {'status': 'clean'}}
            return {'stop_reason': 'stop_batch_native_evaluation_unavailable',
                    'arm': {'disposition': 'stop_batch_native_evaluation_unavailable',
                            'run_id': run_id, 'run_root': str(run_root), 'status': status}}

        return run

    def test_isolated_evaluation_failure_continues_to_second(self):
        run = self.fixture()
        rows = execute_serial(self.slots, self.root, 'run', None, run,
                              lambda order, row: f'{order:02d}-{row["task"]}',
                              on_slot_failure='continue')
        self.assertEqual(self.calls, ['first', 'second'])
        self.assertTrue(rows[0]['continued_after_isolated_failure'])
        self.assertEqual(len(json.loads((self.root / 'selection_result.json').read_text())[
            'remaining_not_started']), 0)

    def test_cleanup_unknown_stops(self):
        run = self.fixture(cleanup=False)
        rows = execute_serial(self.slots, self.root, 'run', None, run,
                              lambda order, row: f'{order:02d}-{row["task"]}',
                              on_slot_failure='continue')
        self.assertEqual(self.calls, ['first'])
        self.assertFalse(rows[0]['continued_after_isolated_failure'])

    def test_identity_unknown_stops(self):
        run = self.fixture(missing_identity=True)
        execute_serial(self.slots, self.root, 'run', None, run,
                       lambda order, row: f'{order:02d}-{row["task"]}',
                       on_slot_failure='continue')
        self.assertEqual(self.calls, ['first'])

    def test_default_remains_stop(self):
        run = self.fixture()
        execute_serial(self.slots, self.root, 'run', None, run,
                       lambda order, row: f'{order:02d}-{row["task"]}')
        self.assertEqual(self.calls, ['first'])


if __name__ == '__main__':
    unittest.main()
