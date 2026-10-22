"""Copy only selected, redacted zero-model evidence; never the GA bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .archive_live_six_task import private_values, redact
from .single_run_certification import EVIDENCE_FILES, verify_evidence


def collect(condition: str, source: Path, target: Path, secrets: list[str]) -> list[dict]:
    identity = json.loads((source / 'run_identity.json').read_text(encoding='utf-8'))
    run = Path(identity['run_root']).resolve(strict=True)
    if not run.is_relative_to(source.resolve(strict=True)):
        raise RuntimeError('fixture run root outside its source')
    if (source / 'authorization.json').exists():
        raise RuntimeError('fixture authorization not removed')
    mapping = {name: run / 'archive' / name for name in EVIDENCE_FILES
               if name not in {'memory_payload.jsonl', 'research_events.jsonl',
                               'fake_authorization_removed.json', 'synthetic_test.sh'}}
    mapping['fake_authorization_removed.json'] = source / 'fake_authorization_removed.json'
    mapping['execution_identity.json'] = source / 'execution_identity.json'
    mapping['synthetic_test.sh'] = run / 'public_task/tests/test.sh'
    events = list((run / 'jobs').rglob('research_events.jsonl'))
    if len(events) != 1:
        raise RuntimeError('fixture Task event log not unique')
    mapping['research_events.jsonl'] = events[0]
    if condition == 'B':
        mapping['memory_payload.jsonl'] = run / 'host_private/archive/memory_payload.jsonl'
        mapping['memory_events.jsonl'] = run / 'host_private/archive/events.jsonl'
    for path in sorted((run / 'archive/fake_provider_requests').glob('*')):
        if path.suffix in {'.json', '.sse'}:
            mapping['fake_requests/' + path.name] = path
    for name in ('controller.stdout.txt', 'controller.stderr.txt'):
        mapping[name] = source / name
    result_files = list((run / 'jobs').rglob('result.json'))
    for number, path in enumerate(result_files):
        mapping[f'harbor_result_{number}.json'] = path
    output = []
    for name, path in sorted(mapping.items()):
        raw = path.read_bytes()
        public, removed = redact(raw, secrets)
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open('xb') as stream:
            stream.write(public)
        output.append({'path': f'{condition}/{name}', 'bytes': len(public),
                       'sha256': hashlib.sha256(public).hexdigest(),
                       'redactions': removed,
                       'private_source_sha256': hashlib.sha256(raw).hexdigest()})
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--a', type=Path, required=True)
    parser.add_argument('--b', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--task-profile-file', type=Path, required=True)
    parser.add_argument('--pma-profile-file', type=Path, required=True)
    parser.add_argument('--research-candidate', choices=('U', 'V1', 'D1'), default='U')
    args = parser.parse_args()
    if args.b is None and args.research_candidate != 'U':
        parser.error('A-only certification requires U')
    args.output.mkdir(parents=True, exist_ok=False)
    secrets = private_values(args.task_profile_file, args.pma_profile_file)
    files = collect('A', args.a, args.output / 'A', secrets)
    if args.b is not None:
        files += collect('B', args.b, args.output / 'B', secrets)
    summary = verify_evidence(args.output, require_committed=False,
                              research_candidate=(args.research_candidate
                                  if args.research_candidate != 'U' else None),
                              conditions=('A', 'B') if args.b is not None else ('A',))
    (args.output / 'FILE_HASHES.json').write_text(json.dumps({
        'schema': 'pma-ga-generic-fixture-redacted-index-v1', 'files': files,
        'certification': summary}, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({'files': len(files), 'conditions': list(summary['outcomes']),
                      'secrets_exported': False}))


if __name__ == '__main__':
    main()
