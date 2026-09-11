"""Read-only, zero-API inventory and descriptive paired-result checks.

Prints JSON to stdout. Does not read hidden tests, credentials or raw traces.
No runnable experiment manifest is produced.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[1]
PANEL = (
    'pyg-2.3.0-roadmap', 'fbr-2.43.0-roadmap',
    'ktx-0.13.0-roadmap', 'rat-0.22.0-roadmap',
    'opt-4.4.0-roadmap', 'fyn-2.2.0-roadmap',
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(root=ROOT):
    registry = root / 'method_discovery/r0_real_tasks/tasks.jsonl'
    rows = [json.loads(line) for line in registry.read_text(
        encoding='utf-8-sig').splitlines() if line.strip()]
    by_id = {row['global_task_id']: row for row in rows}
    if len(by_id) != len(rows):
        raise ValueError('Duplicate registry task IDs')
    sources = defaultdict(Counter)
    families = defaultdict(set)
    for row in rows:
        counts = sources[row['source_key']]
        counts['total'] += 1
        counts[row['split']] += 1
        counts['historical_evaluation_available'] += bool(
            row['historical_execution']['completion_evaluation_available'])
        if row['source_key'] == 'roadmapbench':
            # Prefix is only a provisional grouping, not verified genealogy.
            prefix = row['global_task_id'].split(':', 1)[1].split('-', 1)[0]
            families[prefix].add(row['split'])
    cards = []
    for name in PANEL:
        row = by_id['roadmapbench:' + name]
        if row['split'] != 'method_dev':
            raise ValueError('Panel must remain entirely method_dev')
        directory = root / 'long_context_bench/.cache/m12_roadmap_tasks' / name
        config = directory / 'task.toml'
        instruction = directory / 'instruction.md'
        data = tomllib.loads(config.read_text(encoding='utf-8-sig'))
        cards.append({
            'task_id': row['global_task_id'], 'split': row['split'],
            'old_panel': row['panel'],
            'selection_reason': 'historical_continuity_diagnostic' if name.startswith(
                'fyn-') else 'existing_roadmap_dev_pilot',
            'description': data['metadata']['description'],
            'public_instruction_sha256': sha(instruction),
            'task_config_sha256': sha(config),
            'instruction_bytes': instruction.stat().st_size,
            'declared_environment': data['environment'],
            'declared_agent_timeout_sec': data['agent']['timeout_sec'],
            'declared_verifier_timeout_sec': data['verifier']['timeout_sec'],
            'historical_run_id': row['historical_execution']['run_id'],
            'exposure': 'historically_run; subsequent_exposure_not_fully_enumerated',
            'image_digest': None, 'offline_readiness': 'not_checked',
            'native_success_rule': 'requires_adapter_audit',
        })
    return {
        'schema': 'paper-static-inventory/1',
        'status': 'draft_not_execution_authorized',
        'registry_sha256': sha(registry),
        'source_counts': dict(sorted(sources.items())),
        'split_counts': dict(Counter(row['split'] for row in rows)),
        'cross_split_roadmap_prefixes_unverified': {
            key: sorted(value) for key, value in sorted(families.items())
            if len(value) > 1},
        'panel': cards,
        'claims': {'api_checked': False, 'image_checked': False,
                   'method_effect_measured': False, 'holdout_answers_read': False},
    }


def paired_summary(rows, baseline, treatment):
    """One native binary outcome per task/condition; repeats require a new spec.

    Rows need task_id, condition, status, success. An evaluated outcome must
    use a boolean, never an arbitrary partial reward converted with bool().
    Unpaired/failed runs remain visible. No significance or causal claim.
    """
    if baseline == treatment:
        raise ValueError('Conditions must differ')
    entries = {}
    for row in rows:
        if row['condition'] not in (baseline, treatment):
            continue
        key = (row['task_id'], row['condition'])
        if key in entries:
            raise ValueError('Duplicate task/condition; repetitions not supported')
        if row['status'] == 'evaluated' and type(row.get('success')) is not bool:
            raise ValueError('Evaluated success must be an explicit boolean')
        entries[key] = row
    tasks = sorted({task for task, _ in entries})
    wins = losses = ties = base_success = treated_success = 0
    incomplete = []
    for task in tasks:
        pair = [entries.get((task, condition)) for condition in (baseline, treatment)]
        if any(row is None or row['status'] != 'evaluated' for row in pair):
            incomplete.append({'task_id': task, 'statuses': [
                row['status'] if row else 'missing' for row in pair]})
            continue
        before, after = [row['success'] for row in pair]
        base_success += before
        treated_success += after
        wins += after and not before
        losses += before and not after
        ties += before == after
    count = wins + losses + ties
    return {
        'complete_pairs': count, 'wins': wins, 'losses': losses, 'ties': ties,
        'baseline_successes': base_success, 'treatment_successes': treated_success,
        'paired_success_delta': (wins - losses) / count if count else None,
        'incomplete_pairs': incomplete,
        'scope': 'descriptive_complete_pairs_only; not intention-to-treat or inference',
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path)
    parser.add_argument('--baseline', default='G0')
    parser.add_argument('--treatment', default='G1')
    args = parser.parse_args()
    report = paired_summary(json.loads(args.results.read_text(encoding='utf-8-sig')),
                            args.baseline, args.treatment) if args.results else inventory()
    print(json.dumps(report, ensure_ascii=False, indent=2))
