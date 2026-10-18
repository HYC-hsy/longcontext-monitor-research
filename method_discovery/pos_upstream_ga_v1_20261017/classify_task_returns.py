"""Offline classification of captured Task returns; never change runtime events."""
from __future__ import annotations

from collections import Counter, defaultdict
import json
from pathlib import Path


INCOMPLETE_MARKER = '[!!! 流异常中断'
MAX_TOKENS_MARKER = '[!!! Response truncated: max_tokens !!!]'


def classify_call(events: list[dict]) -> dict:
    """Require positive terminal evidence before calling a response complete."""
    kinds = defaultdict(list)
    for event in events:
        kinds[event['event_type']].append(event.get('payload') or {})
    ready = kinds['provider_request_ready']
    attempts = kinds['provider_request_attempt']
    responses = kinds['provider_response']
    contents = kinds['provider_response_content']
    visible = '\n'.join(
        block.get('text', '')
        for event in contents
        for block in event.get('parsed_visible_blocks', [])
        if isinstance(block, dict) and block.get('type') == 'text'
    )
    last = responses[-1] if responses else {}
    outcome = last.get('outcome')
    stop_reason = last.get('stop_reason')
    message_stop = last.get('message_stop')
    if MAX_TOKENS_MARKER in visible or stop_reason == 'max_tokens':
        category = 'max_tokens'
    elif INCOMPLETE_MARKER in visible:
        category = 'incomplete_stream_marker'
    elif outcome in {'http_error', 'retryable_http_error',
                     'transport_error', 'retryable_transport_error'} or (
            '!!!Error:' in visible or '[Error:' in visible):
        category = 'explicit_provider_error'
    elif (outcome == 'success' and message_stop is True and
          isinstance(stop_reason, str) and stop_reason not in {'', 'max_tokens'}
          and contents):
        category = 'complete_valid_return'
    else:
        category = 'terminal_unproven_or_unknown'
    return {'logical_request': bool(ready),
            'observable_http_attempts': len(attempts),
            'return_records': len(responses),
            'last_captured_outcome': outcome,
            'stop_reason': stop_reason if stop_reason is not None else 'unknown',
            'message_stop': message_stop if message_stop is not None else 'unknown',
            'category': category}


def summarize(path: Path) -> dict:
    by_call = defaultdict(list)
    with path.open(encoding='utf-8') as stream:
        for line in stream:
            event = json.loads(line)
            call_id = event.get('llm_call_id')
            if call_id:
                by_call[call_id].append(event)
    classified = {call_id: classify_call(events)
                  for call_id, events in by_call.items()
                  if any(event['event_type'] == 'provider_request_ready'
                         for event in events)}
    categories = Counter(row['category'] for row in classified.values())
    return {'logical_requests': len(classified),
            'observable_http_attempts': sum(row['observable_http_attempts']
                                             for row in classified.values()),
            'return_records': sum(row['return_records']
                                  for row in classified.values()),
            'categories': dict(categories), 'calls': classified}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('events', type=Path)
    args = parser.parse_args()
    print(json.dumps(summarize(args.events), ensure_ascii=False, indent=2))
