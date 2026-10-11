"""Mechanically render the sanitized zero-model audit bundle for this candidate."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
BASE = '27226b6b94b19e88a288f41ead62d7dd09a794b4'
HOST = 'be9f14c9'
METHOD = '89fa9d2e'
SOURCES = (
    'GenericAgent-main/agentmain.py',
    'GenericAgent-main/ga_monitor_adapter.py',
    'GenericAgent-main/monitor_agent_core/agent.py',
    'GenericAgent-main/monitor_agent_core/runtime.py',
    'GenericAgent-main/monitor_agent_core/narrow_supervisor_v1.py',
    'method_discovery/curator_supervisor_convergence_v0/real_task_effect_pilot_preflight_20261010/pilot_entry.py',
    'method_discovery/curator_supervisor_convergence_v0/real_task_effect_pilot_preflight_20261010/pilot_profile.py',
    'method_discovery/curator_supervisor_convergence_v0/real_task_effect_pilot_preflight_20261010/pilot_offline_harbor.py',
    'method_discovery/curator_supervisor_convergence_v0/real_task_effect_pilot_preflight_20261010/pilot_harbor_hooks.py',
    'GenericAgent-main/tests/test_narrow_supervisor_v1.py',
    'method_discovery/curator_supervisor_convergence_v0/real_task_effect_pilot_preflight_20261010/test_narrow_pilot_bundle.py',
)


def run(*args, env=None):
    return subprocess.run(args, cwd=ROOT, env=env, capture_output=True, text=True,
                          encoding='utf-8', errors='replace', check=False)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    git_head = run('git', 'rev-parse', 'HEAD')
    ancestry = run('git', 'merge-base', '--is-ancestor', METHOD, 'HEAD')
    if git_head.returncode or ancestry.returncode:
        raise RuntimeError('Audit renderer requires the frozen method commit in ancestry')
    status = run('git', 'status', '--short')
    if status.returncode:
        raise RuntimeError('Git status unavailable')
    env = os.environ.copy()
    env['PYTHONPATH'] = str(ROOT) + os.pathsep + str(ROOT / 'GenericAgent-main')
    cmd = [sys.executable, '-m', 'pytest', '--import-mode=importlib', '-s', '-q',
           'GenericAgent-main/tests/test_narrow_supervisor_v1.py',
           'GenericAgent-main/tests/test_ase_v0.py',
           'method_discovery/curator_supervisor_convergence_v0/real_task_effect_pilot_preflight_20261010/test_narrow_pilot_bundle.py',
           'method_discovery/curator_supervisor_convergence_v0/real_task_effect_pilot_preflight_20261010/test_pilot_profile.py',
           'method_discovery/curator_supervisor_convergence_v0/real_task_effect_pilot_preflight_20261010/test_task_terminal_gate.py']
    tests = run(*cmd, env=env)
    diff_check = run('git', 'diff', '--check', BASE, METHOD)
    full_diff = run('git', 'diff', '--binary', BASE, METHOD)
    if full_diff.returncode:
        raise RuntimeError('Full code diff unavailable')
    local_test_diff = run('git', 'diff', '--binary', METHOD, '--', SOURCES[-1])
    lines = [
        'NARROW SUPERVISOR V1 — SANITIZED ZERO-MODEL AUDIT PACK',
        'Status: IMPLEMENTED_READY_FOR_BRAIN_AUDIT (engineering only; no live experiment)',
        f'Actual baseline: {BASE}',
        f'Shared host terminal fix: {HOST}',
        f'Narrow method commit: {METHOD}',
        f'Checkout at capture: {git_head.stdout.strip()}',
        'Branch: crs-v0-20261007; planned remote: public/crs-v0-20261007',
        'No Task, Supervisor, provider API, native evaluator, training, or scoring model calls.',
        'Real-call counts: Task=0 Supervisor=0 provider=0 native_evaluator=0 training=0 scoring=0.',
        '',
        'SCOPE / EFFECTIVE ROUTE',
        'Legacy variant remains default. Narrow variant is explicit, default-off, S route only,',
        'and requires ASE=true, CRS=false, RHR=false, RER=false, history_projection=off.',
        'Task-only T creates no Monitor model route. The method system text is the exact',
        'METHOD_PROMPT in narrow_supervisor_v1.py below; normal/root review append REVIEW_MODE.',
        'The runtime root wake uses ROOT_WAKE. The native root_input replaces the wake text',
        'and retains current handoff, Task Book, Situation, public events and task budget.',
        'Continuation uses the same narrow base system plus the unchanged native',
        'CONTINUATION_MODE_PROMPT and maintenance request. Tool schema is the existing',
        'seven-tool ASE MONITOR_TOOLS: file_read, file_write, file_patch, code_run,',
        'wait, intervene, allow_complete. Code execution retains the existing isolated pilot port.',
        'The allow result remains ALLOW_COMPLETE/MONITOR_ALLOWED mechanically, and adds',
        'NO_SUPERVISORY_OBJECTION as a reason code only for the narrow variant.',
        'Proposal, runtime acceptance, Task terminal state, evaluator eligibility and score',
        'remain distinct. CURRENT_TASK_DONE is a program terminal state, not semantic correctness.',
        '',
        'PREPARED BUNDLE EVIDENCE',
        'The targeted test invokes actual prepare_run/build_bundle for synthetic-credential',
        'unarmed T and S and prints PREPARED_BUNDLE_EVIDENCE below. The temporary bundle',
        'is deleted by pytest; this phase does not prepare a live manifest or authorization.',
        'The S bundle contains narrow_supervisor_v1.py and resolved models.local.json;',
        'the T bundle has no Monitor models.local.json. Both Task client configs and',
        'original public instruction/task.toml identities are asserted equal.',
        'The test then loads that bundled Monitor config into the real provider client,',
        'intercepts its first assembled request before transport, and prints the',
        'system/messages/tools SHA-256 and seven tool names. No provider send occurs.',
        'The client snapshot reports its existing temperature default separately from',
        'the public profile identity; the narrow resolver did not add temperature.',
        'The test compose hash contains temporary host paths and is not a live identity.',
        '',
        'UNVERIFIED / EXCLUDED',
        'No live provider compatibility or real Task/Supervisor deployment was tested.',
        'No real completion claim was assessed; no native evaluation occurred.',
        'Historical Task terminal states are not retroactively reclassified.',
        'The future Fyne N single-run design is only a planning record: S routing with',
        'narrow_v1, no new Task-only run, no Kitex or additional repeats authorized.',
        '',
        'GIT STATUS AT CAPTURE (unrelated __pycache__ preserved):',
        status.stdout,
        '',
        'GIT BLOB BYTE SHA-256 VS WORKTREE BYTE SHA-256 (not Git object IDs):',
    ]
    for source in SOURCES:
        blob = subprocess.run(['git', 'show', f'{METHOD}:{source}'], cwd=ROOT,
                              capture_output=True, check=False)
        current = ROOT / source
        if blob.returncode == 0:
            lines.append(f'{source}\n  git_blob_sha256={sha(blob.stdout)}'
                         f'\n  worktree_sha256={sha(current.read_bytes())}'
                         f'\n  byte_equal={blob.stdout == current.read_bytes()}')
        else:
            lines.append(f'{source}\n  git_blob_unavailable; worktree_sha256={sha(current.read_bytes())}')
    lines.extend([
        '', 'TEST COMMAND:', ' '.join(cmd),
        f'TEST EXIT CODE: {tests.returncode}',
        'TEST STDOUT (complete):', tests.stdout,
        'TEST STDERR (complete):', tests.stderr,
        'git diff --check baseline..method exit code: ' + str(diff_check.returncode),
        'git diff --check stdout:', diff_check.stdout,
        'git diff --check stderr:', diff_check.stderr,
        'FULL IMPLEMENTATION DIFF — BASELINE THROUGH METHOD COMMIT:',
        full_diff.stdout,
        'POST-METHOD TEST EVIDENCE-PRINT DIFF:',
        local_test_diff.stdout,
    ])
    output = HERE / 'NARROW_SUPERVISOR_V1_FULL_AUDIT.txt'
    output.write_bytes('\n'.join(lines).encode('utf-8'))
    print(f'audit_file={output}')
    print(f'audit_sha256={sha(output.read_bytes())}')
    print(f'test_exit={tests.returncode} diff_check_exit={diff_check.returncode}')
    if tests.returncode or diff_check.returncode:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
