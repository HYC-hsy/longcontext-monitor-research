"""Synthetic on-disk evidence validates the real certificate policy checks."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from experiment_runner.runtime_policy import resolve_policy

ROOT = Path(__file__).resolve().parents[1]
RUN = 'method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013'
HARBOR = '459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc'


class PolicyEvidenceTests(unittest.TestCase):
    def verifier(self):
        def mod(name, **values):
            result = types.ModuleType(name)
            result.__dict__.update(values)
            return result
        stubs = {
            RUN + '.prepare_six_task_manifest': mod(RUN + '.prepare_six_task_manifest',
                V3_SOURCE_FILES=(), _committed_source_sha=lambda *args: 'synthetic'),
            RUN + '.single_run_certification': mod(RUN + '.single_run_certification',
                HARBOR_COMMIT=HARBOR, vendor_identity=lambda checkout: {}),
        }
        name = RUN + '.stateful_certification'
        with patch.dict(sys.modules, stubs):
            spec = importlib.util.spec_from_file_location(name, ROOT / (name.replace('.', '/') + '.py'))
            value = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(value)
        value.source_identity = lambda checkout: {}
        return value

    def fixture(self, root):
        policy = resolve_policy({'agent_timeout': 'uncapped'}, {
            'native_agent_seconds': 900, 'native_verifier_seconds': 900},
            {'task_turns_max': None})
        execution = {'source_files': {}, 'vendor_files': {}, 'harbor_commit': HARBOR,
                     'runtime_policy': policy, 'config_sha256': 'synthetic-config'}
        result = {'run_id': 'synthetic', 'task': 'synthetic-task',
            'research_candidate': 'pma_stateful_memory_v1', 'zero_model_fixture_only': True,
            'harbor_return_code': 0, 'worker_return_code': 0, 'cleanup_confirmed': True,
            'native_result': {'status': 'native_recorded'},
            'native_script_observed': True, 'native_reports_checked': True}
        bodies = {
            'execution_identity.json': execution, 'live_result.json': result,
            'stateful_task_terminal.json': {'run_id': 'synthetic', 'task_id': 'synthetic-task',
                'result': 'CURRENT_TASK_DONE', 'stateful_finalization': {'closed': True, 'cycle_count': 2}},
            'worker_ready.json': {'run_id': 'synthetic', 'mode': 'fake-only'},
            'worker_exit.json': {'run_id': 'synthetic'},
            'agent_start_identity.json': {'container_id': 'synthetic-container'},
            'agent_end_native.json': {'container_id': 'synthetic-container', 'writers_stopped': True},
            'fake_authorization_removed.json': {'authorization_removed': True},
            'task_requests.json': {'request_count': 2, 'reminder_counts': [0, 1]},
            'runtime_policy_effective.json': {'runtime_policy': policy,
                'config_sha256': 'synthetic-config', 'run_id': 'synthetic',
                'effective_agent_seconds': None, 'task_files_modified': False,
                'preserved_timeout_caches': {'_verifier_timeout_sec': 900}},
        }
        verifier = self.verifier()
        for name in verifier.REQUIRED:
            (root / name).write_text(json.dumps(bodies.get(name, {})))
        for name, body in bodies.items():
            (root / name).write_text(json.dumps(body))
        (root / 'host_events.jsonl').write_text('\n'.join(json.dumps({'kind': kind}) for kind in
            ('initialize', 'action_batch', 'confirm_task', 'finish')))
        return verifier

    def test_observed_policy_is_hashed_and_returned(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            verifier = self.fixture(root)
            result = verifier.verify_evidence(root, require_committed=False)
            self.assertIn('runtime_policy_effective.json', result['file_sha256'])
            self.assertIsNone(result['tested_runtime_policy']['effective_agent_seconds'])

    def test_missing_or_wrong_effective_policy_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            verifier = self.fixture(root)
            path = root / 'runtime_policy_effective.json'
            original = json.loads(path.read_text())
            for key, wrong in (('effective_agent_seconds', 900), ('run_id', 'other'),
                               ('config_sha256', 'other'), ('task_files_modified', True)):
                with self.subTest(key=key):
                    path.write_text(json.dumps(dict(original, **{key: wrong})))
                    with self.assertRaises(RuntimeError):
                        verifier.verify_evidence(root, require_committed=False)
            path.unlink()
            with self.assertRaises(FileNotFoundError):
                verifier.verify_evidence(root, require_committed=False)


if __name__ == '__main__':
    unittest.main()
