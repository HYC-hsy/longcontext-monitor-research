"""Zero-model, zero-Docker tests for the additive reuse planner."""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from experiment_runner import runtime_reuse as reuse

PROMPT = '''from upstream import PHASE2_SYSTEM
MAINTENANCE = "maintain"
ATTENTION = "attend"
PHASE2_REPLACEMENTS = (("old-a", "new-a"), ("old-b", "new-b"))
def phase2_system():
    text = PHASE2_SYSTEM
    for old, new in PHASE2_REPLACEMENTS:
        text = text.replace(old, new, 1)
    return text + ATTENTION
'''


def entry(text, mode='100644'):
    data = text.encode()
    return {'sha256': reuse.digest(data), 'data': data, 'mode': mode}


def sources(prompt=PROMPT):
    return {reuse.PROMPT_PATH: entry(prompt), 'runner.py': entry('run()'),
            'config.json': entry('{"timeout": 10}'), 'README.md': entry('docs')}


def compare(before, after, **kwargs):
    return reuse.compare_sources(before, after, baseline_config={'timeout': 10},
                                 current_config={'timeout': 10}, **kwargs)


class PromptReuseTests(unittest.TestCase):
    def test_prompt_literals_only(self):
        after = sources(PROMPT.replace('"maintain"', '"maintain better"')
                        .replace('"new-a"', '"new words"'))
        plan = compare(sources(), after)
        self.assertEqual(plan['classification'], 'prompt_text_only')
        self.assertFalse(plan['full_check_required'])
        self.assertNotEqual(plan['baseline']['source_fingerprint'],
                            plan['current']['source_fingerprint'])
        self.assertNotEqual(plan['baseline']['prompt_fingerprint'],
                            plan['current']['prompt_fingerprint'])
        self.assertEqual(plan['baseline']['runtime_fingerprint'],
                         plan['current']['runtime_fingerprint'])
        self.assertFalse(plan['proof_verified'])
        self.assertFalse(plan['execution_authorized'])
        self.assertIn('short_prompt_contract_tests', plan['required_checks'])
        for gate in reuse.ALWAYS_REQUIRED:
            self.assertIn(gate, plan['required_checks'])

    def test_executable_changes_require_full_chain(self):
        variants = [
            PROMPT + '\nimport os\n',
            PROMPT.replace('return text + ATTENTION', 'return text'),
            PROMPT.replace('text.replace', 'text.removeprefix'),
            PROMPT.replace('new, 1', 'new, 2'),
            PROMPT.replace('"maintain"', '"maintain" + " extra"'),
            PROMPT.replace('"maintain"', 'str("maintain")'),
            PROMPT.replace('"maintain"', 'f"maintain {x}"'),
            PROMPT.replace('(("old-a", "new-a"), ("old-b", "new-b"))',
                           '(("old-b", "new-b"), ("old-a", "new-a"))'),
            PROMPT.replace('(("old-a", "new-a"), ("old-b", "new-b"))',
                           '[("old-a", "new-a"), ("old-b", "new-b")]'),
            PROMPT.replace('"old-a"', '"different search key"'),
            PROMPT + '\nTOOL_SCHEMA = {"tool": "new"}\n',
            PROMPT + '\nMAINTENANCE = "again"\n',
            PROMPT.replace('ATTENTION = "attend"', ''),
        ]
        for text in variants:
            with self.subTest(text=text):
                plan = compare(sources(), sources(text))
                self.assertTrue(plan['full_check_required'])
                self.assertEqual(plan['classification'], 'runtime_changed')

    def test_unknown_file_add_remove_modify_is_closed(self):
        before = sources()
        for path in ['plugin.py', 'runtime.json', 'unknown.md', 'settings.yaml']:
            after = copy.deepcopy(before)
            after[path] = entry('anything')
            with self.subTest(path=path):
                self.assertTrue(compare(before, after)['full_check_required'])
                self.assertTrue(compare(after, before)['full_check_required'])
        after = sources()
        after['runner.py'] = entry('run_differently()')
        self.assertTrue(compare(before, after)['full_check_required'])

    def test_json_never_blanket_ignored(self):
        after = sources()
        after['config.json'] = entry('{"timeout": 20}')
        self.assertTrue(compare(sources(), after)['full_check_required'])

    def test_config_and_authorization_never_exempt(self):
        plan = reuse.compare_sources(sources(), sources(),
                    baseline_config={'timeout': 10}, current_config={'timeout': 20})
        self.assertEqual(plan['classification'], 'config_changed')
        self.assertTrue(plan['full_check_required'])
        self.assertFalse(plan['execution_authorized'])
        self.assertIn('one_use_authorization', plan['required_checks'])

    def test_explicit_known_document_does_not_invalidate_runtime(self):
        after = sources()
        after['README.md'] = entry('updated docs')
        self.assertTrue(compare(sources(), after)['full_check_required'])
        plan = compare(sources(), after, non_runtime_paths=['README.md'])
        self.assertFalse(plan['full_check_required'])
        self.assertEqual(plan['classification'], 'non_runtime_only')
        self.assertNotEqual(plan['baseline']['source_fingerprint'],
                            plan['current']['source_fingerprint'])

    def test_new_reviewed_document_is_reusable_but_not_new_code(self):
        after = sources()
        after['NEW_GUIDE.md'] = entry('reviewed guide')
        self.assertTrue(compare(sources(), after)['full_check_required'])
        self.assertFalse(compare(sources(), after,
            non_runtime_paths=['NEW_GUIDE.md'])['full_check_required'])
        after['NEW_GUIDE.py'] = entry('execute()')
        self.assertTrue(compare(sources(), after,
            non_runtime_paths=['NEW_GUIDE.md'])['full_check_required'])
        with self.assertRaises(ValueError):
            compare(sources(), after, non_runtime_paths=['NEW_GUIDE.py'])

    def test_unknown_exclusions_and_prompt_exclusions_rejected(self):
        for names in [[reuse.PROMPT_PATH], ['*.json'], ['new.py'], ['config.json']]:
            with self.assertRaises(ValueError):
                compare(sources(), sources(), non_runtime_paths=names)

    def test_bad_hash_or_missing_prompt_rejected(self):
        after = sources()
        after['runner.py']['sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            compare(sources(), after)
        after = sources()
        del after[reuse.PROMPT_PATH]
        with self.assertRaises(ValueError):
            compare(sources(), after)

    def test_mode_change_is_runtime_change(self):
        after = sources()
        after['runner.py']['mode'] = '100755'
        self.assertTrue(compare(sources(), after)['full_check_required'])

    def test_invalid_baseline_shape_cannot_reuse_even_if_unchanged(self):
        bad = sources(PROMPT.replace('"maintain"', 'str("maintain")'))
        self.assertTrue(compare(bad, bad)['full_check_required'])

    def test_exact_evidence_paths_can_be_excluded_but_new_files_cannot(self):
        before = sources()
        before['proof/execution_identity.json'] = entry('{}')
        after = copy.deepcopy(before)
        after['proof/execution_identity.json'] = entry('{"a": 1}')
        plan = compare(before, after, verified_evidence_paths=['proof/execution_identity.json'])
        self.assertFalse(plan['full_check_required'])
        after['proof/new_runtime.py'] = entry('execute()')
        self.assertTrue(compare(before, after,
            verified_evidence_paths=['proof/execution_identity.json'])['full_check_required'])


class GitSnapshotTests(unittest.TestCase):
    def test_snapshot_rejects_untracked_and_captures_new_tracked_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(['git', 'init', '-q', tmp], check=True)
            p = root / reuse.PROMPT_PATH
            p.parent.mkdir(parents=True)
            p.write_text(PROMPT)
            subprocess.run(['git', '-C', tmp, 'add', '.'], check=True)
            before = reuse.tracked_snapshot(root)
            (root / 'new.py').write_text('new()')
            with self.assertRaises(ValueError):
                reuse.tracked_snapshot(root)
            subprocess.run(['git', '-C', tmp, 'add', '.'], check=True)
            after = reuse.tracked_snapshot(root)
            self.assertTrue(compare(before, after)['full_check_required'])

    def test_index_mode_respected_when_filemode_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(['git', 'init', '-q', tmp], check=True)
            subprocess.run(['git', '-C', tmp, 'config', 'core.filemode', 'false'], check=True)
            p = root / 'runner.py'
            p.write_text('run()')
            p.chmod(0o644)
            subprocess.run(['git', '-C', tmp, 'add', '.'], check=True)
            p.chmod(0o755)
            self.assertEqual(reuse.tracked_snapshot(root)['runner.py']['mode'], '100644')
            if reuse.os.name == 'posix':
                subprocess.run(['git', '-C', tmp, 'config', 'core.filemode', 'true'], check=True)
                self.assertEqual(reuse.tracked_snapshot(root)['runner.py']['mode'], '100755')

    def test_verifier_failure_is_not_a_success_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'proof').mkdir()
            with patch.object(reuse, '_git', side_effect=[b'', b'abc\n']), \
                 patch.object(reuse.subprocess, 'run', side_effect=
                    subprocess.CalledProcessError(1, ['verifier'])):
                with self.assertRaises(subprocess.CalledProcessError):
                    reuse.verify_baseline(Path(tmp), 'proof')

    def test_self_declared_success_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'proof').mkdir()
            result = subprocess.CompletedProcess([], 0, stdout='{"passed": true}')
            with patch.object(reuse, '_git', side_effect=[b'', b'abc\n']), \
                 patch.object(reuse.subprocess, 'run', return_value=result):
                with self.assertRaises(ValueError):
                    reuse.verify_baseline(Path(tmp), 'proof')

    def test_verified_proof_hashes_and_baseline_import_are_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'proof').mkdir()
            data = b'observed evidence'
            (root / 'proof' / 'result.json').write_bytes(data)
            proof = {'outcomes': {'A': {}, 'B': {}},
                     'file_sha256': {'result.json': reuse.digest(data)}}
            result = subprocess.CompletedProcess([], 0, stdout=json.dumps(proof))
            with patch.object(reuse, '_git', side_effect=[b'', b'abc\n']), \
                 patch.object(reuse.subprocess, 'run', return_value=result) as run:
                receipt = reuse.verify_baseline(root, 'proof')
                self.assertEqual(receipt['commit'], 'abc')
                self.assertEqual(receipt['proof'], proof)
                self.assertEqual(run.call_args.kwargs['cwd'], root)
                argv = run.call_args.args[0]
                self.assertEqual(argv[1], '-I')
                self.assertEqual(argv[-1], str(root))
                self.assertIn('require_committed=True', argv[3])
            proof['file_sha256']['result.json'] = '0' * 64
            result.stdout = json.dumps(proof)
            with patch.object(reuse, '_git', side_effect=[b'', b'abc\n']), \
                 patch.object(reuse.subprocess, 'run', return_value=result):
                with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                    reuse.verify_baseline(root, 'proof')

    def test_tracked_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(['git', 'init', '-q', tmp], check=True)
            try:
                (root / 'link.py').symlink_to('outside.py')
            except OSError as exc:
                if os.name == 'nt' and getattr(exc, 'winerror', None) == 1314:
                    self.skipTest('Windows symlink privilege unavailable')
                raise
            subprocess.run(['git', '-C', tmp, 'add', '.'], check=True)
            with self.assertRaises(ValueError):
                reuse.tracked_snapshot(root)

    def test_cli_does_not_accept_passed_json_or_authorize_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'proof').mkdir()
            (root / 'config.json').write_text('{}')
            args = ['--baseline', tmp, '--current', tmp, '--evidence', 'proof',
                    '--baseline-config', str(root / 'config.json'),
                    '--current-config', str(root / 'config.json')]
            with patch.object(reuse, 'verify_baseline', side_effect=ValueError('hashbad')), \
                 patch('sys.stderr'):
                self.assertEqual(reuse.main(args), 2)


if __name__ == '__main__':
    unittest.main()
