"""Copy only selected, redacted zero-model evidence; never the GA bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from .archive_live_six_task import private_values, redact
from .export_gap_visible_audit import Sanitizer, URL
from .single_run_certification import EVIDENCE_FILES, verify_evidence


def _verifiable_evidence_snapshot(raw: bytes, secrets: list[str]) -> tuple[bytes, int]:
    """Keep hash-bearing synthetic IDs intact, or decline unsafe publication."""
    value = json.loads(raw)
    sanitizer = Sanitizer(secrets)
    projected = sanitizer.clean(value)
    if sanitizer.removals or projected != value:
        raise RuntimeError('evidence snapshot needs redaction and cannot retain its binding')
    return raw, 0


def _verifiable_evidence_jsonl(raw: bytes, secrets: list[str]) -> tuple[bytes, int]:
    """Preserve sealed synthetic rows byte-for-byte, or refuse publication."""
    if any(secret.encode('utf-8') in raw for secret in secrets if len(secret) >= 6):
        raise RuntimeError('sealed evidence row needs redaction')

    def scan_view(value):
        if isinstance(value, dict):
            return {key: scan_view(item) for key, item in value.items()
                    if not (key == 'metadata' and item == {})}
        if isinstance(value, list):
            return [scan_view(item) for item in value]
        if isinstance(value, str):
            return URL.sub(lambda match: '[PUBLIC_LOOPBACK_FIXTURE]'
                if re.fullmatch(r'http://127\.0\.0\.1:\d+/', match.group())
                else match.group(), value)
        return value

    sanitizer = Sanitizer(secrets)
    for line in raw.splitlines():
        if not line.strip():
            raise RuntimeError('blank sealed evidence row')
        value = json.loads(line)
        viewed = scan_view(value)
        if sanitizer.clean(viewed) != viewed or sanitizer.removals:
            raise RuntimeError('sealed evidence row needs redaction')
    return raw, 0


def collect(condition: str, source: Path, target: Path, secrets: list[str],
            research_candidate: str = "U", citation_review_gate=None) -> list[dict]:
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
        if research_candidate == 'pma_gap_evidence_v1':
            mapping['memory.json'] = run / 'host_private/archive/memory.json'
        for name in ('gap_cycle.jsonl', 'gap_visible_transport.jsonl'):
            path = run / 'host_private/archive' / name
            if path.is_file():
                mapping[name] = path
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
        if research_candidate == 'pma_gap_evidence_v1' and name == 'memory.json':
            public, removed = _verifiable_evidence_snapshot(raw, secrets)
        elif citation_review_gate and name in {
                'memory_payload.jsonl', 'gap_cycle.jsonl', 'gap_visible_transport.jsonl'}:
            public, removed = _verifiable_evidence_jsonl(raw, secrets)
        else:
            public, removed = redact(raw, secrets)
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open('xb') as stream:
            stream.write(public)
        output.append({'path': f'{condition}/{name}', 'bytes': len(public),
                       'sha256': hashlib.sha256(public).hexdigest(),
                       'redactions': removed,
                       'private_source_sha256': hashlib.sha256(raw).hexdigest()})
    if citation_review_gate:
        from .gate_certification import inspect_evidence
        certificate=inspect_evidence(target,citation_review_gate)
        raw=json.dumps(certificate,ensure_ascii=False,sort_keys=True,indent=2).encode('utf-8')
        (target/'gate_certificate.json').write_bytes(raw)
        output.append({'path':f'{condition}/gate_certificate.json','bytes':len(raw),
                       'sha256':hashlib.sha256(raw).hexdigest(),'redactions':0})
    return output


def protect_evidence_bytes(root: Path) -> dict:
    """Keep raw capture bytes on Git add/checkout, scoped to this evidence root."""
    raw = b"* -text\n"
    with (root / '.gitattributes').open('xb') as stream:
        stream.write(raw)
    return {'path': '.gitattributes', 'bytes': len(raw),
            'sha256': hashlib.sha256(raw).hexdigest(), 'redactions': 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--citation-review-gate',choices=('gate-only','gate-one-repair'))
    parser.add_argument('--a', type=Path, required=True)
    parser.add_argument('--b', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--task-profile-file', type=Path, required=True)
    parser.add_argument('--pma-profile-file', type=Path, required=True)
    parser.add_argument('--research-candidate', choices=('U', 'V1', 'D1',
        'pma_gap_memory_v0', 'pma_gap_evidence_v1'), default='U')
    args = parser.parse_args()
    from .citation_gate_config import validate_gate
    validate_gate(args.citation_review_gate,args.research_candidate)
    if args.b is None and args.research_candidate != 'U':
        parser.error('A-only certification requires U')
    args.output.mkdir(parents=True, exist_ok=False)
    files = [protect_evidence_bytes(args.output)]
    secrets = private_values(args.task_profile_file, args.pma_profile_file)
    files += collect('A', args.a, args.output / 'A', secrets)
    if args.b is not None:
        files += collect('B', args.b, args.output / 'B', secrets, args.research_candidate,args.citation_review_gate)
    summary = verify_evidence(args.output, require_committed=False,citation_review_gate=args.citation_review_gate,
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
