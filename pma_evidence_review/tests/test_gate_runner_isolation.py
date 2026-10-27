"""Runner mechanics only; never replace the real Verifier or its assertions."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pma_evidence_review.tests import run_gate_regressions as runner


class GateRunnerIsolationTests(unittest.TestCase):
    def test_importing_coordinator_does_not_import_harbor_or_change_path(self):
        code = """
import sys
before = list(sys.path)
from pma_evidence_review.tests import run_gate_regressions
assert before == sys.path
assert not any(n == 'harbor' or n.startswith('harbor.') for n in sys.modules)
assert 'memory_agent' not in sys.modules
"""
        subprocess.run([sys.executable, '-B', '-c', code], cwd=runner.ROOT, check=True)

    def test_manifest_is_stable_disjoint_and_preserves_all_old_modules(self):
        pma, native = (runner.suite_manifest(phase) for phase in runner.PHASES)
        expected = ['test_gap_latest_revision_store.py', 'test_gap_latest_revision_agent.py',
                    'test_gap_evidence_agent.py', 'test_gap_evidence_store.py',
                    'test_gap_evidence_host.py', 'test_gap_evidence_aligned_host.py',
                    'test_gap_evidence_alignment_integration.py', 'test_gap_host_integration.py']
        self.assertEqual([Path(name).name for name in pma[-8:]], expected)
        self.assertEqual([Path(name).name for name in native], ['test_evaluation_bootstrap.py'])
        self.assertEqual(len(pma + native), len(set(pma + native)))
        self.assertEqual(pma[:-8], [path.relative_to(runner.ROOT).as_posix() for path in
            sorted((runner.ROOT / 'pma_evidence_review/tests').glob('test_*.py'))])
        self.assertEqual(pma, runner.suite_manifest('pma'))

    def test_fresh_process_paths_and_origins_are_distinct_despite_poisoned_parent(self):
        # Generic probe modules exercise process/path isolation, not a fake Harbor API.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vendor = root / 'stage/vendor/pma_89e5c0d'
            native = root / 'native'
            origins = [vendor / 'external/harbor/src', native / 'src']
            for index, origin in enumerate(origins):
                origin.mkdir(parents=True)
                (origin / 'runner_origin_probe.py').write_text(f'IDENTITY={index}\n', encoding='utf-8')
            other_vendor = root / 'old/vendor/pma_89e5c0d/external/harbor/src'
            code = """
