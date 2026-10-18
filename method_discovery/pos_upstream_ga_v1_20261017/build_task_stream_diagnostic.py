"""Make bounded public projections of retained Task requests, never raw SSE."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import runpy
import subprocess
import sys
from pathlib import Path

from .collect_native_shared import secrets_from_profile


SPECS = (
    ('new_sampler_failure', 'E:/LongContext/pos_retry_two_20261018_v1/01_adaptive-rejection-sampler', -1,
     'llm_52fed9b17c3b46d385e71b64abee390e'),
    ('new_sampler_previous', 'E:/LongContext/pos_retry_two_20261018_v1/01_adaptive-rejection-sampler', -2, None),
    ('old_compressor_failure', 'E:/LongContext/pos_final_two_20261018_v1/04_write-compressor', -1,
     'llm_bc687359ba8e48069a30003b28066867'),
    ('old_compressor_previous', 'E:/LongContext/pos_final_two_20261018_v1/04_write-compressor', -2, None),
    ('pos_nginx_last_complete', 'E:/LongContext/pos_four_live_20261018_v6/01_nginx-request-logging', -1, None),
    ('pos_sqlite_last_complete', 'E:/LongContext/pos_final_two_20261018_v1/03_sqlite-with-gcov', -1, None),
    ('pma_nginx_last_complete', 'E:/pma12_native_r1_20261015/18-nginx-request-logging-B-r1', -1, None),
    ('pma_sqlite_last_complete', 'E:/pma12_native_r1_20261015/22-sqlite-with-gcov-B-r1', -1, None),
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_id(path: Path) -> dict:
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': sha(data)}


def function_ids(path: Path) -> dict:
    source = path.read_text(encoding='utf-8')
    tree = ast.parse(source)
    wanted = ('_parse_claude_sse', '_stream_with_retry')
    return {node.name: {'lines': [node.lineno, node.end_lineno],
                        'sha256': sha(ast.get_source_segment(source, node).encode())}
            for node in tree.body if isinstance(node, ast.FunctionDef)
            and node.name in wanted}


def public_tail(blocks, secrets) -> str:
    value = '\n'.join(str(block.get('text', '')) for block in blocks
                      if isinstance(block, dict) and block.get('type') == 'text')[-360:]
    for secret in secrets:
        value = value.replace(secret, '[REDACTED]')
    return value


def one(label: str, base: Path, offset: int, expected: str | None, secrets) -> dict:
    event_paths = list(base.rglob('research_events.jsonl'))
    if len(event_paths) != 1:
        raise RuntimeError(f'{label}: Task event source is not unique')
    path = event_paths[0]
    rows = []
    for line, raw in enumerate(path.read_bytes().splitlines(), 1):
        if raw.strip():
            rows.append((line, json.loads(raw)))
    requests = [(line, row) for line, row in rows
                if row.get('event_type') == 'provider_request_ready'
                and row.get('payload', {}).get('call_type') == 'task_agent']
    req_line, request = requests[offset]
    call_id = request['llm_call_id']
    if expected and call_id != expected:
        raise RuntimeError(f'{label}: call ID mismatch')
    events = [(line, row) for line, row in rows if row.get('llm_call_id') == call_id]
    by_kind = {}
    for line, row in events:
        by_kind.setdefault(row['event_type'], []).append((line, row))
    def last(kind):
        return by_kind.get(kind, [])[-1] if by_kind.get(kind) else (None, None)
    attempt_line, attempt = last('provider_request_attempt')
    usage_line, usage = last('provider_usage')
    content_line, content = last('provider_response_content')
    response_line, response = last('provider_response')
    action_line, action = last('action_selected')
    if response is None or content is None:
        raise RuntimeError(f'{label}: no captured return')
    payload = request['payload']
    wire = payload.get('content') or {}
    blocks = content.get('payload', {}).get('parsed_visible_blocks') or []
    tail = public_tail(blocks, secrets)
    tool_blocks = [b for b in blocks if isinstance(b, dict)
                   and b.get('type') == 'tool_use']
    stage = next(base.glob('runs/*/control/ga_stage'))
    profile_path = stage / 'mykey.py'
    profile = runpy.run_path(str(profile_path))['native_claude_cc_vibe_opus48']
    terminal_paths = list(base.rglob('task_terminal.json'))
    terminal = json.loads(terminal_paths[0].read_text(encoding='utf-8')) if len(terminal_paths) == 1 else {}
    stdout_paths = list(base.rglob('agent_stdout.log'))
    stdout = stdout_paths[0] if len(stdout_paths) == 1 else None
    debug_lines = stdout.read_bytes().decode('utf-8', errors='replace').splitlines() if stdout else []
    result = {
        'schema': 'task-stream-call-projection-v1', 'label': label,
        'run_id': request.get('run_id'), 'task_id': request.get('task_id'),
        'call_id': call_id, 'call_ordinal': len(requests) + offset + 1,
        'source': file_id(path),
        'source_lines': {'request_ready': req_line, 'attempt': attempt_line,
                         'usage': usage_line, 'parsed_visible_return': content_line,
                         'provider_response': response_line, 'action_selected': action_line},
        'timestamps_utc': {
            'request_ready': request.get('timestamp'),
            'send_attempt': attempt.get('timestamp') if attempt else None,
            'first_raw_sse_event': None,
            'parsed_visible_return': content.get('timestamp'),
            'response_record': response.get('timestamp')},
        'request': {
            'model': payload.get('model'), 'protocol': 'NativeClaudeSession Anthropic messages/SSE',
            'stream': payload.get('stream'),
            'thinking': wire.get('thinking', wire.get('thinking_setting')),
            'max_tokens': wire.get('max_tokens'),
            'temperature_present': 'temperature' in wire,
            'temperature_value_if_present': wire.get('temperature'),
            'message_count': payload.get('message_count'),
            'request_capture_bytes': payload.get('bytes'),
            'request_capture_sha256': payload.get('sha256'),
            'tool_schema_sha256': sha(json.dumps(wire.get('tools'),
                sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()),
            'tool_schema_count': payload.get('tool_count'),
            'endpoint_sha256': payload.get('provider_url_sha256'),
            'local_call_type': payload.get('call_type')},
        'transport': {
            'staged_profile': file_id(profile_path),
            'configured_connect_timeout_seconds': profile.get('timeout', 5),
            'configured_read_timeout_seconds': profile.get('read_timeout', 40),
            'configured_total_response_timeout_seconds': profile.get('total_response_timeout', 0),
            'configured_max_retries': profile.get('max_retries', 4),
            'observable_attempts': len(by_kind.get('provider_request_attempt', [])),
            'http_status': response.get('payload', {}).get('status_code'),
            'response_content_type_saved': None,
            'upstream_request_id_saved': None,
            'provider_response_outcome_record': response.get('payload', {}).get('outcome')},
        'visible_return': {
            'tail': tail,
            'parsed_visible_block_types': [b.get('type') for b in blocks if isinstance(b, dict)],
            'parsed_tool_call_count': len(tool_blocks),
            'selected_tool_call_count': len(action.get('payload', {}).get('tool_names', [])) if action else None,
            'incomplete_stream_marker': '流异常中断' in tail,
            'max_tokens_marker': 'Response truncated: max_tokens' in tail,
            'raw_message_stop_saved': None,
            'raw_stop_reason_saved': None,
            'task_terminal': terminal.get('result')},
        'usage': {'combined_saved': usage.get('payload', {}) if usage else None,
                  'field_origin': {
                      'input_tokens': 'message_start unless overwritten by message_delta; raw event not saved',
                      'cache_creation_input_tokens': 'message_start unless overwritten by message_delta; raw event not saved',
                      'cache_read_input_tokens': 'message_start unless overwritten by message_delta; raw event not saved',
                      'output_tokens': 'message_start or message_delta override; raw event provenance not saved'},
                  'final_message_delta_observed_in_raw_evidence': None,
                  'note': ('Parser merges message_start with message_delta. '
                           'The combined event does not preserve per-field provenance; '
                           'output_tokens=0 is not proof of zero generation.')},
        'deployed_source': {
            'llmcore': file_id(stage / 'llmcore.py'),
            'agent_loop': file_id(stage / 'agent_loop.py'),
            'task_parser_and_retry_functions': function_ids(stage / 'llmcore.py')},
        'preparse_evidence_inventory': {
            'raw_sse_files_in_run': [str(p) for p in base.rglob('*.sse')
                                     if 'bundle' not in p.parts and 'ga_stage' not in p.parts],
            'isolated_transport_logs': [file_id(p) for p in base.rglob('isolated_transport.log')],
            'client_parser_debug_log': file_id(stdout) if stdout else None,
            'client_parser_json_error_line_numbers': [i for i, line in enumerate(debug_lines, 1)
                                                       if '[SSE] JSON parse error:' in line],
            'client_parser_warning_line_numbers': [i for i, line in enumerate(debug_lines, 1)
                                                    if '[WARN]' in line and '流异常中断' in line],
            'client_debug_scope': 'Parsed diagnostics; no preserved raw SSE event bytes or per-frame timestamps',
            'proxy_raw_stream_log': None},
    }
    if offset == -2 and result['visible_return']['incomplete_stream_marker']:
        raise RuntimeError(f'{label}: previous call not normal')
    if 'last_complete' in label and (result['visible_return']['incomplete_stream_marker']
                                    or result['visible_return']['max_tokens_marker']):
        raise RuntimeError(f'{label}: selected response not complete')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    secrets = secrets_from_profile(Path('E:/LongContext/GenericAgent-main/mykey.py'))
    args.output.mkdir(parents=True, exist_ok=False)
    parts = []
    endpoints = set()
    for label, source, offset, expected in SPECS:
        row = one(label, Path(source), offset, expected, secrets)
        endpoints.add(row['request']['endpoint_sha256'])
        path = args.output / f'{label}.json'
        data = (json.dumps(row, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
        if len(data) > 1_000_000:
            raise RuntimeError('projection exceeds 1 MB')
        path.write_bytes(data)
        parts.append({'path': path.name, 'bytes': len(data), 'sha256': sha(data),
                      'source_sha256': row['source']['sha256']})
    test = subprocess.run([sys.executable, '-B', '-m', 'unittest',
        'method_discovery.pos_upstream_ga_v1_20261017.test_task_sse_diagnosis', '-v'],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    test_path = args.output / 'synthetic_test_output.txt'
    test_path.write_bytes(test.stdout)
    parts.append({'path': test_path.name, 'bytes': len(test.stdout),
                  'sha256': sha(test.stdout), 'synthetic': True, 'exit_code': test.returncode})
    if test.returncode:
        raise RuntimeError('synthetic test failed; output retained')
    index = {'schema': 'task-stream-diagnostic-index-v1', 'calls': len(SPECS),
             'selection': ('Failure calls fixed by ID; their immediately prior Task calls; '
                           'last complete Task call from each PoS nginx/sqlite success; '
                           'PMA same-task reward-1 nginx/sqlite runs, last complete Task call.'),
             'endpoint_fingerprints_all_equal': len(endpoints) == 1,
             'raw_sse_recovered': False, 'parts': parts}
    index_path = args.output / 'INDEX.json'
    index_path.write_bytes((json.dumps(index, ensure_ascii=False, indent=2)+'\n').encode())
    for part in parts:
        data = (args.output / part['path']).read_bytes()
        if len(data) != part['bytes'] or sha(data) != part['sha256']:
            raise RuntimeError('public readback mismatch')
        if any(secret.encode() in data for secret in secrets):
            raise RuntimeError('private profile value in public projection')
    print(json.dumps({'calls': len(SPECS), 'files': len(parts)+1,
                      'endpoint_fingerprints_all_equal': len(endpoints) == 1,
                      'test_exit_code': test.returncode,
                      'index_sha256': sha(index_path.read_bytes())}))


if __name__ == '__main__':
    main()
