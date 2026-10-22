"""Exercise production preparation/binding functions without importing Harbor."""

import argparse
import ast
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest import mock

from . import single_run
from .stateful_runtime_policy import policies

STAGE = Path(__file__).resolve().parent


def functions_from(filename, names, **values):
    # Compile the actual pure entry functions, not a duplicate implementation.
    # Their external Docker/Git/Harbor adapters are supplied as explicit fakes.
    tree = ast.parse((STAGE / filename).read_text(encoding='utf-8'))
    tree.body = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name in names]
    scope = dict(__package__=__package__, __file__=str(STAGE/filename),
        Path=Path, json=json, hashlib=hashlib, runpy=runpy,
        TemporaryDirectory=tempfile.TemporaryDirectory, **values)
    exec(compile(tree, str(STAGE/filename), 'exec'), scope)
    return scope


class FrozenPolicyTests(unittest.TestCase):
    def manifest(self, root, runtime):
        task = root/'task.py'
        task.write_text("native_claude_cc_vibe_opus48 = {'model':'claude-opus-4-8', 'context_win': None}")
        pma = root/'pma.json'
        pma.write_text(json.dumps({'claude_monitor_opus48': {'model':'claude-opus-4-8'}}))
        plan = dict(schema='pma-ga-single-plan-v2', execution_authorized=False,
            official_source_git_commit='2fd12b88aafdd04a52c298e3940bcb189f9766d6',
            task='synthetic', condition='B', occurrence=1,
            research_candidate='pma_stateful_memory_v1',
            task_complete_response_policy='complete-response-v1',
            agent_time_protocol='diagnostic-uncapped-v1', **runtime)
        scope = functions_from('prepare_six_task_manifest.py', {'prepare'},
            descriptor=lambda *a, **kw: dict(image_tag='synthetic:tag', public_members=[],
                evaluator_members=[], native_agent_seconds=900),
            materialize_public=lambda source, task, dest, *a, **kw: dest.mkdir(),
            export_task=lambda source, task, dest, **kw: (dest/'test.sh').write_text('exit 0'),
            digest_tree=lambda path: 'synthetic-tree',
            image_identity=lambda tag: dict(repo_digests=['synthetic@sha256:fake'],
                image_id='synthetic', platform='linux/amd64'),
            _sha=lambda path: hashlib.sha256(path.read_bytes()).hexdigest())
        return scope['prepare'](root, task, pma, plan=plan)

    def grant(self, root, manifest):
        bound = dict(manifest['planned_order'][0], batch_id='b', run_id='r',
            config_sha256=manifest['config_sha256'], run_root=str(root/'runs/r'))
        return dict(execution_authorized=True, approved_arms=manifest['planned_order'],
            run_bindings=[bound], output_root=str(root/'runs'), batch_id='b', run_id='r',
            config_sha256=manifest['config_sha256'], audited_code_commit='f'*40,
            task_complete_response_policy='complete-response-v1',
            agent_time_protocol='diagnostic-uncapped-v1', **policies(manifest['config']))

    def test_policies_frozen_before_hash_and_legacy_defaults_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            required = self.manifest(root, {})
            diagnostic = self.manifest(root, dict(native_context_policy='off',
                research_capture_policy='best_effort'))
            self.assertEqual(policies(required['config']), policies({}))
            self.assertEqual(required['config']['native_context_guard_window_tokens'], 1000000)
            self.assertIsNone(diagnostic['config']['native_context_guard_window_tokens'])
            self.assertEqual(diagnostic['config']['native_context_guard_basis'], 'disabled_by_frozen_policy')
            for result in (required, diagnostic):
                expected = hashlib.sha256(json.dumps(result['config'], sort_keys=True,
                    separators=(',', ':')).encode()).hexdigest()
                self.assertEqual(result['config_sha256'], expected)
            self.assertNotEqual(required['config_sha256'], diagnostic['config_sha256'])

    def test_authorization_and_spec_reject_policy_drift(self):
        validator = functions_from('six_task_plan.py', {'validate_plan', '_identity'})['validate_plan']
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = self.manifest(root, dict(native_context_policy='off',
                research_capture_policy='best_effort'))
            granted = self.grant(root, manifest)
            self.assertEqual(len(validator(manifest, granted)), 1)
            for key in policies({}):
                changed = dict(granted, **{key:'required'})
                with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'policies differ'):
                    validator(manifest, changed)
            manifest_file, authorization = root/'manifest.json', root/'authorization.json'
            manifest_file.write_text(json.dumps(manifest))
            granted['manifest_sha256'] = hashlib.sha256(manifest_file.read_bytes()).hexdigest()
            authorization.write_text(json.dumps(granted))
            spec = dict(granted['run_bindings'][0], schema='pma-ga-live-run-v1',
                mode='authorized_live', task_id='synthetic', manifest_path=str(manifest_file),
                authorization_path=str(authorization), manifest_sha256=granted['manifest_sha256'],
                authorization_sha256=hashlib.sha256(authorization.read_bytes()).hexdigest(),
                audited_code_commit='f'*40, agent_time_protocol='diagnostic-uncapped-v1',
                **policies(manifest['config']))
            fake_process = argparse.Namespace(run=mock.Mock(return_value=argparse.Namespace(stdout='f'*40)))
            verify = functions_from('pma_harbor_hooks.py', {'verify_live_spec'},
                validate_plan=validator, subprocess=fake_process)['verify_live_spec']
            verify(spec)
            for key in policies({}):
                with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'policies differ'):
                    verify(dict(spec, **{key:'required'}))

    def test_existing_prepare_cli_supports_strict_opt_in(self):
        base = ['single_run', 'prepare', '--task', 'synthetic', '--condition', 'B',
            '--output', 'unused', '--official-source-git', 'unused', '--task-profile-file', 'unused']
        for extra, expected in [([], policies({})),
                (['--native-context-policy','off','--research-capture-policy','best_effort'],
                 dict(native_context_policy='off', research_capture_policy='best_effort'))]:
            with mock.patch('sys.argv', base+extra), mock.patch.object(single_run, 'prepare', return_value={}) as prepare, \
                    contextlib.redirect_stdout(io.StringIO()):
                single_run.main()
            self.assertEqual(policies(vars(prepare.call_args.args[0])), expected)
        with mock.patch('sys.argv', base+['--native-context-policy','disabled']), \
                contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            single_run.main()

    def test_policy_module_is_in_staged_and_certified_bundle(self):
        for filename in ('offline_launcher.py', 'stateful_certification.py'):
            tree = ast.parse((STAGE/filename).read_text())
            self.assertTrue(any(isinstance(node, ast.Constant) and
                node.value == 'stateful_runtime_policy.py' for node in ast.walk(tree)))


if __name__ == '__main__':
    unittest.main()
