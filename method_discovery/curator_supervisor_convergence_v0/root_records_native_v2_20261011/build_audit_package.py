"""Generate a standalone, credential-free zero-model engineering audit TXT."""

import hashlib
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
CODE_COMMIT = '4e7d60dde41c17059169ddd84c2961ea8e1fc74c'
TESTS = [
    'method_discovery/curator_supervisor_convergence_v0/root_records_native_v2_20261011/test_forensic_v1_rehydration.py',
    'GenericAgent-main/tests/test_root_records_v1.py',
    'GenericAgent-main/tests/test_root_records_native_v2.py',
    'GenericAgent-main/tests/test_monitor_provider.py',
    'GenericAgent-main/tests/test_crs_v0.py',
    'GenericAgent-main/tests/test_rhr_v0.py',
    'GenericAgent-main/tests/test_rer_v0.py',
    'GenericAgent-main/tests/test_root_turn_ceiling.py',
]
SOURCES = [
    'GenericAgent-main/monitor_agent_core/agent.py',
    'GenericAgent-main/monitor_agent_core/provider.py',
    'GenericAgent-main/monitor_agent_core/runtime.py',
    'GenericAgent-main/monitor_agent_core/root_records_native_v2.py',
    'GenericAgent-main/monitor_agent_core/native_projection_capture.py',
    'GenericAgent-main/tests/test_root_records_native_v2.py',
    'method_discovery/curator_supervisor_convergence_v0/root_records_native_v2_20261011/forensic_v1_rehydration.py',
    'method_discovery/curator_supervisor_convergence_v0/root_records_native_v2_20261011/test_forensic_v1_rehydration.py',
]


def run(command, env=None):
    result = subprocess.run(command, cwd=ROOT, env=env, text=True,
                            encoding='utf-8', errors='replace', capture_output=True,
                            check=False)
    return result.returncode, result.stdout, result.stderr


def main():
    env = dict(os.environ)
    env['PYTHONPATH'] = os.pathsep.join(['GenericAgent-main', '.', env.get('PYTHONPATH', '')])
    focused = [sys.executable, '-m', 'pytest', *TESTS, '-q',
               '-k', 'not test_frozen_prompt_and_provider']
    legacy = [sys.executable, '-m', 'pytest',
              'GenericAgent-main/tests/test_rer_v0.py::test_frozen_prompt_and_provider', '-q']
    result_focused = run(focused, env)
    result_legacy = run(legacy, env)
    diff = run(['git', 'show', '--format=', '--no-ext-diff', CODE_COMMIT, '--',
                *SOURCES[:5]])
    parts = [
        'ROOT_RECORDS_NATIVE_V2 ZERO-MODEL AUDIT PACKAGE\n',
        'Code commit: ' + CODE_COMMIT + '\n',
        'No live Task, Supervisor, provider, evaluator, training or scoring-model calls.\n',
        'Display-only trailing blanks are trimmed; the exact binary-safe diff is in the code commit.\n',
    ]
    for name in ('REPORT.md', 'OFFLINE_RESULT.json'):
        path = HERE / name
        parts.append('\n===== ' + name + ' =====\n' + path.read_text(encoding='utf-8'))
    parts.append('\n===== ENUMERATED SOURCE SHA-256 =====\n')
    for name in SOURCES:
        raw = (ROOT / name).read_bytes()
        parts.append(name + ' ' + hashlib.sha256(raw).hexdigest() + '\n')
    for title, command, result in (
            ('TARGETED ZERO-MODEL SUITE', focused, result_focused),
            ('PRE-EXISTING LEGACY BYTE-FREEZE ASSERTION', legacy, result_legacy)):
        code, stdout, stderr = result
        parts.append('\n===== ' + title + ' =====\n')
        parts.append('command: ' + ' '.join(command) + '\nexit_code: ' + str(code) + '\n')
        parts.append('stdout:\n' + stdout + '\nstderr:\n' + stderr)
    parts.append('\n===== COMPLETE PRODUCTION DIFF =====\n')
    parts.append('exit_code: ' + str(diff[0]) + '\n' + diff[1] + '\n' + diff[2])
    for name in SOURCES[5:]:
        parts.append('\n===== FULL ADDED FILE: ' + name + ' =====\n')
        parts.append((ROOT / name).read_text(encoding='utf-8'))
    output = HERE / 'AUDIT_PACKAGE.txt'
    rendered = '\n'.join(line.rstrip(' \t') for line in ''.join(parts).split('\n'))
    output.write_bytes(rendered.encode('utf-8'))
    print(output)
    print('sha256=' + hashlib.sha256(output.read_bytes()).hexdigest())
    print('targeted_exit_code=' + str(result_focused[0]))
    print('legacy_exit_code=' + str(result_legacy[0]))
    return 0 if result_focused[0] == 0 and result_legacy[0] == 1 and diff[0] == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
