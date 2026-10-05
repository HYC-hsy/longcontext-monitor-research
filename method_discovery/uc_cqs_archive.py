"""Copy CQS Stage-1 raw trials and add action/surface locators; no model or verifier."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

from method_discovery import uc_path_control_archive as raw
from method_discovery import uc_cfs_archive as cfs
from method_discovery import uc_dcm_archive as dcm
from method_discovery.uc_cqs_freeze import ROOT, PLAN, CAMPAIGN


RECORDS = ROOT / 'records'
CQS_EVENTS = {'cqs_state_updated', 'cqs_state_cleared', 'cqs_surface_emitted'}


def augment_cqs(slot, summary):
    destination = RECORDS / f"{slot['position']:02d}_{slot['run_id']}"
    dialogue = raw.rows(destination / 'monitor/audit/dialogue.jsonl')
    actions = []
    surfaces = []
    working = Counter()
    for line, row in enumerate(dialogue, 1):
        event = row.get('event')
        if event in CQS_EVENTS:
            item = {'dialogue_line': line, 'review_id': row.get('review_id'),
                    'model_turn': row.get('model_turn'), 'event': event,
                    'active': row.get('active'), 'source': row.get('source'),
                    'source_action': row.get('source_action'),
                    'action_locator': row.get('action_locator'),
                    'rationale_locator': row.get('rationale_locator'),
                    'rendered_char_count': row.get('rendered_char_count')}
            (surfaces if event == 'cqs_surface_emitted' else actions).append(item)
        if event == 'tool_call' and row.get('name') in {'file_read', 'file_write', 'file_patch'}:
            try:
                args = json.loads(row.get('arguments') or '{}')
            except (ValueError, TypeError):
                args = {}
            if str(args.get('path', '')).replace('\\', '/').strip('/') == 'monitor/working.md':
                working[row['name']] += 1
    counts = Counter(row.get('event') for row in dialogue)
    source_counts = Counter(row.get('source') for row in dialogue
                            if row.get('event') == 'cqs_state_updated')
    index = {
        'raw_dialogue': 'monitor/audit/dialogue.jsonl',
        'raw_public_feedback': 'monitor/task_evidence/public_events.jsonl',
        'action_events': actions, 'surface_events': surfaces,
        'review_model_outputs': [{'dialogue_line': line, 'review_id': row.get('review_id'),
                                  'turn': row.get('turn')}
                                 for line, row in enumerate(dialogue, 1)
                                 if row.get('event') == 'model_output'],
        'working_tool_counts': dict(working),
        'cqs_event_counts': {kind: counts[kind] for kind in sorted(CQS_EVENTS)},
        'state_sources': dict(source_counts),
        'dcec_working_view_count': counts['dcec_working_view'],
        'interpretation': 'mechanical action/surface locators only; no concern or outcome classification',
    }
    raw.write(destination / 'CQS_MECHANICAL_INDEX.json', index)
    summary['cqs_mechanical'] = {key: index[key] for key in (
        'working_tool_counts', 'cqs_event_counts', 'state_sources', 'dcec_working_view_count')}
    raw.write(destination / 'MECHANICAL_SUMMARY.json', summary)
    return summary


def main():
    plan = json.loads(PLAN.read_text(encoding='utf-8'))
    if len(plan['slots']) != 2 or [row['run_id'] for row in plan['slots']] != plan['run_order']:
        raise RuntimeError('Frozen CQS two-slot plan mismatch')
    if RECORDS.exists():
        raise RuntimeError('Archive records already exist; no overwrite')
    host = json.loads((CAMPAIGN / 'host_execution/progress.json').read_text(encoding='utf-8'))
    if ([row['run_id'] for row in host] != plan['run_order']
            or any(row.get('status') not in {'completed', 'completed_budget'} for row in host)):
        raise RuntimeError('Host terminal progress is incomplete or differs from frozen order')
    raw.PLAN = PLAN
    raw.PLAN_ROOT = ROOT
    raw.CAMPAIGN = CAMPAIGN
    raw.RECORDS = RECORDS
    cfs.ROOT = ROOT
    cfs.PLAN = PLAN
    cfs.CAMPAIGN = CAMPAIGN
    cfs.RECORDS = RECORDS
    dcm.RECORDS = RECORDS
    summaries = []
    for slot in plan['slots']:
        summary = raw.record_one(slot)
        cfs.augment(dict(slot, condition='CFS'), summary)
        dcm.augment_dcm(slot, summary)
        summaries.append(augment_cqs(slot, summary))
    cfs.copy_host()
    raw.write(ROOT / 'STAGE1_MECHANICAL_SUMMARY.json', {'records': summaries})
    print(json.dumps({'archived_runs': [row['run_id'] for row in summaries],
                      'record_count': len(summaries)}, indent=2))


if __name__ == '__main__':
    main()
