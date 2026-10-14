"""Zero-model checks for the unarmed six-task native-Harbor preparation."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from long_context_bench.scripts.isolated_run_bundle import build_bundle

from . import batch_controller, live_launcher
from .six_task_plan import ORDER, validate_plan
from .six_task_assets import descriptor, materialize_public
from .export_official_evaluator import export_task


class SixTaskNativeBaseTests(unittest.TestCase):
    def test_worker_stop_is_separate_from_memory_save_status(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'control').mkdir()
            private = root / 'host_private'
            private.mkdir()
            (private / 'worker_exit.json').write_text(json.dumps({
                'run_id': 'fixture', 'task_end_saved': False,
                'reason': 'host_stop'}), encoding='utf-8')
            (private / 'worker_stopped_without_task_end.json').write_text(json.dumps({
                'reason': 'host_stop', 'remote_execution': 'unknown',
                'local_save': {'status': 'failed', 'error_type': 'OSError'}}),
                encoding='utf-8')
            worker = SimpleNamespace(pid=123, returncode=0, poll=lambda: 0)
            clearance = live_launcher._worker_clearance(root, worker, 'fixture')
            self.assertTrue(clearance['clean'])
            self.assertFalse(clearance['pma_finalization']['task_end_saved'])
            self.assertEqual(clearance['pma_finalization']['local_save']['status'], 'failed')

    def test_batch_to_real_launcher_and_harbor_uses_fake_send_only(self):
        if os.environ.get('PMA_ZERO_MODEL_INTEGRATION') != '1':
            self.skipTest('explicit zero-model Docker integration not requested')
        stage = Path(__file__).parent
        source_manifest = json.loads((stage / 'six_task_discovery_20261014' /
            'PMA_GA_6TASK_NATIVE_BASE_DRAFT_V2R7.json').read_text(encoding='utf-8'))
        harbor_python = Path(os.environ['PMA_HARBOR_PYTHON']).resolve(strict=True)
        root = Path(os.environ['PMA_ZERO_MODEL_EVIDENCE_ROOT']).resolve(strict=False)
        if root.exists():
            self.fail('zero-model integration output root already exists')
        root.mkdir(parents=True)
        try:
            manifest = root / 'manifest.json'
            auth = root / 'authorization.json'
            source_manifest['zero_model_fixture_only'] = True
            manifest.write_text(json.dumps(source_manifest), encoding='utf-8')
            manifest_hash = hashlib.sha256(manifest.read_bytes()).hexdigest()
            head = subprocess.run(['git', 'rev-parse', 'HEAD'],
                cwd=stage.parents[2], capture_output=True, text=True,
                check=True).stdout.strip()
            bindings = [dict(row, batch_id='zero-model-fixture',
                config_sha256=source_manifest['config_sha256'],
                run_id=f'zero-model-native-{row["order"]}',
                run_root=str(root / f'run-{row["order"]}'))
                for row in source_manifest['planned_order']]
            auth.write_text(json.dumps({'execution_authorized': True,
                'zero_model_fixture_only': True, 'manifest_sha256': manifest_hash,
                'audited_code_commit': head, 'approved_arms': source_manifest['planned_order'],
                'run_bindings': bindings, 'batch_id': 'zero-model-fixture',
                'config_sha256': source_manifest['config_sha256']}), encoding='utf-8')
            command = [str(harbor_python), '-m',
                'method_discovery.curator_supervisor_convergence_v0.'
                'pma_full_upstream_ga_v1_20261013.batch_controller',
                '--zero-model-fixture', '--manifest', str(manifest),
                '--authorization', str(auth), '--batch-result', str(root / 'batch.json'),
                '--ga-source', os.environ['PMA_GA_SOURCE'],
                '--runtime-root', os.environ['PMA_RUNTIME_ROOT'],
                '--task-profile-file', os.environ['PMA_TASK_PROFILE'],
                '--worker-python', str(harbor_python), '--harbor-python', str(harbor_python),
                '--bench-root', os.environ['PMA_BENCH_ROOT'],
                '--official-source-git', os.environ['PMA_OFFICIAL_GIT'],
                '--harbor-source-root', os.environ['PMA_HARBOR_SOURCE']]
            completed = subprocess.run(command, capture_output=True, text=True, timeout=300)
            (root / 'controller.stdout.txt').write_text(completed.stdout, encoding='utf-8')
            (root / 'controller.stderr.txt').write_text(completed.stderr, encoding='utf-8')
            self.assertEqual(completed.returncode, 1, completed.stderr)
            batch = json.loads((root / 'batch.json').read_text(encoding='utf-8'))
            self.assertEqual(len(batch['arms']), 1)
            self.assertEqual(len(batch['not_started']), 23)
            first = root / 'run-1'
            self.assertTrue((first / 'archive/agent_start_identity.json').is_file())
            self.assertTrue((first / 'archive/fake_provider_requests').is_dir())
            self.assertFalse((first / 'archive/native_test_execution.json').exists())
            self.assertFalse((first / 'archive/verification_released.json').exists())
            self.assertEqual(batch['arms'][0]['status']['cleanup_confirmed'], True)
        finally:
            # The raw evidence is deliberately retained for the audit bundle.
            pass
    def test_exact_24_slot_binding_and_duplicate_rejection(self):
        arms = [dict(order=o, task=t, repeat=r, condition=c) for o, t, r, c in ORDER]
        manifest = {'schema': 'pma-ga-live-manifest-v2',
                    'execution_authorized': False, 'planned_order': arms,
                    'config_sha256': 'a' * 64}
        with TemporaryDirectory() as directory:
            bindings = [dict(row, batch_id='batch-fixture', config_sha256='a' * 64,
                             run_id=f'fixture-{row["order"]}',
                             run_root=str(Path(directory) / f'run-{row["order"]}'))
                        for row in arms]
            granted = {'execution_authorized': True, 'approved_arms': arms,
                       'batch_id': 'batch-fixture', 'config_sha256': 'a' * 64,
                       'run_bindings': bindings}
            self.assertEqual(len(validate_plan(manifest, granted)), 24)
            for bad in ('order', 'run_id', 'run_root', 'repeat', 'condition'):
                changed = copy.deepcopy(granted)
                target = 12 if bad == 'repeat' else 1
                changed['run_bindings'][target][bad] = changed['run_bindings'][0][bad]
                with self.subTest(bad=bad), self.assertRaises(RuntimeError):
                    validate_plan(manifest, changed)
            with self.assertRaises(RuntimeError):
                validate_plan(manifest, {**granted, 'execution_authorized': False})

    def test_official_network_preserves_host_only_key_gateway(self):
        with TemporaryDirectory() as directory:
            base = Path(directory)
            source = base / 'source'
            source.mkdir()
            sentinel = 'SECRET-FIXTURE-MUST-NOT-ENTER-TASK'
            (source / 'mykey.py').write_text(
                "native_claude_cc_vibe_opus48 = " + repr({
                    'apibase': 'https://fixture.invalid', 'apikey': sentinel,
                    'model': 'claude-opus-4-8', 'verify': True}) + '\n', encoding='utf-8')
            (source / 'agentmain.py').write_text('pass\n', encoding='utf-8')
            copied, compose_path = build_bundle(
                base / 'bundle', source, base, 'cpython-3.12.12-linux-x86_64-gnu',
                'native_claude_cc_vibe_opus48', None, 15340,
                task_network_policy='official')
            compose = json.loads(compose_path.read_text(encoding='utf-8'))
            main = compose['services']['main']
            for old_override in ('network_mode', 'cap_drop', 'security_opt'):
                self.assertNotIn(old_override, main)
            self.assertIn('model-gateway', compose['services'])
            self.assertFalse((copied / 'mykey.py').exists())
            self.assertNotIn(sentinel, (copied / 'mykey.json').read_text(encoding='utf-8'))
            self.assertIn(sentinel, (base / 'bundle/gateway/config.json').read_text(encoding='utf-8'))
            self.assertNotIn(str(base / 'bundle/gateway'), compose_path.read_text(encoding='utf-8').split('"main"')[1].split('"model-gateway"')[0])

    def test_new_protocol_cannot_start_before_shared_lifecycle_certification(self):
        with self.assertRaisesRegex(RuntimeError, 'evidence/identity not frozen'):
            live_launcher._require_evaluation_state_contract(
                {'schema': 'pma-ga-live-manifest-v2'})

    def test_prepared_evidence_gate_binds_actual_source_and_raw_records(self):
        manifest_path = (Path(__file__).parent / 'six_task_discovery_20261014' /
                         'PMA_GA_6TASK_NATIVE_BASE_DRAFT_V2R7.json')
        if not manifest_path.exists():
            self.skipTest('generated evidence-bound draft not present')
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        live_launcher._require_evaluation_state_contract(manifest)
        changed = copy.deepcopy(manifest)
        name = next(iter(changed['native_shared_certification']['source_files']))
        changed['native_shared_certification']['source_files'][name] = '0' * 64
        with self.assertRaises(RuntimeError):
            live_launcher._require_evaluation_state_contract(changed)

    def test_v2_launcher_stages_fixed_git_source_and_rejects_disagreement(self):
        source = os.environ.get('PMA_OFFICIAL_GIT')
        if not source:
            self.skipTest('fixed official Git source unavailable')
        manifest_path = (Path(__file__).parent / 'six_task_discovery_20261014' /
                         'PMA_GA_6TASK_NATIVE_BASE_DRAFT_V2R7.json')
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'public_task/tests').mkdir(parents=True)
            identity = live_launcher._stage_verifier(
                root, 'db-wal-recovery', manifest, Path(source))
            self.assertEqual(identity['native_test_sh_sha256'],
                             manifest['assets']['db-wal-recovery']['native_test_sh_sha256'])
        for bad in ({**manifest, 'official_source_git_commit': '0' * 40},
                    {**manifest, 'official_evaluator_commit': '0' * 40}):
            with self.subTest(bad=bad.get('official_evaluator_commit')):
                with TemporaryDirectory() as directory, self.assertRaises(RuntimeError):
                    live_launcher._stage_verifier(Path(directory), 'db-wal-recovery',
                                                  bad, Path(source))
        changed = copy.deepcopy(manifest)
        changed['native_shared_certification']['evidence_files']['image_checks.json'] = '0' * 64
        with self.assertRaises(RuntimeError):
            live_launcher._require_evaluation_state_contract(changed)

    def test_native_report_diagnostic_never_converts_missing_tests_to_score(self):
        from .native_shared_verifier import NativeSharedVerifier
        base = {'results': {'tests': [{'name': 'synthetic'}], 'summary': {
            'tests': 1, 'passed': 1, 'failed': 0, 'skipped': 0,
            'pending': 0, 'other': 0}}}
        self.assertTrue(NativeSharedVerifier._report_has_executed_tests(base))
        for changed in ({'results': {'tests': [], 'summary': {
                'tests': 0, 'passed': 0, 'failed': 0, 'skipped': 0,
                'pending': 0, 'other': 0}}},
                        {'results': {'tests': [{'name': 'synthetic'}], 'summary': {
                            'tests': 1, 'passed': 0, 'failed': 0, 'skipped': 1,
                            'pending': 0, 'other': 0}}},
                        {'results': {'tests': [{'name': 'synthetic'}], 'summary': {
                            'tests': 2, 'passed': 1, 'failed': 0, 'skipped': 0,
                            'pending': 0, 'other': 0}}}):
            self.assertFalse(NativeSharedVerifier._report_has_executed_tests(changed))

    def test_research_adapter_strips_provider_env_independent_of_network(self):
        from . import harbor_adapter
        from adapters import harbor_ga_agent as original
        self.assertIs(harbor_adapter.HarborGenericAgent.__base__,
                      original.HarborGenericAgent)
        self.assertNotIn('OPENROUTER_API_KEY', original.FORWARDED_ENV_VARS)
        self.assertNotIn('ANTHROPIC_API_KEY', original.FORWARDED_ENV_VARS)
        self.assertIn('GA_PMA_UPSTREAM_ENABLED', original.FORWARDED_ENV_VARS)

    def test_fixed_six_assets_load_with_actual_harbor_task(self):
        location = os.environ.get('PMA_OFFICIAL_GIT')
        if not location:
            self.skipTest('set PMA_OFFICIAL_GIT to fixed source for integration')
        from harbor.models.task.task import Task
        source = Path(location).resolve(strict=True)
        for name in dict.fromkeys(row[1] for row in ORDER):
            with self.subTest(task=name), TemporaryDirectory() as directory:
                task = Path(directory) / name
                expected = descriptor(source, name)
                materialize_public(source, name, task, expected['public_members'])
                (task / 'tests').mkdir()
                export_task(source, name, task / 'tests')
                (task / 'solution').mkdir()
                loaded = Task(task)
                self.assertTrue(loaded.instruction)
                self.assertEqual(loaded.config.agent.timeout_sec,
                                 expected['native_agent_seconds'])
                self.assertEqual(loaded.config.verifier.timeout_sec,
                                 expected['native_verifier_seconds'])

    def test_controller_actual_subprocess_argv_includes_source_repeat_and_clean_harbor(self):
        arms = [dict(order=o, task=t, repeat=r, condition=c) for o, t, r, c in ORDER]
        with TemporaryDirectory() as directory:
            base = Path(directory)
            bindings = [dict(row, batch_id='fixture', config_sha256='a' * 64,
                             run_id=f'fixture-{row["order"]}',
                             run_root=str(base / f'run-{row["order"]}'))
                        for row in arms]
            manifest = base / 'manifest.json'
            auth = base / 'auth.json'
            manifest.write_text(json.dumps({'schema': 'pma-ga-live-manifest-v2',
                'execution_authorized': False, 'planned_order': arms,
                'config_sha256': 'a' * 64}), encoding='utf-8')
            auth.write_text(json.dumps({'execution_authorized': True,
                'approved_arms': arms, 'run_bindings': bindings,
                'batch_id': 'fixture', 'config_sha256': 'a' * 64,
                'audited_code_commit': 'test-only'}), encoding='utf-8')
            args = SimpleNamespace(manifest=str(manifest), authorization=str(auth),
                batch_result=str(base / 'result.json'), ga_source='ga',
                runtime_root='runtime', task_profile_file='profile',
                worker_python='worker-python', harbor_python='harbor-python',
                bench_root='bench', python_home='python-home',
                official_source_git='fixed-official-git',
                harbor_source_root='clean-harbor', pma_profile_file=None)
            calls = []
            def recorded(argv, **kwargs):
                calls.append(argv)
                return SimpleNamespace(returncode=1)
            with patch.object(batch_controller, 'verify_live_spec'), patch.object(
                    batch_controller.subprocess, 'run', side_effect=recorded):
                outcome = batch_controller.run_batch(args)
            self.assertEqual(len(calls), 1)
            argv = calls[0]
            for option, value in (('--official-source-git', 'fixed-official-git'),
                                  ('--harbor-source-root', 'clean-harbor'),
                                  ('--repeat', '1'), ('--order', '1')):
                self.assertEqual(argv[argv.index(option) + 1], value)
            self.assertEqual(len(outcome['not_started']), 23)

    def test_controller_simulated_full_order_keeps_each_repeat_independent(self):
        arms = [dict(order=o, task=t, repeat=r, condition=c) for o, t, r, c in ORDER]
        with TemporaryDirectory() as directory:
            base = Path(directory)
            bindings = [dict(row, batch_id='fixture', config_sha256='b' * 64,
                             run_id=f'new-{row["order"]:02d}',
                             run_root=str(base / f'new-{row["order"]:02d}'))
                        for row in arms]
            manifest = base / 'manifest.json'
            auth = base / 'auth.json'
            manifest.write_text(json.dumps({'schema': 'pma-ga-live-manifest-v2',
                'execution_authorized': False, 'planned_order': arms,
                'config_sha256': 'b' * 64}), encoding='utf-8')
            auth.write_text(json.dumps({'execution_authorized': True,
                'approved_arms': arms, 'run_bindings': bindings,
                'batch_id': 'fixture', 'config_sha256': 'b' * 64,
                'audited_code_commit': 'test-only'}), encoding='utf-8')
            args = SimpleNamespace(manifest=str(manifest), authorization=str(auth),
                batch_result=str(base / 'result.json'), ga_source='ga',
                runtime_root='runtime', task_profile_file='profile',
                worker_python='worker-python', harbor_python='harbor-python',
                bench_root='bench', python_home='python-home',
                official_source_git='fixed-official-git',
                harbor_source_root='clean-harbor', pma_profile_file='pma-profile')
            seen = []
            def completed(argv, **kwargs):
                root = Path(argv[argv.index('--run-root') + 1])
                condition = argv[argv.index('--condition') + 1]
                seen.append((argv[argv.index('--order') + 1], root, condition))
                archive = root / 'archive'
                archive.mkdir(parents=True)
                (archive / 'agent_start_identity.json').write_text('{}', encoding='utf-8')
                (archive / 'live_result.json').write_text(json.dumps({
                    'schema': 'pma-ga-live-manifest-v2', 'primary_failure': None,
                    'cleanup_confirmed': True, 'remaining_containers': [],
                    'cleanup_errors': [], 'harbor_return_code': 0,
                    'frozen_product': True, 'evaluation_released': True,
                    'condition': condition, 'worker_return_code': 0,
                    'native_result': {'status': 'native_recorded',
                                      'rewards': {'reward': 0.0}},
                    'native_upload_checked': True, 'native_script_observed': True,
                    'native_reports_checked': True}), encoding='utf-8')
                return SimpleNamespace(returncode=0)
            with patch.object(batch_controller, 'verify_live_spec'), patch.object(
                    batch_controller.subprocess, 'run', side_effect=completed):
                outcome = batch_controller.run_batch(args)
            self.assertEqual(len(seen), 24)
            self.assertEqual([int(row[0]) for row in seen], list(range(1, 25)))
            self.assertEqual(len({row[1] for row in seen}), 24)
            self.assertEqual(outcome['not_started'], [])
            self.assertIsNone(outcome['stop_reason'])


if __name__ == '__main__':
    unittest.main()
