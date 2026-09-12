"""Describe a local, behavior-preserving source checkpoint; never run agents.

No keys, generated runs, hidden task tests or dependency installation.
Existing historical source is saved as-is, not counted as a new mechanism.
"""
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess

from paper_bundle_inventory import ROOT, selected_files

SEEDS = (
    'method_discovery/clean_monitor_prepare_real_task_gate.py',
    'method_discovery/prepare_tool_feedback_run.py',
    'long_context_bench/scripts/run_ultralong_m12_proofs.py',
    'long_context_bench/adapters/harbor_ga_agent.py',
)
SEARCH = (ROOT / 'method_discovery', ROOT / 'long_context_bench',
          ROOT / 'long_context_bench/scripts')


def local_imports(path):
    tree = ast.parse(path.read_text(encoding='utf-8-sig'), filename=str(path))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.append(node.module)
            names.extend(node.module + '.' + alias.name for alias in node.names)
    for name in names:
        if name.split('.')[0].startswith('mykey'):
            continue
        for base in SEARCH:
            candidate = base.joinpath(*name.split('.')).with_suffix('.py')
            if candidate.is_file():
                yield candidate
                break


def checkpoint_files():
    files = set(selected_files(ROOT / 'GenericAgent-main'))
    pending = [ROOT / seed for seed in SEEDS]
    seen = set()
    while pending:
        path = pending.pop()
        if path in seen:
            continue
        seen.add(path)
        pending.extend(local_imports(path))
    files.update(seen)
    files.update(ROOT / p for p in (
        'GenericAgent-main/pyproject.toml',
        'method_discovery/r0_real_tasks/tasks.jsonl',
        'method_discovery/r0_real_tasks/protocol.json',
    ))
    # Deterministic test code, never hidden benchmark evaluation fixtures.
    for base, pattern in (
        ('GenericAgent-main/tests', 'test*monitor*.py'),
        ('long_context_bench/tests', 'test*isolat*.py'),
        ('long_context_bench/tests', 'test*harbor*.py'),
        ('long_context_bench/tests', 'test_failure_snapshot.py'),
        ('long_context_bench/tests', 'test_run_ultralong_m12_proofs.py'),
    ):
        files.update((ROOT / base).glob(pattern))
    return sorted(files)


def report():
    rows, flags, syntax = [], [], []
    for path in checkpoint_files():
        relative = path.relative_to(ROOT).as_posix()
        data = path.read_bytes()
        if (re.search(rb'\b(?:sk-|ghp_|github_pat_)[A-Za-z0-9_-]{24,}', data)
                or re.search(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----', data)):
            flags.append(relative)
        if path.suffix == '.py':
            try:
                ast.parse(data, filename=relative)
            except SyntaxError as exc:
                syntax.append({'path': relative, 'line': exc.lineno})
        blob = subprocess.run(['git', '-c', f'safe.directory={ROOT.as_posix()}',
                               'hash-object', '--', relative], cwd=ROOT,
                              check=True, capture_output=True, text=True).stdout.strip()
        rows.append({'path': relative, 'bytes': len(data),
                     'worktree_sha256': hashlib.sha256(data).hexdigest(),
                     'git_filtered_blob': blob})
    return {'schema': 'historical-engineering-checkpoint/1',
            'purpose': 'local_recovery_not_method_acceptance_or_public_release',
            'files': rows, 'file_count': len(rows),
            'credential_pattern_flags': flags, 'python_syntax_errors': syntax,
            'dynamic_imports_and_external_dependencies': 'not_fully_resolved',
            'exclusions': ['mykey and actual credentials', 'gateway configs',
                           'task workspaces and logs', 'hidden task tests',
                           'Docker images and installed environments'],
            'runtime_readiness': 'not_proven_by_source_checkpoint',
            'note': 'Git text normalization may change byte SHA; filtered blob records saved identity.'}


if __name__ == '__main__':
    print(json.dumps(report(), ensure_ascii=False, indent=2))
