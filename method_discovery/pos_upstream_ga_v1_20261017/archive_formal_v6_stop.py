"""Archive the stopped v6 formal sequence without resuming any execution."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.archive_live_six_task import UnsafePublicProjection, redact
from .collect_native_shared import secrets_from_profile


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def remove_transport_identity(value):
    """Remove provider-generated device/session identity, not model-visible text."""
    if isinstance(value, dict):
        return {key: ('[REDACTED_PROVIDER_USER_ID]' if key == 'user_id' else
                remove_transport_identity(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [remove_transport_identity(item) for item in value]
    return value


def public(raw: bytes, secrets: list[str]) -> tuple[bytes, int]:
    projected, count = redact(raw, secrets)
    text = projected.decode('utf-8')
    try:
        records = [json.loads(line) for line in text.splitlines() if line.strip()]
        if records:
            before = sum(line.count('"user_id"') for line in text.splitlines())
            records = [remove_transport_identity(row) for row in records]
            text = '\n'.join(json.dumps(row, ensure_ascii=False) for row in records) + '\n'
            count += before
    except ValueError:
        pass  # Non-JSON logs have already passed through the shared redactor.
    if any(secret in text for secret in secrets):
        raise RuntimeError('private profile value remains')
    return text.encode('utf-8'), count


def mapping(source: Path) -> dict[str, Path]:
    first = source / '01_nginx-request-logging'
    second = source / '02_adaptive-rejection-sampler'
    identity = json.loads((first / 'run_identity.json').read_text(encoding='utf-8'))
    run = Path(identity['run_root']).resolve(strict=True)
    if not run.is_relative_to(first.resolve(strict=True)):
        raise RuntimeError('first run root outside its task directory')
    trials = list((run / 'jobs').glob('*/*'))
    trials = [p for p in trials if (p / 'agent/research_events.jsonl').is_file()]
    if len(trials) != 1:
        raise RuntimeError('first task trial not unique')
    trial = trials[0]
    selected = {}
    for index, base in ((1, first), (2, second)):
        prefix = f'{index:02d}'
        for name in ('manifest.json', 'plan.json', 'run_identity.json',
                     'serial_start.json', 'serial_result.json',
                     'authorization_removed.json', 'serial_stdout.txt',
                     'serial_stderr.txt', 'batch_result.json'):
            path = base / name
            if path.is_file():
                selected[f'{prefix}/{name}'] = path
        cap = base / 'provider_public/CAPTURE_INDEX.json'
        if cap.is_file():
            selected[f'{prefix}/CAPTURE_INDEX.json'] = cap
    for name in ('agent_start_identity.json', 'agent_end_native.json',
                 'control_process_registry.json', 'harbor.stderr.log',
                 'harbor.stdout.log', 'live_command_public.json',
                 'live_result.json', 'native_evaluator_uploaded.json',
                 'native_reports_checked.json', 'native_test_execution.json',
                 'pos_archive_status.json', 'prepared.json',
                 'verification_released.json', 'writer_termination_check.json'):
        path = run / 'archive' / name
        if path.is_file():
            selected['01/archive/' + name] = path
    for name in ('research_events.jsonl', 'task_terminal.json',
                 'agent_stdout.log', 'agent_stderr.log',
                 'agent_process_return_code.txt'):
        path = trial / 'agent' / name
        if path.is_file():
            selected['01/task/' + name] = path
    for name in ('result.json', 'verifier/ctrf.json',
                 'verifier/reward.txt', 'verifier/test-stdout.txt'):
        path = trial / name
        if path.is_file():
            selected['01/task/' + name] = path
    for name in ('events.jsonl', 'events.provider.jsonl',
                 'events.result.json', 'events.close.json'):
        path = first / 'provider_public' / name
        if path.is_file():
            selected['01/pos_public/' + name] = path
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--target', type=Path, required=True)
    parser.add_argument('--task-profile', type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    for child in source.glob('*/authorization.json'):
        raise RuntimeError(f'active authorization remains: {child}')
    secrets = secrets_from_profile(args.task_profile)
    files = mapping(source)
    args.target.mkdir(parents=True, exist_ok=False)
    rows = []
    omissions = []
    for name, path in sorted(files.items()):
        raw = path.read_bytes()
        try:
            data, count = public(raw, secrets)
        except UnsafePublicProjection:
            omissions.append(dict(path=name, reason='unsafe_structured_projection',
                                  source_bytes=len(raw), source_sha256=sha(raw)))
            continue
        destination = args.target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open('xb') as stream:
            stream.write(data)
        if destination.read_bytes() != data:
            raise RuntimeError('public readback mismatch: ' + name)
        rows.append(dict(path=name, source_bytes=len(raw), source_sha256=sha(raw),
                         public_bytes=len(data), public_sha256=sha(data),
                         redactions=count))
    report = dict(schema='pos-ga-formal-v6-stop-archive-v1', files=rows,
                  omissions=omissions,
                  source=str(source), public_copy_is_byte_identical=False)
    index = args.target / 'FILE_HASHES.json'
    with index.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps(dict(file_count=len(rows), omissions=len(omissions),
                          redactions=sum(x['redactions'] for x in rows),
                          index_sha256=sha(index.read_bytes()))))


if __name__ == '__main__':
    main()
