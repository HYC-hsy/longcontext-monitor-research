import argparse
import hashlib
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
        if hasattr(args, 'evaluation_bootstrap_protocol'):
            single = json.loads((root / 'plan.json').read_text())
            single['evaluation_bootstrap_protocol'] = args.evaluation_bootstrap_protocol
            (root / 'plan.json').write_text(json.dumps(single))
            manifest['config'] = {'evaluation_bootstrap_protocol': args.evaluation_bootstrap_protocol}
        if hasattr(args, 'evaluation_cache'):
            single = json.loads((root / 'plan.json').read_text())
            single['evaluation_cache'] = args.evaluation_cache
            (root / 'plan.json').write_text(json.dumps(single))
            manifest.setdefault('config', {})['evaluation_cache'] = args.evaluation_cache
        if hasattr(args, 'evaluation_download_retry'):
            single = json.loads((root / 'plan.json').read_text())
            single['evaluation_download_retry'] = args.evaluation_download_retry
            (root / 'plan.json').write_text(json.dumps(single))
            manifest.setdefault('config', {})['evaluation_download_retry'] = args.evaluation_download_retry
        if hasattr(args, 'preserve_pre_eval_snapshot'):
            single = json.loads((root / 'plan.json').read_text())
            single['preserve_pre_eval_snapshot'] = args.preserve_pre_eval_snapshot
            (root / 'plan.json').write_text(json.dumps(single))
            manifest.setdefault('config', {})['preserve_pre_eval_snapshot'] = args.preserve_pre_eval_snapshot
        if args.fake_only and args.research_candidate == 'pma_stateful_memory_v1':
            driver = importlib.import_module(DRIVER + '.single_run')
            replies = Path(driver.__file__).with_name('stateful_fixture_replies.json')
            manifest['stateful_fake_replies_sha256'] = hashlib.sha256(replies.read_bytes()).hexdigest()
        if hasattr(args, 'runtime_policy'):
            from experiment_runner.runtime_policy import resolve_policy
            single = json.loads((root / 'plan.json').read_text())
            single['runtime_policy'] = args.runtime_policy
            (root / 'plan.json').write_text(json.dumps(single))
            manifest.setdefault('config', {})['runtime_policy'] = resolve_policy(args.runtime_policy,
                {'native_agent_seconds': 900, 'native_verifier_seconds': 900},
                {'task_turns_max': (None if args.research_candidate in {
                    'pma_stateful_memory_v1', 'pma_gap_memory_v0', 'pma_gap_evidence_v1'} else 300)})
            for key in ('native_context_policy', 'research_capture_policy'):
                value = getattr(args, key, 'required')
                single[key] = value
                manifest['config'][key] = value
            (root / 'plan.json').write_text(json.dumps(single))
        config = manifest.setdefault('config', {})
        config.update(research_candidate=args.research_candidate,
                      task_complete_response_policy='complete-response-v1' if args.task_complete_response else 'disabled')
        if args.research_candidate == 'pma_stateful_memory_v1':
            config.update(agent_time_protocol='runtime-policy-v1',
                          native_context_policy=getattr(args, 'native_context_policy', 'required'),
                          research_capture_policy=getattr(args, 'research_capture_policy', 'required'))
        manifest.update(schema='pos-ga-single-manifest-v1' if args.condition == 'P' else
                        'pma-ga-live-manifest-v5', execution_authorized=False,
                        config_sha256='synthetic-config',
                        upstream_commit='6818cfa6434dbc91fcf67f0b3eb12a91db47433f',
                        assets={args.task: {'native_agent_seconds': 900, 'native_verifier_seconds': 900}},
                        planned_order=[{'order': 1, 'task': args.task, 'repeat': args.occurrence,
                                        'condition': args.condition, 'research_candidate': args.research_candidate}])
        if args.condition == 'P':
            config['name'] = args.research_candidate
            config['citation_mode'] = 'visible_tool_fields_v2'
        (root / 'manifest.json').write_text(json.dumps(manifest))
        run_id = 'fixture-' + str(len(self.prepared))
        identity = {'run_id': run_id, 'run_root': str(root / 'runs' / run_id),
                    'output_root': str(root / 'runs'), 'execution_authorized': False,
                    'plan_sha256': hashlib.sha256((root / 'plan.json').read_bytes()).hexdigest(),
                    'manifest_sha256': hashlib.sha256((root / 'manifest.json').read_bytes()).hexdigest()}
        (root / 'run_identity.json').write_text(json.dumps(identity))
        return identity


    def run(self, args):
        self.runs.append(args)
        self.task_response_environment = os.environ.get('GA_TASK_COMPLETE_RESPONSE')
        return {'stop_reason': 'fixture_failure' if self.fail_run else None,
                'arm': {'disposition': 'failed' if self.fail_run else 'completed'}}


