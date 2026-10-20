"""Publish a narrow, redacted copy of a stopped synthetic native-SHARED run."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import runpy

from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.archive_live_six_task import redact
from .provider_capture import inspect_provider_capture


def secrets_from_profile(path: Path) -> list[str]:
    profile = runpy.run_path(str(path))['native_claude_cc_vibe_opus48']
    values = []
    for key, value in profile.items():
        if (isinstance(value, str) and len(value) >= 6 and any(word in key.lower()
                for word in ('key', 'token', 'secret', 'password', 'base', 'url'))):
            values.append(value)
    return sorted(set(values), key=len, reverse=True)


def redact_client_metadata(public: bytes) -> tuple[bytes, int]:
    """Remove transport client identity without changing model-visible messages."""

    text = public.decode('utf-8')
    if 'user_id' not in text:
        return public, 0
    changes = 0

    def project(value):
        nonlocal changes
        if isinstance(value, dict):
            result = {}
            for key, item in value.items():
                if key == 'metadata' and isinstance(item, dict) and 'user_id' in item:
                    item = dict(item)
                    item['user_id'] = '[REDACTED_CLIENT_ID]'
                    changes += 1
                result[key] = project(item)
            return result
        if isinstance(value, list):
            return [project(item) for item in value]
        if isinstance(value, str) and value.lstrip().startswith(('{', '[')):
            try:
                nested = json.loads(value)
            except ValueError:
                if '"user_id"' in value:
                    raise RuntimeError('unparseable client metadata in public copy')
            else:
                before = changes
                nested = project(nested)
                if changes != before:
                    return json.dumps(nested, ensure_ascii=False)
        return value

    try:
        projected = project(json.loads(text))
        rendered = json.dumps(projected, ensure_ascii=False)
    except ValueError:
        rendered_lines = []
        for line in text.splitlines():
            if not line.strip():
                rendered_lines.append('')
                continue
            try:
                rendered_lines.append(json.dumps(project(json.loads(line)),
                                                 ensure_ascii=False))
            except ValueError as error:
                raise RuntimeError('unparseable client metadata in public copy') from error
        rendered = '\n'.join(rendered_lines) + ('\n' if text.endswith('\n') else '')
    if '"user_id"' in rendered and changes == 0:
        raise RuntimeError('unprojected client metadata in public copy')
    return rendered.encode('utf-8'), changes


def mapping_for(source: Path) -> dict[str, Path]:
    identity = json.loads((source / 'run_identity.json').read_text(encoding='utf-8'))
    manifest = json.loads((source / 'manifest.json').read_text(encoding='utf-8'))
    run = Path(identity['run_root']).resolve(strict=True)
    if not run.is_relative_to(source.resolve(strict=True)):
        raise RuntimeError('run root outside source')
    if (source / 'authorization.json').exists():
        raise RuntimeError('synthetic authorization remains live')
    archive = run / 'archive'
    selected = ('agent_start_identity.json', 'agent_end_native.json',
                'control_process_registry.json', 'harbor.stderr.log',
                'harbor.stdout.log', 'live_command_public.json',
                'live_result.json', 'native_evaluator_uploaded.json',
                'native_reports_checked.json', 'native_test_execution.json',
                'pos_archive_status.json', 'prepared.json',
                'verification_released.json', 'writer_termination_check.json')
    mapping = {name: archive / name for name in selected}
    for name in ('execution_identity.json', 'fake_authorization_removed.json',
                 'run_identity.json', 'plan.json', 'manifest.json',
                 'batch_result.json', 'controller.stdout.txt',
                 'controller.stderr.txt'):
        mapping[name] = source / name
    for path in sorted((archive / 'fake_provider_requests').glob('*')):
        if path.suffix in {'.json', '.sse'}:
            mapping['fake_requests/' + path.name] = path
    pos = run / 'control/pos_archive'
    event_names = ['events.jsonl', 'events.host.jsonl', 'events.result.json',
                   'events.close.json']
    if manifest.get('candidate_profile_fixture_only') is not True:
        event_names.append('events.stderr.log')
    for name in event_names:
        mapping[name] = pos / name
    if (pos / 'events.provider.jsonl').is_file():
        mapping['events.provider.jsonl'] = pos / 'events.provider.jsonl'
    if (pos / 'events.bridge.jsonl').is_file():
        mapping['events.bridge.jsonl'] = pos / 'events.bridge.jsonl'
    trial = list((run / 'jobs').glob('*/*'))
    trial = [path for path in trial if (path / 'agent/research_events.jsonl').is_file()]
    if len(trial) != 1:
        raise RuntimeError('Task trial not unique')
    task = trial[0]
    for name in ('agent/research_events.jsonl', 'agent/task_terminal.json',
                 'agent/agent_stdout.log', 'agent/agent_stderr.log',
                 'agent/isolated_transport.log', 'agent/agent_process_return_code.txt',
                 'verifier/test-stdout.txt', 'verifier/reward.txt',
                 'result.json'):
        mapping[name] = task / name
    mapping['synthetic_test.sh'] = run / 'public_task/tests/test.sh'
    mapping['synthetic_instruction.md'] = run / 'public_task/instruction.md'
    mapping['synthetic_task.toml'] = run / 'public_task/task.toml'
    if manifest.get('candidate_profile_fixture_only') is True:
        mapping['host_private/worker_ready.json'] = run / 'host_private/worker_ready.json'
        mapping['host_private/fake_host_calls.jsonl'] = archive / 'fake_host_calls.jsonl'
        spool = run / 'control/spool'
        for kind in ('requests', 'responses'):
            for path in sorted((spool / kind).glob('*.json')):
                mapping[f'spool/{kind}/{path.name}'] = path
    return mapping


def collect(source: Path, target: Path, secrets: list[str]) -> list[dict]:
    mapping = mapping_for(source)
    rows = []
    for name, path in sorted(mapping.items()):
        raw = path.read_bytes()
        public, count = redact(raw, secrets)
        public, client_count = redact_client_metadata(public)
        count += client_count
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open('xb') as stream:
            stream.write(public)
        rows.append({'path': 'normal/' + name, 'bytes': len(public),
                     'sha256': hashlib.sha256(public).hexdigest(),
                     'private_source_sha256': hashlib.sha256(raw).hexdigest(),
                     'redactions': count})
    return rows


def collect_provider_capture(source: Path, target: Path, secrets: list[str],
                             run_id: str, task_id: str, *, profile_mode: bool) -> dict:
    """Copy stopped worker ledgers, retaining source and public byte identities."""
    capture = inspect_provider_capture(source, run_id, task_id,
                                       profile_mode=profile_mode)
    if profile_mode and not (source / 'events.bridge.jsonl').is_file():
        raise RuntimeError('PoS IPC diagnostic ledger missing')
    if profile_mode:
        started, finished, closed = set(), set(), 0
        for raw in (source / 'events.bridge.jsonl').read_text(
                encoding='utf-8').splitlines():
            row = json.loads(raw)
            if row.get('run_id') != run_id or row.get('task_id') != task_id:
                raise RuntimeError('PoS IPC diagnostic identity differs')
            event, command_id = row.get('event'), row.get('command_id')
            if event == 'command_started':
                if command_id in started:
                    raise RuntimeError('PoS IPC command identity reused')
                started.add(command_id)
            elif event == 'command_finished':
                finished.add(command_id)
            elif event == 'bridge_closed':
                closed += 1
        if not started or started != finished or closed != 1:
            raise RuntimeError('PoS IPC diagnostic ledger incomplete')
        close = json.loads((source / 'events.close.json').read_text(encoding='utf-8'))
        if close.get('diagnostic_persist_error_type') is not None:
            raise RuntimeError('PoS IPC diagnostic persistence incomplete')
    target.mkdir(parents=True, exist_ok=False)
    files = []
    names = ['events.jsonl', 'events.provider.jsonl', 'events.bridge.jsonl', 'events.result.json',
             'events.close.json']
    if not profile_mode:
        names.append('events.stderr.log')
    for name in names:
        path = source / name
        if not path.is_file():
            continue
        raw = path.read_bytes()
        public, count = redact(raw, secrets)
        public, client_count = redact_client_metadata(public)
        count += client_count
        destination = target / name
        with destination.open('xb') as stream:
            stream.write(public)
        if destination.read_bytes() != public:
            raise RuntimeError('published provider file readback differs')
        files.append({'path':name, 'source_bytes':len(raw),
            'source_sha256':hashlib.sha256(raw).hexdigest(),
            'public_bytes':len(public),
            'public_sha256':hashlib.sha256(public).hexdigest(),
            'redactions':count})
    report = {'schema':'pos-ga-provider-capture-archive-v1',
        'run_id':run_id,'task_id':task_id,'capture':capture,'files':files,
        'public_copy_is_byte_identical_to_source':all(
            row['source_sha256'] == row['public_sha256'] for row in files)}
    (target/'CAPTURE_INDEX.json').write_text(json.dumps(report,ensure_ascii=False,
        indent=2)+'\n',encoding='utf-8',newline='\n')
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--failure-source', type=Path, action='append', default=[])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--task-profile-file', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    secrets = secrets_from_profile(args.task_profile_file)
    rows = collect(args.source, args.output / 'normal', secrets)
    for source in args.failure_source:
        for name in ('controller.stdout.txt', 'controller.stderr.txt'):
            path = source / name
            if not path.is_file():
                continue
            raw = path.read_bytes()
            public, count = redact(raw, secrets)
            destination = args.output / 'failures' / source.name / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open('xb') as stream:
                stream.write(public)
            rows.append({'path': destination.relative_to(args.output).as_posix(),
                         'bytes': len(public), 'sha256': hashlib.sha256(public).hexdigest(),
                         'private_source_sha256': hashlib.sha256(raw).hexdigest(),
                         'redactions': count})
    index = {'schema': 'pos-ga-native-shared-evidence-v1', 'files': rows,
             'source_kind': 'redacted_copies_of_existing_run_records',
             'new_real_model_calls': 0, 'official_evaluator_calls': 0}
    (args.output / 'FILE_HASHES.json').write_text(json.dumps(index, ensure_ascii=False,
        indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'files': len(rows), 'redactions': sum(x['redactions'] for x in rows),
                      'real_model_calls': 0, 'official_evaluator_calls': 0}))


if __name__ == '__main__':
    main()
