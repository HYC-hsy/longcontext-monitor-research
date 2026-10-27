"""Offline regressions in fresh PMA/vendor and native-Harbor processes.

The coordinator imports no PMA/Harbor code. Native Harbor must be the existing
pinned checkout, never the incompatible Harbor bundled with pinned PMA.
"""
import argparse
from contextlib import ExitStack
import hashlib
import importlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import traceback
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT / 'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013'
VENDOR = STAGE / 'vendor/pma_89e5c0d'
NATIVE_COMMIT = '459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc'
PHASES = ('pma', 'native')
PMA_TESTS = (
    'test_gap_latest_revision_store.py', 'test_gap_latest_revision_agent.py',
    'test_gap_evidence_agent.py', 'test_gap_evidence_store.py',
    'test_gap_evidence_host.py', 'test_gap_evidence_aligned_host.py',
    'test_gap_evidence_alignment_integration.py', 'test_gap_host_integration.py',
)


def suite_manifest(phase):
    files = (sorted((ROOT / 'pma_evidence_review/tests').glob('test_*.py')) +
             [STAGE / 'tests' / name for name in PMA_TESTS]) if phase == 'pma' else [
                 STAGE / 'tests/test_evaluation_bootstrap.py']
    return [path.relative_to(ROOT).as_posix() for path in files]


def is_vendor_path(path):
    return '/vendor/pma_89e5c0d' in str(Path(path).resolve()).replace('\\', '/').lower()


def phase_paths(phase, inherited, native_root=None):
    # Remove vendor paths from other worktrees and editable .pth installations too.
    paths = [str(ROOT)]
    if phase == 'pma':
        paths += [str(VENDOR / 'external/harbor/src'), str(VENDOR / 'src'), str(STAGE)]
    elif native_root is not None:
        paths += [str(native_root / 'src')]
    paths += [path for path in inherited if path and not is_vendor_path(path)]
    return list(dict.fromkeys(paths))


def child_environment(phase, native_root=None):
    env = os.environ.copy()
    env['PYTHONPATH'] = os.pathsep.join(phase_paths(
        phase, env.get('PYTHONPATH', '').split(os.pathsep), native_root))
    env.update(PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1',
               LITELLM_LOCAL_MODEL_COST_MAP='True')
    return env


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def test_ids(suite):
    return [test.id() for test in test_ids_as_cases(suite)]


def test_ids_as_cases(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from test_ids_as_cases(test)
        else:
            yield test


def harbor_identity(phase, native_root):
    spec = importlib.util.find_spec('harbor')
    if spec is None or spec.origin is None:
        raise RuntimeError('Harbor unavailable; use the existing pinned native environment '
                           'or --native-harbor-source-root (no vendor fallback)')
    package = Path(spec.origin).resolve()
    expected = VENDOR / 'external/harbor/src/harbor' if phase == 'pma' else (
        native_root / 'src/harbor' if native_root else package.parent)
    if package != (expected / '__init__.py').resolve() or (phase == 'native' and is_vendor_path(package)):
        raise RuntimeError(f'{phase} Harbor origin mismatch: {package}; expected {expected}')
    identity = {'package': str(package)}
    if phase == 'native':
        source = expected.parent.parent.resolve()
        commit = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'],
                                         text=True).strip()
        if commit != NATIVE_COMMIT:
            raise RuntimeError(f'native Harbor commit {commit} != pinned {NATIVE_COMMIT}: {source}')
        changed = subprocess.check_output(
            ['git', '-C', str(source), 'status', '--porcelain', '--untracked-files=all', '--', 'src/harbor'],
            text=True)
        if changed.strip():
            raise RuntimeError(f'native Harbor source is not clean: {source}\n{changed}')
        identity.update(source_root=str(source), commit=commit)
    module = importlib.import_module('harbor.verifier.verifier')
    origin = Path(module.__file__).resolve()
    if origin != (expected / 'verifier/verifier.py').resolve():
        raise RuntimeError(f'{phase} Verifier origin mismatch: {origin}')
    identity.update(verifier=str(origin), has_resolve_tests=hasattr(module.Verifier, '_resolve_tests'))
    return identity


