"""Index frozen CRS trial events mechanically; no semantic scoring."""

from __future__ import annotations

from collections import Counter
import hashlib
import json

from method_discovery import uc_path_control_archive as raw
from method_discovery.curator_supervisor_convergence_v0.crs_v01_fyne_gate_infra_replacement3_20261007 import archive_invalid


def main() -> None:
    archive = archive_invalid.DESTINATION
    dialogue = raw.rows(archive / 'monitor/audit/dialogue.jsonl')
    progress = raw.rows(archive / 'monitor/audit/progress.jsonl')
    reviews = raw.rows(archive / 'monitor/audit/reviews.jsonl')
    results = {row.get('tool_id'): (line, row)
               for line, row in enumerate(dialogue, 1)
               if row.get('event') == 'tool_result'}
    allows = []
    for line, row in enumerate(dialogue, 1):
        if row.get('event') != 'tool_call' or row.get('name') != 'allow_complete':
            continue
        arguments = row.get('arguments')
        canonical = json.dumps(arguments, sort_keys=True, ensure_ascii=False,
                               separators=(',', ':')).encode('utf-8')
        receipt_line, receipt = results.get(row.get('tool_id'), (None, {}))
        data = receipt.get('data') or {}
        allows.append({
            'dialogue_line': line, 'review_id': row.get('review_id'),
            'model_turn': row.get('turn'), 'tool_id': row.get('tool_id'),
            'arguments_sha256': hashlib.sha256(canonical).hexdigest(),
            'tool_result_line': receipt_line,
            'status': data.get('status') if isinstance(data, dict) else None,
            'mechanical_error': data.get('error') if isinstance(data, dict) else None,
        })
    crs_events = [{'dialogue_line': line, 'event': row.get('event'),
                   'review_id': row.get('review_id')}
                  for line, row in enumerate(dialogue, 1)
                  if 'crs' in str(row.get('event', '')).lower()]
    index = {
        'schema': 'crs-v01-mechanical-trace-index/1',
        'run_id': archive_invalid.RUN_ID,
        'semantic_scoring': None,
        'dialogue_rows': len(dialogue),
        'progress_rows': len(progress),
        'review_rows': len(reviews),
        'root_reviews': [{'review_line': line, 'action': row.get('action'),
                          'handoff': row.get('handoff')}
                         for line, row in enumerate(reviews, 1)
                         if row.get('frame') == 'root'],
        'root_allow_complete_calls': allows,
        'crs_events': crs_events,
        'model_error_events': [{'dialogue_line': line, 'review_id': row.get('review_id'),
                                'error_type': row.get('error_type')}
                               for line, row in enumerate(dialogue, 1)
                               if row.get('event') == 'model_error'],
        'exit_tool_result_reasons': dict(Counter(row.get('reason') for row in dialogue
                                                  if row.get('event') == 'exit_tool_results')),
        'gateway_raw_request_response_archive': {
            'path': 'bridge/gateway_control_raw.zip',
            'sha256': raw.digest(archive / 'bridge/gateway_control_raw.zip')},
    }
    raw.write(archive / 'CRS_TRACE_INDEX.json', index)
    print(json.dumps({'root_allow_complete_calls': len(allows),
                      'crs_events': len(crs_events),
                      'root_reviews': len(index['root_reviews']),
                      'model_errors': len(index['model_error_events'])}, ensure_ascii=False))


if __name__ == '__main__':
    main()
