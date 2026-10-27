"""Exact-byte checkout and simulated Windows paths; no model/profile access."""
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from pma_evidence_review.benchmark import core
from pma_evidence_review.tests.no_network import install_guard


REPO = Path(__file__).resolve().parents[2]
DATA = Path('pma_evidence_review/benchmark/candidate_data')
PIN = 'dcadeb1fabe2c2518307e8763ea5f6118688027394e514b575ce07d4fe482928'
NAMES = ('MANIFEST.json', 'cases.json', 'evaluation-only.json', 'inventory.json', 'requests.json')


class BenchmarkPortabilityTests(unittest.TestCase):
    def setUp(self):
        install_guard(self)

    def test_windows_path_git_object_and_provenance_are_posix(self):
        relative = PureWindowsPath(core.ROOT/'INDEX.json')
        self.assertIn('\\', str(relative))
        with patch.object(core.subprocess, 'check_output', wraps=subprocess.check_output) as git:
            record = core.checked_file(REPO, relative)
        self.assertEqual(git.call_args.args[0],
                         ['git', 'show', core.SOURCE_COMMIT+':'+relative.as_posix()])
        self.assertEqual(record['path'], relative.as_posix())

    def test_writer_uses_utf8_lf_even_with_windows_text_default(self):
        native_open = Path.open

        def windows_open(path, mode='r', *args, **kwargs):
            if 'b' not in mode:
                kwargs.setdefault('newline', '\r\n')
            return native_open(path, mode, *args, **kwargs)

        value = {'text': '中文\nverbatim'}
        expected = (json.dumps(value, ensure_ascii=False, indent=2)+'\n').encode('utf-8')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'data.json'
            with patch.object(Path, 'open', new=windows_open):
                core.write(path, value)
            self.assertEqual(path.read_bytes(), expected)
            with self.assertRaises(FileExistsError):
                core.write(path, value)

    def test_newline_tampering_is_still_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in NAMES:
                shutil.copyfile(REPO/DATA/name, root/name)
            original = (root/'MANIFEST.json').read_bytes()
            (root/'MANIFEST.json').write_bytes(original.replace(b'\n', b'\r\n'))
            with self.assertRaisesRegex(ValueError, 'frozen_manifest_mismatch'):
                core.load_dataset(root, PIN)
            (root/'MANIFEST.json').write_bytes(original)
            path = root/'cases.json'
            path.write_bytes(path.read_bytes().replace(b'\n', b'\r\n'))
            with self.assertRaisesRegex(ValueError, 'manifest_hash'):
                core.load_dataset(root, PIN)
            relative = core.ROOT/'INDEX.json'
            path = root/relative
            path.parent.mkdir(parents=True)
            raw = (REPO/relative).read_bytes()
            path.write_bytes(raw.replace(b'\n', b'\r\n'))
            with patch.object(core.subprocess, 'check_output', return_value=raw):
                with self.assertRaisesRegex(ValueError, 'public_commit_file_mismatch'):
                    core.checked_file(root, relative)

    def test_autocrlf_fresh_checkout_and_windows_rebuild_match_frozen_bytes(self):
        # A tiny local Git repository borrows the original object database read-only
        # so SOURCE_COMMIT stays real, without fetching or copying the full history.
        audit = json.loads((REPO/DATA/'inventory.json').read_text(encoding='utf-8'))
        assets = [Path(row['path']) for row in audit['files']]
        assets += [DATA/name for name in NAMES]
        paths = set(assets)
        for path in assets:
            for parent in path.parents:
                attributes = parent/'.gitattributes'
                if (REPO/attributes).is_file():
                    paths.add(attributes)
        specs = json.loads((REPO/'pma_evidence_review/benchmark/specs.json').read_text(encoding='utf-8'))
        env = {**os.environ, 'GIT_NO_LAZY_FETCH': '1', 'GIT_TERMINAL_PROMPT': '0'}

        def git(repo, *args):
            return subprocess.check_output(['git', '-c', 'core.hooksPath=',
                '-c', 'commit.gpgsign=false', '-C', str(repo), *args],
                env=env, stderr=subprocess.STDOUT)

        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory)/'origin'
            fixture.mkdir()
            git(fixture, 'init')
            objects = Path(git(REPO, 'rev-parse', '--git-path', 'objects').decode().strip())
            if not objects.is_absolute():
                objects = REPO/objects
            (fixture/'.git/objects/info/alternates').write_bytes(
                (objects.resolve().as_posix()+'\n').encode('utf-8'))
            for relative in paths:
                target = fixture/relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((REPO/relative).read_bytes())
            (fixture/'unprotected.txt').write_bytes(b'checkout control\n')
            git(fixture, '-c', 'core.autocrlf=false', 'add', '.')
            git(fixture, '-c', 'user.name=Offline Fixture', '-c', 'user.email=fixture.invalid@example.invalid',
                'commit', '-m', 'Exact-byte checkout fixture')
            checkout = Path(directory)/'checkout'
            git(fixture, 'clone', '--shared', '--no-checkout', str(fixture), str(checkout))
            git(checkout, 'config', '--local', 'core.autocrlf', 'true')
            git(checkout, 'checkout', '--detach', 'HEAD')
            self.assertEqual((checkout/'unprotected.txt').read_bytes(), b'checkout control\r\n')
            for relative in assets:
                self.assertEqual((checkout/relative).read_bytes(), (REPO/relative).read_bytes(),
                                 relative.as_posix())
            self.assertEqual(hashlib.sha256((checkout/DATA/'MANIFEST.json').read_bytes()).hexdigest(), PIN)
            self.assertEqual(len(core.load_dataset(checkout/DATA, PIN)['cases.json']), 29)
            rebuilt = Path(directory)/'rebuilt'
            # PureWindowsPath reproduces backslash str() behavior on every OS;
            # local filesystem access still uses native Path throughout.
            with patch.object(core, 'ROOT', PureWindowsPath(core.ROOT)):
                core.build(checkout, specs, rebuilt)
            for name in NAMES:
                self.assertEqual((rebuilt/name).read_bytes(), (REPO/DATA/name).read_bytes(), name)
            self.assertEqual(len(core.load_dataset(rebuilt, PIN)['cases.json']), 29)
