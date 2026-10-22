"""Read public task metadata from a local, immutable Git commit.

Never reads evaluator bodies, solutions, or executes task/profile code.
"""
import hashlib
from pathlib import Path
import re
import subprocess
import tomllib

TASK_ID = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*\Z')
COMMIT_ID = re.compile(r'[0-9a-f]{40}\Z')


def safe_task(task):
    if not isinstance(task, str) or TASK_ID.fullmatch(task) is None:
        raise ValueError('unsafe task ID')
    return task


def _git(source, *args):
    return subprocess.run(['git', '-C', str(source), *args], check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout


def catalog(dataset, tasks=None):
    if not isinstance(dataset, dict) or set(dataset) != {'source_git', 'commit'}:
        raise ValueError('dataset requires exactly source_git and commit')
    source = Path(dataset['source_git']).resolve(strict=True)
    commit = dataset['commit']
    if not isinstance(commit, str) or COMMIT_ID.fullmatch(commit) is None:
        raise ValueError('dataset commit must be a full lowercase SHA')
    resolved = _git(source, 'rev-parse', '--verify', commit + '^{commit}').decode().strip()
    if resolved != commit:
        raise ValueError('dataset commit identity mismatch')
    names = _git(source, 'ls-tree', '--name-only', '-d', commit).decode().splitlines()
    selected = sorted(name for name in names if TASK_ID.fullmatch(name)) if tasks is None else sorted(set(tasks))
    result = []
    for task in selected:
        safe_task(task)
        rows = _git(source, 'ls-tree', '-r', commit, '--', task + '/').decode().splitlines()
        blobs = {}
        for row in rows:
            metadata, path = row.split('\t', 1)
            mode, kind, oid = metadata.split()
            if kind == 'blob' and mode in {'100644', '100755'}:
                blobs[path[len(task) + 1:]] = oid
        required = {'task.toml', 'instruction.md', 'tests/test.sh'}
        valid = required <= blobs.keys() and any(p.startswith('environment/') for p in blobs)
        if not valid:
            if tasks is None:
                continue
            raise ValueError(f'task package incomplete: {task}')
        raw = _git(source, 'show', f'{commit}:{task}/task.toml')
        metadata = tomllib.loads(raw.decode())
        result.append({'task': task, 'task_toml_sha256': hashlib.sha256(raw).hexdigest(),
                       'public_blobs': {p: oid for p, oid in blobs.items()
                                        if p in {'instruction.md', 'task.toml'} or p.startswith('environment/')},
                       'agent_timeout_sec': metadata.get('agent', {}).get('timeout_sec'),
                       'verifier_timeout_sec': metadata.get('verifier', {}).get('timeout_sec')})
    return {'schema': 'ga-dataset-catalog-v1', 'commit': commit, 'tasks': result}
