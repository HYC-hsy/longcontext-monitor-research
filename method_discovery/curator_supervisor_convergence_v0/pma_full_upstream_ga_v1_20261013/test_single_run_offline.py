"""Offline identity and real Docker control-process checks for single-run V4."""

import copy
import json
import os
from pathlib import Path
import subprocess
import shutil
import time
import unittest
import uuid
from types import SimpleNamespace

from .control_processes import scan, probe_registered, stop_registered
from .archive_live_six_task import redact, UnsafePublicProjection
from .live_launcher import _require_evaluation_state_contract
from .run_selection import _slots, execute
from .six_task_plan import validate_plan
from .single_run_certification import verify_evidence


class SingleRunOfflineTests(unittest.TestCase):
    def test_real_ga_snapshot_policy_reaches_manifest_plan(self):
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        from .single_run import prepare
        with TemporaryDirectory() as directory:
            base = Path(directory)
            for name in ('task.py', 'pma.json'):
                (base / name).write_text('fixture')
            args = SimpleNamespace(output=str(base / 'prepared'), condition='A',
                research_candidate='U', task='db-wal-recovery', occurrence=1,
                fake_only=False, runtime_policy=None, task_complete_response=False,
                official_source_git=str(base), task_profile_file=str(base / 'task.py'),
                pma_profile_file=str(base / 'pma.json'), certification_dir=None,
                preserve_pre_eval_snapshot=True)
            with patch('method_discovery.curator_supervisor_convergence_v0.'
                       'pma_full_upstream_ga_v1_20261013.prepare_six_task_manifest.prepare',
                       return_value={'config': {'preserve_pre_eval_snapshot': True}}) as backend:
                prepare(args)
            self.assertIs(backend.call_args.kwargs['plan']['preserve_pre_eval_snapshot'], True)
            self.assertIs(json.loads((base / 'prepared/plan.json').read_text())[
                'preserve_pre_eval_snapshot'], True)

    def test_download_retry_reaches_real_manifest_api_for_non_sqlite(self):
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        from .single_run import prepare
        with TemporaryDirectory() as directory:
            base = Path(directory)
            for name in ('task.py', 'pma.json'):
                (base / name).write_text('fixture')
            args = SimpleNamespace(output=str(base / 'prepared'), condition='B',
                research_candidate='pma_gap_memory_v0', task='db-wal-recovery',
                occurrence=1, fake_only=False, runtime_policy=None,
                task_complete_response=False, official_source_git=str(base),
                task_profile_file=str(base / 'task.py'),
                pma_profile_file=str(base / 'pma.json'), certification_dir=None,
                evaluation_bootstrap_protocol='download_retry_v1',
                evaluation_download_retry={'max_attempts': 3})
            with patch('method_discovery.curator_supervisor_convergence_v0.'
                       'pma_full_upstream_ga_v1_20261013.prepare_six_task_manifest.prepare',
                       return_value={'config': {'evaluation_bootstrap_protocol':
                                               'download_retry_v1'}}) as backend:
                prepare(args)
            submitted = backend.call_args.kwargs['plan']
            self.assertEqual(submitted['evaluation_download_retry'], {'max_attempts': 3})
            self.assertEqual(submitted['evaluation_bootstrap_protocol'], 'download_retry_v1')
            self.assertEqual(json.loads((base / 'prepared/plan.json').read_text())[
                'evaluation_download_retry'], {'max_attempts': 3})

    def test_cached_plan_reaches_real_single_run_manifest_api(self):
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        from .single_run import prepare
        with TemporaryDirectory() as directory:
            base = Path(directory)
            for name in ('task.py', 'pma.json'):
                (base / name).write_text('fixture')
            cache = {'bundle_path': str(base), 'manifest_sha256': 'a' * 64,
                     'identity': {'protocol': 'persistent_bundle_v1'}}
            args = SimpleNamespace(output=str(base / 'prepared'), condition='B',
                research_candidate='pma_gap_memory_v0', task='sqlite-with-gcov',
                occurrence=1, fake_only=False, runtime_policy=None,
                task_complete_response=False, official_source_git=str(base),
                task_profile_file=str(base / 'task.py'),
                pma_profile_file=str(base / 'pma.json'), certification_dir=None,
                evaluation_bootstrap_protocol='persistent_bundle_v1',
                evaluation_cache=cache)
            with patch('experiment_runner.evaluation_cache.verify_bundle'), patch(
                    'experiment_runner.evaluation_cache.require_offline_ready'), patch(
                    'method_discovery.curator_supervisor_convergence_v0.'
                    'pma_full_upstream_ga_v1_20261013.prepare_six_task_manifest.prepare',
                    return_value={'config': {'evaluation_cache': cache}}) as backend:
                prepare(args)
            submitted = backend.call_args.kwargs['plan']
            self.assertEqual(submitted['evaluation_cache'], cache)
            self.assertEqual(submitted['evaluation_bootstrap_protocol'], 'persistent_bundle_v1')
            self.assertEqual(json.loads((base / 'prepared/plan.json').read_text())[
                'evaluation_cache'], cache)

    def test_committed_fixture_binds_executed_source_and_bytes(self):
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        old_fixture = (Path(__file__).parent / 'generic_single_run_20261015' /
                       'certification_fixture_v5')
        with self.assertRaises(RuntimeError):
            verify_evidence(old_fixture)
        fixture = (Path(__file__).parent / 'decision_reminder_v1_20261017' /
                   'certification_fixture_u')
        # This immutable certificate predates the newly bound cache/runtime
        # source, so it must now reject rather than certify the current tree.
        with self.assertRaises(RuntimeError):
            verify_evidence(fixture)
        with patch('method_discovery.curator_supervisor_convergence_v0.'
                   'pma_full_upstream_ga_v1_20261013.single_run_certification.'
                   'source_identity', return_value={'changed': 'source'}):
            with self.assertRaises(RuntimeError):
                verify_evidence(fixture, require_committed=False)
        with TemporaryDirectory() as directory:
            copy = Path(directory) / 'fixture'
            shutil.copytree(fixture, copy)
            executed = copy / 'A' / 'execution_identity.json'
            wrong = json.loads(executed.read_text(encoding='utf-8'))
            wrong['source_files']['GenericAgent-main/llmcore.py'] = '0' * 64
            executed.write_text(json.dumps(wrong), encoding='utf-8')
            with self.assertRaises(RuntimeError):
                verify_evidence(copy, require_committed=False)
            with self.assertRaises((ValueError, RuntimeError)):
                verify_evidence(copy)

    def test_stream_projection_removes_private_delta_and_preserves_public(self):
        original = (b'data: {"delta":{"type":"redacted_thinking",'
                    b'"data":"PRIVATE_DELTA"},"id":"req-1"}\n\n'
                    b'data: {"delta":{"type":"text_delta",'
                    b'"text":"public"},"id":"req-1"}\n\n')
        public, changed = redact(original, [])
        self.assertEqual(changed, 1)
        self.assertNotIn(b'PRIVATE_DELTA', public)
        self.assertIn(b'public', public)
        self.assertIn(b'req-1', public)
        self.assertEqual(original.count(b'PRIVATE_DELTA'), 1)
        with self.assertRaises(UnsafePublicProjection):
            redact(b'data: {"type":"redacted_thinking","data":', [])
        multiple = (b'{"content":[{"type":"redacted_thinking",'
                    b'"data":"PRIVATE_ONE"}]}\n'
                    b'{"content":[{"type":"text","text":"public"}]}\n')
        projected, changed = redact(multiple, [])
        self.assertEqual(changed, 1)
        self.assertNotIn(b'PRIVATE_ONE', projected)
        self.assertIn(b'public', projected)

    def test_preparation_and_run_receipts_are_distinct(self):
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        from .export_official_evaluator import COMMIT
        with TemporaryDirectory() as directory:
            base = Path(directory)
            plan = base / 'plan.json'
            plan.write_text(json.dumps({'schema': 'pma-ga-ordered-selection-v1',
                'execution_authorized': False, 'official_source_git_commit': COMMIT,
                'slots': [{'task': 'constraints-scheduling', 'condition': 'A',
                           'occurrence': 1}]}), encoding='utf-8')
            root = base / 'selection'
            args = type('Args', (), dict(plan=str(plan), output=str(root),
                official_source_git='unused', task_profile_file='unused',
                pma_profile_file='unused', fake_only=True, certification_dir=None,
                ga_source='unused', runtime_root='unused', worker_python='unused',
                harbor_python='unused', bench_root='unused',
                harbor_source_root='unused', python_home='unused'))()
            with patch('method_discovery.curator_supervisor_convergence_v0.'
                       'pma_full_upstream_ga_v1_20261013.single_run.prepare',
                       side_effect=lambda a: Path(a.output).mkdir() or {'run_id': 'one'}):
                args.mode = 'prepare'
                self.assertEqual(len(execute(args)), 1)
            self.assertTrue((root / 'selection_preparation.json').is_file())
            slot = root / '01-constraints-scheduling-A-r1'
            (slot / 'authorization.json').write_text('{}', encoding='utf-8')
            with patch('method_discovery.curator_supervisor_convergence_v0.'
                       'pma_full_upstream_ga_v1_20261013.single_run.run',
                       return_value={'stop_reason': None,
                                     'arm': {'disposition': 'completed'}}):
                args.mode = 'run'
                self.assertEqual(execute(args)[0]['result']['arm']['disposition'],
                                 'completed')
            self.assertTrue((root / 'selection_result.json').is_file())
            with self.assertRaises(FileExistsError):
                execute(args)

    def test_single_run_exit_code_uses_disposition_not_reward(self):
        from unittest.mock import patch
        from .single_run import main
        argv = ['single_run', 'run', '--output', 'unused', '--authorization', 'unused']
        for name in ('ga-source', 'runtime-root', 'task-profile-file',
                     'worker-python', 'harbor-python', 'bench-root',
                     'official-source-git', 'harbor-source-root'):
            argv.extend(['--' + name, 'unused'])
        with patch('sys.argv', argv):
            for arm in (None, {'disposition': 'arm_failed_isolated'}):
                with patch('method_discovery.curator_supervisor_convergence_v0.'
                           'pma_full_upstream_ga_v1_20261013.single_run.run',
                           return_value={'stop_reason': None, 'arm': arm}):
                    with self.assertRaises(SystemExit) as result:
                        main()
                    self.assertEqual(result.exception.code, 1)
            with patch('method_discovery.curator_supervisor_convergence_v0.'
                       'pma_full_upstream_ga_v1_20261013.single_run.run',
                       return_value={'stop_reason': None,
                                     'arm': {'disposition': 'completed',
                                             'reward': 0}}):
                main()

    def test_public_projection_removes_nested_hidden_thinking(self):
        request = {'messages': [{'content': [{'type': 'thinking',
                    'thinking': 'PRIVATE_REASONING_SENT_TO_PROVIDER',
                    'signature': 'PRIVATE_SIGNATURE'},
                    {'type': 'text', 'text': 'public request'}]}],
                   'response': {'redacted_thinking': 'PRIVATE_ENCRYPTED'}}
        public, count = redact(json.dumps(request).encode(), [])
        self.assertEqual(count, 3)
        self.assertNotIn(b'PRIVATE_REASONING', public)
        self.assertNotIn(b'PRIVATE_SIGNATURE', public)
        self.assertNotIn(b'PRIVATE_ENCRYPTED', public)
        projected = json.loads(public)
        self.assertEqual(projected['messages'][0]['content'][1]['text'],
                         'public request')
        self.assertIn('private_sha256', projected['messages'][0]['content'][0]['thinking'])

    def test_selection_subsets_repeats_and_identity(self):
        base = {'schema': 'pma-ga-ordered-selection-v1',
                'execution_authorized': False,
                'official_source_git_commit':
                    '2fd12b88aafdd04a52c298e3940bcb189f9766d6',
                'slots': [{'task': 'constraints-scheduling', 'condition': 'A',
                           'occurrence': 1}]}
        self.assertEqual(len(_slots(base)), 1)
        subset = copy.deepcopy(base)
        subset['slots'].append({'task': 'constraints-scheduling',
                                'condition': 'A', 'occurrence': 2})
        self.assertEqual(len(_slots(subset)), 2)
        subset['slots'].append(dict(subset['slots'][0]))
        with self.assertRaises(ValueError):
            _slots(subset)
        subset['slots'][-1]['task'] = '../escape'
        with self.assertRaises(ValueError):
            _slots(subset)

    def test_single_binding_never_authorizes_changed_slot(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            slot = {'order': 1, 'task': 'constraints-scheduling',
                    'condition': 'B', 'repeat': 3}
            manifest = {'schema': 'pma-ga-live-manifest-v4',
                        'execution_authorized': False,
                        'planned_order': [slot], 'assets': {slot['task']: {}},
                        'config_sha256': 'a' * 64}
            binding = dict(slot, run_id='one', run_root=str(Path(directory) / 'one'),
                           batch_id='one-batch', config_sha256='a' * 64)
            grant = {'execution_authorized': True, 'approved_arms': [slot],
                     'run_bindings': [binding], 'run_id': 'one', 'batch_id': 'one-batch',
                     'config_sha256': 'a' * 64, 'output_root': directory}
            self.assertEqual(validate_plan(manifest, grant), [binding])
            for field, value in [('task', 'other'), ('condition', 'A'),
                                 ('repeat', 2), ('order', 2)]:
                bad = copy.deepcopy(manifest)
                bad['planned_order'][0][field] = value
                with self.subTest(field=field), self.assertRaises(RuntimeError):
                    validate_plan(bad, grant)
            with self.assertRaises(RuntimeError):
                _require_evaluation_state_contract(manifest)
            manifest['zero_model_fixture_only'] = True
            _require_evaluation_state_contract(manifest)

    @unittest.skipUnless(os.environ.get('PMA_CONTROL_DOCKER_FIXTURE') == '1',
                         'explicit Docker fixture not requested')
    def test_registered_wrapper_stops_but_task_service_survives(self):
        container = 'pma-control-fixture-' + uuid.uuid4().hex[:12]
        image = os.environ['PMA_CONTROL_FIXTURE_IMAGE']
        runtime = os.environ['PMA_CONTROL_RUNTIME']
        python = ('/opt/m4-runtime/python/cpython-3.12.12-linux-x86_64-gnu/'
                  'bin/python3.12')
        run_id = 'fixture-' + uuid.uuid4().hex[:12]
        launch = subprocess.run(['docker', 'run', '-d', '--rm', '--name', container,
            '--mount', f'type=bind,source={runtime},target=/opt/m4-runtime,readonly',
            '--entrypoint', 'sh', image, '-c', 'sleep 120'],
            capture_output=True, text=True, timeout=60)
        self.assertEqual(launch.returncode, 0, launch.stderr)
        try:
            self.assertEqual(scan(container, python, run_id)['processes'], [])
            service = subprocess.run(['docker', 'exec', '-d', container, python,
                '-m', 'http.server', '18765', '--bind', '127.0.0.1'],
                capture_output=True, text=True, timeout=30)
            self.assertEqual(service.returncode, 0, service.stderr)
            started = subprocess.run(['docker', 'exec', '-d', container, 'sh', '-c',
                f'# GA_WRAPPER_RUN_ID={run_id}\nsleep 60'],
                capture_output=True, text=True, timeout=30)
            self.assertEqual(started.returncode, 0, started.stderr)
            snapshot = scan(container, python, run_id)
            self.assertEqual(len(snapshot['processes']), 1)
            identity = dict(snapshot['processes'][0],
                            pid_namespace=snapshot['pid_namespace'], run_id=run_id)
            altered = dict(identity, start_ticks='0')
            with self.assertRaises(RuntimeError):
                stop_registered(container, python, altered)
            stop_registered(container, python, identity)
            for _ in range(20):
                if not scan(container, python, run_id)['processes']:
                    break
                time.sleep(.1)
            self.assertEqual(scan(container, python, run_id)['processes'], [])
            self.assertIn(probe_registered(container, python, identity),
                          {'exited', 'pid_reused'})
            escaped = subprocess.run(['docker', 'exec', '-d', container, 'sh', '-c',
                f'# GA_WRAPPER_RUN_ID={run_id}\nwhile [ ! -f /tmp/escape-control ]; '
                'do sleep .1; done; exec sleep 60'],
                capture_output=True, text=True, timeout=30)
            self.assertEqual(escaped.returncode, 0, escaped.stderr)
            for _ in range(30):
                candidates = scan(container, python, run_id)['processes']
                if candidates:
                    break
                time.sleep(.1)
            self.assertEqual(len(candidates), 1)
            escaped_id = dict(candidates[0], pid_namespace=snapshot['pid_namespace'],
                              run_id=run_id)
            subprocess.run(['docker', 'exec', container, 'touch', '/tmp/escape-control'],
                           check=True, capture_output=True, timeout=30)
            for _ in range(30):
                if probe_registered(container, python, escaped_id) == 'identity_changed':
                    break
                time.sleep(.1)
            self.assertEqual(probe_registered(container, python, escaped_id),
                             'identity_changed')
            with self.assertRaises(RuntimeError):
                stop_registered(container, python, escaped_id)
            alive = subprocess.run(['docker', 'inspect', '-f', '{{.State.Running}}',
                                    container], capture_output=True, text=True)
            self.assertEqual(alive.stdout.strip(), 'true')
            for _ in range(20):
                request = subprocess.run(['docker', 'exec', container, python, '-c',
                    "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:18765').status)"],
                    capture_output=True, text=True, timeout=30)
                if request.returncode == 0:
                    break
                time.sleep(.1)
            self.assertEqual(request.returncode, 0, request.stderr)
            self.assertEqual(request.stdout.strip(), '200')
        finally:
            subprocess.run(['docker', 'rm', '-f', container], capture_output=True,
                           text=True, timeout=30)
