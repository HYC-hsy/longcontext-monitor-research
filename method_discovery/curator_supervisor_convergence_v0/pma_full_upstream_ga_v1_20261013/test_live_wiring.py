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

from . import live_launcher, pma_harbor_hooks


def write_json(path: Path, value: dict) -> str:
    path.write_text(json.dumps(value, sort_keys=True), encoding='utf-8')
    return hashlib.sha256(path.read_bytes()).hexdigest()


class LiveWiringTests(unittest.TestCase):
    def test_missing_pma_credential_rejects_b_before_preparation(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / 'manifest.json'
            auth = root / 'auth.json'
            manifest_hash = write_json(manifest, {'execution_authorized': False})
            write_json(auth, {'execution_authorized': True,
                              'manifest_sha256': manifest_hash})
            args = SimpleNamespace(manifest=str(manifest), authorization=str(auth),
                                   condition='B', run_root=str(root / 'uncreated'))
            with (patch.dict(os.environ, {'PMA_MEMORY_API_KEY': ''}),
                  patch.object(live_launcher, '_prepare_common') as prepare):
                with self.assertRaisesRegex(RuntimeError, 'credential'):
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
            manifest_hash = write_json(manifest, {'execution_authorized': False, 'arms': arms})
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
        task_only = {key: good[key] for key in ('run_id', 'task_id', 'result')}
        self.assertTrue(hooks.terminal_identity_valid(task_only))
        self.assertTrue(hooks.legal_terminal(metadata, task_only, True, False))

    def test_real_branch_uses_harbor_hook_not_offline_gateway(self):
        with TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / 'new-run'
            profile = base / 'profile.py'
            profile.write_text('fixture', encoding='utf-8')
            manifest = base / 'manifest.json'
            auth = base / 'auth.json'
            manifest_hash = write_json(manifest, {'execution_authorized': False,
                'assets': {'db-wal-recovery': {'public_task_tree_sha256': 'public'}} ,
                'task_profile_sha256': hashlib.sha256(profile.read_bytes()).hexdigest()})
            write_json(auth, {'execution_authorized': True,
                              'manifest_sha256': manifest_hash,
                              'audited_code_commit': 'fixed-head'})
            args = SimpleNamespace(manifest=str(manifest), authorization=str(auth),
                task='db-wal-recovery', condition='A', run_root=str(root), run_id='new-run',
                order=1, task_profile_file=str(profile), ga_source=str(base),
                runtime_root=str(base), worker_python=str(profile), harbor_python=str(profile),
                bench_root=str(base), python_home='python',
                task_profile='native_claude_cc_vibe_opus48')
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
                  patch.object(live_launcher.subprocess, 'Popen', side_effect=start),
                  patch.object(live_launcher, 'clean_owned_containers', return_value=[]),
                  patch.object(live_launcher, 'capture_mounts', return_value=[])):
                result = live_launcher.run_live(args)
            self.assertEqual(result['harbor_return_code'], 0)
            self.assertEqual(len(seen), 1)
            self.assertIn('pma_harbor_cli', ' '.join(seen[0]))
            self.assertIn('--enable-verification', seen[0])
            self.assertNotIn('--disable-verification', seen[0])
            self.assertFalse(result['evaluation_released'])


if __name__ == '__main__':
    unittest.main()
