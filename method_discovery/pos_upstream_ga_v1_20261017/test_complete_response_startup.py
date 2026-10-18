"""Zero-model checks of the new PoS Task policy authorization seam."""
from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013 import single_run
from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.six_task_plan import validate_plan
from .retry_two import prior_identity


class CompleteResponseStartupTests(unittest.TestCase):
    def records(self, root: Path):
        slot = {'order': 1, 'task': 'adaptive-rejection-sampler', 'repeat': 1,
                'condition': 'P', 'research_candidate': 'PoS'}
        run_root = str(root / 'runs' / 'pos-test')
        manifest = {'schema': 'pos-ga-single-manifest-v1',
                    'execution_authorized': False,
                    'upstream_commit': '6818cfa6434dbc91fcf67f0b3eb12a91db47433f',
                    'zero_model_fixture_only': False,
                    'config': {'task_complete_response_policy': 'complete-response-v1'},
                    'config_sha256': '1' * 64, 'planned_order': [slot],
                    'assets': {slot['task']: {}}}
        bound = dict(slot, run_id='pos-test', run_root=run_root,
                     batch_id='pos-test', config_sha256=manifest['config_sha256'])
        grant = {'execution_authorized': True, 'zero_model_fixture_only': False,
                 'approved_arms': [slot], 'run_bindings': [bound],
                 'run_id': 'pos-test', 'batch_id': 'pos-test',
                 'config_sha256': manifest['config_sha256'],
                 'output_root': str(root / 'runs'),
                 'task_complete_response_policy': 'complete-response-v1'}
        identity = {'run_id': 'pos-test', 'run_root': run_root,
                    'manifest_sha256': 'manifest-test'}
        grant['manifest_sha256'] = identity['manifest_sha256']
        for name, value in [('manifest.json', manifest),
                            ('run_identity.json', identity),
                            ('authorization.json', grant)]:
            (root / name).write_text(json.dumps(value), encoding='utf-8')
        return manifest, grant

    def test_policy_is_required_in_grant_and_actual_entry(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            manifest, grant = self.records(root)
            self.assertEqual(len(validate_plan(manifest, grant)), 1)
            altered = dict(grant, task_complete_response_policy='disabled')
            with self.assertRaisesRegex(RuntimeError, 'authorization incomplete'):
                validate_plan(manifest, altered)
            args = type('Args', (), {'output': str(root),
                'authorization': str(root / 'authorization.json'),
                'zero_model_fixture': False,
                **{name: 'test-only' for name in ('ga_source', 'runtime_root',
                    'task_profile_file', 'pma_profile_file', 'worker_python',
                    'harbor_python', 'bench_root', 'official_source_git',
                    'harbor_source_root', 'python_home')}})()
            with patch.dict(os.environ, {'GA_TASK_COMPLETE_RESPONSE': '0'}), \
                 patch.object(single_run, 'run_batch') as batch:
                with self.assertRaisesRegex(RuntimeError, 'Task response policy'):
                    single_run.run(args)
                batch.assert_not_called()
            with patch.dict(os.environ, {'GA_TASK_COMPLETE_RESPONSE': '1'}), \
                 patch.object(single_run, 'run_batch', return_value={
                     'arms': [{'disposition': 'completed'}], 'stop_reason': None}) as batch:
                self.assertEqual(single_run.run(args)['run_id'], 'pos-test')
                batch.assert_called_once()

    def test_v4_history_is_checked_against_its_retained_bytes(self):
        old = prior_identity()
        self.assertEqual(len(old['preflight_index_sha256']), 64)
        self.assertEqual(old['historical_review']['reviewed_code_commit'],
                         '0fd4395a029dd3fb801a25eba0148249bcfa7321')


if __name__ == '__main__':
    unittest.main(verbosity=2)
