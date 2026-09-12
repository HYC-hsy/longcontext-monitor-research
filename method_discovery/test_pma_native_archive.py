import asyncio
import hashlib
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest

from pma_native_archive import archive_workspace


class ArchiveTests(unittest.TestCase):
    def test_complete_workspace_and_hash(self):
        commands = []
        class Env:
            async def exec(self, command, **kwargs):
                commands.append(command)
                return NS(return_code=0)
            async def download_file(self, remote, local):
                Path(local).write_bytes(b'complete fixture')
        with tempfile.TemporaryDirectory() as directory:
            result = asyncio.run(archive_workspace(Env(), directory))
            self.assertEqual(result['sha256'], hashlib.sha256(b'complete fixture').hexdigest())
            self.assertIn('-C /app .', commands[0])
            self.assertEqual(result['boundary'], 'agent stopped; before hidden verifier')

    def test_reject_root_archive(self):
        with self.assertRaises(ValueError):
            asyncio.run(archive_workspace(None, '.', '/'))


if __name__ == '__main__':
    unittest.main()
