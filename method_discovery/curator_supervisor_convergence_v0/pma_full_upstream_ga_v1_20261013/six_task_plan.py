"""Exact, still-unarmed identity contract for the 24-slot discovery panel."""

from __future__ import annotations

import re
from pathlib import Path

from .export_official_evaluator import SIX_TASKS


ORDER = (
    (1, "db-wal-recovery", 1, "A"), (2, "db-wal-recovery", 1, "B"),
    (3, "fix-code-vulnerability", 1, "B"), (4, "fix-code-vulnerability", 1, "A"),
    (5, "cobol-modernization", 1, "A"), (6, "cobol-modernization", 1, "B"),
    (7, "custom-memory-heap-crash", 1, "B"),
    (8, "custom-memory-heap-crash", 1, "A"),
    (9, "multi-source-data-merger", 1, "A"),
    (10, "multi-source-data-merger", 1, "B"),
    (11, "large-scale-text-editing", 1, "B"),
    (12, "large-scale-text-editing", 1, "A"),
    (13, "large-scale-text-editing", 2, "A"),
    (14, "large-scale-text-editing", 2, "B"),
    (15, "multi-source-data-merger", 2, "B"),
    (16, "multi-source-data-merger", 2, "A"),
    (17, "custom-memory-heap-crash", 2, "A"),
    (18, "custom-memory-heap-crash", 2, "B"),
    (19, "cobol-modernization", 2, "B"),
    (20, "cobol-modernization", 2, "A"),
    (21, "fix-code-vulnerability", 2, "A"),
    (22, "fix-code-vulnerability", 2, "B"),
    (23, "db-wal-recovery", 2, "B"), (24, "db-wal-recovery", 2, "A"),
)


def _identity(row: dict) -> tuple:
    return tuple(row.get(k) for k in ("order", "task", "repeat", "condition"))


def validate_plan(manifest: dict, granted: dict) -> list[dict]:
    if manifest.get('schema') == 'pma-ga-live-manifest-v4':
        arms = manifest.get('planned_order')
        bindings = granted.get('run_bindings')
        if (manifest.get('execution_authorized') is not False or
                granted.get('execution_authorized') is not True or
                not isinstance(arms, list) or len(arms) != 1 or
                not isinstance(bindings, list) or len(bindings) != 1 or
                granted.get('approved_arms') != arms or
                not isinstance(granted.get('output_root'), str)):
            raise RuntimeError('single-run authorization incomplete')
        row, bound = arms[0], bindings[0]
        if (set(row) != {'order', 'task', 'repeat', 'condition'} or
                row['order'] != 1 or type(row['repeat']) is not int or
                row['repeat'] < 1 or row['condition'] not in {'A', 'B'} or
                set(manifest.get('assets', {})) != {row['task']} or
                _identity(bound) != _identity(row) or
                bound.get('run_id') != granted.get('run_id') or
                bound.get('config_sha256') != manifest.get('config_sha256') or
                bound.get('batch_id') != granted.get('batch_id') or
                granted.get('config_sha256') != manifest.get('config_sha256')):
            raise RuntimeError('single-run binding differs from frozen plan')
        root = Path(bound.get('run_root', '')).resolve(strict=False)
        if (not bound.get('run_id') or not bound.get('batch_id') or
                root.parent != Path(granted['output_root']).resolve(strict=False)):
            raise RuntimeError('single-run root or identity invalid')
        return bindings
    if manifest.get("schema") == "pma-ga-live-manifest-v3":
        arms = manifest.get("planned_order")
        bindings = granted.get("run_bindings")
        if (manifest.get("execution_authorized") is not False or
                granted.get("execution_authorized") is not True or
                not isinstance(arms, list) or not arms or
                not isinstance(bindings, list) or len(bindings) != len(arms) or
                granted.get("approved_arms") != arms or
                {row.get("task") for row in arms} != set(manifest.get("assets", {})) or
                not isinstance(granted.get("output_root"), str)):
            raise RuntimeError("V3 plan or authorization incomplete")
        seen_slots = set()
        for number, row in enumerate(arms, 1):
            key = (row.get("task"), row.get("repeat"), row.get("condition"))
            if (set(row) != {"order", "task", "repeat", "condition"} or
                    row.get("order") != number or type(row.get("repeat")) is not int or
                    row["repeat"] < 1 or row["task"] not in SIX_TASKS or
                    row["condition"] not in {"A", "B"} or key in seen_slots):
                raise RuntimeError("V3 slot identity invalid or duplicated")
            seen_slots.add(key)
        if tuple(map(_identity, bindings)) != tuple(map(_identity, arms)):
            raise RuntimeError("V3 authorized order differs")
        batch_id, config_hash = granted.get("batch_id"), manifest.get("config_sha256")
        if (not isinstance(batch_id, str) or not batch_id or
                not isinstance(config_hash, str) or
                re.fullmatch(r"[0-9a-f]{64}", config_hash) is None or
                granted.get("config_sha256") != config_hash):
            raise RuntimeError("V3 batch identity invalid")
        output_root = Path(granted["output_root"]).resolve(strict=False)
        run_ids, roots = set(), set()
        for binding in bindings:
            run_id, run_root = binding.get("run_id"), binding.get("run_root")
            if (binding.get("batch_id") != batch_id or
                    binding.get("config_sha256") != config_hash or
                    not isinstance(run_id, str) or not run_id or
                    not isinstance(run_root, str) or not run_root):
                raise RuntimeError("V3 run binding incomplete")
            root = Path(run_root).resolve(strict=False)
            if (root.parent != output_root or root in roots or run_id in run_ids):
                raise RuntimeError("V3 run identity reused or outside output root")
            roots.add(root)
            run_ids.add(run_id)
        return bindings
    if (manifest.get("schema") != "pma-ga-live-manifest-v2" or
            manifest.get("execution_authorized") is not False or
            granted.get("execution_authorized") is not True):
        raise RuntimeError("six-task live authorization absent")
    arms = manifest.get("planned_order")
    bindings = granted.get("run_bindings")
    if (not isinstance(arms, list) or not isinstance(bindings, list) or
            tuple(map(_identity, arms)) != ORDER or
            tuple(map(_identity, bindings)) != ORDER or
            granted.get("approved_arms") != arms):
        raise RuntimeError("six-task order or complete approval differs")
    batch_id = granted.get("batch_id")
    config_hash = manifest.get("config_sha256")
    if (not isinstance(batch_id, str) or not batch_id or
            not isinstance(config_hash, str) or
            re.fullmatch(r"[0-9a-f]{64}", config_hash) is None or
            granted.get("config_sha256") != config_hash):
        raise RuntimeError("six-task batch or configuration identity missing")
    run_ids, roots = set(), set()
    for binding in bindings:
        run_id, run_root = binding.get("run_id"), binding.get("run_root")
        if (binding.get("batch_id") != batch_id or
                binding.get("config_sha256") != config_hash or
                not isinstance(run_id, str) or not run_id or
                not isinstance(run_root, str) or not run_root):
            raise RuntimeError("six-task run binding incomplete")
        root = Path(run_root).resolve(strict=False)
        if run_id in run_ids or root in roots:
            raise RuntimeError("six-task run identity reused")
        run_ids.add(run_id)
        roots.add(root)
    return bindings