import json, os, runner_origin_probe as probe
assert not hasattr(probe, 'parent_only')
probe.parent_only = True
print(json.dumps({'pid': os.getpid(), 'origin': probe.__file__, 'identity': probe.IDENTITY}))
"""
            with patch.object(runner, 'VENDOR', vendor), patch.dict(os.environ,
                    {'PYTHONPATH': os.pathsep.join([str(other_vendor), str(origins[0])])}):
                rows = []
                for phase in runner.PHASES:
                    env = runner.child_environment(phase, native)
                    if phase == 'native':
                        self.assertFalse(any(runner.is_vendor_path(p) for p in env['PYTHONPATH'].split(os.pathsep)))
                    result = subprocess.run([sys.executable, '-B', '-c', code], env=env,
                        cwd=runner.ROOT, check=True, capture_output=True, text=True)
                    rows.append(json.loads(result.stdout))
            self.assertNotEqual(rows[0]['pid'], rows[1]['pid'])
            self.assertNotIn(os.getpid(), [row['pid'] for row in rows])
            for index, row in enumerate(rows):
                self.assertEqual(row['identity'], index)
                self.assertEqual(Path(row['origin']), origins[index] / 'runner_origin_probe.py')

    def test_editable_vendor_paths_removed_and_native_explicit_path_first(self):
        inherited = [str(runner.VENDOR / 'src'), str(runner.VENDOR / 'external/harbor/src'),
                     '/another/vendor/pma_89e5c0d/external/harbor/src', '/dependencies']
        native = Path('/native')
        paths = runner.phase_paths('native', inherited, native)
        self.assertEqual(paths[:2], [str(runner.ROOT), str(native / 'src')])
        self.assertEqual(paths[2:], ['/dependencies'])
        self.assertEqual(runner.phase_paths('pma', inherited)[1], str(runner.VENDOR / 'external/harbor/src'))

    def test_native_rejects_vendor_origin_without_patching_verifier(self):
        spec = SimpleNamespace(origin=str(runner.VENDOR / 'external/harbor/src/harbor/__init__.py'))
        with patch.object(runner.importlib.util, 'find_spec', return_value=spec):
            with self.assertRaisesRegex(RuntimeError, 'origin mismatch'):
                runner.harbor_identity('native', None)

    def test_native_rejects_wrong_commit_before_import(self):
        source = Path('/native')
        spec = SimpleNamespace(origin=str(source / 'src/harbor/__init__.py'))
        with patch.object(runner.importlib.util, 'find_spec', return_value=spec), \
                patch.object(runner.subprocess, 'check_output', return_value='wrong-commit\n'):
            with self.assertRaisesRegex(RuntimeError, '!= pinned'):
                runner.harbor_identity('native', source)

    def test_exit_aggregation_runs_both_and_preserves_raw_streams_and_counts(self):
        for codes in ((0, 0), (1, 0), (0, 1), (2, 1)):
            with self.subTest(codes=codes), tempfile.TemporaryDirectory() as tmp:
                seen = []
                def launch(command, **kwargs):
                    phase = command[command.index('--phase') + 1]
                    seen.append(phase)
                    code = codes[len(seen) - 1]
                    kwargs['stdout'].write(('raw stdout ' + phase + '\n').encode())
                    kwargs['stderr'].write(('raw stderr ' + phase + '\n').encode())
                    report = Path(command[command.index('--phase-report') + 1])
                    runner.write_json(report, {'exit_code': code, 'successful': code == 0,
                        'test_ids': [phase + '.original_assertion'], 'tests_run': 1,
                        'errors': int(code != 0), 'failures': 0, 'skipped': 0})
                    self.assertEqual(command[0], sys.executable)
                    self.assertIn('-B', command)
                    return SimpleNamespace(returncode=code)
                with patch.object(runner.subprocess, 'run', side_effect=launch), \
                        patch.object(sys, 'stdout', io.StringIO()), patch.object(sys, 'stderr', io.StringIO()):
                    exit_code = runner.run_children(Path(tmp))
                self.assertEqual(seen, ['pma', 'native'])
                self.assertEqual(exit_code, int(any(codes)))
                report = json.loads((Path(tmp) / 'summary.json').read_text())
                self.assertEqual(report['totals']['tests_run'], 2)
                self.assertEqual(report['totals']['errors'], sum(code != 0 for code in codes))
                for phase in seen:
                    for stream in ('stdout', 'stderr'):
                        self.assertEqual((Path(tmp) / f'{phase}.{stream}.txt').read_bytes(),
                                         f'raw {stream} {phase}\n'.encode())

    def test_spawn_failure_or_missing_child_report_cannot_pass(self):
        for problem in ('missing', 'spawn', 'malformed', 'not_object'):
            with self.subTest(problem=problem), tempfile.TemporaryDirectory() as tmp:
                seen = []
                def launch(command, **kwargs):
                    seen.append(command[command.index('--phase') + 1])
                    if problem == 'spawn' and len(seen) == 1:
                        raise OSError('synthetic unavailable interpreter')
                    if problem in ('malformed', 'not_object'):
                        Path(command[command.index('--phase-report') + 1]).write_text(
                            '{' if problem == 'malformed' else '[]', encoding='utf-8')
                    return SimpleNamespace(returncode=0)
                with patch.object(runner.subprocess, 'run', side_effect=launch), \
                        patch.object(sys, 'stdout', io.StringIO()), patch.object(sys, 'stderr', io.StringIO()):
                    self.assertEqual(runner.run_children(Path(tmp)), 1)
                self.assertEqual(seen, ['pma', 'native'])

    def test_nested_inventory_preserves_ids_without_loss(self):
        first = unittest.FunctionTestCase(lambda: None, description='first')
        second = unittest.FunctionTestCase(lambda: None, description='second')
        suite = unittest.TestSuite([first, unittest.TestSuite([second])])
        self.assertEqual(runner.test_ids(suite), [first.id(), second.id()])
