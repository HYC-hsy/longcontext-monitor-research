"""Host verifier boundary tests with synthetic commands, never task assertions."""

import asyncio
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from harbor.verifier.verifier import Verifier

from .native_shared_verifier import NativeSharedVerifier
from .test_download_retry import Result, UV_SCRIPT


class FakeEnvironment:
    os = 'linux'

    def __init__(self, original, effective, fail_stage=None):
        self.original, self.effective = original, effective
        self.fail_stage = fail_stage
        self.commands = []
        self.uploaded = []

    async def upload_dir(self, **kwargs):
        self.uploaded.append(('dir', kwargs))

    async def upload_file(self, **kwargs):
        self.uploaded.append(('file', kwargs))

    async def exec(self, command, **kwargs):
        self.commands.append(command)
        if 'find tests -type f' in command:
            return Result(stdout=hashlib.sha256(self.original).hexdigest() + '  tests/test.sh\n')
        if command.startswith('sha256sum /logs/verifier/'):
            return Result(stdout=hashlib.sha256(self.effective).hexdigest() +
                          '  /logs/verifier/download_retry_v1/test.sh\n')
        if self.fail_stage == 'uv_download' and '/installer.part ' in command:
            return Result(return_code=22, stdout='', stderr='HTTP 502')
        return Result()


class NativeDownloadBoundaryTests(unittest.TestCase):
    def _run(self, fail_stage=None):
        from .download_retry import plan
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / 'archive'
            archive.mkdir()
            script = root / 'test.sh'
            script.write_bytes(UV_SCRIPT)
            (archive / 'agent_end_native.json').write_text(json.dumps({
                'run_id': 'synthetic-run', 'writers_stopped': True,
                'container_id': 'synthetic-container'}))
            verifier_dir = root / 'verifier'
            verifier_dir.mkdir()
            spec = {'evaluation_protocol': 'official_shared_v2',
                    'evaluation_bootstrap_protocol': 'download_retry_v1',
                    'evaluation_download_retry': {'max_attempts': 3},
                    'run_id': 'synthetic-run', 'task_id': 'synthetic-task',
                    'archive_root': str(archive),
                    'official_source_git_commit': 'synthetic-commit',
                    'official_evaluator_files': [{'relative': 'tests/test.sh',
                        'sha256': hashlib.sha256(UV_SCRIPT).hexdigest()}],
                    'expected_native_reports': ['/logs/verifier/ctrf.json']}
            spec_file = root / 'spec.json'
            spec_file.write_text(json.dumps(spec))
            env = FakeEnvironment(UV_SCRIPT, plan(UV_SCRIPT, 3).effective, fail_stage)
            verifier = object.__new__(NativeSharedVerifier)
            verifier.environment = env
            verifier.task = SimpleNamespace(paths=SimpleNamespace(
                test_path_for=lambda _: script))
            verifier.trial_paths = SimpleNamespace(verifier_dir=verifier_dir)
            started = []

            async def synthetic_super(instance):
                started.append(True)
                await instance.environment.exec(
                    command='cd /logs/verifier/ && bash /tests/test.sh',
                    user='root', timeout_sec=60)
                (verifier_dir / 'ctrf.json').write_text(json.dumps({'results': {
                    'tests': [{'name': 'synthetic'}],
                    'summary': {'tests': 1, 'passed': 1, 'failed': 0,
                                'skipped': 0, 'pending': 0, 'other': 0}}}))
                return {'synthetic': True}

            with patch.dict(os.environ, {'PMA_HARBOR_SPEC': str(spec_file)}), patch.object(
                    NativeSharedVerifier, '_resolve_tests', return_value=([root], None, None)), patch.object(
                    Verifier, 'verify', synthetic_super):
                if fail_stage:
                    with self.assertRaisesRegex(Exception, 'uv_download'):
                        asyncio.run(verifier.verify())
                else:
                    asyncio.run(verifier.verify())
            receipt = json.loads((archive / 'download_retry_v1.json').read_text())
            return started, receipt, env.commands

    def test_download_failure_never_starts_test_entry(self):
        started, receipt, commands = self._run('uv_download')
        self.assertEqual(started, [])
        self.assertEqual(receipt['status'], 'bootstrap_failed')
        self.assertEqual(receipt['test_starts'], 0)
        self.assertFalse(any('bash /tests/test.sh' in command for command in commands))

    def test_success_starts_exactly_one_test_entry(self):
        started, receipt, commands = self._run()
        self.assertEqual(started, [True])
        self.assertEqual(receipt['status'], 'evaluation_completed')
        self.assertEqual(receipt['test_starts'], 1)
        self.assertEqual(receipt['coverage'], 'apt_curl_uvx')
        self.assertEqual(sum('bash /tests/test.sh' in command for command in commands), 0)
        self.assertEqual(sum('bash /logs/verifier/download_retry_v1/test.sh' in command
                             for command in commands), 1)


if __name__ == '__main__':
    unittest.main()
