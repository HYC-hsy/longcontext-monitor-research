"""Create a credential-free, reproducible TXT of this limited zero-model repair."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
BASE = '65f7058a143a997f33471d76800af1d3add28630'
CODE = 'db36f67e75ad9c10f7bcb124ad060a6505e6bcf5'
SOURCE_PATHS = [
    'GenericAgent-main/monitor_agent_core/agent.py',
    'GenericAgent-main/monitor_agent_core/runtime.py',
]
CHANGED = [
    'GenericAgent-main/monitor_agent_core/agent.py',
    'GenericAgent-main/tests/test_root_records_native_v2.py',
]
TESTS = [
    'method_discovery/curator_supervisor_convergence_v0/root_records_native_v2_20261011/test_forensic_v1_rehydration.py',
    'GenericAgent-main/tests/test_root_records_v1.py',
    'GenericAgent-main/tests/test_root_records_native_v2.py',
    'GenericAgent-main/tests/test_monitor_provider.py',
    'GenericAgent-main/tests/test_crs_v0.py',
    'GenericAgent-main/tests/test_rhr_v0.py',
    'GenericAgent-main/tests/test_rer_v0.py',
    'GenericAgent-main/tests/test_root_turn_ceiling.py',
    'GenericAgent-main/tests/test_monitor_continuation_purpose_boundary.py',
    'GenericAgent-main/tests/test_monitor_continuation_mode.py',
    'GenericAgent-main/tests/test_monitor_continuation_repair.py',
]


def run(args, env=None):
    return subprocess.run(args, cwd=ROOT, env=env, text=True, encoding='utf-8',
                          errors='replace', capture_output=True, check=False)


def identity(commit, path):
    blob = subprocess.check_output(['git', 'cat-file', 'blob', commit + ':' + path], cwd=ROOT)
    oid = subprocess.check_output(['git', 'rev-parse', commit + ':' + path], cwd=ROOT).decode().strip()
    worktree = (ROOT / path).read_bytes()
    return (f'{commit} {path}\nGit blob OID: {oid}\n'
            f'Git blob bytes SHA-256: {hashlib.sha256(blob).hexdigest()} ({len(blob)} bytes)\n'
            f'Current worktree bytes SHA-256: {hashlib.sha256(worktree).hexdigest()} '
            f'({len(worktree)} bytes)\n'
            f'Current worktree CRLF-to-LF equals that blob: '
            f'{worktree.replace(bytes([13, 10]), bytes([10])) == blob}\n')


def section(title, result, command):
    return (f'\n===== {title} =====\ncommand: {" ".join(command)}\n'
            f'exit_code: {result.returncode}\n'
            f'stdout_json: {json.dumps(result.stdout, ensure_ascii=False)}\n'
            f'stderr_json: {json.dumps(result.stderr, ensure_ascii=False)}\n')


def main():
    if run(['git', 'diff', '--quiet', CODE, 'HEAD', '--', *CHANGED]).returncode != 0:
        raise SystemExit('Audited code files changed after the repair commit')
    env = dict(os.environ)
    env['PYTHONPATH'] = os.pathsep.join(['GenericAgent-main', '.', env.get('PYTHONPATH', '')])
    tests = [sys.executable, '-m', 'pytest', *TESTS, '-q', '-k',
             'not test_frozen_prompt_and_provider and not '
             'test_forced_compaction_then_replaced_root_uses_current_contract']
    diff = ['git', 'diff', '--no-ext-diff', BASE, CODE, '--', *CHANGED]
    check = ['git', 'diff', '--check', BASE, CODE, '--', *CHANGED]
    tested, changed, checked = run(tests, env), run(diff), run(check)
    seams = [sys.executable, '-m', 'pytest',
             'GenericAgent-main/tests/test_root_records_native_v2.py', '-vv', '-k',
             'real_continuation_format_repair_capture or '
             'format_repair_prompt_tamper_fails_before_transport_and_cleans_up or '
             'native_noop_projection_still_binds_capture or '
             'noop_projection_tracks_native_maintenance']
    seam_result = run(seams, env)
    legacy = [sys.executable, '-m', 'pytest',
              'GenericAgent-main/tests/test_rer_v0.py::test_frozen_prompt_and_provider', '-q']
    dependency = [sys.executable, '-m', 'pytest',
                  'GenericAgent-main/tests/test_monitor_continuation_repair.py::'
                  'test_forced_compaction_then_replaced_root_uses_current_contract', '-q']
    legacy_result, dependency_result = run(legacy, env), run(dependency, env)
    report = (HERE / 'REPORT.md').read_text(encoding='utf-8')
    parts = ['ROOT_RECORDS_NATIVE_V2 LIMITED REPAIR — ZERO-MODEL AUDIT\n',
             'Code commit: ' + CODE + '\n', 'Archive baseline: 3c50e34cae5b01c9859928ef068f22196b6f2ee6\n',
             'Task/Supervisor/provider/evaluator/training/scoring-model calls: 0\n',
             '\n===== REPORT.md =====\n', report,
             '\n===== SOURCE IDENTITIES =====\n']
    for commit in (BASE, CODE):
        for path in SOURCE_PATHS:
            parts.append(identity(commit, path))
    parts.extend([section('TARGETED ZERO-MODEL TESTS', tested, tests),
                  section('NEW INTEGRATION SEAMS', seam_result, seams),
                  section('EXCLUDED OLD PROVIDER BYTE FREEZE', legacy_result, legacy),
                  section('EXCLUDED SHORTUUID DEPENDENCY', dependency_result, dependency),
                  section('COMPLETE CODE DIFF', changed, diff),
                  section('DIFF CHECK', checked, check)])
    parts.append('\n===== AUDIT BUILDER SOURCE =====\n' + Path(__file__).read_text(encoding='utf-8'))
    output = HERE / 'AUDIT_PACKAGE.txt'
    output.write_bytes(''.join(parts).encode('utf-8'))
    print('audit_package=' + str(output))
    print('sha256=' + hashlib.sha256(output.read_bytes()).hexdigest())
    print('test_exit_code=' + str(tested.returncode))
    print('diff_exit_code=' + str(changed.returncode))
    print('check_exit_code=' + str(checked.returncode))
    return 0 if all(result.returncode == 0 for result in (
        tested, seam_result, changed, checked)) else 1


if __name__ == '__main__':
    raise SystemExit(main())
