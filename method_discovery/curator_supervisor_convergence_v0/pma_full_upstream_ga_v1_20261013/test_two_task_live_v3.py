"""Four-slot, real-launcher/Harbor/Docker zero-model integration fixture."""

from __future__ import annotations

import hashlib
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from .six_task_plan import validate_plan
from .live_launcher import _require_evaluation_state_contract


STAGE = Path(__file__).resolve().parent
REPO = STAGE.parents[2]


class TwoTaskLiveV3Tests(unittest.TestCase):
    def test_v3_order_binding_and_fail_closed_evaluation_gate(self):
        slots = [dict(order=i, task=t, repeat=1, condition=c) for i, t, c in (
            (1, 'headless-terminal', 'A'), (2, 'headless-terminal', 'B'),
            (3, 'cancel-async-tasks', 'B'), (4, 'cancel-async-tasks', 'A'))]
        manifest = {'schema': 'pma-ga-live-manifest-v3',
                    'execution_authorized': False, 'planned_order': slots,
                    'assets': {task: {} for task in ('headless-terminal',
                                                     'cancel-async-tasks')},
                    'config_sha256': 'a' * 64}
        with self.assertRaises(RuntimeError):
            _require_evaluation_state_contract(manifest)
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            bindings = [dict(row, batch_id='test', config_sha256='a' * 64,
                             run_id=f'test-{row["order"]}',
                             run_root=str(Path(directory) / f'run-{row["order"]}'))
                        for row in slots]
            grant = {'execution_authorized': True, 'approved_arms': slots,
                     'run_bindings': bindings, 'batch_id': 'test',
                     'config_sha256': 'a' * 64, 'output_root': directory}
            self.assertEqual(len(validate_plan(manifest, grant)), 4)
            for change in ('order', 'repeat', 'condition', 'run_id', 'run_root'):
                bad = copy.deepcopy(grant)
                bad['run_bindings'][1][change] = (
                    2 if change == 'repeat' else bad['run_bindings'][0][change])
                with self.subTest(change=change), self.assertRaises(RuntimeError):
                    validate_plan(manifest, bad)
            bad = copy.deepcopy(manifest)
            bad['planned_order'][0]['task'] = 'unregistered-task'
            with self.assertRaises(RuntimeError):
                validate_plan(bad, grant)

    def test_four_slots_through_real_batch_entry(self):
        root_name = os.environ.get('PMA_TWO_TASK_FIXTURE_ROOT')
        if not root_name:
            self.skipTest('explicit four-slot Docker fixture not requested')
        root = Path(root_name).resolve(strict=False)
        if root.exists():
            self.fail('zero-model evidence root already exists')
        root.mkdir(parents=True)
        prepared = json.loads((STAGE / 'two_task_live_20261015' /
            'MANIFEST_PREPARED.json').read_text(encoding='utf-8'))
        self.assertEqual(prepared['schema'], 'pma-ga-live-manifest-v3')
        prepared['zero_model_fixture_only'] = True
        manifest = root / 'manifest.json'
        manifest.write_text(json.dumps(prepared, indent=2), encoding='utf-8')
        manifest_sha = hashlib.sha256(manifest.read_bytes()).hexdigest()
        head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO,
                              capture_output=True, text=True, check=True).stdout.strip()
        bindings = [dict(row, run_id=f'two-task-zero-{row["order"]}',
                         run_root=str(root / f'run-{row["order"]}'),
                         batch_id='two-task-zero',
                         config_sha256=prepared['config_sha256'])
                    for row in prepared['planned_order']]
        authorization = root / 'authorization.json'
        authorization.write_text(json.dumps({
            'execution_authorized': True, 'zero_model_fixture_only': True,
            'manifest_sha256': manifest_sha, 'audited_code_commit': head,
            'approved_arms': prepared['planned_order'],
            'run_bindings': bindings, 'batch_id': 'two-task-zero',
            'config_sha256': prepared['config_sha256'],
            'output_root': str(root)}, indent=2), encoding='utf-8')
        command = [sys.executable, '-m',
            'method_discovery.curator_supervisor_convergence_v0.'
            'pma_full_upstream_ga_v1_20261013.batch_controller',
            '--zero-model-fixture', '--manifest', str(manifest),
            '--authorization', str(authorization),
            '--batch-result', str(root / 'batch.json'),
            '--ga-source', os.environ['PMA_GA_SOURCE'],
            '--runtime-root', os.environ['PMA_RUNTIME_ROOT'],
            '--task-profile-file', os.environ['PMA_TASK_PROFILE'],
            '--pma-profile-file', os.environ['PMA_PMA_PROFILE'],
            '--worker-python', sys.executable, '--harbor-python', sys.executable,
            '--bench-root', os.environ['PMA_BENCH_ROOT'],
            '--official-source-git', os.environ['PMA_OFFICIAL_GIT'],
            '--harbor-source-root', os.environ['PMA_HARBOR_SOURCE']]
        try:
            completed = subprocess.run(command, capture_output=True, text=True,
                                       timeout=1200)
        finally:
            authorization.unlink(missing_ok=True)
            (root / 'fake_authorization_removed.json').write_text(json.dumps({
                'authorization_removed': not authorization.exists(),
                'fixture_only': True}), encoding='utf-8')
        (root / 'controller.stdout.txt').write_text(completed.stdout, encoding='utf-8')
        (root / 'controller.stderr.txt').write_text(completed.stderr, encoding='utf-8')
        self.assertEqual(completed.returncode, 0, completed.stderr)
        batch = json.loads((root / 'batch.json').read_text(encoding='utf-8'))
        self.assertEqual(len(batch['arms']), 4)
        self.assertEqual(batch['not_started'], [])
        for arm in batch['arms']:
            self.assertEqual(arm['disposition'], 'completed')
            self.assertGreaterEqual(arm['status']['fake_provider_captures'], 2)
            self.assertTrue(arm['status']['cleanup_confirmed'])
            self.assertEqual(arm['status']['native_result']['status'],
                             'native_recorded')
            self.assertTrue(arm['status']['native_upload_checked'])
            self.assertTrue(arm['status']['native_script_observed'])
            self.assertTrue((Path(arm['run_root']) / 'archive' /
                             'agent_start_identity.json').is_file())
            trace = list((Path(arm['run_root']) / 'jobs').rglob('research_events.jsonl'))
            self.assertEqual(len(trace), 1)
            task_events = [json.loads(line) for line in trace[0].read_text(
                encoding='utf-8').splitlines()]
            self.assertTrue(any(row['event_type'] == 'provider_request_ready' and
                                row['payload'].get('content_availability') == 'complete'
                                for row in task_events))
            self.assertTrue(any(row['event_type'] == 'provider_response_content' and
                                row['payload'].get('parsed_visible_blocks')
                                for row in task_events))
            private = Path(arm['run_root']) / 'host_private' / 'archive'
            if arm['status']['condition'] == 'B':
                self.assertTrue((private / 'memory_payload.jsonl').is_file())
                self.assertGreater((private / 'memory_payload.jsonl').stat().st_size, 0)
                self.assertTrue((private / 'events.jsonl').is_file())
                phases = [json.loads(line)['phase'] for line in
                    (private / 'memory_payload.jsonl').read_text(
                        encoding='utf-8').splitlines()]
                self.assertIn('bank_management', phases)
                self.assertIn('context_decision', phases)
                events = [json.loads(line) for line in
                    (private / 'events.jsonl').read_text(
                        encoding='utf-8').splitlines()]
                self.assertTrue(any(row.get('result', {}).get('reminder')
                                    for row in events))
                second = (Path(arm['run_root']) / 'archive' /
                          'fake_provider_requests/0002.json')
                self.assertIn('Offline PMA reminder.', second.read_text(encoding='utf-8'))
            else:
                self.assertFalse((private / 'memory_payload.jsonl').exists())
        for first, second in ((1, 2), (4, 3)):
            a = json.loads((root / f'run-{first}/archive/fake_provider_requests/0001.json'
                            ).read_text(encoding='utf-8'))['body']
            b = json.loads((root / f'run-{second}/archive/fake_provider_requests/0001.json'
                            ).read_text(encoding='utf-8'))['body']
            a.pop('metadata', None)
            b.pop('metadata', None)
            self.assertEqual(a, b)


if __name__ == '__main__':
    unittest.main()
