"""Export bounded public evidence from one same-run B/Harbor fake fixture."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .archive_live_six_task import private_values, redact
from .stateful_certification import verify_evidence


def collect(source: Path, target: Path, task_profile: Path,
            pma_profile: Path) -> dict:
    source = source.resolve(strict=True)
    identity = json.loads((source / 'run_identity.json').read_text(encoding='utf-8'))
    run = Path(identity['run_root']).resolve(strict=True)
    if not run.is_relative_to(source) or (source / 'authorization.json').exists():
        raise RuntimeError('stateful fixture root or temporary authorization invalid')
    if target.exists():
        raise FileExistsError(target)
    target.mkdir(parents=True)
    jobs = list((run / 'jobs').rglob('research_events.jsonl'))
    if len(jobs) != 1:
        raise RuntimeError('stateful Task event log not unique')
    mapping = {name: run / 'archive' / name for name in (
        'live_result.json', 'prepared.json', 'agent_start_identity.json',
        'agent_end_native.json', 'stateful_task_terminal.json',
        'writer_termination_check.json', 'control_process_registry.json',
        'native_test_execution.json', 'native_reports_checked.json',
        'native_evaluator_uploaded.json', 'verification_released.json')}
    mapping.update({
        'execution_identity.json': source / 'execution_identity.json',
        'fake_authorization_removed.json': source / 'fake_authorization_removed.json',
        'synthetic_test.sh': run / 'public_task/tests/test.sh',
        'worker_ready.json': run / 'host_private/worker_ready.json',
        'worker_exit.json': run / 'host_private/worker_exit.json',
        'host_events.jsonl': run / 'host_private/archive/events.jsonl',
        'research_events.jsonl': jobs[0],
    })
    secrets = private_values(task_profile, pma_profile)
    files = []
    for name, path in sorted(mapping.items()):
        raw = path.read_bytes()
        public, removed = redact(raw, secrets)
        if len(public) > 1000000:
            raise RuntimeError('stateful public evidence requires record-boundary splitting')
        output = target / name
        with output.open('xb') as stream:
            stream.write(public)
        files.append({'path': name, 'raw_sha256': hashlib.sha256(raw).hexdigest(),
                      'public_sha256': hashlib.sha256(public).hexdigest(),
                      'public_bytes': len(public), 'redactions': removed})
    requests = sorted((run / 'archive/fake_provider_requests').glob('*.json'))
    if len(requests) != 2:
        raise RuntimeError('stateful fake Task generation count differs')
    summary = {'request_count': len(requests), 'reminder_counts': [], 'requests': []}
    for path in requests:
        raw = path.read_bytes()
        body = json.loads(raw)['body']
        messages = body['messages']
        count = raw.count(b'Auxiliary memory information')
        summary['reminder_counts'].append(count)
        summary['requests'].append({'private_request_sha256': hashlib.sha256(raw).hexdigest(),
            'model': body['model'], 'stream': body['stream'],
            'message_count': len(messages), 'tool_schema_count': len(body.get('tools', [])),
            'has_tool_result': any(any(isinstance(part, dict) and
                part.get('type') == 'tool_result' for part in message.get('content', []))
                for message in messages)})
    public = json.dumps(summary, sort_keys=True, indent=2).encode('utf-8')
    (target / 'task_requests.json').write_bytes(public)
    files.append({'path': 'task_requests.json', 'raw_sha256': None,
                  'public_sha256': hashlib.sha256(public).hexdigest(),
                  'public_bytes': len(public), 'redactions': 0,
                  'kind': 'derived_from_private_fake_request_bytes'})
    certification = verify_evidence(target, require_committed=False)
    (target / 'FILE_HASHES.json').write_text(json.dumps({
        'schema': 'stateful-single-fake-public-v1', 'files': files,
        'certification': certification}, indent=2), encoding='utf-8')
    return {'files': len(files), 'run_id': certification['run_id'],
            'task_requests': certification['task_requests']}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--task-profile-file', type=Path, required=True)
    parser.add_argument('--pma-profile-file', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(collect(args.source, args.output,
        args.task_profile_file, args.pma_profile_file)))


if __name__ == '__main__':
    main()
