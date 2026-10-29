"""No Task or verifier calls: private pre-evaluation checkpoint boundary."""

import json
import subprocess
import unittest
from unittest.mock import patch

from . import pre_eval_snapshot as snapshot
from .live_launcher import live_status_success


RUN = 'pma-' + 'a' * 16
CONTAINER = 'b' * 64
BASE = 'sha256:' + 'c' * 64
IMAGE = 'sha256:' + 'd' * 64


class SnapshotTests(unittest.TestCase):
    def test_required_snapshot_is_not_silently_skipped(self):
        status = {'schema': 'pma-ga-live-manifest-v5', 'condition': 'A',
                  'zero_model_fixture_only': False, 'primary_failure': None,
                  'harbor_return_code': 0, 'cleanup_confirmed': True,
                  'frozen_product': True, 'evaluation_released': True,
                  'native_result': {'status': 'native_recorded'},
                  'native_upload_checked': True, 'native_script_observed': True,
                  'native_reports_checked': True, 'snapshot_required': True,
                  'snapshot_saved': False}
        self.assertFalse(live_status_success(status))
        status['snapshot_saved'] = True
        self.assertTrue(live_status_success(status))

    def test_refuses_mounted_app_before_any_pause(self):
        row = {'Id': CONTAINER, 'Image': BASE, 'State': {'Running': True, 'Paused': False},
               'Mounts': [{'Destination': '/app', 'Type': 'volume'}]}
        with patch.object(snapshot, '_inspect', return_value=row), \
                patch.object(snapshot, '_run') as docker:
            with self.assertRaisesRegex(RuntimeError, 'mounted /app'):
                snapshot.capture(run_id=RUN, task_id='example', container_id=CONTAINER,
                                 source_image_id=BASE)
            docker.assert_not_called()

    def test_refuses_mounted_app_subdirectory(self):
        row = {'Id': CONTAINER, 'Image': BASE, 'State': {'Running': True, 'Paused': False},
               'Mounts': [{'Destination': '/app/workspace', 'Type': 'volume'}]}
        with patch.object(snapshot, '_inspect', return_value=row), \
                patch.object(snapshot, '_run') as docker:
            with self.assertRaisesRegex(RuntimeError, 'mounted /app'):
                snapshot.capture(run_id=RUN, task_id='example', container_id=CONTAINER,
                                 source_image_id=BASE)
            docker.assert_not_called()

    def test_commits_private_layer_and_confirms_main_running(self):
        row = {'Id': CONTAINER, 'Image': BASE, 'State': {'Running': True, 'Paused': False},
               'Mounts': [{'Destination': '/logs/agent', 'Type': 'bind'}]}
        calls = []
        def docker(*args, **kwargs):
            calls.append(args)
            if args[:2] == ('image', 'inspect'):
                return subprocess.CompletedProcess(args, 0, json.dumps([{'Id': IMAGE}]), '')
            if args[0] == 'commit':
                return subprocess.CompletedProcess(args, 0, IMAGE + '\n', '')
            return subprocess.CompletedProcess(args, 0, '', '')
        def process(args, **kwargs):
            self.assertEqual(args[:3], ['docker', 'image', 'inspect'])
            return subprocess.CompletedProcess(args, 1, b'', b'not found')
        with patch.object(snapshot, '_inspect', return_value=row), \
                patch.object(snapshot, '_run', side_effect=docker), \
                patch.object(snapshot.subprocess, 'run', side_effect=process):
            receipt = snapshot.capture(run_id=RUN, task_id='example', container_id=CONTAINER,
                                       source_image_id=BASE)
            self.assertEqual(receipt['checkpoint_image_id'], IMAGE)
            self.assertEqual(receipt['filesystem_capture'], 'docker_commit_writable_layer')
            self.assertFalse(receipt['native_evaluator_started'])
            self.assertFalse(receipt['process_state_captured'])
        self.assertEqual([call[0] for call in calls], ['commit', 'image'])


if __name__ == '__main__':
    unittest.main()
