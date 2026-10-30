"""Narrow regression for reshard's post-Agent evaluation cache boundary."""

import unittest
import tarfile
from tempfile import TemporaryDirectory
from pathlib import Path

from experiment_runner.evaluation_cache import _archive_index
from experiment_runner.prepared_dependency_cache import (
    ISOLATED_UVX_LAYOUT, ISOLATED_UVX_ROOT, uvx_environment,
    verifier_test_command,
)


class PreparedDependencyUvxIsolationTests(unittest.TestCase):
    def test_isolated_cache_is_not_task_uv_cache(self):
        manifest = {'cache_layout': ISOLATED_UVX_LAYOUT}
        env = uvx_environment(manifest, offline=True)
        self.assertIn('UV_CACHE_DIR=/' + ISOLATED_UVX_ROOT + '/cache', env)
        self.assertIn('UV_PYTHON_INSTALL_DIR=/' + ISOLATED_UVX_ROOT + '/python', env)
        self.assertIn('UV_OFFLINE=1', env)
        self.assertNotIn('/root/.cache/uv', env)

    def test_official_script_bytes_and_shell_redirection_preserved(self):
        command = '(/tests/test.sh) > /logs/verifier/test-stdout.txt 2>&1'
        manifest = {'cache_layout': ISOLATED_UVX_LAYOUT}
        wrapped = verifier_test_command(command, manifest)
        self.assertIn("sh -c '" + command + "'", wrapped)
        self.assertTrue(wrapped.startswith('env HOME=/root '))
        self.assertEqual(verifier_test_command(command, {}), command)

    def test_isolated_archive_root_is_allowed(self):
        with TemporaryDirectory() as temporary:
            archive = Path(temporary) / 'cache.tar'
            with tarfile.open(archive, 'w') as tar:
                entry = tarfile.TarInfo(ISOLATED_UVX_ROOT)
                entry.type = tarfile.DIRTYPE
                entry.mode = 0o755
                tar.addfile(entry)
            with self.assertRaises(Exception):
                _archive_index(archive)
            self.assertIn(ISOLATED_UVX_ROOT,
                          _archive_index(archive, extra_roots=(ISOLATED_UVX_ROOT,)))


if __name__ == '__main__':
    unittest.main()
