"""Zero-execution inventory of the existing GA isolation copy policy.

Never calls build_bundle (which loads keys). This is an audit mirror, not a
new runtime allowlist. Content preservation and semantic review remain separate.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
DIRECTORIES = ('assets', 'memory', 'plugins', 'monitor_agent_core', 'pma_baseline',
               'reflect', 'ga_cli', 'frontends')
IGNORED = {'__pycache__', 'tests', '.git', 'file_access_stats.json'}


def selected_files(source):
    selected = [p for p in source.glob('*.py') if not p.name.startswith('mykey')]
    for name in DIRECTORIES:
        directory = source / name
        if not directory.exists():
            continue
        if name == 'memory':
            selected.extend(p for p in directory.iterdir()
                            if p.is_file() and p.suffix in {'.py', '.md', '.txt'})
        else:
            selected.extend(p for p in directory.rglob('*') if p.is_file()
                            and not any(part in IGNORED for part in p.relative_to(directory).parts)
                            and p.suffix != '.pyc')
    if any(p.is_symlink() or any(parent.is_symlink() for parent in p.parents
                                if parent != source.parent) for p in selected):
        raise ValueError('Symlink needs separate review')
    return sorted(set(selected))


def inventory(root=ROOT):
    source = root / 'GenericAgent-main'
    git = subprocess.run(['git', '-c', f'safe.directory={root.as_posix()}',
                          'ls-files', '--', 'GenericAgent-main'],
                         cwd=root, check=True, capture_output=True, text=True)
    tracked = set(git.stdout.splitlines())
    rows = []
    for path in selected_files(source):
        data = path.read_bytes()
        # A warning is not proof of a real secret; never output matched values.
        warning = bool(re.search(rb'\bsk-[A-Za-z0-9_-]{24,}', data))
        relative = path.relative_to(root).as_posix()
        rows.append({'path': relative, 'bytes': len(data),
                     'sha256': None if warning else hashlib.sha256(data).hexdigest(),
                     'tracked': relative in tracked,
                     'credential_pattern_review_required': warning,
                     'semantic_review': 'not_certified'})
    return {'schema': 'runtime-copy-inventory/1', 'files': rows,
            'files_selected': len(rows),
            'untracked_files': sum(not r['tracked'] for r in rows),
            'credential_pattern_flags': sum(r['credential_pattern_review_required'] for r in rows),
            'is_clean_baseline_certification': False,
            'dependencies_pinned': False,
            'excludes': ['actual mykey configurations', 'generated gateway credentials',
                         'runtime environment and images', 'host orchestration dependencies'],
            'policy_source_sha256': hashlib.sha256((root /
                'long_context_bench/scripts/isolated_run_bundle.py').read_bytes()).hexdigest()}


if __name__ == '__main__':
    print(json.dumps(inventory(), ensure_ascii=False, indent=2))
