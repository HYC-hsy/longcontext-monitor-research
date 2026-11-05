"""Exact two-slot GA + predictive PMA pilot; separate from the old 24-slot panel."""

from __future__ import annotations

from pathlib import Path


SCHEMA = 'pma-ga-live-two-task-v1'
ORDER = ((1, 'rstan-to-pystan', 1, 'B'),
         (2, 'nginx-request-logging', 1, 'B'))


def identity(row: dict) -> tuple:
    return tuple(row.get(k) for k in ('order', 'task', 'repeat', 'condition'))


def validate_plan(manifest: dict, authorized: dict) -> list[dict]:
    if (manifest.get('schema') != SCHEMA or
            manifest.get('execution_authorized') is not False or
            authorized.get('execution_authorized') is not True):
        raise RuntimeError('two-task authorization absent')
    arms, bindings = manifest.get('planned_order'), authorized.get('run_bindings')
    if (not isinstance(arms, list) or not isinstance(bindings, list) or
            tuple(map(identity, arms)) != ORDER or
            tuple(map(identity, bindings)) != ORDER or
            authorized.get('approved_arms') != arms):
        raise RuntimeError('two-task order or approval differs')
    if (authorized.get('config_sha256') != manifest.get('config_sha256') or
            authorized.get('audited_code_commit') != manifest.get('code_commit')):
        raise RuntimeError('two-task code/config binding differs')
    run_ids, roots = set(), set()
    for row in bindings:
        root = Path(row.get('run_root', '')).resolve(strict=False)
        if (row.get('run_id') in run_ids or root in roots or
                not isinstance(row.get('run_id'), str) or not row['run_id'] or
                not isinstance(row.get('run_root'), str) or not row['run_root'] or
                row.get('config_sha256') != manifest['config_sha256']):
            raise RuntimeError('two-task run binding incomplete or reused')
        run_ids.add(row['run_id'])
        roots.add(root)
    return bindings
