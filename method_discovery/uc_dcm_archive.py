"""Copy original DCM trial material and add mechanical locators; no model call."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

from method_discovery import uc_path_control_archive as raw
from method_discovery import uc_cfs_archive as cfs
from method_discovery.uc_dcm_freeze import ROOT, PLAN, CAMPAIGN


RECORDS = ROOT / 'records'
DCM_EVENTS = {
    'dcm_release_attempted', 'dcm_boundary_issued', 'dcm_post_boundary_tool',
    'dcm_release_confirmed', 'dcm_release_abandoned',
    'dcm_review_ended_with_boundary_pending',
}


def augment_dcm(slot, summary):
    destination = RECORDS / f"{slot['position']:02d}_{slot['run_id']}"
    dialogue = raw.rows(destination / 'monitor/audit/dialogue.jsonl')
    indexed = [(line, row) for line, row in enumerate(dialogue, 1)
               if row.get('event') in DCM_EVENTS]
    boundaries = {row.get('challenge_id'): row for _, row in indexed
                  if row.get('event') == 'dcm_boundary_issued'}
    handoffs = {row.get('review_id'): row.get('handoff') for row in dialogue
                if row.get('event') == 'root_frame_input'}
    tools = []
    for line, row in indexed:
        if row.get('event') != 'dcm_post_boundary_tool':
            continue
        issued = boundaries.get(row.get('challenge_id'), {}).get('issued_at_model_turn')
        turn = row.get('model_turn')
        relation = ('same_response' if isinstance(turn, int) and turn == issued else
                    'post_receipt' if isinstance(turn, int) and isinstance(issued, int)
                    and turn > issued else 'unknown')
        tools.append({'dialogue_line': line, 'review_id': row.get('review_id'),
                      'challenge_id': row.get('challenge_id'), 'tool_name': row.get('tool_name'),
                      'model_turn': turn, 'issued_at_model_turn': issued, 'relation': relation,
                      'task_path': row.get('task_path'), 'session_id': row.get('session_id'),
                      'command_locator': row.get('command_locator')})
    counts = Counter(row.get('event') for _, row in indexed)
    dispositions = Counter(row.get('disposition') for _, row in indexed
                           if row.get('event') in {'dcm_release_abandoned',
                                                   'dcm_review_ended_with_boundary_pending'})
    ordinary_inputs = [(line, row) for line, row in enumerate(dialogue, 1)
                       if row.get('event') == 'model_input']
    extra_requests = sum(any(row.get('review_id') == boundary.get('review_id')
                             and isinstance(row.get('turn'), int)
                             and isinstance(boundary.get('issued_at_model_turn'), int)
                             and row['turn'] > boundary['issued_at_model_turn']
                             for _, row in ordinary_inputs)
                         for boundary in boundaries.values())
    index = {
        'raw_dialogue': 'monitor/audit/dialogue.jsonl',
        'events': [{'dialogue_line': line, 'event': row.get('event'),
                    'review_id': row.get('review_id'), 'model_turn': row.get('model_turn'),
                    'challenge_id': row.get('challenge_id'), 'release_kind': row.get('release_kind'),
                    'frame': row.get('frame'), 'disposition': row.get('disposition'),
                    'handoff': handoffs.get(row.get('review_id'))}
                   for line, row in indexed],
        'post_boundary_tools': tools,
        'counts': dict(counts), 'dispositions': dict(dispositions),
        'boundary_scopes': dict(Counter(row.get('release_kind') for row in boundaries.values())),
        'same_response_tools': sum(item['relation'] == 'same_response' for item in tools),
        'post_receipt_file_reads': sum(item['relation'] == 'post_receipt'
                                       and item['tool_name'] == 'file_read' for item in tools),
        'post_receipt_code_runs': sum(item['relation'] == 'post_receipt'
                                      and item['tool_name'] == 'code_run' for item in tools),
        'extra_model_inputs_after_boundary_upper_bound': extra_requests,
        'interpretation': 'mechanical sequencing only; no measurement-quality verdict',
    }
    raw.write(destination / 'DCM_MECHANICAL_INDEX.json', index)
    summary['dcm_mechanical'] = {key: index[key] for key in (
        'counts', 'dispositions', 'boundary_scopes', 'same_response_tools',
        'post_receipt_file_reads', 'post_receipt_code_runs',
        'extra_model_inputs_after_boundary_upper_bound')}
    raw.write(destination / 'MECHANICAL_SUMMARY.json', summary)
    return summary


def main():
    plan = json.loads(PLAN.read_text(encoding='utf-8'))
    if len(plan['slots']) != 4 or [row['run_id'] for row in plan['slots']] != plan['run_order']:
        raise RuntimeError('Frozen DCM plan mismatch')
    if RECORDS.exists():
        raise RuntimeError('Archive records already exist; no overwrite')
    host = json.loads((CAMPAIGN / 'host_execution/progress.json').read_text(encoding='utf-8'))
    slots = plan['slots'][:len(host)]
    if [row['run_id'] for row in slots] != [row['run_id'] for row in host]:
        raise RuntimeError('Host progress differs from frozen order')
    raw.PLAN = PLAN
    raw.PLAN_ROOT = ROOT
    raw.CAMPAIGN = CAMPAIGN
    raw.RECORDS = RECORDS
    cfs.ROOT = ROOT
    cfs.PLAN = PLAN
    cfs.CAMPAIGN = CAMPAIGN
    cfs.RECORDS = RECORDS
    summaries = []
    for slot in slots:
        jobs = CAMPAIGN / 'jobs' / slot['run_id']
        if jobs.is_dir() and any(path.is_dir() for path in jobs.iterdir()):
            original = raw.record_one(slot)
            # Both arms have CFS enabled; this only selects the existing CFS
            # delta copier, without changing any archived condition label.
            cfs_slot = dict(slot, condition='CFS')
            cfs.augment(cfs_slot, original)
            summaries.append(augment_dcm(slot, original))
        else:
            summaries.append({'run_id': slot['run_id'], 'status': 'no_trial_artifact',
                              'host_progress': next(row for row in host if row['run_id'] == slot['run_id'])})
    cfs.copy_host()
    raw.write(ROOT / 'BLOCK_MECHANICAL_SUMMARY.json', {'records': summaries})
    print(json.dumps({'archived_runs': [row['run_id'] for row in summaries]}, indent=2))


if __name__ == '__main__':
    main()
