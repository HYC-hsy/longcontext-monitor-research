"""Exercise the actual native-SHARED hooks with finite container/receipt mocks."""
import asyncio
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.pma_harbor_hooks import NativeSharedTrialHooks, _tree_sha256


class TerminalHandoffTests(unittest.TestCase):
    def test_auxiliary_terminal_unavailability_never_adds_evaluation_gate(self):
        for case in ('normal', 'host_journal_incomplete', 'cat_nonzero',
                     'invalid_json', 'missing_fields', 'identity_conflict'):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                archive, control, tests = (root / name for name in
                                           ('archive', 'control', 'tests'))
                for directory in (archive, control / 'pos_archive', tests,
                                  archive / 'registered_control_processes'):
                    directory.mkdir(parents=True, exist_ok=True)
                (tests / 'test.sh').write_bytes(b'#!/bin/sh\nexit 0\n')
                (control / 'sidecar_stopped.json').write_text(json.dumps({
                    'run_id': 'run', 'clean': True, 'stopped': True}), encoding='utf-8')
                (archive / 'control_process_registry.json').write_text(json.dumps({
                    'run_id': 'run', 'container_id': 'main', 'pid_namespace': 'namespace'}),
                    encoding='utf-8')
                registered = {'pid': 100, 'start_ticks': 5,
                    'argv_sha256': 'fixed', 'kind': 'transport',
                    'run_id': 'run', 'pid_namespace': 'namespace'}
                (archive / 'registered_control_processes/100-5.json').write_text(
                    json.dumps(registered), encoding='utf-8')
                for filename, status in (('events.result.json', 'completed'),
                                         ('events.close.json', 'graceful_exit')):
                    (control / 'pos_archive' / filename).write_text(json.dumps({
                        'run_id': 'run', 'task_id': 'task', 'status': status,
                        'worker_return_code': 0}), encoding='utf-8')
                terminal = {'run_id': 'run', 'task_id': 'task',
                    'result': 'CURRENT_TASK_DONE',
                    'pma_finalization': {'status': 'not_enabled'},
                    'pos_finalization': {'status': 'completed',
                                         'archive_incomplete': case == 'host_journal_incomplete'},
                    'pos_archive_incomplete': case == 'host_journal_incomplete',
                    'pos_auxiliary_errors': ([{'kind': 'terminal', 'error_type': 'OSError'}]
                                             if case == 'host_journal_incomplete' else [])}
                if case == 'missing_fields':
                    del terminal['result']
                if case == 'identity_conflict':
                    terminal['run_id'] = 'another-run'
                raw = 'not-json' if case == 'invalid_json' else json.dumps(terminal)
                async def compose(command):
                    return SimpleNamespace(stdout='gateway\n' if command[:2] ==
                                           ['ps', '-a'] else '')
                async def container_exec(*args, **kwargs):
                    return SimpleNamespace(return_code=1 if case == 'cat_nonzero' else 0,
                                           stdout=raw)
                environment = SimpleNamespace(_run_docker_compose_command=compose,
                                              exec=container_exec)
                hook = object.__new__(NativeSharedTrialHooks)
                hook.archive, hook.control = archive, control
                hook.spec = {'run_id': 'run', 'task_id': 'task', 'condition': 'P',
                    'zero_model_fixture_only': True,
                    'native_tests_tree_sha256': _tree_sha256(tests),
                    'native_test_sh_sha256': hashlib.sha256(
                        (tests / 'test.sh').read_bytes()).hexdigest()}
                hook.container_id = 'main'
                hook._control_namespace = 'namespace'
                hook._control_python = 'python'
                hook.baseline_pids = {'100'}
                hook._finish_control_watch = AsyncMock()
                hook._main_id = AsyncMock(return_value='main')
                hook.trial = SimpleNamespace(agent_environment=environment,
                    result=SimpleNamespace(agent_result=None),
                    task=SimpleNamespace(paths=SimpleNamespace(tests_dir=tests)))
                def docker(args, **kwargs):
                    return SimpleNamespace(returncode=0,
                        stdout=('false\n' if args[1] == 'inspect' else
                                'PID CMD\n100 control\n200 task-service\n'))
                with patch('method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.pma_harbor_hooks.subprocess.run', side_effect=docker), patch(
                    'method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.pma_harbor_hooks.scan_control_processes',
                    return_value={'pid_namespace': 'namespace', 'processes': []}), patch(
                    'method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.pma_harbor_hooks.probe_registered',
                    return_value='exited'):
                    async def run():
                        await hook.agent_end(None)
                        await hook.verification_start(None)
                    if case == 'identity_conflict':
                        with self.assertRaisesRegex(RuntimeError, 'identity conflict'):
                            asyncio.run(run())
                        self.assertFalse((archive / 'verification_released.json').exists())
                        continue
                    asyncio.run(run())
                status = json.loads((archive / 'pos_archive_status.json').read_text())
                self.assertTrue((archive / 'verification_released.json').is_file())
                self.assertEqual(status['task_terminal_status'],
                                 'available' if case in {'normal', 'host_journal_incomplete'}
                                 else 'partial' if case == 'missing_fields'
                                 else 'unavailable')
                self.assertEqual(status['task_result'], 'CURRENT_TASK_DONE' if case in
                                 {'normal', 'host_journal_incomplete'} else None)
                self.assertEqual(status['archive_incomplete'], case != 'normal')
                if case == 'host_journal_incomplete':
                    self.assertEqual(status['auxiliary_errors'],
                                     [{'kind': 'terminal', 'error_type': 'OSError'}])


if __name__ == '__main__':
    unittest.main(verbosity=2)
