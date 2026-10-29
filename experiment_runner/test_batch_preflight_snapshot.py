"""The GA batch preflight must carry the same snapshot binding as the launcher."""

import argparse
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013 import batch_controller


class BatchPreflightSnapshotTest(unittest.TestCase):
    def test_snapshot_flag_reaches_preflight(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = root / 'manifest.json'
            authorization = root / 'authorization.json'
            manifest.write_text(json.dumps({
                'schema': 'pma-ga-live-manifest-v4',
                'config': {'preserve_pre_eval_snapshot': True},
            }), encoding='utf-8')
            authorization.write_text(json.dumps({
                'audited_code_commit': 'a' * 40,
            }), encoding='utf-8')
            binding = {'order': 1, 'task': 'git-leak-recovery',
                       'condition': 'A', 'research_candidate': 'U',
                       'run_id': 'test-run', 'run_root': str(root / 'run'),
                       'repeat': 1}
            args = argparse.Namespace(
                manifest=str(manifest), authorization=str(authorization),
                batch_result=str(root / 'batch_result.json'),
                ga_source='ga', runtime_root='runtime', task_profile_file='task',
                pma_profile_file=None, worker_python='worker',
                harbor_python='harbor', bench_root='bench', python_home='python',
                official_source_git='official', harbor_source_root='native',
                zero_model_fixture=False, candidate_profile_fixture=False,
                stateful_fake_replies=None)
            seen = []

            def capture(spec):
                seen.append(spec)
                raise StopIteration

            with patch.object(batch_controller, 'validate_plan', return_value=[binding]), \
                    patch.object(batch_controller, 'verify_live_spec', side_effect=capture):
                with self.assertRaises(StopIteration):
                    batch_controller.run_batch(args)
            self.assertEqual(len(seen), 1)
            self.assertIs(seen[0]['preserve_pre_eval_snapshot'], True)


if __name__ == '__main__':
    unittest.main()
