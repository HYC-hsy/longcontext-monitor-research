"""Real local adapters with synthetic assets/environments; no Docker or HTTP."""
import asyncio
import ast
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch

from experiment_runner.runtime_policy import apply_harbor_policy
from experiment_runner.methods import clean_candidate_environment, resolve

ROOT = Path(__file__).resolve().parents[1]
RUN = ('method_discovery.curator_supervisor_convergence_v0.'
       'pma_full_upstream_ga_v1_20261013')


def module(name, **attributes):
    value = types.ModuleType(name)
    value.__dict__.update(attributes)
    return value


class RuntimeIntegrationTests(unittest.TestCase):
    def test_stale_candidate_configuration_is_removed_and_restored(self):
        from experiment_runner.__main__ import method_environment
        import os
        dirty = {'GA_STATEFUL_MEMORY_ENABLED': '1', 'GA_STATEFUL_MEMORY_MODE': 'live',
                 'GA_STATEFUL_UNCAPPED_TOTAL': '1', 'GA_POS_PROFILE_FILE': 'private',
                 'GA_POS_ENABLED': '1', 'GA_PMA_UPSTREAM_DEADLINE_EPOCH': '1',
                 'GA_MONITOR_CONFIG': 'old', 'GA_TASK_DEADLINE_EPOCH': '1',
                 'UNCHANGED': 'value'}
        cleaned = clean_candidate_environment(dirty)
        self.assertEqual(cleaned, {'UNCHANGED': 'value'})
        self.assertEqual(dirty['GA_POS_ENABLED'], '1')
        for name in ('ga-only', 'pma', 'pma-stateful', 'pos'):
            with self.subTest(method=name), patch.dict(os.environ, dirty, clear=True):
                with method_environment(resolve(name)):
                    self.assertNotIn('GA_STATEFUL_MEMORY_MODE', os.environ)
                    self.assertNotIn('GA_POS_PROFILE_FILE', os.environ)
                    self.assertNotIn('GA_TASK_DEADLINE_EPOCH', os.environ)
                    self.assertEqual(os.environ['GA_POS_ENABLED'], '0')
                self.assertEqual(dict(os.environ), dirty)

    def load_manifest_builder(self):
        bundle = 'long_context_bench.scripts.isolated_run_bundle'
        fake_digest = lambda path: hashlib.sha256(str(sorted(
            p.relative_to(path).as_posix() for p in Path(path).rglob('*'))).encode()).hexdigest()
        stubs = {bundle: module(bundle, digest_tree=fake_digest),
                 RUN + '.offline_launcher': module(RUN + '.offline_launcher', image_identity=None)}
        with patch.dict(sys.modules, stubs):
            name = RUN + '.prepare_six_task_manifest'
            spec = importlib.util.spec_from_file_location(name, ROOT / (name.replace('.', '/') + '.py'))
            result = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(result)
        return result

    def prepare(self, requested):
        builder = self.load_manifest_builder()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task = root / 'task.py'
            task.write_text("native_claude_cc_vibe_opus48 = {'model': 'claude-opus-4-8', 'context_win': 10000}")
            # Windows reserves AUX even when a filename has an extension.
            auxiliary = root / 'auxiliary_profile.json'
            auxiliary.write_text(json.dumps({'claude_monitor_opus48': {'model': 'claude-opus-4-8'}}))
            def materialize(source, name, target, expected, **kwargs):
                target.mkdir()
                (target / 'task.toml').write_text('[agent]\ntimeout_sec=900\n')
            def export(source, name, target, **kwargs):
                (target / 'test.sh').write_text('# synthetic test fixture\n')
            asset = {'public_members': [], 'evaluator_members': [],
                     'image_tag': 'synthetic/image:test', 'native_agent_seconds': 900,
                     'native_verifier_seconds': 900}
            image = {'repo_digests': ['synthetic/image@sha256:abc'],
                     'image_id': 'synthetic', 'platform': 'synthetic'}
            plan = {'schema': 'pma-ga-single-plan-v2', 'execution_authorized': False,
                    'official_source_git_commit': '2fd12b88aafdd04a52c298e3940bcb189f9766d6',
                    'task': 'synthetic-task', 'condition': 'B', 'occurrence': 1,
                    'research_candidate': 'pma_stateful_memory_v1',
                    'task_complete_response_policy': 'complete-response-v1',
                    'agent_time_protocol': ('diagnostic-uncapped-v1' if requested is None
                                            else 'runtime-policy-v1')}
            if requested is not None:
                plan['runtime_policy'] = requested
            with patch.object(builder, 'descriptor', return_value=asset), \
                    patch.object(builder, 'materialize_public', side_effect=materialize), \
                    patch.object(builder, 'export_task', side_effect=export), \
                    patch.object(builder, 'image_identity', return_value=image):
                return builder.prepare(root, task, auxiliary, plan=plan)

    def test_requested_policy_is_frozen_before_hash_and_old_manifest_unchanged(self):
        legacy = self.prepare(None)
        official = self.prepare({'agent_timeout': 'official'})
        relaxed = self.prepare({'agent_timeout': 'uncapped'})
        self.assertNotIn('runtime_policy', legacy['config'])
        self.assertEqual(official['config']['agent_wall_seconds'], 900)
        self.assertIsNone(relaxed['config']['agent_wall_seconds'])
        self.assertIsNone(relaxed['config']['runtime_policy']['outer_timeout_seconds'])
        for value in (official, relaxed):
            expected = hashlib.sha256(json.dumps(value['config'], sort_keys=True,
                separators=(',', ':')).encode()).hexdigest()
            self.assertEqual(value['config_sha256'], expected)
        self.assertNotEqual(official['config_sha256'], relaxed['config_sha256'])

    def test_changed_policy_does_not_accept_old_authorization(self):
        from importlib import import_module
        validate = import_module(RUN + '.six_task_plan').validate_plan
        official = self.prepare({'agent_timeout': 'official'})
        relaxed = self.prepare({'agent_timeout': 'uncapped'})
        arm = official['planned_order'][0]
        root = str(Path('/tmp/synthetic-experiment').resolve())
        binding = dict(arm, run_id='test', batch_id='batch', run_root=root + '/test',
                       config_sha256=official['config_sha256'])
        grant = {'execution_authorized': True, 'approved_arms': [arm],
                 'run_bindings': [binding], 'output_root': root,
                 'run_id': 'test', 'batch_id': 'batch',
                 'config_sha256': official['config_sha256'],
                 'agent_time_protocol': official['config']['agent_time_protocol'],
                 'task_complete_response_policy': 'complete-response-v1'}
        self.assertEqual(validate(official, grant), [binding])
        with self.assertRaises(RuntimeError):
            validate(relaxed, grant)

    def load_adapter(self):
        class BaseAgent:
            def __init__(self, **kwargs):
                self.model_name = kwargs['model_name']
        async def preserve(*args):
            return None
        stubs = {
            'adapters.failure_snapshot': module('adapters.failure_snapshot', preserve_failed_workspace=preserve),
            'adapters.isolated_setup': module('adapters.isolated_setup', start_isolated_transport=preserve,
                                               ENVIRONMENT_NOTE=''),
            'harbor.agents.base': module('harbor.agents.base', BaseAgent=BaseAgent),
            'harbor.environments.base': module('harbor.environments.base', BaseEnvironment=object),
            'harbor.models.agent.context': module('harbor.models.agent.context', AgentContext=object),
        }
        with patch.dict(sys.modules, stubs):
            spec = importlib.util.spec_from_file_location('_isolated_adapter_under_test',
                ROOT / 'long_context_bench/adapters/harbor_ga_agent.py')
            result = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(result)
        return result

    def exercise_adapter(self, timeout):
        adapter = self.load_adapter().HarborGenericAgent(
            run_id='synthetic', expected_model='synthetic', model_name='synthetic',
            python_home='python', ga_source_sha256='synthetic', timeout_sec=timeout)
        class Environment:
            def __init__(self):
                self.calls = []
            async def exec(self, command, **kwargs):
                self.calls.append((command, kwargs))
                return types.SimpleNamespace(return_code=0, stdout='0', stderr='')
        environment = Environment()
        with patch.dict('os.environ', {}, clear=True):
            asyncio.run(adapter.run('synthetic task', environment, types.SimpleNamespace()))
        return next(item for item in environment.calls if '# GA_WRAPPER_RUN_ID=' in item[0])

    def test_actual_adapter_uncapped_shell_and_exec_have_no_total_limit(self):
        command, kwargs = self.exercise_adapter('uncapped')
        self.assertIn('while true; do', command)
        self.assertNotIn('seq 1', command)
        self.assertIsNone(kwargs['timeout_sec'])
        self.assertIn('kill -0', command)
        self.assertIn('wait "$pid"', command)
        shell = shutil.which('sh')
        if shell is None and sys.platform == 'win32':
            candidate = Path(r'C:\Program Files\Git\bin\sh.exe')
            shell = str(candidate) if candidate.is_file() else None
        self.assertIsNotNone(shell, 'a POSIX shell is required to check the wrapper')
        syntax = subprocess.run([shell, '-n'], input=command, text=True,
                                capture_output=True, check=False)
        self.assertEqual(syntax.returncode, 0, syntax.stderr)

    def test_actual_adapter_finite_path_keeps_timeout(self):
        command, kwargs = self.exercise_adapter(30)
        self.assertIn('for i in $(seq 1 15); do', command)
        self.assertEqual(kwargs['timeout_sec'], 120)

    def test_adapter_rejects_invalid_limit(self):
        cls = self.load_adapter().HarborGenericAgent
        for value in (0, -1, True, float('inf'), float('nan')):
            with self.subTest(value=value), self.assertRaises(ValueError):
                cls(run_id='synthetic', expected_model='synthetic', model_name='synthetic',
                    python_home='python', ga_source_sha256='synthetic', timeout_sec=value)

    def test_adapter_pin_matches_actual_source(self):
        raw = (ROOT / 'long_context_bench/adapters/harbor_ga_agent.py').read_bytes()
        overlay = (ROOT / (RUN.replace('.', '/') + '/harbor_adapter.py')).read_text()
        self.assertIn(hashlib.sha256(raw).hexdigest(), overlay)

    def test_frozen_turn_policy_ignores_mutable_plan_mode_limit(self):
        parsed = ast.parse((ROOT / 'GenericAgent-main/agent_loop.py').read_text(encoding='utf-8'))
        function = next(node for node in ast.walk(parsed)
                        if isinstance(node, ast.FunctionDef) and node.name == 'within_turn_limit')
        module = ast.Module(body=[function], type_ignores=[])
        import os
        context = {'explicit_turn_policy': True, 'max_turns': 7, 'local_turn': 6,
                   'handler': types.SimpleNamespace(max_turns=1), 'os': os,
                   'stateful_enabled': True, 'stateful_mode': 'live'}
        exec(compile(ast.fix_missing_locations(module), '<actual-GA-turn-policy>', 'exec'), context)
        self.assertTrue(context['within_turn_limit']())
        context['local_turn'] = 7
        self.assertFalse(context['within_turn_limit']())
        context['max_turns'] = None
        context['local_turn'] = 1000
        self.assertTrue(context['within_turn_limit']())


if __name__ == '__main__':
    unittest.main()