class FrontendTests(unittest.TestCase):
    def setUp(self):
        identity = patch('experiment_runner.startup.code_identity', return_value={
            'kind': 'synthetic_test_identity', 'code_commit': 'fixture'})
        identity.start()
        self.addCleanup(identity.stop)
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

    def test_all_method_policy_prepare_matrix(self):
        from experiment_runner.methods import builtin_specs
        cases = ({}, {'agent_timeout': 1.5, 'task_turns': 2},
                 {'agent_timeout': 'uncapped', 'task_turns': 'uncapped'})
        for method in builtin_specs():
            for index, policy in enumerate(cases):
                with self.subTest(method=method.name, policy=policy):
                    config = dict(self.config, method=method.name, runtime_policy=policy,
                                  slots=[{'task': 'sqlite-with-gcov'}])
                    plan = build_plan(config)
                    backend = FakeBackend()
                    output = self.root / (method.name + str(index))
                    self.assertTrue(succeeded(execute(plan, output, 'prepare', backend), 1, 'prepare'))
                    self.assertEqual(backend.runs, [])
                    self.assertEqual(backend.prepared[0].runtime_policy, policy)
                    self.assertEqual(plan['slots'][0]['effective_runtime_policy']['method_default_task_turns'],
                                     method.task_turns_max)

    def test_defaults_and_explicit_empty_for_every_method_and_alias(self):
        from dataclasses import replace
        from experiment_runner.methods import builtin_specs, register
        for method in builtin_specs():
            config = dict(self.config, method=method.name)
            absent = build_plan(config)['slots'][0]
            expected = method.research_candidate in {
                'pma_stateful_memory_v1', 'pma_gap_memory_v0', 'pma_gap_evidence_v1'}
            self.assertEqual('effective_runtime_policy' in absent, expected)
            explicit = build_plan(dict(config, runtime_policy={}))['slots'][0]
            self.assertEqual(explicit['effective_runtime_policy']['effective_agent_seconds'], 900)
        register(replace(builtin_specs()[0], name='test-ga-runtime-alias'))
        config = dict(self.config, method='test-ga-runtime-alias')
        self.assertNotIn('effective_runtime_policy', build_plan(config)['slots'][0])
        self.assertIn('effective_runtime_policy', build_plan(dict(config, runtime_policy={}))['slots'][0])

    def test_fresh_run_automatic_prepare_isolated_and_once(self):
        for name in ('first', 'second'):
            backend = FakeBackend()
            output = self.root / name
            self.assertTrue(succeeded(execute(self.plan, output, 'run', backend), 2, 'run'))
            self.assertEqual(len(backend.prepared), 2)
            self.assertEqual(len(backend.runs), 2)
            self.assertTrue((output / 'run_claim.json').exists())
            self.assertFalse(list(output.rglob('.run_binding.json')))
            with self.assertRaises(FileExistsError):
                execute(self.plan, output, 'run', backend)

    def test_run_claim_blocks_concurrent_entry(self):
        backend = FakeBackend()
        execute(self.plan, self.output, 'prepare', backend)
        (self.output / 'run_claim.json').write_text('{}')
        with self.assertRaises(FileExistsError):
            execute(self.plan, self.output, 'run', backend)
        self.assertEqual(backend.runs, [])

    def test_identity_tampering_and_prior_allocation_rejected(self):
        from experiment_runner.startup import internal_binding
        backend = FakeBackend()
        execute(self.plan, self.output, 'prepare', backend)
        directory = next(self.output.glob('01-*'))
        path = directory / 'run_identity.json'
        original = json.loads(path.read_text())
        for key, value in (('run_id', '../escape'), ('run_root', '/tmp/escape'),
                           ('output_root', '/tmp'), ('plan_sha256', 'changed'),
                           ('manifest_sha256', 'changed'), ('execution_authorized', True)):
            path.write_text(json.dumps(dict(original, **{key: value})))
            with self.assertRaises(ValueError):
                internal_binding(directory)
        path.write_text(json.dumps(original))
        (directory / 'runs' / 'old-attempt').mkdir(parents=True)
        with self.assertRaises(FileExistsError):
            internal_binding(directory)

    def test_transient_record_cleanup_on_failure_and_existing_file_preserved(self):
        backend = FakeBackend(fail_run=True)
        execute(self.plan, self.output, 'prepare', backend)
        directory = next(self.output.glob('01-*'))
        old = directory / 'authorization.json'
        old.write_text('user-owned')
        rows = execute(self.plan, self.output, 'run', backend)
        self.assertEqual(len(backend.runs), 1)
        self.assertFalse(succeeded(rows, 2, 'run'))
        self.assertEqual(old.read_text(), 'user-owned')
        self.assertFalse(list(self.output.rglob('.run_binding.json')))

    def test_summary_is_planned_and_source_is_visible(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from experiment_runner.runtime_policy import print_plan_summary
        output = StringIO()
        with redirect_stdout(output):
            print_plan_summary(build_plan(dict(self.config, runtime_policy={'task_turns': 7})))
        text = output.getvalue()
        self.assertIn('planned limits', text)
        self.assertIn('turns=7', text)
        self.assertIn('source: official', text)
        self.assertIn('runtime checks pending', text)
        output = StringIO()
        with redirect_stdout(output):
            print_plan_summary(build_plan(dict(self.config, runtime_policy={
                'agent_timeout': 'uncapped', 'task_turns': 'uncapped'})))
        self.assertIn('agent=uncapped (source: uncapped)', output.getvalue())
        self.assertNotIn('uncappeds', output.getvalue())

    def test_versioned_evaluator_bootstrap_is_frozen_and_real_only(self):
        self.config['evaluation_bootstrap_protocol'] = 'bootstrap_retry_v1'
        plan = build_plan(self.config)
        backend = FakeBackend()
        self.assertTrue(succeeded(execute(plan, self.output, 'prepare', backend), 2, 'prepare'))
        self.assertEqual(backend.prepared[0].evaluation_bootstrap_protocol,
                         'bootstrap_retry_v1')
        self.assertEqual(json.loads(next(self.output.glob('01-*/manifest.json')).read_text())[
            'config']['evaluation_bootstrap_protocol'], 'bootstrap_retry_v1')
        self.config['environment']['fake_only'] = True
        with self.assertRaisesRegex(ValueError, 'real sqlite'):
            from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.single_run import prepare
            # The actual backend rejects fake-only before materializing a task.
            prepare(argparse.Namespace(condition='B', research_candidate='pma_stateful_memory_v1',
                runtime_policy=None, evaluation_bootstrap_protocol='bootstrap_retry_v1',
                task='sqlite-with-gcov', fake_only=True, output=str(self.root / 'no-start')))

    def test_ga_only_pre_evaluation_snapshot_is_explicit_and_bound(self):
        self.config['method'] = 'ga-only'
        self.config['slots'] = [{'task': 'sqlite-with-gcov'}]
        self.config['preserve_pre_eval_snapshot'] = True
        self.config['environment']['fake_only'] = False
        plan = build_plan(self.config)
        backend = FakeBackend()
        self.assertTrue(succeeded(execute(plan, self.output, 'prepare', backend), 1, 'prepare'))
        self.assertTrue(backend.prepared[0].preserve_pre_eval_snapshot)
        manifest = json.loads(next(self.output.glob('01-*/manifest.json')).read_text())
        self.assertIs(manifest['config']['preserve_pre_eval_snapshot'], True)
        self.config['method'] = 'pma'
        with self.assertRaisesRegex(ValueError, 'requires a real ga-only'):
            build_plan(self.config)

    def test_persistent_cache_binding_reaches_backend_and_is_frozen(self):
        cache = {'bundle_path': str((self.root / 'bundle').resolve()), 'manifest_sha256': 'a' * 64,
                 'identity': {'protocol': 'persistent_bundle_v1'}}
        self.config['evaluation_bootstrap_protocol'] = 'persistent_bundle_v1'
        self.config['evaluation_cache'] = cache
        plan = build_plan(self.config)
        backend = FakeBackend()
        self.assertTrue(succeeded(execute(plan, self.output, 'prepare', backend), 2, 'prepare'))
        self.assertEqual(backend.prepared[0].evaluation_cache, cache)
        manifest = json.loads(next(self.output.glob('01-*/manifest.json')).read_text())
        self.assertEqual(manifest['config']['evaluation_cache'], cache)
        self.config['evaluation_cache'] = {**cache, 'manifest_sha256': 'b' * 64}
        with self.assertRaisesRegex(ValueError, 'configuration/adapter/catalog changed'):
            execute(build_plan(self.config), self.output, 'run', backend)

    def test_download_retry_is_frozen_and_reaches_driver_without_cache(self):
        self.config.update(method='pma-gap', slots=[{'task': 'db-wal-recovery'}],
                           evaluation_bootstrap_protocol='download_retry_v1',
                           evaluation_download_retry={'max_attempts': 3},
                           on_slot_failure='continue')
        self.public['tasks'].append({'task': 'db-wal-recovery',
                                     'agent_timeout_sec': 900,
                                     'verifier_timeout_sec': 900})
        plan = build_plan(self.config)
        backend = FakeBackend()
        self.assertEqual(execute(plan, self.output, 'prepare', backend)[0]['status'],
                         'prepared_not_authorized')
        self.assertEqual(backend.prepared[0].evaluation_download_retry, {'max_attempts': 3})
        self.assertNotIn('evaluation_cache', vars(backend.prepared[0]))
        manifest = json.loads(next(self.output.glob('01-*/manifest.json')).read_text())
        self.assertEqual(manifest['config']['evaluation_download_retry'], {'max_attempts': 3})
        self.assertEqual(plan['config']['on_slot_failure'], 'continue')
        changed = {**self.config, 'evaluation_download_retry': {'max_attempts': 2}}
        with self.assertRaisesRegex(ValueError, 'configuration/adapter/catalog changed'):
            execute(build_plan(changed), self.output, 'run', backend)

    def test_download_retry_defaults_and_rejects_bad_options(self):
        self.config['evaluation_bootstrap_protocol'] = 'download_retry_v1'
        path = self.root / 'config.json'
        path.write_text(json.dumps(self.config))
        loaded = load_config(path)
        self.assertEqual(loaded['evaluation_download_retry'], {'max_attempts': 3})
        self.config['evaluation_download_retry'] = {'max_attempts': 0}
        path.write_text(json.dumps(self.config))
        with self.assertRaisesRegex(ValueError, 'max_attempts'):
            load_config(path)
        self.config['evaluation_download_retry'] = {'max_attempts': 3}
        self.config['evaluation_bootstrap_protocol'] = 'original'
        path.write_text(json.dumps(self.config))
        with self.assertRaisesRegex(ValueError, 'requires download_retry_v1'):
            load_config(path)

    def test_cache_config_is_absolute_and_requires_offline_receipt(self):
        config = {**self.config, 'evaluation_bootstrap_protocol': 'persistent_bundle_v1',
                  'evaluation_cache': {'bundle_path': 'bundle',
                      'manifest_sha256': 'a' * 64, 'identity': {'protocol': 'persistent_bundle_v1'}}}
        path = self.root / 'config.json'
        path.write_text(json.dumps(config), encoding='utf-8')
        (self.root / 'bundle').mkdir()
        with patch('experiment_runner.evaluation_cache.verify_bundle'), patch(
                'experiment_runner.evaluation_cache.require_offline_ready') as ready:
            loaded = load_config(path)
        self.assertEqual(loaded['evaluation_cache']['bundle_path'], str((self.root / 'bundle').resolve()))
        ready.assert_called_once_with(str((self.root / 'bundle').resolve()), 'a' * 64)
        with patch('experiment_runner.evaluation_cache.verify_bundle'), patch(
                'experiment_runner.evaluation_cache.require_offline_ready',
                side_effect=RuntimeError('offline acceptance missing')):
            with self.assertRaisesRegex(RuntimeError, 'offline acceptance missing'):
                load_config(path)

    def test_gap_runtime_policy_is_frozen_without_stateful_transport(self):
        self.config['method'] = 'pma-gap'
        self.config['slots'] = [{'task': 'sqlite-with-gcov'}]
        self.config['runtime_policy'] = {'agent_timeout': 'uncapped',
            'task_turns': 'uncapped', 'verifier_timeout': 'official'}
        plan = build_plan(self.config)
        slot = plan['slots'][0]
        self.assertEqual(slot['adapter']['research_candidate'], 'pma_gap_memory_v0')
        self.assertIsNone(slot['effective_runtime_policy']['effective_agent_seconds'])
        backend = FakeBackend()
        self.assertEqual(execute(plan, self.output, 'prepare', backend)[0]['status'],
                         'prepared_not_authorized')
        self.assertEqual(backend.prepared[0].runtime_policy,
                         self.config['runtime_policy'])
        self.assertFalse(backend.prepared[0].task_complete_response)
        self.config['native_context_policy'] = 'off'
        with self.assertRaisesRegex(ValueError, 'stateful transport policy'):
            build_plan(self.config)

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

    def test_stateful_fake_replies_match_frozen_fixture(self):
        self.config['environment']['fake_only'] = True
        plan = build_plan(self.config)
        backend = FakeBackend()
        self.assertTrue(succeeded(execute(plan, self.output, 'prepare', backend), 2, 'prepare'))
        self.authorize()
        self.assertTrue(succeeded(execute(plan, self.output, 'run', backend), 2, 'run'))
        replies = Path(backend.runs[0].stateful_fake_replies)
        self.assertEqual(replies.name, 'stateful_fixture_replies.json')
        self.assertEqual(hashlib.sha256(replies.read_bytes()).hexdigest(),
            json.loads(next(self.output.glob('01-*/manifest.json')).read_text())[
                'stateful_fake_replies_sha256'])

    def test_stateful_fake_replies_identity_mismatch_rejected(self):
        self.config['environment']['fake_only'] = True
        plan = build_plan(self.config)
        backend = FakeBackend()
        execute(plan, self.output, 'prepare', backend)
        self.authorize()
        directory = next(self.output.glob('01-*/'))
        manifest_path = directory / 'manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['stateful_fake_replies_sha256'] = '0' * 64
        manifest_path.write_text(json.dumps(manifest))
        binding_path = directory / 'frontend_binding.json'
        binding = json.loads(binding_path.read_text())
        binding['manifest_sha256'] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        binding_path.write_text(json.dumps(binding))
        rows = execute(plan, self.output, 'run', backend)
        self.assertEqual(rows[0]['status'], 'not_started_validation_failure')
        self.assertIn('identity mismatch', rows[0]['error'])
        self.assertFalse(backend.runs)

    def test_ga_only_fake_has_no_stateful_replies(self):
        self.config['method'] = 'ga-only'
        self.config['environment']['fake_only'] = True
        plan = build_plan(self.config)
        backend = FakeBackend()
        execute(plan, self.output, 'prepare', backend)
        self.authorize()
        self.assertTrue(succeeded(execute(plan, self.output, 'run', backend), 2, 'run'))
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

    def test_stateful_transport_policies_freeze_and_reach_prepare(self):
        self.config.update(native_context_policy='off', research_capture_policy='best_effort')
        plan = build_plan(self.config)
        self.assertNotEqual(plan['plan_sha256'], self.plan['plan_sha256'])
        backend = FakeBackend()
        rows = execute(plan, self.output, 'prepare', backend)
        self.assertTrue(succeeded(rows, 2, 'prepare'))
        self.assertEqual(backend.prepared[0].native_context_policy, 'off')
        self.assertEqual(backend.prepared[0].research_capture_policy, 'best_effort')
        directory = next(self.output.glob('01-*/'))
        single = json.loads((directory / 'plan.json').read_text())
        manifest = json.loads((directory / 'manifest.json').read_text())
        for key, value in (('native_context_policy', 'off'),
                           ('research_capture_policy', 'best_effort')):
            self.assertEqual(single[key], value)
            self.assertEqual(manifest['config'][key], value)
        self.config['native_context_policy'] = 'required'
        with self.assertRaisesRegex(ValueError, 'changed'):
            execute(build_plan(self.config), self.output, 'run', backend)

    def test_stateful_transport_policy_rejects_invalid_or_legacy(self):
        self.config['native_context_policy'] = 'unknown'
        path = self.root / 'invalid.json'
        path.write_text(json.dumps(self.config))
        with self.assertRaisesRegex(ValueError, 'invalid stateful'):
            load_config(path)
        self.config.update(native_context_policy='off', method='pma')
        with self.assertRaisesRegex(ValueError, 'unsupported'):
            build_plan(self.config)

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

    def test_policy_supported_by_all_adapters(self):
        self.config.update(method='pma', runtime_policy={})
        self.assertIn('effective_runtime_policy', build_plan(self.config)['slots'][0])

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

    def test_explicit_run_needs_no_approval_file(self):
        backend = FakeBackend()
        execute(self.plan, self.output, 'prepare', backend)
        rows = execute(self.plan, self.output, 'run', backend)
        self.assertTrue(succeeded(rows, 2, 'run'))
        self.assertEqual(len(backend.runs), 2)
        self.assertFalse(list(self.output.rglob('.run_binding.json')))

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
