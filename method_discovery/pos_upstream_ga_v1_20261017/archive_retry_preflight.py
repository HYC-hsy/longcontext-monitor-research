"""Publish bounded old-call and retained v4 evidence, without replaying either."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from .archive_formal_v6_stop import public
from .classify_task_returns import summarize
from .collect_native_shared import secrets_from_profile
from .test_profile_worker_integration import FAKE_KEY


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def provenance(path: Path) -> dict:
    raw = path.read_bytes()
    return {'source_path': str(path), 'source_bytes': len(raw),
            'source_sha256': sha(raw)}


def records(path: Path, wanted: set[int]) -> list[dict]:
    result = []
    with path.open('rb') as stream:
        for number, raw in enumerate(stream, 1):
            if number in wanted:
                result.append({'source_line': number, 'source_line_sha256': sha(raw),
                               'record': json.loads(raw)})
    if {row['source_line'] for row in result} != wanted:
        raise RuntimeError('required original lines unavailable')
    return result


def final_call(old: Path) -> dict:
    run = old / '04_write-compressor/runs/pos-390e3b64fc144eba'
    trial = next(p for p in (run / 'jobs').glob('*/*')
                 if (p / 'agent/research_events.jsonl').is_file())
    task = trial / 'agent/research_events.jsonl'
    host = run / 'control/pos_archive/events.host.jsonl'
    stdout = trial / 'agent/agent_stdout.log'
    task_rows = []
    for row in records(task, set(range(745, 752))):
        event = row['record']
        payload = event['payload']
        kind = event['event_type']
        safe = {}
        allowed = {
            'provider_request_ready': ('content_availability', 'sha256', 'bytes',
                                       'model', 'stream', 'message_count',
                                       'tool_count', 'max_retries', 'call_type'),
            'provider_request_attempt': ('attempt',),
            'provider_usage': ('input_tokens', 'output_tokens',
                               'cache_creation_input_tokens',
                               'cache_read_input_tokens', 'raw_usage'),
            'provider_response_content': ('attempt', 'parsed_visible_blocks',
                                          'hidden_thinking_excluded'),
            'provider_response': ('attempt', 'status_code', 'outcome'),
            'action_selected': ('tool_names', 'tool_call_ids', 'response_sha256'),
            'termination': ('result', 'error'),
        }
        for key in allowed[kind]:
            if key in payload:
                safe[key] = payload[key]
        task_rows.append({'source_line': row['source_line'],
                          'source_line_sha256': row['source_line_sha256'],
                          'time': event.get('timestamp'),
                          'event': kind, 'call_id': event.get('llm_call_id'),
                          'payload': safe})
    expected = task_rows[0]['call_id']
    if any(row['call_id'] != expected for row in task_rows[:-1]):
        raise RuntimeError('final Task call identity mismatch')
    host_rows = []
    for row in records(host, {663, 664}):
        event = row['record']
        payload = event['payload']
        host_rows.append({'source_line': row['source_line'],
            'source_line_sha256': row['source_line_sha256'],
            'kind': event['kind'], 'turn': payload.get('turn'),
            'public_content': payload.get('content') if
                event['kind'] == 'decision_selected' else None,
            'action_count': len(payload.get('actions', [])),
            'tool_result_count': len(payload.get('tool_results', [])),
            'provider_error': payload.get('provider_error', 'unknown')})
    stdout_rows = []
    with stdout.open('rb') as stream:
        for number, raw in enumerate(stream, 1):
            if number in range(5318, 5324):
                stdout_rows.append({'source_line': number,
                                    'source_line_sha256': sha(raw),
                                    'text': raw.decode('utf-8', 'replace').rstrip('\r\n')})
    if len(stdout_rows) != 6:
        raise RuntimeError('compressor observation lines unavailable')
    return {'schema': 'pos-ga-old-compressor-last-task-call-v1',
            'call_id': expected, 'task_source': provenance(task),
            'host_source': provenance(host),
            'stdout_source': provenance(stdout),
            'task_events': task_rows, 'host_events': host_rows,
            'prior_compressor_observation': stdout_rows,
            'raw_stop_reason': 'unknown_not_archived',
            'raw_message_stop': 'unknown_not_archived',
            'underlying_stream_interruption_cause': 'unknown'}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--old-run', type=Path, required=True)
    parser.add_argument('--v4', type=Path, required=True)
    parser.add_argument('--target', type=Path, required=True)
    parser.add_argument('--task-profile', type=Path, required=True)
    args = parser.parse_args()
    old = args.old_run.resolve(strict=True)
    v4 = args.v4.resolve(strict=True)
    target = args.target
    target.mkdir(parents=True, exist_ok=False)
    secrets = secrets_from_profile(args.task_profile) + [FAKE_KEY]
    small = final_call(old)
    selected: dict[str, tuple[Path | None, bytes | None]] = {
        'old_compressor/final_task_call.json':
            (None, (json.dumps(small, ensure_ascii=False, indent=2) + '\n').encode()),
    }
    trial = next(p for p in (old / '04_write-compressor/runs/pos-390e3b64fc144eba/jobs').glob('*/*')
                 if (p / 'agent/research_events.jsonl').is_file())
    classification = summarize(trial / 'agent/research_events.jsonl')
    final = classification['calls'][small['call_id']]
    compact = {key: value for key, value in classification.items() if key != 'calls'}
    compact['final_call_id'] = small['call_id']
    compact['final_call'] = final
    selected['old_compressor/return_classification.json'] = (
        None, (json.dumps(compact, ensure_ascii=False, indent=2) + '\n').encode())
    command = [sys.executable, '-B', '-m', 'unittest', '-v',
               'method_discovery.pos_upstream_ga_v1_20261017.test_task_return_classification']
    checked = subprocess.run(command, capture_output=True, text=True,
                             encoding='utf-8', timeout=30)
    if checked.returncode != 0:
        raise RuntimeError('offline classification tests failed')
    selected['offline_tests/command.json'] = (None,
        (json.dumps({'argv': command, 'return_code': checked.returncode},
                    ensure_ascii=False, indent=2) + '\n').encode())
    selected['offline_tests/stdout.txt'] = (None, checked.stdout.encode())
    selected['offline_tests/stderr.txt'] = (None, checked.stderr.encode())
    for name, path in {
        'v4/docker.stdout.txt': v4 / 'docker.stdout.txt',
        'v4/docker.stderr.txt': v4 / 'docker.stderr.txt',
        'v4/profile_integration_result.json':
            v4 / 'control/pos_archive/profile_integration_result.json',
        'v4/isolation_identity.json': v4 / 'bundle/isolation_identity.json',
        'v4/events.bridge.jsonl':
            v4 / 'control/pos_archive/events.bridge.jsonl',
        'v4/timeout/events.bridge.jsonl':
            v4 / 'control/pos_archive/timeout_case/events.bridge.jsonl',
        'v4/timeout/events.provider.jsonl':
            v4 / 'control/pos_archive/timeout_case/events.provider.jsonl',
        'v4/CAPTURE_INDEX.json':
            v4 / 'control/pos_archive/public_provider/CAPTURE_INDEX.json',
    }.items():
        selected[name] = (path, None)
    rows = []
    for name, (path, generated) in selected.items():
        raw = path.read_bytes() if path is not None else generated
        assert raw is not None
        data, redactions = public(raw, secrets)
        if any(secret.encode() in data for secret in secrets):
            raise RuntimeError('secret remains in ' + name)
        dest = target / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        rows.append({'path': name, 'source_path': str(path) if path else
                     'generated_from_recorded_source_lines',
                     'source_bytes': len(raw), 'source_sha256': sha(raw),
                     'public_bytes': len(data), 'public_sha256': sha(data),
                     'redactions': redactions})
    identity = {}
    source = v4 / 'bundle/source'
    for name in ('pos_bridge.py', 'llmcore.py', 'research_runtime.py',
                 'pos_runtime/worker.py', 'pos_runtime/episode.py'):
        identity[name] = provenance(source / name)
    output = target / 'SOURCE_AND_PUBLIC_HASHES.json'
    output.write_text(json.dumps({'schema':'pos-ga-preflight-evidence-v1',
        'files':rows, 'v4_actual_bundle': identity},
        ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    for row in rows:
        if sha((target / row['path']).read_bytes()) != row['public_sha256']:
            raise RuntimeError('public readback mismatch')
    print(json.dumps({'files': len(rows), 'redactions': sum(r['redactions'] for r in rows),
                      'index_sha256': sha(output.read_bytes())}))


if __name__ == '__main__':
    main()
