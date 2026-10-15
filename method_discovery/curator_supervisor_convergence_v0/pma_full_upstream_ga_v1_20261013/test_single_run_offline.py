"""Offline identity and real Docker control-process checks for single-run V4."""

import copy
import json
import os
from pathlib import Path
import subprocess
import time
import unittest
import uuid

from .control_processes import scan, stop_registered
from .archive_live_six_task import redact
from .live_launcher import _require_evaluation_state_contract
from .run_selection import _slots
from .six_task_plan import validate_plan


class SingleRunOfflineTests(unittest.TestCase):
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
