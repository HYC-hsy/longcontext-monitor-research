"""Explicit opt-in, source identity, and launch wiring; no launch is executed."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pma_evidence_review.tests.test_selection_deployment import ROOT, STAGE, REL, source_contract

spec = importlib.util.spec_from_file_location('maintenance_config', STAGE / 'citation_gate_config.py')
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)


class MaintenancePolicyTests(unittest.TestCase):
    def test_explicit_policy_cannot_fall_back_or_combine_with_gate(self):
        policy = config.MAINTENANCE_POLICY
        self.assertEqual(config.worker_flags(None, 'pma_gap_evidence_v1', None, policy),
                         ['--memory-maintenance-policy', policy])
        self.assertEqual(config.worker_flags(None, 'pma_gap_evidence_v1'), [])
        for candidate, gate, strategy, condition in (
                ('U', None, None, 'B'), ('pma_gap_evidence_v1', 'gate-only', None, 'B'),
                ('pma_gap_evidence_v1', None, config.CLAIM_SPLIT_SEMANTIC, 'B'),
                ('pma_gap_evidence_v1', None, None, 'A')):
            with self.assertRaises(ValueError):
                config.validate_maintenance(policy, candidate, gate, strategy, condition)
        with self.assertRaises(ValueError):
            config.validate_maintenance('typo', 'pma_gap_evidence_v1')
        frozen = {'memory_maintenance_policy': policy}
        with self.assertRaisesRegex(ValueError, 'differs'):
            config.require_maintenance_binding(None, frozen, 'pma_gap_evidence_v1')
        with self.assertRaises(ValueError):
            config.validate_strategy(None, config.CLAIM_SPLIT_SEMANTIC)

    def test_non_gate_host_manifest_contains_and_checks_new_dependencies(self):
        files = source_contract()['EVIDENCE_GAP_SOURCE_FILES']
        for name in ('maintenance_no_review_agent.py', 'verbatim_selection_mixin.py',
                     'citation_gate_config.py', 'selection_context.py', 'tag_selection_contract.py'):
            self.assertEqual(files.count((REL / name).as_posix()), 1)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in files:
                p = root / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(b'# synthetic source\r\n')
            hashes = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in files}
            frozen = {'research_candidate': 'pma_gap_evidence_v1',
                'memory_maintenance_policy': config.MAINTENANCE_POLICY,
                'maintenance_source_sha256': hashes}
            with patch.object(config, '__file__', str(root / REL / 'citation_gate_config.py')), \
                    patch.object(config, 'maintenance_source_paths', return_value=list(files)):
                config.verify_gate_sources(frozen)
                target = (REL / 'maintenance_no_review_agent.py').as_posix()
                with self.assertRaisesRegex(ValueError, 'identity differs'):
                    config.verify_gate_sources({**frozen, 'maintenance_source_sha256': {}})
                (root / target).write_bytes(b'changed\n')
                with self.assertRaisesRegex(ValueError, 'identity differs'):
                    config.verify_gate_sources(frozen)
                (root / target).unlink()
                with self.assertRaises(FileNotFoundError):
                    config.verify_gate_sources(frozen)
        with self.assertRaisesRegex(ValueError, 'without policy'):
            config.verify_gate_sources({'maintenance_source_sha256': {}})

    def test_policy_is_forwarded_at_each_host_boundary(self):
        # Static wiring complements complete real factory/dispatcher tests.
        for filename in ('single_run.py', 'prepare_six_task_manifest.py',
                         'batch_controller.py', 'live_launcher.py', 'worker_main.py',
                         'pma_harbor_hooks.py', 'episode.py'):
            text = (STAGE / filename).read_text()
            ast.parse(text)
            self.assertIn('memory_maintenance_policy', text, filename)
        self.assertIn('require_maintenance_binding', (STAGE / 'pma_harbor_hooks.py').read_text())
        self.assertIn("maintenance_policy=", (STAGE / 'live_launcher.py').read_text())

    def test_frontend_freezes_policy_and_detects_dropped_switch(self):
        from experiment_runner.__main__ import build_plan, execute, succeeded
        from experiment_runner.test_runner_frontend import FakeBackend
        from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.export_official_evaluator import COMMIT
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            value = {'schema': 'ga-experiment-plan-v1', 'method': 'pma-gap-evidence',
                'slots': [{'task': 'fix-ocaml-gc'}], 'runtime_policy': {},
                'memory_maintenance_policy': config.MAINTENANCE_POLICY,
                'dataset': {'source_git': str(root), 'commit': COMMIT},
                'environment': {'fake_only': True, 'profiles': {
                    'task_profile_file': '/unused-task', 'pma_profile_file': '/unused-memory'}}}
            public = {'tasks': [{'task': 'fix-ocaml-gc', 'agent_timeout_sec': 900, 'verifier_timeout_sec': 900}]}
            with patch('experiment_runner.__main__.catalog', return_value=public):
                plan = build_plan(value)
            for dropped in (False, True):
                backend = FakeBackend()
                original = backend.prepare
                def prepare(args):
                    result = original(args)
                    if not dropped:
                        for name in ('plan.json', 'manifest.json'):
                            p = Path(args.output) / name
                            data = json.loads(p.read_text())
                            target = data if name == 'plan.json' else data.setdefault('config', {})
                            target['memory_maintenance_policy'] = args.memory_maintenance_policy
                            p.write_text(json.dumps(data))
                    return result
                backend.prepare = prepare
                rows = execute(plan, root / str(dropped), 'prepare', backend)
                self.assertEqual(backend.prepared[0].memory_maintenance_policy, config.MAINTENANCE_POLICY)
                if dropped:
                    self.assertEqual(rows[0]['status'], 'preparation_failed')
                    self.assertIn('maintenance policy differs', rows[0]['error'])
                else:
                    self.assertTrue(succeeded(rows, 1, 'prepare'), rows)
