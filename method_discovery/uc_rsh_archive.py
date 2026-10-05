"""Archive original RSH trial bytes and add provenance locators; no execution."""

from __future__ import annotations

from collections import Counter
import json

from method_discovery import uc_dcm_archive as inherited
from method_discovery import uc_path_control_archive as raw
from method_discovery.uc_rsh_freeze import ROOT, PLAN, CAMPAIGN


RECORDS = ROOT / 'records'
RSH_EVENTS = {'rsh_root_started', 'rsh_direct_observation_visible',
              'rsh_horizon_emitted', 'rsh_root_ended'}


def augment(slot, summary):
    destination = RECORDS / f"{slot['position']:02d}_{slot['run_id']}"
    dialogue = raw.rows(destination / 'monitor/audit/dialogue.jsonl')
    indexed = [(line, row) for line, row in enumerate(dialogue, 1)
               if row.get('event') in RSH_EVENTS]
    if (slot['condition'] == 'CFS+DCM' and indexed):
        raise RuntimeError('RSH-off trial contains RSH events')
    horizons = [(line, row) for line, row in indexed
                if row.get('event') == 'rsh_horizon_emitted']
    event_index = {
        'raw_dialogue': 'monitor/audit/dialogue.jsonl',
        'events': [{
            'dialogue_line': line, 'event': row['event'],
            'review_id': row.get('review_id'),
            'root_identity': row.get('root_identity'),
            'challenge_id': row.get('challenge_id'),
            'tool_id': row.get('tool_id'),
            'call_event_locator': row.get('call_event_locator'),
            'result_event_locator': row.get('result_event_locator'),
        } for line, row in indexed],
        'horizons': [{
            'dialogue_line': line, 'review_id': row.get('review_id'),
            'challenge_id': row.get('challenge_id'),
            'root_identity': row.get('root_identity'),
            'fresh_task_file_read_count': row.get('fresh_task_file_read_count'),
            'fresh_code_run_count': row.get('fresh_code_run_count'),
            'fresh_original_task_read': row.get('fresh_original_task_read'),
            'full_original_task_in_root_input': row.get('full_original_task_in_root_input'),
            'cfs_situation': row.get('latest_full_cfs_situation'),
            'rendered_char_count': row.get('rendered_char_count'),
            'rendered_horizon_locator': f'monitor/audit/dialogue.jsonl#{line}/rendered_content',
            'fresh_task_file_reads': row.get('fresh_task_file_reads'),
            'fresh_supervisor_code_runs': row.get('fresh_supervisor_code_runs'),
        } for line, row in horizons],
    }
    raw.write(destination / 'RSH_MECHANICAL_INDEX.json', event_index)
    counts = Counter(row['event'] for _, row in indexed)
    summary['rsh_mechanical'] = {
        'event_counts': dict(counts),
        'horizon_count': len(horizons),
        'fresh_task_file_reads_total': sum(row.get('fresh_task_file_read_count') or 0
                                           for _, row in horizons),
        'fresh_supervisor_code_runs_total': sum(row.get('fresh_code_run_count') or 0
                                                for _, row in horizons),
        'fresh_original_task_reread_horizons': sum(bool(row.get('fresh_original_task_read'))
                                                  for _, row in horizons),
        'cfs_root_changed_paths_at_horizons': [
            (row.get('latest_full_cfs_situation') or {}).get('changed_path_count')
            for _, row in horizons],
        'cfs_task_code_run_rows_at_horizons': [
            (row.get('latest_full_cfs_situation') or {}).get('task_code_run_rows')
            for _, row in horizons],
    }
    raw.write(destination / 'MECHANICAL_SUMMARY.json', summary)
    return summary


def main():
    plan = json.loads(PLAN.read_text(encoding='utf-8'))
    host = json.loads((CAMPAIGN / 'host_execution/progress.json').read_text(encoding='utf-8'))
    if len(host) != 4 or [row['run_id'] for row in host] != plan['run_order']:
        raise RuntimeError('Host execution is not the frozen four-slot batch')
    if any(row['status'] not in {'completed', 'completed_budget'} for row in host):
        raise RuntimeError('Host execution contains an infrastructure stop')
    inherited.ROOT = ROOT
    inherited.PLAN = PLAN
    inherited.CAMPAIGN = CAMPAIGN
    inherited.RECORDS = RECORDS
    inherited.main()
    summaries = []
    for slot in plan['slots']:
        summary = json.loads((RECORDS / f"{slot['position']:02d}_{slot['run_id']}" /
                              'MECHANICAL_SUMMARY.json').read_text(encoding='utf-8'))
        summaries.append(augment(slot, summary))
    raw.write(ROOT / 'BLOCK_MECHANICAL_SUMMARY.json', {'records': summaries})
    print(json.dumps({'archived_runs': [row['run_id'] for row in summaries],
                      'rsh_horizons': [row['rsh_mechanical']['horizon_count']
                                       for row in summaries]}, indent=2))


if __name__ == '__main__':
    main()
