import argparse
import importlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from experiment_runner.__main__ import build_plan, execute, load_config, succeeded, main, method_environment, DRIVER


class FakeBackend:
    def __init__(self, fail_run=False):
        self.prepared = []
        self.runs = []
        self.fail_run = fail_run

    def prepare(self, args):
        self.prepared.append(args)
        root = Path(args.output)
        root.mkdir()
        (root / 'plan.json').write_text(json.dumps({
            'condition': args.condition, 'research_candidate': args.research_candidate,
            'task_complete_response_policy': 'complete-response-v1' if args.task_complete_response else 'disabled'}))
        manifest = {'fixture': True}
        if hasattr(args, 'runtime_policy'):
            from experiment_runner.runtime_policy import resolve_policy
            single = json.loads((root / 'plan.json').read_text())
            single['runtime_policy'] = args.runtime_policy
            (root / 'plan.json').write_text(json.dumps(single))
            manifest['config'] = {'runtime_policy': resolve_policy(args.runtime_policy,
                {'native_agent_seconds': 900, 'native_verifier_seconds': 900},
                {'task_turns_max': None})}
        (root / 'manifest.json').write_text(json.dumps(manifest))
        return {'run_id': str(len(self.prepared)), 'execution_authorized': False}

    def run(self, args):
        self.runs.append(args)
        self.task_response_environment = os.environ.get('GA_TASK_COMPLETE_RESPONSE')
        return {'stop_reason': 'fixture_failure' if self.fail_run else None,
                'arm': {'disposition': 'failed' if self.fail_run else 'completed'}}


class FrontendTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.commit = importlib.import_module(DRIVER + '.export_official_evaluator').COMMIT
        self.config = {'schema': 'ga-experiment-plan-v1',
            'dataset': {'source_git': str(self.root), 'commit': self.commit},
            'method': 'pma-stateful', 'slots': [{'task': 'sqlite-with-gcov'},
                {'task': 'sqlite-with-gcov', 'occurrence': 2}],
            'environment': {'profiles': {'task_profile_file': '/task.py', 'pma_profile_file': '/pma.py'},
                'paths': {k: '/fixture/' + k for k in ('ga_source', 'runtime_root',
                    'worker_python', 'harbor_python', 'bench_root', 'harbor_source_root')}}}
        self.public = {'tasks': [{'task': 'sqlite-with-gcov', 'agent_timeout_sec': 900,
                                 'verifier_timeout_sec': 900}]}
        mock = patch('experiment_runner.__main__.catalog', return_value=self.public)
        mock.start()
        self.addCleanup(mock.stop)
        self.plan = build_plan(self.config)
        self.output = self.root / 'prepared'

    def authorize(self):
        for directory in self.output.iterdir():
            if directory.is_dir():
                (directory / 'authorization.json').write_text('{}')

    def test_prepare_and_serial_run_use_adapter(self):
        backend = FakeBackend()
        rows = execute(self.plan, self.output, 'prepare', backend)
        self.assertTrue(succeeded(rows, 2, 'prepare'))
        self.assertEqual(backend.prepared[0].research_candidate, 'pma_stateful_memory_v1')
        self.assertTrue(backend.prepared[0].task_complete_response)
        self.assertFalse(any(self.output.rglob('authorization.json')))
        self.authorize()
        rows = execute(self.plan, self.output, 'run', backend)
        self.assertTrue(succeeded(rows, 2, 'run'))
        self.assertEqual(len(backend.runs), 2)
        self.assertFalse(backend.runs[0].candidate_profile_fixture)
        self.assertIsNone(backend.runs[0].stateful_fake_replies)

    def test_default_stateful_policy_is_explicit_official(self):
        self.assertNotIn('runtime_policy', self.config)
        row = self.plan['slots'][0]
        self.assertEqual(row['requested_runtime_policy'], {})
        self.assertEqual(row['effective_runtime_policy']['effective_agent_seconds'], 900)
        self.assertEqual(row['effective_runtime_policy']['protocol_label'], 'official_agent_limits')
        backend = FakeBackend()
        rows = execute(self.plan, self.output, 'prepare', backend)
        self.assertTrue(succeeded(rows, 2, 'prepare'))
        self.assertEqual(backend.prepared[0].runtime_policy, {})
        manifest = json.loads(next(self.output.glob('01-*/manifest.json')).read_text())
        self.assertEqual(manifest['config']['runtime_policy'], row['effective_runtime_policy'])

    def test_legacy_omitted_policy_remains_omitted(self):
        self.config['method'] = 'pma'
        plan = build_plan(self.config)
        self.assertNotIn('requested_runtime_policy', plan['slots'][0])
        self.assertNotIn('effective_runtime_policy', plan['slots'][0])
        backend = FakeBackend()
        rows = execute(plan, self.output, 'prepare', backend)
        self.assertTrue(succeeded(rows, 2, 'prepare'))
        self.assertFalse(hasattr(backend.prepared[0], 'runtime_policy'))

    def test_default_policy_cannot_be_ignored(self):
        backend = FakeBackend()
        original = backend.prepare
        def ignoring(args):
            del args.runtime_policy
            return original(args)
        backend.prepare = ignoring
        rows = execute(self.plan, self.output, 'prepare', backend)
        self.assertEqual(rows[0]['status'], 'preparation_failed')
        self.assertIn('ignored', rows[0]['error'])

    def test_runtime_policy_forwarded_and_bound(self):
        self.config['runtime_policy'] = {'agent_timeout': 'uncapped', 'task_turns': 'uncapped'}
        plan = build_plan(self.config)
        self.assertIsNone(plan['slots'][0]['effective_runtime_policy']['effective_agent_seconds'])
        backend = FakeBackend()
        rows = execute(plan, self.output, 'prepare', backend)
        self.assertTrue(succeeded(rows, 2, 'prepare'))
        self.assertEqual(backend.prepared[0].runtime_policy, self.config['runtime_policy'])

    def test_ignored_policy_rejected(self):
        self.config['runtime_policy'] = {'agent_timeout': 'uncapped'}
        backend = FakeBackend()
        original = backend.prepare
        def ignoring(args):
            del args.runtime_policy
            return original(args)
        backend.prepare = ignoring
        rows = execute(build_plan(self.config), self.output, 'prepare', backend)
        self.assertEqual(rows[0]['status'], 'preparation_failed')
        self.assertIn('ignored', rows[0]['error'])

    def test_unsupported_policy_rejected(self):
        self.config.update(method='pma', runtime_policy={})
        with self.assertRaisesRegex(ValueError, 'unsupported'):
            build_plan(self.config)

    def test_response_environment_scoped(self):
        backend = FakeBackend()
        execute(self.plan, self.output, 'prepare', backend)
        self.authorize()
        with patch.dict(os.environ, {'GA_TASK_COMPLETE_RESPONSE': 'outside'}):
            execute(self.plan, self.output, 'run', backend)
            self.assertEqual(os.environ['GA_TASK_COMPLETE_RESPONSE'], 'outside')
        self.assertEqual(backend.task_response_environment, '1')

    def test_polluted_method_flags_are_scoped_and_restored(self):
        from experiment_runner.methods import resolve
        flags = ('GA_STATEFUL_MEMORY_ENABLED', 'GA_POS_ENABLED',
                 'GA_PMA_UPSTREAM_ENABLED', 'GA_PMA_ENABLED',
                 'GA_MONITOR_ENABLED', 'GA_M0_MONITOR_ENABLED',
                 'GA_POS_PMA_COMPLEMENT', 'GA_POS_PMA_SHARED_VIEW')
        polluted = {flag: '1' for flag in flags}
        polluted.update(GA_EXPERIMENT_TASK_TURNS='17', GA_TASK_COMPLETE_RESPONSE='1')
        for name in ('ga-only', 'pma', 'pma-stateful', 'pos'):
            for fail in (False, True):
                with self.subTest(method=name, raises=fail), patch.dict(os.environ, polluted):
                    try:
                        with method_environment(resolve(name)):
                            for flag in flags:
                                self.assertEqual(os.environ[flag], '0')
                            self.assertNotIn('GA_EXPERIMENT_TASK_TURNS', os.environ)
                            expected = '1' if resolve(name).task_complete_response else None
                            self.assertEqual(os.environ.get('GA_TASK_COMPLETE_RESPONSE'), expected)
                            if fail:
                                raise RuntimeError('fixture failure')
                    except RuntimeError:
                        self.assertTrue(fail)
                    for key, value in polluted.items():
                        self.assertEqual(os.environ[key], value)

    def test_absent_method_flags_remain_absent_after_failure(self):
        from experiment_runner.methods import resolve
        keys = resolve('ga-only').runtime_environment()
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError):
                with method_environment(resolve('ga-only')):
                    raise RuntimeError('fixture failure')
            for key in keys:
                self.assertNotIn(key, os.environ)

    def test_failure_stops_and_records_remaining(self):
        backend = FakeBackend(fail_run=True)
        execute(self.plan, self.output, 'prepare', backend)
        self.authorize()
        rows = execute(self.plan, self.output, 'run', backend)
        self.assertFalse(succeeded(rows, 2, 'run'))
        self.assertEqual(len(backend.runs), 1)
        result = json.loads((self.output / 'selection_result.json').read_text())
        self.assertEqual(len(result['remaining_not_started']), 1)

    def test_no_approval_means_zero_runs(self):
        backend = FakeBackend()
        execute(self.plan, self.output, 'prepare', backend)
        rows = execute(self.plan, self.output, 'run', backend)
        self.assertEqual(rows[0]['status'], 'not_started_missing_approval')
        self.assertEqual(backend.runs, [])

    def test_changed_config_rejected(self):
        backend = FakeBackend()
        execute(self.plan, self.output, 'prepare', backend)
        self.config['environment']['profiles']['task_profile_file'] = '/changed.py'
        with self.assertRaisesRegex(ValueError, 'changed'):
            execute(build_plan(self.config), self.output, 'run', backend)
        self.assertEqual(backend.runs, [])

    def test_manifest_tamper_is_not_started(self):
        backend = FakeBackend()
        execute(self.plan, self.output, 'prepare', backend)
        self.authorize()
        next(self.output.glob('01-*/manifest.json')).write_text('{}')
        rows = execute(self.plan, self.output, 'run', backend)
        self.assertEqual(rows[0]['status'], 'not_started_validation_failure')
        self.assertEqual(backend.runs, [])

    def test_plan_rejects_unknown_method_without_backend(self):
        self.config['method'] = 'no-such-method'
        with self.assertRaisesRegex(ValueError, 'unknown method'):
            build_plan(self.config)
        self.assertFalse(self.output.exists())

    def test_bad_parallel_rejected_on_load(self):
        self.config['execution'] = 'parallel'
        path = self.root / 'config.json'
        path.write_text(json.dumps(self.config))
        with self.assertRaisesRegex(ValueError, 'serial'):
            load_config(path)

    def test_plan_cli_never_imports_backend_or_executes_profiles(self):
        path = self.root / 'config.json'
        path.write_text(json.dumps(self.config))
        output = self.root / 'plan.json'
        with patch('experiment_runner.__main__._backend', side_effect=AssertionError('no backend')):
            self.assertEqual(main(['plan', '--config', str(path), '--output', str(output)]), 0)
        self.assertEqual(json.loads(output.read_text())['schema'], 'ga-experiment-resolved-v1')

    def test_malformed_outcome_not_counted_twice(self):
        backend = FakeBackend()
        execute(self.plan, self.output, 'prepare', backend)
        self.authorize()
        backend.run = lambda args: {'unexpected': 'shape'}
        rows = execute(self.plan, self.output, 'run', backend)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['status'], 'not_started_validation_failure')
        result = json.loads((self.output / 'selection_result.json').read_text())
        self.assertEqual(len(result['remaining_not_started']), 1)

    def test_legacy_slots_preserved(self):
        legacy = importlib.import_module(DRIVER + '.run_selection')
        plan = {'schema': 'pma-ga-ordered-selection-v1', 'execution_authorized': False,
                'official_source_git_commit': self.commit,
                'slots': [{'task': 'sqlite-with-gcov', 'condition': 'A', 'occurrence': 1}]}
        self.assertEqual(legacy._slots(plan), plan['slots'])
        plan['slots'][0]['condition'] = 'P'
        with self.assertRaises(ValueError):
            legacy._slots(plan)


if __name__ == '__main__':
    unittest.main()
