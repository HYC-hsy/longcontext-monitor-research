"""Post-termination raw archive and mechanical B+J trace index; no models."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import zipfile

from method_discovery import uc_path_control_archive as raw
from method_discovery.curator_supervisor_convergence_v0.crs_v01_fyne_gate_infra_replacement_20261007 import archive_result as inherited


ROOT = Path(__file__).resolve().parent
RUN_ID = 'crs-rhr-v0-fyne-bj-r1'
CAMPAIGN = Path(r'E:\LongContext\long_context_bench\output\crs_rhr_fyne_mechanism_gate')
DESTINATION = ROOT / 'archive' / 'r1'


def rows(path):
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]


def build_index():
    dialogue = rows(DESTINATION / 'monitor/audit/dialogue.jsonl')
    named = [dict(event, locator=f'monitor/audit/dialogue.jsonl#{number}')
             for number, event in enumerate(dialogue, 1)]
    crs = [row for row in named if str(row.get('event', '')).startswith('crs_')]
    rhr = [row for row in named if str(row.get('event', '')).startswith('rhr_')]
    calls = [row for row in named if row.get('event') == 'tool_call'
             and row.get('name') == 'allow_complete']
    call_ids = {row.get('tool_id') for row in calls}
    errors = [row for row in named if row.get('event') == 'tool_result'
              and row.get('tool_id') in call_ids
              and isinstance(row.get('data'), dict)
              and row['data'].get('status') == 'error']
    visible = [row for row in named if row.get('event') == 'model_input'
               and 'Root Horizon Reset' in json.dumps(row, ensure_ascii=False)]
    zip_path = DESTINATION / 'bridge/gateway_control_raw.zip'
    request_counts = {'total': 0, 'monitor': 0, 'task': 0,
                      'root_flat_crs_schema': 0, 'local_ordinary_schema': 0,
                      'provider_visible_crs': 0, 'provider_visible_rhr': 0,
                      'provider_visible_citable_handles': 0}
    actual_visible = []
    with zipfile.ZipFile(zip_path) as zipped:
        for name in zipped.namelist():
            if not name.endswith('.request.json'):
                continue
            bytes_ = zipped.read(name)
            request = json.loads(bytes_)
            request_counts['total'] += 1
            allow = next((tool for tool in request.get('tools') or []
                          if tool.get('name') == 'allow_complete'), None)
            if allow is None:
                request_counts['task'] += 1
                continue
            request_counts['monitor'] += 1
            schema = json.dumps(allow, ensure_ascii=False)
            request_counts['root_flat_crs_schema' if 'release_blocking_state' in schema
                           else 'local_ordinary_schema'] += 1
            body = json.dumps({'system': request.get('system'),
                               'messages': request.get('messages')}, ensure_ascii=False)
            request_counts['provider_visible_crs'] += 'Contrastive Release State' in body
            request_counts['provider_visible_citable_handles'] += 'obs:code:' in body or 'obs:read:' in body
            if 'Root Horizon Reset' in body:
                request_counts['provider_visible_rhr'] += 1
                actual_visible.append({
                    'gateway_zip_entry': name,
                    'request_sha256': hashlib.sha256(bytes_).hexdigest(),
                    'root_horizon_digests': sorted(set(re.findall(
                        r'root_horizon_digest=([0-9a-f]{64})', body))),
                    'exact_request_source': 'bridge/gateway_control_raw.zip',
                })
    result = {
        'schema': 'crs-rhr-fyne-mechanical-index/1',
        'run_id': RUN_ID,
        'semantic_scoring': None,
        'root_allow_complete_calls': calls,
        'crs_events': crs,
        'rhr_events': rhr,
        'crs_validation_errors': errors,
        'rhr_model_input_locators': [row['locator'] for row in visible],
        'provider_visible_rhr_requests': actual_visible,
        'provider_request_visibility_counts': request_counts,
        'gateway_raw_zip_sha256': raw.digest(zip_path),
        'distinct_focal_state_digests': sorted({row.get('state_digest')
                                                for row in crs if row.get('state_digest')}),
        'distinct_root_horizon_digests': sorted({row.get('root_horizon_digest')
                                                 for row in rhr if row.get('root_horizon_digest')}),
    }
    raw.write(DESTINATION / 'RHR_TRACE_INDEX.json', result)
    summary_path = DESTINATION / 'MECHANICAL_SUMMARY.json'
    summary = json.loads(summary_path.read_text(encoding='utf-8'))
    counts = lambda items: {event: sum(row['event'] == event for row in items)
                            for event in sorted({row['event'] for row in items})}
    summary['condition'] = 'crs_v02_plus_rhr_v0'
    public = rows(DESTINATION / 'monitor/task_evidence/public_events.jsonl')
    summary['task_turns'] = max((row.get('task_turn', 0) or 0 for row in public), default=0)
    summary['root_handoff_count'] = sum(row.get('event') == 'root_frame_input' for row in dialogue)
    summary['echo_submissions'] = sum(row.get('event') == 'curator_echo_submission_pending'
                                      for row in dialogue)
    summary['echo_activations'] = sum(row.get('event') == 'curator_echo_delivery_confirmed'
                                      for row in dialogue)
    summary['echo_consumptions'] = sum(row.get('event') == 'curator_echo_consumed'
                                       for row in dialogue)
    summary['task_book_mutations'] = sum(row.get('event') == 'curator_task_book_mutated'
                                         for row in dialogue)
    summary['crs_rhr_mechanics'] = {
        'root_allow_complete_calls': len(calls),
        'crs_events': counts(crs),
        'rhr_events': counts(rhr),
        'crs_validation_errors': len(errors),
        'distinct_focal_state_digests': result['distinct_focal_state_digests'],
        'distinct_root_horizon_digests': result['distinct_root_horizon_digests'],
        'provider_request_visibility_counts': request_counts,
        'trace_index_sha256': raw.digest(DESTINATION / 'RHR_TRACE_INDEX.json'),
    }
    raw.write(summary_path, summary)


def main():
    manifest = json.loads((CAMPAIGN / 'runs' / RUN_ID / 'manifest.json').read_text(encoding='utf-8'))
    if (manifest.get('run_id') != RUN_ID or manifest.get('valid') is not True
            or manifest.get('trial_outcome') != 'agent_phase_completed'):
        raise RuntimeError('Expected this one completed, valid agent phase')
    inherited.RUN_ID = RUN_ID
    inherited.ROOT = ROOT
    inherited.CAMPAIGN = CAMPAIGN
    inherited.DESTINATION = DESTINATION
    inherited.STAGING = Path(r'E:\crs_rhr_fyne_archive_stage_r1')
    inherited.EXTRACTION = Path(r'E:\crs_rhr_fyne_private_20261007\final_workspace_extract_r1')
    inherited.main()
    build_index()
    print(json.dumps({'archive': str(DESTINATION),
                      'rhr_index': str(DESTINATION / 'RHR_TRACE_INDEX.json')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
