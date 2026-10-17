"""No-network checks of the explicit PMA Harbor entry and evaluation gate."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from . import batch_controller, live_launcher, pma_harbor_hooks


def write_json(path: Path, value: dict) -> str:
    path.write_text(json.dumps(value, sort_keys=True), encoding='utf-8')
    return hashlib.sha256(path.read_bytes()).hexdigest()


class LiveWiringTests(unittest.TestCase):
    def test_missing_pma_profile_rejects_b_before_preparation(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / 'manifest.json'
            auth = root / 'auth.json'
            manifest_hash = write_json(manifest, {'schema': 'pma-ga-live-manifest-v1',
                                                  'execution_authorized': False})
            write_json(auth, {'execution_authorized': True,
                              'manifest_sha256': manifest_hash})
            args = SimpleNamespace(manifest=str(manifest), authorization=str(auth),
                                   condition='B', run_root=str(root / 'uncreated'),
                                   pma_profile_file=None)
            with patch.object(live_launcher, '_prepare_common') as prepare:
                with self.assertRaisesRegex(RuntimeError, 'profile'):
                    live_launcher.run_live(args)
                prepare.assert_not_called()
            self.assertFalse((root / 'uncreated').exists())

    def test_authorization_matches_all_four_bindings_and_exact_head(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            arms = [dict(order=i, task=task, condition=condition) for i, task, condition in (
                (1, 'db-wal-recovery', 'A'), (2, 'db-wal-recovery', 'B'),
                (3, 'fix-code-vulnerability', 'B'), (4, 'fix-code-vulnerability', 'A'))]
            bindings = [dict(arm, run_id=f'fresh-{arm["order"]}',
                             run_root=str(root / f'fresh-{arm["order"]}')) for arm in arms]
            manifest = root / 'manifest.json'
            auth = root / 'auth.json'
            manifest_hash = write_json(manifest, {'schema': 'pma-ga-live-manifest-v1',
                                                 'execution_authorized': False, 'arms': arms})
            auth_value = dict(execution_authorized=True, manifest_sha256=manifest_hash,
                              audited_code_commit='fixed-head', approved_arms=arms,
                              run_bindings=bindings)
            auth_hash = write_json(auth, auth_value)
            spec = dict(schema='pma-ga-live-run-v1', mode='authorized_live',
                        manifest_path=str(manifest), manifest_sha256=manifest_hash,
                        authorization_path=str(auth), authorization_sha256=auth_hash,
                        audited_code_commit='fixed-head', task_id=arms[0]['task'],
                        **bindings[0])
            with patch.object(pma_harbor_hooks.subprocess, 'run', return_value=SimpleNamespace(
                    stdout='fixed-head\n')):
                pma_harbor_hooks.verify_live_spec(spec)
                for change in ({'task': 'wrong'}, {'condition': 'B'}, {'order': 2},
                               {'audited_code_commit': 'wrong'}):
                    with self.assertRaises(RuntimeError):
                        pma_harbor_hooks.verify_live_spec({**spec, **change})
                duplicate = [*bindings[:3], bindings[0]]
                spec['authorization_sha256'] = write_json(auth, {**auth_value,
                                                                  'run_bindings': duplicate})
                with self.assertRaises(RuntimeError):
                    pma_harbor_hooks.verify_live_spec(spec)
                spec['authorization_sha256'] = write_json(auth, auth_value)
                spec['manifest_sha256'] = write_json(manifest, {
                    'execution_authorized': False, 'arms': list(reversed(arms))})
                with self.assertRaises(RuntimeError):
                    pma_harbor_hooks.verify_live_spec(spec)

    def test_b_requires_saved_pma_and_task_terminal(self):
        hooks = object.__new__(pma_harbor_hooks.PMATrialHooks)
        hooks.spec = {'condition': 'B', 'run_id': 'run', 'task_id': 'task'}
        good = {'run_id': 'run', 'task_id': 'task', 'result': 'CURRENT_TASK_DONE',
                'pma_finalization': {'status': 'saved'}}
        metadata = {'round_end_seen': True, 'wrapper_return_code': 0,
                    'archive_status': 'finished'}
        self.assertTrue(hooks.terminal_identity_valid(good))
        self.assertTrue(hooks.legal_terminal(metadata, good, True, False))
        for terminal in ({**good, 'pma_finalization': {'status': 'failed'}},
                         {**good, 'result': 'PROVIDER_FAILURE'}):
            self.assertFalse(hooks.legal_terminal(metadata, terminal,
                                                  hooks.terminal_identity_valid(terminal), False))
        self.assertFalse(hooks.legal_terminal(metadata, good, True, True))
        hooks.spec['condition'] = 'A'
        task_only = {**good, 'pma_finalization': {'status': 'not_enabled'}}
        self.assertTrue(hooks.terminal_identity_valid(task_only))
        self.assertTrue(hooks.legal_terminal(metadata, task_only, True, False))
        for terminal in ({key: task_only[key] for key in ('run_id', 'task_id', 'result')},
                         {**task_only, 'run_id': 'other'},
                         {**task_only, 'task_id': 'other'},
                         {**task_only, 'pma_finalization': {'status': 'saved'}},
                         {**task_only, 'pma_finalization': {'status': 'unknown'}},
                         {**task_only, 'unexpected': True}):
            self.assertFalse(hooks.terminal_identity_valid(terminal))
        hooks.spec['condition'] = 'B'
        for terminal in ({**good, 'run_id': 'other'},
                         {**good, 'task_id': 'other'},
                         {**good, 'pma_finalization': {'status': 'not_enabled'}},
                         {**good, 'pma_finalization': {'status': 'failed'}},
                         {**good, 'unexpected': True}):
            self.assertFalse(hooks.terminal_identity_valid(terminal))

    def test_archived_terminals_rejudged_without_changing_original_freeze(self):
        archive = Path(__file__).resolve().parent / 'live_batch_retry_20261014' / 'raw' / 'arms'
        metadata = {'round_end_seen': True, 'wrapper_return_code': 0,
                    'archive_status': 'finished'}
        for arm, condition in (('db_a', 'A'), ('db_b', 'B'),
                               ('code_b', 'B'), ('code_a', 'A')):
            root = archive / arm
            terminal_files = list((root / 'jobs').rglob('task_terminal.json'))
            self.assertEqual(len(terminal_files), 1)
            terminal = json.loads(terminal_files[0].read_text(encoding='utf-8'))
            frozen = json.loads((root / 'archive' / 'agent_end_frozen.json')
                                .read_text(encoding='utf-8'))
            clearance = json.loads((root / 'control' / 'sidecar_stopped.json')
                                   .read_text(encoding='utf-8'))
            self.assertEqual(clearance, {'run_id': terminal['run_id'], 'clean': True})
            hooks = object.__new__(pma_harbor_hooks.PMATrialHooks)
            hooks.spec = {'condition': condition, 'run_id': terminal['run_id'],
                          'task_id': terminal['task_id']}
            self.assertTrue(hooks.terminal_identity_valid(terminal))
            self.assertTrue(hooks.legal_terminal(metadata, terminal, True, False))
            if condition == 'A':
                self.assertIsNone(frozen['task_terminal'])
                self.assertFalse((root / 'host_private' / 'worker_exit.json').exists())
            else:
                receipt = json.loads((root / 'host_private' / 'worker_exit.json')
                                     .read_text(encoding='utf-8'))
                self.assertEqual(receipt['reason'], 'task_end')
                self.assertIs(receipt['task_end_saved'], True)

    def test_real_branch_uses_harbor_hook_not_offline_gateway(self):
        with TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / 'new-run'
            profile = base / 'profile.py'
            profile.write_text('fixture', encoding='utf-8')
            manifest = base / 'manifest.json'
            auth = base / 'auth.json'
            manifest_hash = write_json(manifest, {'schema': 'pma-ga-live-manifest-v1',
                'execution_authorized': False,
                'assets': {'db-wal-recovery': {'public_task_tree_sha256': 'public'}} ,
                'task_profile_sha256': hashlib.sha256(profile.read_bytes()).hexdigest()})
            write_json(auth, {'execution_authorized': True,
                              'manifest_sha256': manifest_hash,
                              'audited_code_commit': 'fixed-head'})
            args = SimpleNamespace(manifest=str(manifest), authorization=str(auth),
                task='db-wal-recovery', condition='A', run_root=str(root), run_id='new-run',
                order=1, task_profile_file=str(profile), ga_source=str(base),
                runtime_root=str(base), worker_python=str(profile), harbor_python=str(profile),
                bench_root=str(base), official_source_git=str(base), python_home='python',
                task_profile='native_claude_cc_vibe_opus48')
            args.pma_profile_file = None
            prepared = {'image_id': 'fixed-image', 'public_task_tree_sha256': 'public',
                        'ga_bundle_tree_sha256': 'source'}
            seen = []
            def prepare(_args, *, fake_gateway):
                self.assertFalse(fake_gateway)
                for name in ('control', 'archive', 'bundle/source'):
                    (root / name).mkdir(parents=True, exist_ok=True)
                return prepared
            class FakeHarbor:
                returncode = 0
                def poll(self):
                    return 0
            def start(command, **_kwargs):
                seen.append(command)
                return FakeHarbor()
            with (patch.object(live_launcher, '_prepare_common', side_effect=prepare),
                  patch.object(live_launcher, 'verify_live_spec'),
                  patch.object(live_launcher, '_stage_verifier', return_value={}),
                  patch.object(live_launcher, '_require_evaluation_state_contract'),
                  patch.object(live_launcher.subprocess, 'Popen', side_effect=start),
                  patch.object(live_launcher, 'clean_owned_containers', return_value=[]),
                  patch.object(live_launcher, 'capture_mounts', return_value=[])):
                result = live_launcher.run_live(args)
            self.assertEqual(result['harbor_return_code'], 0, result)
            self.assertEqual(len(seen), 1)
            self.assertIn('pma_harbor_cli', ' '.join(seen[0]))
            self.assertIn('--enable-verification', seen[0])
            self.assertNotIn('--disable-verification', seen[0])
            self.assertFalse(result['evaluation_released'])

    def test_structured_exit_does_not_confuse_zero_reward_with_failure(self):
        base = dict(primary_failure=None, harbor_return_code=0,
                    cleanup_confirmed=True, frozen_product=True,
                    evaluation_released=True, condition='A', native_reward=0)
        self.assertTrue(live_launcher.live_status_success(base))
        for change in (dict(harbor_return_code=1), dict(cleanup_confirmed=False),
                       dict(primary_failure={'type': 'RuntimeError'}),
                       dict(evaluation_released=False)):
            self.assertFalse(live_launcher.live_status_success({**base, **change}))
        self.assertFalse(live_launcher.live_status_success({**base, 'condition': 'B',
                                                            'worker_return_code': 1}))

    def test_serial_disposition_requires_identity_and_cleanup(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / 'archive'
            archive.mkdir()
            status = dict(primary_failure=None, harbor_return_code=1,
                          cleanup_confirmed=True, remaining_containers=[],
                          cleanup_errors=[], frozen_product=False,
                          evaluation_released=False, condition='A')
            self.assertEqual(batch_controller.disposition(status, root),
                             'stop_batch_identity_unconfirmed')
            (archive / 'agent_start_identity.json').write_text('{}', encoding='utf-8')
            self.assertEqual(batch_controller.disposition(status, root),
                             'arm_failed_isolated')
            self.assertEqual(batch_controller.disposition({**status,
                'cleanup_confirmed': False}, root), 'stop_batch_cleanup_or_status_unknown')
            self.assertEqual(batch_controller.disposition({**status,
                'primary_failure': {'type': 'RuntimeError'}}, root),
                'stop_batch_shared_runtime_unknown')


if __name__ == '__main__':
    unittest.main()
