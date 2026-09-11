"""Offline evaluator metadata and explicitly scoped source fingerprints.

No evaluator execution, model imports, credentials, or test assertions read.
The evaluator wrapper is inspected by researchers, never exported online.
"""
import ast
import hashlib
import json
import math
from pathlib import Path
import re

from paper_protocol_audit import PANEL, ROOT, sha


def normalize_reward(record, expected_phases):
    """Derived full-score indicator; not a substitute for run validity checks."""
    value = record.get('reward')
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError('Missing or invalid native reward')
    passed, total = record.get('phases_passed'), record.get('total_phases')
    if (type(passed) is not int or type(total) is not int
            or total != expected_phases or not 0 <= passed <= total):
        raise ValueError('Invalid or mismatched phase counts')
    success = passed == total
    if success != (value == 1):
        raise ValueError('Full-score and phase-count disagreement')
    return {'success': success, 'partial_score': value,
            'success_definition': 'all_native_phases_passed/1',
            'run_validity': 'must_be_checked_separately'}


def inspect_scoring(path):
    source = path.read_text(encoding='utf-8-sig')
    match = re.search(r'^weights\s*=\s*(\[[^\n]+\])', source, re.MULTILINE)
    if not match:
        raise ValueError('Unrecognized scoring wrapper')
    weights = ast.literal_eval(match.group(1))
    total = re.search(r'"total_phases":\s*(\d+)', source)
    if (not total or len(weights) != int(total.group(1))
            or any(type(w) not in (int, float) or w <= 0 for w in weights)):
        raise ValueError('Scoring metadata mismatch')
    if 'sum(w * p for w, p in zip(weights, passed))' not in source:
        raise ValueError('Unknown aggregation; manual audit required')
    if 'print(score / total)' not in source:
        raise ValueError('Unknown normalization; manual audit required')
    return {'wrapper_sha256': sha(path), 'weights': weights,
            'total_phases': len(weights), 'weight_sum': sum(weights),
            'native_metric': 'weighted_binary_phase_pass_fraction',
            'derived_success': 'all_native_phases_passed',
            'online_visibility': 'forbidden; researcher_post_termination_only'}


def snapshot(root=ROOT):
    scores = {}
    for task in PANEL:
        path = root / 'long_context_bench/.cache/m12_roadmap_tasks' / task / 'tests/test.sh'
        scores['roadmapbench:' + task] = inspect_scoring(path)
    core = root / 'GenericAgent-main/monitor_agent_core'
    selected = list(core.glob('*.py')) + [root / name for name in (
        'GenericAgent-main/ga_monitor_adapter.py',
        'method_discovery/clean_monitor_prepare_real_task_gate.py',
        'method_discovery/prepare_tool_feedback_run.py',
        'long_context_bench/adapters/harbor_ga_agent.py',
        'long_context_bench/adapters/isolated_setup.py',
        'long_context_bench/adapters/isolated_transport.py',
        'long_context_bench/scripts/isolated_run_bundle.py',
        'long_context_bench/scripts/run_ultralong_m12_proofs.py',
    )]
    files = {p.relative_to(root).as_posix(): sha(p) for p in sorted(selected)}
    digest = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    return {'schema': 'paper-scoring-provenance/1', 'scoring': scores,
            'source_scope': 'monitor_core_and_selected_integration_only',
            'source_files': files, 'scope_sha256': digest,
            'complete_runnable_snapshot': False,
            'excluded': ['credentials', 'task_agent_other_sources', 'dependencies',
                         'container_images', 'runtime_configuration', 'test_assertions'],
            'warning': 'Fingerprint detects changes; does not preserve uncommitted source or prove readiness.'}


if __name__ == '__main__':
    print(json.dumps(snapshot(), ensure_ascii=False, indent=2))