def run_phase(phase, report, native_root=None):
    record = {'phase': phase, 'pid': os.getpid(), 'python': sys.version,
              'executable': sys.executable, 'suite_files': suite_manifest(phase)}
    code = 2
    try:
        if any(name == 'harbor' or name.startswith('harbor.') for name in sys.modules):
            raise RuntimeError('Harbor was imported before phase isolation')
        sys.path[:] = phase_paths(phase, sys.path, native_root)
        record['sys_path'] = list(sys.path)
        os.chdir(ROOT)
        from pma_evidence_review.tests.no_network import install_guard
        guard = unittest.TestCase()
        install_guard(guard)
        try:
            with ExitStack() as stack:
                if phase == 'pma':
                    original = importlib.metadata.version
                    def version(name):
                        try:
                            return original(name)
                        except importlib.metadata.PackageNotFoundError:
                            if name == 'harbor':
                                return '0.0.0-source-checkout-test-only'
                            raise
                    stack.enter_context(patch('importlib.metadata.version', side_effect=version))
                    # Existing import compatibility remains PMA-only; no Verifier API patch.
                    import typing_extensions
                    stack.enter_context(patch('typing.TypedDict', typing_extensions.TypedDict))
                suite = unittest.TestSuite()
                if phase == 'native' and sys.version_info < (3, 12):
                    skipped = unittest.skip('Pinned native Harbor verifier requires Python 3.12 syntax; not executed')(lambda: None)
                    suite.addTest(unittest.FunctionTestCase(skipped))
                    record['native_module_not_executed'] = True
                else:
                    record['harbor'] = harbor_identity(phase, native_root)
                    for name in record['suite_files']:
                        path = ROOT / name
                        suite.addTests(unittest.TestLoader().discover(str(path.parent), pattern=path.name))
                ids = test_ids(suite)
                if len(ids) != len(set(ids)):
                    raise RuntimeError('duplicate test IDs in phase inventory')
                record['test_ids'] = ids
                record['inventory_sha256'] = hashlib.sha256('\n'.join(ids).encode()).hexdigest()
                write_json(report, record)
                print('GATE_PHASE ' + json.dumps({key: value for key, value in record.items()
                      if key not in ('test_ids', 'sys_path', 'suite_files')}), flush=True)
                result = unittest.TextTestRunner(verbosity=2).run(suite)
                record.update(tests_run=result.testsRun, errors=len(result.errors),
                              failures=len(result.failures), skipped=len(result.skipped),
                              successful=result.wasSuccessful())
                code = 0 if result.wasSuccessful() else 1
                if 'harbor' in record:
                    record['harbor_after'] = harbor_identity(phase, native_root)
                    if record['harbor_after'] != record['harbor']:
                        raise RuntimeError('Harbor identity changed during tests')
        finally:
            guard.doCleanups()
    except Exception as exc:
        traceback.print_exc()
        record['infrastructure_error'] = f'{type(exc).__name__}: {exc}'
        code = 2
    record['exit_code'] = code
    write_json(report, record)
    return code


def run_children(report_dir, native_root=None):
    records = []
    for phase in PHASES:  # Always run both, even if the first has errors or cannot start.
        report = report_dir / f'{phase}.json'
        command = [sys.executable, '-X', 'utf8', '-B', str(Path(__file__).resolve()),
                   '--phase', phase, '--phase-report', str(report)]
        if native_root is not None:
            command += ['--native-harbor-source-root', str(native_root)]
        record = {'phase': phase, 'suite_files': suite_manifest(phase)}
        with (report_dir / f'{phase}.stdout.txt').open('wb') as stdout, \
                (report_dir / f'{phase}.stderr.txt').open('wb') as stderr:
            try:
                child = subprocess.run(command, cwd=ROOT, env=child_environment(phase, native_root),
                                       stdout=stdout, stderr=stderr)
                record['returncode'] = child.returncode
            except OSError as exc:
                record.update(returncode=2, infrastructure_error=str(exc))
        for channel in ('stdout', 'stderr'):
            data = (report_dir / f'{phase}.{channel}.txt').read_bytes()
            stream = getattr(sys, channel)
            if hasattr(stream, 'buffer'):
                stream.buffer.write(data)
            else:
                stream.write(data.decode('utf-8', errors='replace'))
            stream.flush()
        if report.exists():
            try:
                result = json.loads(report.read_text(encoding='utf-8'))
                if not isinstance(result, dict):
                    raise ValueError('child report must be an object')
                record['result'] = result
            except (OSError, ValueError) as exc:
                record.update(returncode=2, infrastructure_error=f'invalid child report: {exc}')
        else:
            record.setdefault('infrastructure_error', 'child report missing')
        if 'infrastructure_error' in record:
            print(f"{phase}: {record['infrastructure_error']}", file=sys.stderr, flush=True)
        records.append(record)
    ids = [name for row in records for name in row.get('result', {}).get('test_ids', [])]
    valid = all(row['returncode'] == 0 and row.get('result', {}).get('exit_code') == 0
                and row.get('result', {}).get('successful') is True
                and row['result'].get('tests_run', 0) == len(row['result'].get('test_ids', [])) > 0
                for row in records)
    summary = {'phases': records, 'duplicate_test_ids': len(ids) != len(set(ids)),
               'totals': {key: sum(row.get('result', {}).get(key, 0) for row in records)
                          for key in ('tests_run', 'errors', 'failures', 'skipped')}}
    summary['exit_code'] = 0 if valid and not summary['duplicate_test_ids'] else 1
    write_json(report_dir / 'summary.json', summary)
    print('GATE_SUMMARY ' + json.dumps({'totals': summary['totals'],
          'phase_exit_codes': {row['phase']: row['returncode'] for row in records},
          'exit_code': summary['exit_code']}), flush=True)
    return summary['exit_code']


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-harbor-source-root', type=Path)
    parser.add_argument('--report-dir', type=Path, help='new directory for raw child logs and inventories')
    parser.add_argument('--phase', choices=PHASES, help=argparse.SUPPRESS)
    parser.add_argument('--phase-report', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    native = args.native_harbor_source_root.resolve() if args.native_harbor_source_root else None
    if args.phase:
        if args.phase_report is None:
            parser.error('--phase requires --phase-report')
        return run_phase(args.phase, args.phase_report, native)
    if args.report_dir:
        output = args.report_dir.resolve()
        output.mkdir(parents=True, exist_ok=False)
        return run_children(output, native)
    with tempfile.TemporaryDirectory(prefix='gate-regressions-') as directory:
        return run_children(Path(directory), native)


if __name__ == '__main__':
    raise SystemExit(main())
