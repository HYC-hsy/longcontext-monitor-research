"""Stdlib-only safety/unit tests; not Docker integration or evaluator tests."""
import copy
import hashlib
import asyncio
from types import SimpleNamespace
import json
import os
import shutil
from pathlib import Path
import tarfile
import tempfile
import subprocess
import unittest
from unittest.mock import patch

import evaluation_cache as cache


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.store = self.root / 'store'
        self.identity = dict(protocol=cache.PROTOCOL, task='sqlite-with-gcov',
            original_sha256=cache.ORIGINAL_SHA256, base_image='ubuntu@sha256:' + 'a' * 64,
            os_id='ubuntu', os_version='24.04', architecture='x86_64', python='3.13.9',
            python_executable='/root/.local/share/uv/python/cpython-3.13.9/bin/python3.13',
            versions=cache.VERSIONS.copy())
        for name in (*cache.BIN_FILES, self.identity['python_executable'][1:],
                     'root/.cache/uv/wheels/fake.whl', 'var/cache/evaluation-debs/curl.deb'):
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(('fixture:' + name).encode())
            path.chmod(0o755)
        self.bundle = cache.publish_bundle(self.source, self.store, self.identity)
        self.manifest_sha = hashlib.sha256((self.bundle / 'manifest.json').read_bytes()).hexdigest()

    def test_hit_and_no_overwrite(self):
        original = (self.bundle / 'manifest.json').read_bytes()
        (self.source / cache.BIN_FILES[0]).write_text('new build, same identity')
        self.assertEqual(cache.publish_bundle(self.source, self.store, self.identity), self.bundle)
        self.assertEqual((self.bundle / 'manifest.json').read_bytes(), original)
        cache.verify_bundle(self.bundle, self.identity)

    def test_corrupted_payload(self):
        with open(self.bundle / 'payload.tar', 'ab') as stream:
            stream.write(b'corruption')
        with self.assertRaises(cache.CacheMiss):
            cache.verify_bundle(self.bundle, self.identity)
        with self.assertRaises(cache.CacheMiss):
            cache.publish_bundle(self.source, self.store, self.identity)

    def test_missing_file(self):
        (self.bundle / 'payload.tar').unlink()
        with self.assertRaises(cache.CacheMiss):
            cache.verify_bundle(self.bundle, self.identity)

    def test_wrong_identity(self):
        identity = copy.deepcopy(self.identity)
        identity['architecture'] = 'aarch64'
        with self.assertRaises(cache.CacheMiss):
            cache.verify_bundle(self.bundle, identity)

    def test_mutable_image_rejected(self):
        self.identity['base_image'] = 'ubuntu:24.04'
        with self.assertRaises(cache.CacheMiss):
            cache.validate_identity(self.identity)

    def test_complete_staging_not_hit(self):
        staging = self.store / '.building-interrupted'
        shutil.copytree(self.bundle, staging)
        with self.assertRaises(cache.CacheMiss):
            cache.verify_bundle(staging, self.identity)

    def test_half_published(self):
        (self.bundle / 'COMPLETE').unlink()
        with self.assertRaises(cache.CacheMiss):
            cache.verify_bundle(self.bundle, self.identity)

    def test_missing_payload_entry_even_with_new_inventory(self):
        path = self.source / cache.BIN_FILES[0]
        path.unlink()
        with self.assertRaises(cache.CacheMiss):
            cache.publish_bundle(self.source, self.root / 'new-store', self.identity)

    def test_manifest_change(self):
        manifest = json.loads((self.bundle / 'manifest.json').read_text())
        manifest['files'].pop(cache.BIN_FILES[0])
        self.rewrite_manifest(manifest)
        with self.assertRaises(cache.CacheMiss):
            cache.verify_bundle(self.bundle, self.identity)

    def rewrite_manifest(self, manifest):
        raw = json.dumps(manifest).encode()
        (self.bundle / 'manifest.json').write_bytes(raw)
        (self.bundle / 'COMPLETE').write_text(hashlib.sha256(raw).hexdigest())

    def test_archive_path_and_link_attacks(self):
        cases = [('root/.cache/uv/../../../../tmp/escape', None, None),
                 ('/tmp/escape', None, None), ('root/.cache/uv/link', '/etc/passwd', None),
                 ('root/.cache/uv/link', '../../../../etc', None),
                 ('root/.cache/uv/hard', cache.BIN_FILES[0], tarfile.LNKTYPE)]
        for name, target, kind in cases:
            with self.subTest(name=name, target=target):
                archive = self.root / 'bad.tar'
                with tarfile.open(archive, 'w') as tar:
                    item = tarfile.TarInfo(name)
                    if target:
                        item.type = kind or tarfile.SYMTYPE
                        item.linkname = target
                    tar.addfile(item)
                with self.assertRaises(cache.CacheMiss):
                    cache._archive_index(archive)

    def test_member_under_symlink(self):
        archive = self.root / 'bad.tar'
        with tarfile.open(archive, 'w') as tar:
            for name, target in [('root/.cache/uv/link', '/root/.local/share/uv/python'),
                                 ('root/.cache/uv/link/escape', None)]:
                item = tarfile.TarInfo(name)
                if target:
                    item.type, item.linkname = tarfile.SYMTYPE, target
                tar.addfile(item)
        with self.assertRaises(cache.CacheMiss):
            cache._archive_index(archive)

    def test_destination_ancestor_symlink_no_write(self):
        destination = self.root / 'target'
        destination.mkdir()
        outside = self.root / 'outside'
        outside.mkdir()
        try:
            (destination / 'root').symlink_to(outside, target_is_directory=True)
        except OSError as exc:
            if os.name == 'nt' and getattr(exc, 'winerror', None) == 1314:
                self.skipTest('Windows symlink privilege unavailable')
            raise
        with self.assertRaises(cache.CacheMiss):
            cache.restore_bundle(self.bundle, self.identity, destination)
        self.assertEqual(list(outside.iterdir()), [])

    def test_restore_and_absolute_link_preserved(self):
        python = self.source / self.identity['python_executable'][1:]
        link = python.parent / 'python'
        try:
            link.symlink_to(self.identity['python_executable'])
        except OSError as exc:
            if os.name == 'nt' and getattr(exc, 'winerror', None) == 1314:
                self.skipTest('Windows symlink privilege unavailable')
            raise
        bundle = cache.publish_bundle(self.source, self.root / 'linked-store', self.identity)
        destination = self.root / 'target'
        destination.mkdir()
        cache.restore_bundle(bundle, self.identity, destination)
        self.assertEqual(os.readlink(destination / link.relative_to(self.source)), self.identity['python_executable'])
        for name in cache.BIN_FILES:
            self.assertEqual((destination / name).read_bytes(), (self.source / name).read_bytes())

    def test_hardlinked_source_stored_as_files(self):
        os.link(self.source / 'root/.cache/uv/wheels/fake.whl', self.source / 'root/.cache/uv/copy.whl')
        bundle = cache.publish_bundle(self.source, self.root / 'linked-store', self.identity)
        manifest = cache.verify_bundle(bundle, self.identity)
        self.assertEqual(manifest['files']['root/.cache/uv/copy.whl']['type'], 'file')

    def test_failure_before_publish_never_hits(self):
        with patch.object(cache, '_archive_index', side_effect=cache.CacheMiss('injected')):
            with self.assertRaises(cache.CacheMiss):
                cache.publish_bundle(self.source, self.root / 'crash-store', self.identity)
        self.assertEqual(list((self.root / 'crash-store').iterdir()), [])

    def test_destination_hardlink_no_write(self):
        destination = self.root / 'target'
        path = destination / cache.BIN_FILES[0]
        path.parent.mkdir(parents=True)
        protected = self.root / 'task-artifact'
        protected.write_text('do not change')
        os.link(protected, path)
        with self.assertRaises(cache.CacheMiss):
            cache.restore_bundle(self.bundle, self.identity, destination)
        self.assertEqual(protected.read_text(), 'do not change')

    def mark_fixture_ready(self):
        receipt = {'manifest_sha256': self.manifest_sha,
            'payload_sha256': cache._sha(self.bundle / 'payload.tar'),
            'acceptance': 'clean-docker-network-none-v1'}
        (self.bundle / 'OFFLINE_READY.json').write_text(json.dumps(receipt))

    def test_prepare_root_upload_and_bundled_python(self):
        self.mark_fixture_ready()
        calls, uploads, records = [], [], []
        async def execute(**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(return_code=0, stderr='', stdout='')
        async def upload(**kwargs):
            uploads.append(kwargs)
        asyncio.run(cache.prepare_cached(execute, upload, self.bundle, self.identity, records.append, expected_manifest_sha256=self.manifest_sha))
        self.assertEqual(len(uploads), 4)
        self.assertEqual(len(calls), 3)
        self.assertTrue(all(c['user'] == 'root' for c in calls))
        self.assertIn('/bootstrap' + self.identity['python_executable'], calls[1]['command'])
        self.assertIn('sha256sum -c', calls[1]['command'])
        self.assertNotIn('apt-get', calls[1]['command'])
        self.assertNotIn('/tests', calls[1]['command'])

    def test_unaccepted_bundle_fails_before_exec(self):
        async def forbidden(**kwargs):
            self.fail('must reject before invoking container')
        with self.assertRaisesRegex(cache.CacheMiss, 'acceptance'):
            asyncio.run(cache.prepare_cached(forbidden, forbidden, self.bundle,
                self.identity, lambda row: None, expected_manifest_sha256=self.manifest_sha))

    def test_frozen_manifest_mismatch(self):
        self.mark_fixture_ready()
        with self.assertRaisesRegex(cache.CacheMiss, 'frozen manifest'):
            cache.require_offline_ready(self.bundle, 'b' * 64)

    def test_cleanup_failure_does_not_hide_restore_error(self):
        self.mark_fixture_ready()
        calls, records = [], []
        async def execute(**kwargs):
            calls.append(kwargs)
            failed = len(calls) > 1
            return SimpleNamespace(return_code=1 if failed else 0, stderr='failure', stdout='')
        async def upload(**kwargs):
            pass
        with self.assertRaisesRegex(cache.CacheMiss, 'cache_restore_offline_check'):
            asyncio.run(cache.prepare_cached(execute, upload, self.bundle,
                self.identity, records.append, expected_manifest_sha256=self.manifest_sha))
        self.assertEqual(len(calls), 3)
        self.assertTrue(any(r.get('status') == 'failed' and r['stage'] == 'cache_stage_cleanup' for r in records))

    def test_unlisted_destination_deb_fails_before_any_write(self):
        destination = self.root / 'target'
        extra = destination / 'var/cache/evaluation-debs/not-in-manifest.deb'
        extra.parent.mkdir(parents=True)
        extra.write_text('must never execute or delete')
        with self.assertRaisesRegex(cache.CacheMiss, 'unlisted destination'):
            cache.restore_bundle(self.bundle, self.identity, destination)
        self.assertEqual(extra.read_text(), 'must never execute or delete')
        self.assertFalse((destination / cache.BIN_FILES[0]).exists())

    def test_install_only_manifest_debs(self):
        manifest = cache.verify_bundle(self.bundle, self.identity)
        with patch.object(cache.subprocess, 'run') as run:
            cache.install_manifest_debs(manifest)
        self.assertEqual(run.call_args.args[0], ['dpkg', '-i', '/var/cache/evaluation-debs/curl.deb'])
        self.assertFalse(run.call_args.kwargs['shell'])

    def test_cross_platform_build_uses_only_docker_no_host_shell(self):
        def fake_run(command, **kwargs):
            self.assertFalse(kwargs['shell'])
            self.assertEqual(command[0], 'docker')
            if '--network' not in command:
                self.assertIn('/builder/build.sh', command)
                mounted = next(item.split(':/builder/build.sh:ro')[0] for item in command
                    if item.endswith(':/builder/build.sh:ro'))
                self.assertNotIn(b'\r', Path(mounted).read_bytes())
                return SimpleNamespace(stdout='BUNDLE=/output/' + self.bundle.name + '\n')
            self.assertIn('none', command)
            self.assertIn('/bin/bash', command)  # container entrypoint, not host
            self.assertFalse((self.bundle / 'OFFLINE_READY.json').exists())
            return SimpleNamespace(returncode=0)
        with patch.object(cache.subprocess, 'run', side_effect=fake_run) as run:
            result = cache.build_bundle(self.store, self.identity['base_image'])
        self.assertEqual(run.call_count, 2)
        self.assertEqual(result, self.bundle)
        cache.require_offline_ready(result, self.manifest_sha)

    def test_failed_clean_container_leaves_bundle_unready(self):
        def fake_run(command, **kwargs):
            if '--network' in command:
                raise subprocess.CalledProcessError(1, command)
            return SimpleNamespace(stdout='BUNDLE=/output/' + self.bundle.name + '\n')
        with patch.object(cache.subprocess, 'run', side_effect=fake_run):
            with self.assertRaises(subprocess.CalledProcessError):
                cache.build_bundle(self.store, self.identity['base_image'])
        with self.assertRaisesRegex(cache.CacheMiss, 'acceptance'):
            cache.require_offline_ready(self.bundle, self.manifest_sha)

    def test_build_mutable_base_never_calls_docker(self):
        with patch.object(cache.subprocess, 'run') as run:
            with self.assertRaises(cache.CacheMiss):
                cache.build_bundle(self.store, 'ubuntu:24.04')
        run.assert_not_called()

    def test_unlisted_tests_not_packaged(self):
        tests = self.source / 'tests'
        tests.mkdir()
        (tests / 'test.sh').write_text('must not package')
        bundle = cache.publish_bundle(self.source, self.root / 'clean-store', self.identity)
        self.assertFalse(any(n.startswith('tests') for n in cache.verify_bundle(bundle, self.identity)['files']))


if __name__ == '__main__':
    unittest.main()
