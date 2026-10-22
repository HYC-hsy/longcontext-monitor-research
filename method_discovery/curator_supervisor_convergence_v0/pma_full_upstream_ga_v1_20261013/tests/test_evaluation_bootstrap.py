"""No official task test is run by these evaluator-preparation checks."""

import asyncio
import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013 import evaluation_bootstrap as boot
from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.native_shared_verifier import NativeSharedVerifier
from harbor.verifier.verifier import Verifier


class BootstrapContractTests(unittest.TestCase):
    def test_exact_split_preserves_test_suffix(self):
        original = boot.PREPARATION_PREFIX + boot.TEST_BOUNDARY + b'echo synthetic-sentinel\nexit 3\n'
        with patch.object(boot, 'ORIGINAL_SHA256', hashlib.sha256(original).hexdigest()):
            effective = boot.effective_script(original, task=boot.TASK)
            self.assertEqual(effective, boot.EFFECTIVE_HEADER + original[len(boot.PREPARATION_PREFIX):])
            self.assertEqual(effective.count(b'synthetic-sentinel'), 1)
            with self.assertRaises(boot.BootstrapFailed):
                boot.effective_script(original + b'changed', task=boot.TASK)
            with self.assertRaises(boot.BootstrapFailed):
                boot.effective_script(original, task='other-task')

    def test_retry_and_offline_boundary_are_explicit(self):
        commands = dict(boot.commands())
        self.assertIn('Acquire::Retries=3', commands['apt_update'])
        self.assertIn('APT::Update::Error-Mode=any', commands['apt_update'])
        self.assertIn('Acquire::Retries=3', commands['apt_install'])
        self.assertIn('--retry 3', commands['uv_install'])
        self.assertIn('pipefail', commands['uv_install'])
        self.assertIn('pytest==8.4.1', commands['dependency_versions'])
        self.assertIn('pytest-json-ctrf==0.3.5', commands['dependency_versions'])
        self.assertNotIn(b'apt-get', boot.EFFECTIVE_HEADER)
        self.assertIn(b'UV_OFFLINE=1', boot.EFFECTIVE_HEADER)


class BootstrapFailureTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_stages_once_and_no_test_entry(self):
        calls, events = [], []
        async def execute(*, command, user, timeout_sec):
            calls.append(command)
            if 'uvx --version' in command:
                output = 'uvx 0.9.5'
            elif 'python -c' in command:
                output = '8.4.1\n0.3.5'
            else:
                output = 'prepared'
            return SimpleNamespace(return_code=0, stdout=output, stderr='')
        await boot.prepare(execute, events.append)
        self.assertEqual(len(calls), len(boot.commands()))
        self.assertTrue(all(event['status'] == 'complete' for event in events[1::2]))
        self.assertFalse(any('/tests/test_outputs.py' in command for command in calls))

    async def test_first_transient_download_is_handled_inside_finite_apt_invocation(self):
        calls, events = [], []
        async def execute(*, command, user, timeout_sec):
            calls.append(command)
            # The host invokes APT once. Its own bounded file retry recovers a 502.
            return SimpleNamespace(return_code=0,
                stdout='HTTP 502 on first file attempt; retry succeeded\nuvx 0.9.5\n8.4.1\n0.3.5',
                stderr='')
        await boot.prepare(execute, events.append)
        self.assertEqual(len(calls), len(boot.commands()))
        self.assertEqual(events[-1]['status'], 'complete')

    async def test_continuous_download_failure_stops_before_tests(self):
        for failed_stage in ('apt_update', 'apt_install', 'curl_version',
                             'uv_install', 'dependency_versions', 'plugin_contract'):
            with self.subTest(stage=failed_stage):
                calls, events = [], []
                async def execute(*, command, user, timeout_sec):
                    stage = boot.commands()[len(calls)][0]
                    calls.append(command)
                    return SimpleNamespace(return_code=22 if stage == failed_stage else 0,
                        stdout='uvx 0.9.5\n8.4.1\n0.3.5', stderr='HTTP 502')
                with self.assertRaises(boot.BootstrapFailed) as caught:
                    await boot.prepare(execute, events.append)
                self.assertEqual(caught.exception.stage, failed_stage)
                self.assertEqual(len(calls), [name for name, _ in boot.commands()].index(failed_stage) + 1)
                self.assertFalse(any('/tests/test_outputs.py' in command for command in calls))

    async def test_wrong_dependency_versions_fail_closed(self):
        events = []
        async def execute(*, command, user, timeout_sec):
            return SimpleNamespace(return_code=0,
                stdout='uvx 0.9.5' if 'uvx --version' in command else '8.4.2\n0.3.5',
                stderr='')
        with self.assertRaises(boot.BootstrapFailed) as caught:
            await boot.prepare(execute, events.append)
        self.assertEqual(caught.exception.stage, 'dependency_versions')

    async def test_signature_or_cache_integrity_error_is_not_bypassed(self):
        for failed_stage in ('apt_update', 'dependency_versions'):
            with self.subTest(stage=failed_stage):
                calls = []
                async def execute(*, command, user, timeout_sec):
                    stage = boot.commands()[len(calls)][0]
                    calls.append(stage)
                    return SimpleNamespace(return_code=100 if stage == failed_stage else 0,
                        stdout='uvx 0.9.5\n8.4.1\n0.3.5',
                        stderr='signature/hash mismatch' if stage == failed_stage else '')
                with self.assertRaises(boot.BootstrapFailed):
                    await boot.prepare(execute, lambda _row: None)
                self.assertEqual(calls[-1], failed_stage)


class VerifierBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def _exercise(self, *, protocol='bootstrap_retry_v1', fail_stage=None,
                        make_report=True, stale_report=False, assertion_failure=False,
                        raise_after_start=False):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive, tests, verifier_dir = (root / name for name in ('archive', 'tests', 'verifier'))
            for directory in (archive, tests, verifier_dir):
                directory.mkdir()
            original = boot.PREPARATION_PREFIX + boot.TEST_BOUNDARY + b'echo synthetic-only\n'
            script = tests / 'test.sh'
            script.write_bytes(original)
            sha = hashlib.sha256(original).hexdigest()
            spec = {'run_id': 'synthetic-1', 'task_id': boot.TASK,
                    'archive_root': str(archive), 'evaluation_protocol': 'official_shared_v2',
                    'evaluation_bootstrap_protocol': protocol,
                    'official_source_git_commit': 'synthetic-test-identity',
                    'official_evaluator_files': [{'relative': 'tests/test.sh', 'sha256': sha}],
                    'expected_native_reports': ['/logs/verifier/ctrf.json']}
            spec_path = root / 'spec.json'
            spec_path.write_text(json.dumps(spec), encoding='utf-8')
            (archive / 'agent_end_native.json').write_text(json.dumps({
                'run_id': spec['run_id'], 'container_id': 'synthetic-container',
                'writers_stopped': True}), encoding='utf-8')
            if stale_report:
                (verifier_dir / 'ctrf.json').write_text('old', encoding='utf-8')
            executed, uploaded = [], []
            async def execute(command, **kwargs):
                executed.append(command)
                if 'find tests -type f' in command:
                    return SimpleNamespace(return_code=0, stdout=f'{sha}  tests/test.sh\n', stderr='')
                if 'test ! -e /logs/verifier/ctrf.json' in command:
                    return SimpleNamespace(return_code=1 if stale_report else 0,
                                           stdout='', stderr='')
                if 'sha256sum /logs/verifier/bootstrap_retry_v1/test.sh' in command:
                    digest = hashlib.sha256(uploaded[-1]).hexdigest()
                    return SimpleNamespace(return_code=0, stdout=digest + '  test.sh\n', stderr='')
                stage = next((name for name, value in boot.commands() if value == command), None)
                if fail_stage is not None and stage == fail_stage:
                    return SimpleNamespace(return_code=22, stdout='', stderr='HTTP 502')
                text = ('uvx 0.9.5' if stage == 'uv_version' else
                        '8.4.1\n0.3.5' if stage == 'dependency_versions' else 'prepared')
                return SimpleNamespace(return_code=0, stdout=text, stderr='')
            async def upload_file(*, source_path, target_path):
                uploaded.append(Path(source_path).read_bytes())
            async def upload_dir(*, source_dir, target_dir):
                return None
            async def fake_super(self):
                await self.environment.exec(command='(/tests/test.sh) > /logs/verifier/test-stdout.txt 2>&1')
                if raise_after_start:
                    raise RuntimeError('synthetic verifier transport interrupted')
                if make_report:
                    (verifier_dir / 'ctrf.json').write_text(json.dumps({'results': {
                        'tests': [{'name': 'synthetic'}],
                        'summary': {'tests': 1, 'passed': 0 if assertion_failure else 1,
                                    'failed': 1 if assertion_failure else 0,
                                    'skipped': 0, 'pending': 0, 'other': 0}}}),
                        encoding='utf-8')
                return 'synthetic-result'
            obj = NativeSharedVerifier.__new__(NativeSharedVerifier)
            obj.environment = SimpleNamespace(os='synthetic', exec=execute,
                                              upload_file=upload_file, upload_dir=upload_dir)
            obj.task = SimpleNamespace(paths=SimpleNamespace(test_path_for=lambda _os: script))
            obj.trial_paths = SimpleNamespace(verifier_dir=verifier_dir)
            with (patch.dict(os.environ, PMA_HARBOR_SPEC=str(spec_path)),
                  patch.object(NativeSharedVerifier, '_resolve_tests', return_value=([tests], tests, script)),
                  patch('method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.native_shared_verifier.EnvironmentPaths.for_os',
                        return_value=SimpleNamespace(tests_dir='/tests')),
                  patch.object(Verifier, 'verify', fake_super),
                  patch.object(boot, 'ORIGINAL_SHA256', sha),
                  patch('method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.native_shared_verifier.effective_script',
                        side_effect=lambda data, task: boot.effective_script(data, task=task))):
                error = None
                try:
                    result = await obj.verify()
                except Exception as exc:
                    error = exc
                    result = None
            receipt = (json.loads((archive / 'bootstrap_retry_v1.json').read_text())
                       if (archive / 'bootstrap_retry_v1.json').exists() else None)
            return result, error, receipt, executed, uploaded

    async def test_success_starts_exactly_one_test_after_preparation(self):
        result, error, receipt, executed, uploaded = await self._exercise()
        self.assertIsNone(error)
        self.assertEqual(result, 'synthetic-result')
        self.assertEqual(receipt['status'], 'evaluation_completed')
        self.assertEqual(receipt['test_starts'], 1)
        self.assertEqual(len(uploaded), 1)
        self.assertEqual(sum('/logs/verifier/test-stdout.txt' in command for command in executed), 1)

    async def test_bootstrap_failure_never_starts_test(self):
        _, error, receipt, executed, _ = await self._exercise(fail_stage='apt_install')
        self.assertIsInstance(error, boot.BootstrapFailed)
        self.assertEqual(receipt['status'], 'bootstrap_failed')
        self.assertEqual(receipt['test_starts'], 0)
        self.assertFalse(any('test-stdout.txt' in command for command in executed))

    async def test_started_without_report_is_unavailable(self):
        _, error, receipt, _, _ = await self._exercise(make_report=False)
        self.assertIsInstance(error, RuntimeError)
        self.assertEqual(receipt['status'], 'reports_missing')
        self.assertEqual(receipt['test_starts'], 1)

    async def test_interrupted_test_start_records_missing_report(self):
        _, error, receipt, _, _ = await self._exercise(raise_after_start=True)
        self.assertIsInstance(error, RuntimeError)
        self.assertEqual(receipt['status'], 'reports_missing')
        self.assertEqual(receipt['test_starts'], 1)

    async def test_test_assertion_failure_is_not_bootstrap_failure(self):
        result, error, receipt, _, _ = await self._exercise(assertion_failure=True)
        self.assertIsNone(error)
        self.assertEqual(result, 'synthetic-result')
        self.assertEqual(receipt['status'], 'evaluation_completed')

    async def test_stale_report_rejected_before_preparation(self):
        _, error, receipt, executed, _ = await self._exercise(stale_report=True)
        self.assertIsInstance(error, RuntimeError)
        self.assertIsNone(receipt)
        self.assertFalse(any('apt-get' in command for command in executed))

    async def test_original_protocol_uses_original_test_entry(self):
        result, error, receipt, executed, uploaded = await self._exercise(protocol='original')
        self.assertIsNone(error)
        self.assertEqual(result, 'synthetic-result')
        self.assertIsNone(receipt)
        self.assertFalse(uploaded)
        self.assertTrue(any('/tests/test.sh' in command for command in executed))


if __name__ == '__main__':
    unittest.main()
