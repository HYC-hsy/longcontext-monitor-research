"""Read-only provider-ready working exposure audit for the single baseline."""

from __future__ import annotations

from collections import Counter
import json
import zipfile

from method_discovery import uc_path_control_archive as raw
from method_discovery.uc_cqs_kitex_baseline_prepare import ROOT, RUN_ID


def main() -> None:
    record = ROOT / 'records' / f'01_{RUN_ID}'
    dialogue = raw.rows(record / 'monitor/audit/dialogue.jsonl')
    view = [row for row in dialogue if row.get('event') == 'dcec_working_view']
    archive_path = record / 'bridge/gateway_control_raw.zip'
    with zipfile.ZipFile(archive_path) as archive:
        names = [name for name in archive.namelist() if name.endswith('.request.json')]
        working = [name for name in names
                   if b'<dcec_working_state>' in archive.read(name)]
        cqs = [name for name in names
               if b'Supervisory Control Continuity' in archive.read(name)]
    result = {
        'run_id': RUN_ID,
        'provider_ready_request_files_total': len(names),
        'provider_ready_requests_containing_dcec_working_state': len(working),
        'provider_ready_requests_containing_cqs_continuity': len(cqs),
        'dcec_working_view_audit_events': len(view),
        'view_status_distribution': dict(Counter(row.get('status') for row in view)),
        'truncated_view_events': sum(row.get('truncated') is True for row in view),
        'max_source_characters': max((row.get('source_characters') or 0 for row in view), default=0),
        'max_visible_characters': max((row.get('visible_characters') or 0 for row in view), default=0),
        'original_provider_ready_archive': 'bridge/gateway_control_raw.zip',
        'original_view_audit': 'monitor/audit/dialogue.jsonl',
        'note': 'request-local active context is removed from persistent provider_history after each request; gateway request bodies retain the actual sent input',
    }
    if len(working) != len(view) or cqs:
        raise RuntimeError('Provider-ready working exposure differs from audit or CQS appeared')
    raw.write(record / 'PROVIDER_INPUT_EXPOSURE_AUDIT.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
