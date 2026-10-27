"""Missing gap policy fails before profiles, artifacts, grants or runtime."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013 import single_run as sr
from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013 import single_run_fixture as sf


class GatePolicyPreflightTests(unittest.TestCase):
    def args(self, root, **changes):
        values = dict(task='sqlite-with-gcov', condition='B', occurrence=1,
                      research_candidate='pma_gap_evidence_v1', fake_only=True,
                      output=str(root), citation_review_gate='gate-only')
        values.update(changes)
        return NS(**values)

    def test_missing_gap_policy_rejected_before_output_for_all_modes(self):
        for candidate in ('pma_gap_memory_v0', 'pma_gap_evidence_v1'):
            modes = (None,) if candidate == 'pma_gap_memory_v0' else (None, 'gate-only', 'gate-one-repair')
            for mode in modes:
                with self.subTest(candidate=candidate, mode=mode), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp) / 'must-not-be-created'
                    with patch.object(Path, 'mkdir', side_effect=AssertionError('filesystem mutation')):
                        with self.assertRaisesRegex(ValueError, 'explicit runtime policy'):
                            sr.prepare(self.args(root, research_candidate=candidate,
                                                 citation_review_gate=mode))
                    self.assertFalse(root.exists())

    def test_missing_policy_also_rejected_for_formal_preparation(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'explicit runtime policy'):
                sr.prepare(self.args(Path(tmp)/'new', fake_only=False,
                                     certification_dir='existing-certificate'))

    def test_non_object_policy_rejected_before_output(self):
        for bad in ([], 'uncapped', 1, True):
            with self.subTest(bad=bad), patch.object(Path, 'mkdir', side_effect=AssertionError('filesystem mutation')):
                with self.assertRaisesRegex(ValueError, 'requested-policy JSON object'):
                    sr.prepare(self.args(Path('unused'), runtime_policy=bad))

    def test_explicit_requested_policy_passes_preflight_without_defaulting(self):
        requested = {'agent_timeout': 'uncapped', 'task_turns': 'uncapped',
                     'verifier_timeout': 'official'}
        args = self.args(Path('unused'), runtime_policy=requested)
        with patch.object(Path, 'mkdir', side_effect=RuntimeError('after_policy_preflight')):
            with self.assertRaisesRegex(RuntimeError, 'after_policy_preflight'):
                sr.prepare(args)
        self.assertIs(args.runtime_policy, requested)
        self.assertEqual(requested, {'agent_timeout': 'uncapped', 'task_turns': 'uncapped',
                                     'verifier_timeout': 'official'})

    def test_a_keeps_no_policy_and_rejects_gap_policy_override(self):
        args = self.args(Path('unused'), condition='A', research_candidate='U', citation_review_gate=None)
        with patch.object(Path, 'mkdir', side_effect=RuntimeError('baseline_unchanged')):
            with self.assertRaisesRegex(RuntimeError, 'baseline_unchanged'):
                sr.prepare(args)
        args.runtime_policy = {}
        with self.assertRaisesRegex(ValueError, 'supported candidate'):
            sr.prepare(args)

    def test_fixture_missing_policy_stops_before_grant_or_subprocess(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'uncreated'
            argv = ['fixture', '--task', 'sqlite-with-gcov', '--condition', 'B',
                    '--research-candidate', 'pma_gap_evidence_v1', '--citation-review-gate',
                    'gate-only', '--output', str(root), '--service-fixture']
            for key in ('official-source-git', 'task-profile-file', 'ga-source', 'runtime-root',
                        'worker-python', 'harbor-python', 'bench-root', 'harbor-source-root', 'pma-profile-file'):
                argv += ['--'+key, 'not-read']
            with patch('sys.argv', argv), patch.object(sf.subprocess, 'run',
                    side_effect=AssertionError('subprocess started')):
                with self.assertRaisesRegex(ValueError, 'explicit runtime policy'):
                    sf.main()
            self.assertFalse(root.exists())

    def test_fixture_forwards_requested_policy_unchanged(self):
        requested = {'agent_timeout': 'uncapped', 'task_turns': 'uncapped', 'verifier_timeout': 'official'}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'policy.json'
            path.write_text(json.dumps(requested), encoding='utf-8')
            for mode in ('gate-only', 'gate-one-repair'):
                argv = ['fixture', '--task', 'sqlite-with-gcov', '--condition', 'B',
                        '--research-candidate', 'pma_gap_evidence_v1', '--citation-review-gate', mode,
                        '--output', 'unused', '--runtime-policy-file', str(path)]
                for key in ('official-source-git', 'task-profile-file', 'ga-source', 'runtime-root',
                            'worker-python', 'harbor-python', 'bench-root', 'harbor-source-root', 'pma-profile-file'):
                    argv += ['--'+key, 'not-read']
                with patch('sys.argv', argv), patch.object(sf, 'prepare',
                        side_effect=RuntimeError('stop_before_assets')) as prepare:
                    with self.assertRaisesRegex(RuntimeError, 'stop_before_assets'):
                        sf.main()
                    self.assertEqual(prepare.call_args.args[0].runtime_policy, requested)
                    self.assertEqual(prepare.call_args.args[0].citation_review_gate, mode)

    def test_stateful_fake_plan_remains_independent_of_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = sr.prepare_stateful_fake(NS(fake_only=True, output=str(Path(tmp)/'new')))
            self.assertEqual(plan['research_candidate'], 'pma_stateful_memory_v1')
            self.assertNotIn('citation_review_gate', plan)
            self.assertFalse(plan['execution_authorized'])

    def test_main_prepare_rejects_dropped_gate_before_manifest_identity(self):
        from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013 import prepare_six_task_manifest as pm
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp); out = p/'new'
            args = self.args(out, runtime_policy={}, official_source_git=str(p),
                             task_profile_file=str(p), pma_profile_file=str(p))
            with patch.object(pm, 'prepare', return_value={'config': {}}):
                with self.assertRaisesRegex(ValueError, 'gate differs'):
                    sr.prepare(args)
            self.assertFalse((out/'manifest.json').exists())
            self.assertFalse((out/'run_identity.json').exists())
            self.assertEqual(json.loads((out/'plan.json').read_text())['citation_review_gate'], 'gate-only')

    def test_actual_prepare_plan_manifest_identity_chain_for_both_modes(self):
        # Only local asset/image boundaries are synthetic; real CLI prepare,
        # plan/schema handling, policy resolution, config hash and file identity
        # are exercised. No Harbor, Docker, Task or profile secrets are used.
        import hashlib
        from contextlib import ExitStack
        from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013 import prepare_six_task_manifest as pm
        requested = {'agent_timeout': 'uncapped', 'task_turns': 'uncapped', 'verifier_timeout': 'official'}
        for mode in ('gate-only', 'gate-one-repair'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
                p = Path(tmp); out = p/'new'; task = p/'task.py'; memory = p/'pma.json'
                task.write_text("native_claude_cc_vibe_opus48={'model':'claude-opus-4-8'}\n", encoding='utf-8')
                memory.write_text(json.dumps({'claude_monitor_opus48': {'model':'claude-opus-4-8'}}), encoding='utf-8')
                desc = {'image_tag':'fixture/task:v1', 'public_members':[], 'evaluator_members':[],
                        'native_agent_seconds':900, 'native_verifier_seconds':900}
                stack.enter_context(patch.object(pm, 'descriptor', return_value=desc))
                def materialize(source, name, public, members, **kwargs): public.mkdir()
                def export(source, name, tests, **kwargs): (tests/'test.sh').write_text('true\n', encoding='utf-8')
                stack.enter_context(patch.object(pm, 'materialize_public', side_effect=materialize))
                stack.enter_context(patch.object(pm, 'export_task', side_effect=export))
                stack.enter_context(patch.object(pm, 'image_identity', return_value={
                    'repo_digests':['fixture/task@sha256:'+'0'*64], 'image_id':'fixture-image', 'platform':'linux/amd64'}))
                stack.enter_context(patch.object(pm, '_committed_source_sha', return_value='1'*64))
                args = self.args(out, citation_review_gate=mode, runtime_policy=requested,
                                 official_source_git=str(p), task_profile_file=str(task), pma_profile_file=str(memory))
                identity = sr.prepare(args)
                plan = json.loads((out/'plan.json').read_text(encoding='utf-8'))
                manifest = json.loads((out/'manifest.json').read_text(encoding='utf-8'))
                self.assertEqual(plan['citation_review_gate'], mode)
                self.assertEqual(plan['runtime_policy'], requested)
                self.assertEqual(manifest['config']['citation_review_gate'], mode)
                self.assertTrue(manifest['config']['citation_gate_source_sha256'])
                policy = manifest['config']['runtime_policy']
                self.assertEqual(policy['requested'], requested)
                self.assertIsNone(policy['effective_agent_seconds'])
                self.assertIsNone(policy['effective_task_turns'])
                self.assertEqual(policy['official_verifier_seconds'], 900)
                self.assertEqual(manifest['config_sha256'], hashlib.sha256(json.dumps(
                    manifest['config'], sort_keys=True, separators=(',', ':')).encode()).hexdigest())
                self.assertEqual(identity['plan_sha256'], hashlib.sha256((out/'plan.json').read_bytes()).hexdigest())
                self.assertEqual(identity['manifest_sha256'], hashlib.sha256((out/'manifest.json').read_bytes()).hexdigest())
                self.assertTrue(manifest['zero_model_fixture_only'])
                self.assertFalse(identity['execution_authorized'])
