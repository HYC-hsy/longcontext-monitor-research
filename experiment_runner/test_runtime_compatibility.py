"""Compatibility with the parallel diagnostic runner; no HTTP, Docker or models."""
import ast
import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import tomllib
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / 'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013'


def definitions(filename, names, namespace):
    tree = ast.parse((RUN / filename).read_text())
    selected = [node for node in tree.body if getattr(node, 'name', None) in names]
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(RUN / filename), 'exec'), namespace)
    return namespace


class RuntimeCompatibilityTests(unittest.TestCase):
    def test_legacy_derivation_preserves_verifier_and_source_receipt(self):
        ns = definitions('live_launcher.py', {'_derive_uncapped_task'}, {
            'Path': Path, 'tomllib': tomllib, 'hashlib': hashlib, 're': re, 'json': json,
            'digest_tree': lambda root: 'derived-tree'})
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'public_task').mkdir()
            path = root / 'public_task/task.toml'
            before = b'[verifier]\ntimeout_sec = 900.0\n[agent]\ntimeout_sec = 900.0\n'
            path.write_bytes(before)
            receipt = ns['_derive_uncapped_task'](root)
            self.assertEqual(receipt['original_task_toml_sha256'], hashlib.sha256(before).hexdigest())
            self.assertEqual(tomllib.loads(path.read_text()), {'verifier': {'timeout_sec': 900.0}, 'agent': {}})
            self.assertIsNone(receipt['agent_timeout_sec'])

    def test_legacy_derivation_rejects_unrelated_official_limits(self):
        ns = definitions('live_launcher.py', {'_derive_uncapped_task'}, {
            'Path': Path, 'tomllib': tomllib, 'hashlib': hashlib, 're': re, 'json': json,
            'digest_tree': lambda root: 'derived-tree'})
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'public_task').mkdir()
            path = root / 'public_task/task.toml'
            before = b'[verifier]\ntimeout_sec = 100.0\n[agent]\ntimeout_sec = 100.0\n'
            path.write_bytes(before)
            with self.assertRaises(RuntimeError):
                ns['_derive_uncapped_task'](root)
            self.assertEqual(path.read_bytes(), before)

    def adapter(self):
        class Base:
            async def run(self, instruction, environment, context):
                self.observed = (self.timeout_sec, environment)
        ns = definitions('harbor_adapter.py', {'HarborGenericAgent'}, {
            'original': types.SimpleNamespace(HarborGenericAgent=Base), 'os': os})
        agent = ns['HarborGenericAgent']()
        agent.timeout_sec = 900.0
        agent.condition_id = 'stateful-memory-v1'
        return agent

    def test_legacy_diagnostic_uses_native_none_not_old_template(self):
        agent, environment = self.adapter(), object()
        with patch.dict(os.environ, {'GA_STATEFUL_AGENT_TIME_PROTOCOL': 'diagnostic-uncapped-v1',
                                     'GA_STATEFUL_MEMORY_ENABLED': '1'}, clear=True):
            asyncio.run(agent.run('task', environment, object()))
        self.assertEqual(agent.observed, (None, environment))

    def test_explicit_finite_policy_not_forced_uncapped_by_adapter(self):
        agent, environment = self.adapter(), object()
        with patch.dict(os.environ, {'GA_STATEFUL_AGENT_TIME_PROTOCOL': 'runtime-policy-v1'}, clear=True):
            asyncio.run(agent.run('task', environment, object()))
        self.assertEqual(agent.observed, (900.0, environment))

    def test_wrong_identity_cannot_activate_legacy_uncapping(self):
        agent = self.adapter()
        with patch.dict(os.environ, {'GA_STATEFUL_AGENT_TIME_PROTOCOL': 'diagnostic-uncapped-v1'}, clear=True):
            with self.assertRaises(RuntimeError):
                asyncio.run(agent.run('task', object(), object()))
        self.assertFalse(hasattr(agent, 'observed'))

    def test_explicit_policy_skips_derived_task_mutation(self):
        tree = ast.parse((RUN / 'live_launcher.py').read_text())
        assignment = next(node for node in ast.walk(tree) if isinstance(node, ast.Assign)
                          and any(isinstance(target, ast.Name) and target.id == 'diagnostic_task'
                                  for target in node.targets))
        calls = []
        for policy in ({}, {'effective_agent_seconds': None}, {'effective_agent_seconds': 1800}):
            ns = {'stateful': True, 'runtime_policy': policy, 'root': object(),
                  '_derive_uncapped_task': lambda root: calls.append(root)}
            exec(compile(ast.Module(body=[assignment], type_ignores=[]), '<selection>', 'exec'), ns)
            self.assertIsNone(ns['diagnostic_task'])
        self.assertEqual(calls, [])

    def test_launcher_allows_finite_explicit_policy_but_not_implicit_legacy_cap(self):
        tree = ast.parse((RUN / 'live_launcher.py').read_text())
        guard = next(node for node in ast.walk(tree) if isinstance(node, ast.If)
                     and any(isinstance(child, ast.Constant) and child.value ==
                             'stateful authorization, policy or uncapped identity mismatch'
                             for child in ast.walk(node)) and len(node.body) == 1
                     and isinstance(node.body[0], ast.Raise))
        config = {'task_turns_max': 20, 'agent_wall_seconds': 1800,
                  'runtime_policy': {'effective_agent_seconds': 1800}}
        ns = {'stateful': True, 'args': types.SimpleNamespace(condition='B'),
              'fixture': False, 'manifest': {'config': config},
              'task_policy': 'complete-response-v1', 'actual_task_policy': 'complete-response-v1',
              'authorized': {'task_complete_response_policy': 'complete-response-v1'}}
        code = compile(ast.Module(body=[guard], type_ignores=[]), '<launcher-guard>', 'exec')
        exec(code, ns)
        del config['runtime_policy']
        with self.assertRaises(RuntimeError):
            exec(code, ns)
        config.update(task_turns_max=None, agent_wall_seconds=None)
        exec(code, ns)

    def test_adapter_byte_pin_matches_actual_native_none_implementation(self):
        tree = ast.parse((RUN / 'harbor_adapter.py').read_text())
        pin = next(node.value.value for node in tree.body if isinstance(node, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == 'EXPECTED_ADAPTER_SHA256' for t in node.targets))
        self.assertEqual(pin, hashlib.sha256((ROOT / 'long_context_bench/adapters/harbor_ga_agent.py').read_bytes()).hexdigest())


if __name__ == '__main__':
    unittest.main()
