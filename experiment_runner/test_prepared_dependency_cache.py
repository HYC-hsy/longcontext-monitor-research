"""Dependency-only cache contract; no model, Task or native verifier run."""

import asyncio
import hashlib
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

from .evaluation_cache import _archive_index
from .prepared_dependency_cache import verify_bundle, restore


class PreparedDependencyCacheTests(unittest.TestCase):
    def test_pinned_bundle_and_offline_restore_order(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            payload = root / 'payload.tar'
            content = root / 'uv'
            content.write_bytes(b'synthetic dependency file')
            with tarfile.open(payload, 'w') as archive:
                archive.add(content, 'root/.local/bin/uv', recursive=False)
            manifest = {
                'schema': 'ga20-apt-uv-dependency-prototype-v1',
                'status': 'clean_container_offline_ready',
                'task': 'sample', 'image_repo_digest': 'sample@sha256:' + 'a' * 64,
                'image_id': 'sha256:' + 'a' * 64,
                'original_test_sha256': 'b' * 64,
                'apt': ['curl'], 'uv_wheels': ['pytest==8.4.1'],
                'payload_sha256': hashlib.sha256(payload.read_bytes()).hexdigest(),
                'files': _archive_index(payload),
            }
            manifest_file = root / 'manifest.json'
            manifest_file.write_text(json.dumps(manifest), encoding='utf-8')
            for name in ('builder.exit.json', 'offline.exit.json'):
                (root / name).write_text('{"exit_code": 0}', encoding='utf-8')
            cache = {'bundle_path': str(root),
                     'manifest_sha256': hashlib.sha256(manifest_file.read_bytes()).hexdigest()}
            self.assertEqual(verify_bundle(cache, task='sample',
                image_digest=manifest['image_repo_digest'], image_id=manifest['image_id'],
                original_sha256='b' * 64, coverage='apt_curl_uvx'), manifest)
            with self.assertRaisesRegex(ValueError, 'identity'):
                verify_bundle(cache, task='wrong', image_digest=manifest['image_repo_digest'],
                              image_id=manifest['image_id'], original_sha256='b' * 64,
                              coverage='apt_curl_uvx')
            commands, uploads, receipts = [], [], []

            async def execute(*, command, **_):
                commands.append(command)
                return type('Result', (), {'return_code': 0})()

            async def upload(*, source_path, target_path):
                uploads.append((source_path, target_path))

            asyncio.run(restore(execute, upload, cache, manifest, receipts.append))
            self.assertEqual(len(uploads), 2)
            self.assertTrue(any('sha256sum -c' in cmd for cmd in commands))
            self.assertTrue(any('UV_OFFLINE=1' in cmd for cmd in commands))
            self.assertTrue(any('dpkg -i' in cmd for cmd in commands))
            self.assertFalse(any('apt-get' in cmd or 'curl ' in cmd for cmd in commands))
            self.assertEqual(receipts[-1]['stage'], 'cache_stage_cleanup')


if __name__ == '__main__':
    unittest.main()
