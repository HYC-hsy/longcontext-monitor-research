"""Read-only run audit; writes derived metrics beside this script, no API calls."""
import collections
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--run', default='clean-monitor-fyn-2.2.0-roadmap-literature-transfer-20260913-r1')
parser.add_argument('--trial', default='fyn-2.2.0-roadmap__moZMPPE')
parser.add_argument('--stop', default='2026-09-12T18:48:14Z')
parser.add_argument('--output', default='r1_observation_metrics.json')
args = parser.parse_args()
RUN = args.run
AGENT = ROOT / 'long_context_bench/output/clean_monitor_real_tasks/fyn-2.2.0-roadmap/jobs' / RUN / args.trial / 'agent'


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


audit = AGENT / 'monitor/monitor_private/audit'
dialogue = rows(audit / 'dialogue.jsonl')
progress = rows(audit / 'progress.jsonl')
events = rows(AGENT / 'research_events.jsonl')
synopsis = rows(AGENT / 'monitor/task_evidence/synopsis.jsonl')
calls = [r for r in dialogue if r['event'] == 'tool_call']
contexts = []
for call in calls:
    if call['name'] != 'review_context':
        continue
    result = next(r for r in dialogue if r['event'] == 'tool_result' and r['tool_id'] == call['tool_id'])
    contexts.append({'id': call['tool_id'], 'timestamp': call['timestamp'],
                     'arguments': json.loads(call['arguments']),
                     'returned_context_characters': len(result['data'].get('context', '')),
                     'error': result['data'].get('error')})

accepted = {r['request_id']: r['usage'] for r in progress if r['event'] == 'request_usage'}
visible = {r['request_id']: r.get('usage', {}) for r in progress if r['event'] == 'response_text_contract'}
task_usage = [r['payload'] for r in events if r['event_type'] == 'provider_usage' and r['payload'].get('call_type') == 'task_agent']


def sum_usage(items, keys):
    items = list(items)
    return {'responses_with_usage': len(items), **{key: sum(r.get(key, 0) or 0 for r in items) for key in keys}}


report = {
    'run_id': RUN, 'status': 'stopped_diagnostic_protocol_failure',
    'stop_utc': args.stop, 'native_score': None,
    'last_task_turn': max(r.get('task_turn', 0) for r in synopsis),
    'tool_counts': dict(collections.Counter(r['name'] for r in calls)),
    'review_context_calls': contexts,
    'interventions': [{'timestamp': r['timestamp'], 'tool_id': r['tool_id'], 'arguments': json.loads(r['arguments'])}
                      for r in calls if r['name'] == 'intervene'],
    'monitor_accepted_usage': sum_usage(accepted.values(), ['input_tokens', 'output_tokens']),
    'monitor_visible_completed_usage_including_rejected': sum_usage(visible.values(), ['input_tokens', 'output_tokens']),
    'task_usage': sum_usage(task_usage, ['input_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens', 'output_tokens']),
    'text_mismatches': [r for r in progress if r['event'] == 'response_text_contract' and r.get('mismatch')],
    'ignored_tool_only_whitespace_count': sum(r['event'] == 'response_text_contract' and bool(r.get('ignored_tool_only_whitespace')) for r in progress),
    'decision_attention_count': sum(r['event'] == 'decision_attention' for r in dialogue),
    'runtime_failures': [r for r in rows(AGENT / 'monitor/runtime_receipts.jsonl') if r.get('kind') == 'failure'],
    'unsuccessful_requests': [r for r in progress if r['event'] == 'request_finished' and r['outcome'] != 'success'],
    'limits': ['No final native evaluation; early diagnostic stop.',
               'Visible usage is not a complete provider bill; aborted/unreported calls may be missing.',
               'Two candidates enabled together; no independent causal attribution.'],
}
destination = Path(__file__).with_name(args.output)
destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: v for k, v in report.items() if k not in ('interventions', 'text_mismatches', 'unsuccessful_requests')}, ensure_ascii=False, indent=2))
