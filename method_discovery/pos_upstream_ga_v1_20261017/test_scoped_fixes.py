"""Fixed-blob verifier staging and PoS terminal/archive propagation; no model calls."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.export_official_evaluator import COMMIT, official_members
from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.live_launcher import _evaluator_members, _stage_verifier
from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.pma_harbor_hooks import pos_archive_summary
from method_discovery.pos_upstream_ga_v1_20261017.single_manifest import FOUR

GA = Path(__file__).resolve().parents[2] / 'GenericAgent-main'
sys.path.insert(0, str(GA))
from agentmain import build_task_terminal_record


class ScopedFixes(unittest.TestCase):
    def test_evaluator_member_schema_rejects_missing_conflicting_or_malformed(self):
        member = {'path': 'tests/test.sh', 'sha256': 'a' * 64, 'bytes': 12}
        for schema, primary in (('pos-ga-single-manifest-v1', 'evaluator_members'),
                                ('pma-ga-live-manifest-v5', 'official_evaluator_members')):
            with self.subTest(schema=schema):
                other = 'official_evaluator_members' if primary == 'evaluator_members' else 'evaluator_members'
                manifest = {'schema': schema, 'zero_model_fixture_only': False,
                            'assets': {'task': {primary: [member]}}}
                self.assertEqual(_evaluator_members(manifest, 'task'), [member])
                manifest['assets']['task'][other] = [dict(member)]
                self.assertEqual(_evaluator_members(manifest, 'task'), [member])
                manifest['assets']['task'][other][0]['sha256'] = 'b' * 64
                with self.assertRaises(RuntimeError): _evaluator_members(manifest, 'task')
                del manifest['assets']['task'][other]
                for bad in (None, {}, 'text', [], [None], [{}],
                            [{'path': 'tests/test.sh', 'sha256': None}]):
                    manifest['assets']['task'][primary] = bad
                    with self.assertRaises(RuntimeError): _evaluator_members(manifest, 'task')
                del manifest['assets']['task'][primary]
                manifest['assets']['task'][other] = [member]
                with self.assertRaises(RuntimeError): _evaluator_members(manifest, 'task')
        synthetic = {'schema': 'pos-ga-single-manifest-v1',
                     'zero_model_fixture_only': True,
                     'assets': {'pos-synthetic-file-http': {'official_evaluator_members': [],
                         'evaluator_members': []}}}
        self.assertEqual(_evaluator_members(synthetic, 'pos-synthetic-file-http'), [])

    def test_four_registered_evaluators_stage_from_fixed_blobs(self):
        source = Path(os.environ.get('POS_OFFICIAL_SOURCE_GIT',
                                    'E:/pma_d1_tb2_source_20261017'))
        if not source.is_dir():
            self.fail('fixed official Git source unavailable: ' + str(source))
        for task in FOUR:
            with self.subTest(task=task), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                members = [{k: v for k, v in row.items() if k != 'raw'}
                           for row in official_members(source, task, registered=True)]
                from long_context_bench.scripts.isolated_run_bundle import digest_tree
                from hashlib import sha256
                import tempfile as _tempfile
                with _tempfile.TemporaryDirectory() as staged:
                    tests = Path(staged)
                    from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.export_official_evaluator import export_task
                    export_task(source, task, tests, registered=True)
                    expected_tree = digest_tree(tests)
                    expected_sh = sha256((tests / 'test.sh').read_bytes()).hexdigest()
                manifest = {'schema': 'pos-ga-single-manifest-v1',
                    'official_source_git_commit': COMMIT,
                    'assets': {task: {'evaluator_members': members,
                        'native_tests_tree_sha256': expected_tree,
                        'native_test_sh_sha256': expected_sh}}}
                (root / 'public_task/tests').mkdir(parents=True)
                self.assertEqual(_stage_verifier(root, task, manifest, source)
                                 ['native_tests_tree_sha256'], expected_tree)
                with self.assertRaises((KeyError, RuntimeError, ValueError)):
                    _stage_verifier(root, 'not-the-registered-task', manifest, source)
                with tempfile.TemporaryDirectory() as bad:
                    (Path(bad) / 'public_task/tests').mkdir(parents=True)
                    corrupt = json.loads(json.dumps(manifest))
                    corrupt['assets'][task]['evaluator_members'][0]['sha256'] = '0' * 64
                    with self.assertRaises(RuntimeError):
                        _stage_verifier(Path(bad), task, corrupt, source)

    def test_host_archive_failure_reaches_persisted_terminal_and_native_summary(self):
        for failure in (False, True):
            with self.subTest(failure=failure):
                errors = [{'kind': 'terminal', 'error_type': 'OSError'}] if failure else []
                outcome = {'result': 'CURRENT_TASK_DONE',
                           'pos_archive_incomplete': failure,
                           'pos_auxiliary_errors': errors}
                final = {'status': 'completed', 'receipt_bound': True,
                         'close_status': 'graceful_exit', 'worker_return_code': 0,
                         'archive_incomplete': failure, 'auxiliary_errors': errors}
                terminal = build_task_terminal_record('run', 'task', outcome,
                    {'status': 'not_enabled'}, final)
                result = {'run_id': 'run', 'task_id': 'task', 'status': 'completed'}
                closed = {'run_id': 'run', 'task_id': 'task',
                          'status': 'graceful_exit', 'worker_return_code': 0}
                summary = pos_archive_summary('run', 'task', terminal, result, closed)
                self.assertEqual(terminal['result'], 'CURRENT_TASK_DONE')
                self.assertEqual(summary['task_result'], 'CURRENT_TASK_DONE')
                self.assertIs(summary['archive_incomplete'], failure)
                self.assertEqual(summary['auxiliary_errors'], errors)
                self.assertTrue(summary['result_bound'] and summary['close_bound'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
