"""Read-only monitor telemetry coverage, never a clean-effect leaderboard.

Outputs aggregates only: no prompts, messages, credentials or hidden answers.
Old trials are compatibility fixtures, not paired method evidence.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JOBS = ROOT / 'long_context_bench/output/clean_monitor_real_tasks/fyn-2.2.0-roadmap/jobs'
RUNS = (
    'clean-monitor-fyn-2.2.0-roadmap-phase1-tool-feedback-base-20260911-r1',
    'clean-monitor-fyn-2.2.0-roadmap-phase1-tool-feedback-treatment-20260911-r2',
    'clean-monitor-fyn-2.2.0-roadmap-phase1-feedback-b-20260911-r3',
)


def read_jsonl(path):
    if not path.exists():
        return [], {'present': False, 'valid_rows': 0, 'invalid_lines': [], 'sha256': None}
    records, invalid = [], []
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for line_number, raw in enumerate(stream, 1):
            digest.update(raw)
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
                if not isinstance(row, dict):
                    raise ValueError('Non-object record')
                records.append(row)
            except (ValueError, UnicodeError):
                invalid.append(line_number)
    return records, {'present': True, 'valid_rows': len(records),
                     'invalid_lines': invalid, 'sha256': digest.hexdigest()}


def usage_totals(records):
    totals, available = {}, {}
    for field in ('input_tokens', 'output_tokens', 'total_tokens'):
        values = [r[field] for r in records if type(r.get(field)) is int and r[field] >= 0]
        totals[field] = sum(values) if values else None
        available[field] = len(values)
    return {'reported_fields_sum': totals, 'rows_with_valid_field': available,
            'rows': len(records), 'is_complete_billed_cost': False}


def analyze(progress, usage, receipts):
    starts, finishes, by_request = {}, {}, {}
    duplicate_starts = duplicate_finishes = unkeyed_usage = 0
    conflicting_usage = set()
    for row in progress:
        kind, key = row.get('event'), row.get('request_id')
        if kind == 'request_started' and key:
            duplicate_starts += key in starts
            starts[key] = row
        if kind == 'request_finished' and key:
            duplicate_finishes += key in finishes
            finishes[key] = row
        if kind == 'request_usage':
            if not key or not isinstance(row.get('usage'), dict):
                unkeyed_usage += 1
                continue
            value = row['usage']
            if key in by_request and by_request[key] != value:
                conflicting_usage.add(key)
            else:
                by_request[key] = value
    usable = {key: value for key, value in by_request.items()
              if key not in conflicting_usage and key in starts}
    token_complete = {
        key for key, value in usable.items()
        if all(type(value.get(f)) is int and value[f] >= 0
               for f in ('input_tokens', 'output_tokens'))}
    interventions = [r for r in receipts if r.get('kind') == 'intervention']
    handed = [r for r in interventions
              if r.get('delivery') == 'handed_to_task_interrupt_interface']
    return {
        'progress_events': dict(Counter(r.get('event', '<missing>') for r in progress)),
        'request_starts': len(starts), 'request_finishes': len(finishes),
        'started_without_finish': len(set(starts) - set(finishes)),
        'finished_without_start': len(set(finishes) - set(starts)),
        'duplicate_start_records': duplicate_starts,
        'duplicate_finish_records': duplicate_finishes,
        'requests_with_usage_event': len(usable),
        'requests_with_input_and_output': len(token_complete),
        'usage_coverage_fraction': len(token_complete) / len(starts) if starts else None,
        'started_without_complete_usage': len(set(starts) - token_complete),
        'usage_without_start': len(set(by_request) - set(starts)),
        'unkeyed_usage_records': unkeyed_usage,
        'conflicting_usage_request_count': len(conflicting_usage),
        'progress_usage': usage_totals(list(usable.values())),
        'provider_usage_separate_crosscheck_do_not_add': usage_totals(usage),
        'request_outcomes': dict(Counter(r.get('outcome', '<missing>') for r in finishes.values())),
        'interventions': len(interventions), 'interface_handoffs': len(handed),
        'handoffs_with_timestamp_field': sum(type(r.get('timestamp')) in (int, float) for r in handed),
        'behavioral_uptake': None, 'end_to_end_delivery_latency': None,
        'task_agent_usage': None, 'dollars': None,
        'missing_metric_reason': 'Actor/receipt semantic joins and billing not implemented; unknown is not zero.',
    }


def audit_trial(trial):
    monitor = trial / 'agent/monitor'
    audit = monitor / 'monitor_private/audit'
    files = {'progress': audit / 'progress.jsonl',
             'usage': audit / 'provider_usage.jsonl',
             'receipts': monitor / 'runtime_receipts.jsonl'}
    loaded = {name: read_jsonl(path) for name, path in files.items()}
    data = analyze(*(loaded[key][0] for key in ('progress', 'usage', 'receipts')))
    return {'trial': trial.name, 'scope': 'historical_log_fixture_only',
            'eligible_for_clean_effect_table': False,
            'files': {key: value[1] for key, value in loaded.items()},
            'counts_describe_readable_records_only': True, 'coverage': data}


def report():
    runs = []
    for run in RUNS:
        directory = JOBS / run
        trials = sorted(p for p in directory.glob('fyn-*') if p.is_dir())
        if len(trials) != 1:
            runs.append({'run': run, 'status': 'missing_or_ambiguous_trial',
                         'trial_count': len(trials)})
            continue
        runs.append({'run': run, **audit_trial(trials[0])})
    return {'schema': 'historical-monitor-coverage/1',
            'selection': 'fixed base, treatment and transport-failure fixtures; not score selection',
            'api_called': False, 'runs': runs}


if __name__ == '__main__':
    print(json.dumps(report(), ensure_ascii=False, indent=2))
