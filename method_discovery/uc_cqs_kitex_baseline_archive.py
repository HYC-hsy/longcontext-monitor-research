"""Archive the single diagnostic baseline using existing raw/CFS/DCM collectors."""

from __future__ import annotations

from collections import Counter
import json

from method_discovery import uc_path_control_archive as raw
from method_discovery import uc_cfs_archive as cfs
from method_discovery import uc_dcm_archive as dcm
from method_discovery.uc_cqs_kitex_baseline_prepare import ROOT, CAMPAIGN


def main() -> None:
    plan_path = ROOT / 'PLAN.json'
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    if len(plan['slots']) != 1 or plan['run_order'] != [plan['slots'][0]['run_id']]:
        raise RuntimeError('Single frozen baseline identity mismatch')
    slot = plan['slots'][0]
    host = CAMPAIGN / 'host_execution/progress.json'
    progress = json.loads(host.read_text(encoding='utf-8'))
    if len(progress) != 1 or progress[0]['run_id'] != slot['run_id']:
        raise RuntimeError('Host terminal record mismatch')
    if progress[0]['status'] not in {'completed', 'completed_budget'}:
        raise RuntimeError('Trial not in an archivable terminal state')
    records = ROOT / 'records'
    if records.exists():
        raise RuntimeError('Archive already exists; do not overwrite')
    raw.PLAN = plan_path
    raw.PLAN_ROOT = ROOT
    raw.CAMPAIGN = CAMPAIGN
    raw.RECORDS = records
    cfs.ROOT = ROOT
    cfs.PLAN = plan_path
    cfs.CAMPAIGN = CAMPAIGN
    cfs.RECORDS = records
    dcm.RECORDS = records
    summary = raw.record_one(slot)
    cfs.augment(slot, summary)
    dcm.augment_dcm(slot, summary)
    destination = records / f"01_{slot['run_id']}"
    dialogue = raw.rows(destination / 'monitor/audit/dialogue.jsonl')
    counts = Counter(row.get('event') for row in dialogue)
    cqs_events = {key: counts[key] for key in ('cqs_state_updated', 'cqs_state_cleared',
                                               'cqs_surface_emitted')}
    if any(cqs_events.values()):
        raise RuntimeError('CQS-off baseline unexpectedly emitted CQS events')
    working_tools = Counter()
    for row in dialogue:
        if row.get('event') != 'tool_call' or row.get('name') not in {'file_read', 'file_write', 'file_patch'}:
            continue
        try:
            args = json.loads(row.get('arguments') or '{}')
        except (TypeError, ValueError):
            args = {}
        if str(args.get('path', '')).replace('\\', '/').strip('/') == 'monitor/working.md':
            working_tools[row['name']] += 1
    working = {
        'automatic_dcec_working_view_events': counts['dcec_working_view'],
        'automatic_root_working_view_events': counts['root_working_view'],
        'cqs_events': cqs_events,
        'working_tool_counts': dict(working_tools),
        'view_event_locators': [{'dialogue_line': i, 'review_id': row.get('review_id'),
                                 'event': row.get('event'), 'chars': row.get('visible_chars')}
                                for i, row in enumerate(dialogue, 1)
                                if row.get('event') in {'dcec_working_view', 'root_working_view'}],
        'raw_dialogue': 'monitor/audit/dialogue.jsonl',
        'raw_provider_history': 'monitor/audit/provider_history.json',
        'raw_working': 'monitor/private/working.md',
    }
    raw.write(destination / 'WORKING_EXPOSURE_INDEX.json', working)
    summary['working_exposure'] = {key: working[key] for key in (
        'automatic_dcec_working_view_events', 'automatic_root_working_view_events',
        'cqs_events', 'working_tool_counts')}
    raw.write(destination / 'MECHANICAL_SUMMARY.json', summary)
    cfs.copy_host()
    raw.write(ROOT / 'BASELINE_MECHANICAL_SUMMARY.json', {'records': [summary]})
    print(json.dumps({'archived_run': slot['run_id'], 'record': str(destination),
                      'working_views': counts['dcec_working_view'],
                      'cqs_events': cqs_events}, indent=2))


if __name__ == '__main__':
    main()
