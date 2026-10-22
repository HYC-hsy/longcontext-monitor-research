"""Dependency-only retry contracts; no benchmark assertion is executed."""

import asyncio
from dataclasses import dataclass
import unittest

from .download_retry import plan, prepare
from .evaluation_bootstrap import BootstrapFailed


UV_SCRIPT = (b'#!/bin/bash\n\n# Install curl\napt-get update\n'
             b'apt-get install -y curl git\n\n# Install uv\n'
             b'curl -LsSf https://astral.sh/uv/0.9.5/install.sh | sh\n\n'
             b'source $HOME/.local/bin/env\n\n# Check directory\n'
             b'uvx \\\n  -p 3.13 \\\n  -w pytest==8.4.1 \\\n'
             b'  -w pytest-json-ctrf==0.3.5 \\\n'
             b'  pytest --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA\n'
             b'if [ $? -eq 0 ]; then echo 1 > /logs/verifier/reward.txt; fi\n')


@dataclass
class Result:
    return_code: int = 0
    stdout: str = 'ok'
    stderr: str = ''


class DownloadRetryTests(unittest.TestCase):
    def test_apt_curl_uvx_keeps_test_and_reward_bytes(self):
        selected = plan(UV_SCRIPT, 3)
        self.assertEqual(selected.coverage, 'apt_curl_uvx')
        suffix = UV_SCRIPT.split(b'source $HOME/.local/bin/env\n', 1)[1]
        self.assertTrue(selected.effective.endswith(suffix))
        self.assertIn('apt-get -o Acquire::Retries=2 install -y curl git',
                      dict(selected.stages)['apt_install'])
        download = dict(selected.stages)['uv_download']
        self.assertIn('--retry 2', download)
        self.assertIn('-o /logs/verifier/download_retry_v1/installer.part', download)
        self.assertNotIn('| sh', download)
        self.assertEqual(sum(name == 'uv_install' for name, _ in selected.stages), 1)
        self.assertIn('UV_HTTP_RETRIES=2', dict(selected.stages)['uv_dependencies'])

    def test_first_download_failure_stops_before_installer_and_tests(self):
        seen, records = [], []
        async def run(*, command, user, timeout_sec):
            seen.append(command)
            return Result(22 if '/installer.part ' in command else 0)
        with self.assertRaises(BootstrapFailed):
            asyncio.run(prepare(run, records.append, plan(UV_SCRIPT, 3).stages))
        self.assertFalse(any(command.startswith('sh /logs/verifier') for command in seen))
        self.assertEqual(records[-1]['stage'], 'uv_download')
        self.assertEqual(records[-1]['status'], 'failed')

    def test_dependency_success_invokes_each_stage_once(self):
        seen = []
        async def run(*, command, user, timeout_sec):
            seen.append(command)
            return Result()
        stages = plan(UV_SCRIPT, 3).stages
        asyncio.run(prepare(run, lambda _: None, stages))
        self.assertEqual(len(seen), len(stages))
        self.assertEqual(sum(command.startswith('sh /logs/verifier') for command in seen), 1)

    def test_pip_packages_and_test_suffix_preserved(self):
        original = (b'#!/bin/bash\n# dependency\npip install pytest==8.4.2 '
                    b'requests==2.32.5 pytest-json-ctrf==0.3.5\n\n'
                    b'pytest --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA\n'
                    b'echo $? > /logs/verifier/reward.txt\n')
        selected = plan(original, 3)
        self.assertEqual(selected.coverage, 'pip')
        self.assertEqual(selected.stages[0][1],
                         'pip install --retries 3 pytest==8.4.2 requests==2.32.5 '
                         'pytest-json-ctrf==0.3.5')
        self.assertTrue(selected.effective.endswith(original.split(b'\n\n', 1)[1]))

    def test_nonstandard_script_is_exact_original_once(self):
        original = b'#!/bin/bash\ncustom-download | sh\npytest /tests/test_outputs.py\n'
        selected = plan(original, 3)
        self.assertEqual(selected.coverage, 'uncovered_original_once')
        self.assertEqual(selected.effective, original)
        self.assertEqual(selected.stages, ())

    def test_no_retry_of_test_or_scoring_command(self):
        for selected in (plan(UV_SCRIPT, 3),):
            self.assertFalse(any('test_outputs.py' in command or 'reward.txt' in command
                                 for _, command in selected.stages))
        with self.assertRaises(ValueError):
            plan(UV_SCRIPT, 0)
        with self.assertRaises(ValueError):
            plan(UV_SCRIPT, True)


if __name__ == '__main__':
    unittest.main()
