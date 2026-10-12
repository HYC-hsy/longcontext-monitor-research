"""Mechanically package the frozen zero-model static finish evidence; no execution."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RAW = HERE / 'STATIC_FINISH_RAW_20261012'
BASE = '2c5b95ee45b27f87045613fb1335b37caa59f586'
CODE = 'f3793d1e5ec02b5bcbf88b8e3cacb3e8abfbb4f2'


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def main() -> None:
    if not (RAW / 'FINAL_TESTS').is_dir() or not (RAW / 'FINAL3_TESTS').is_dir() or not (
            RAW / 'FINAL3_ARTIFACTS').is_dir():
        raise RuntimeError('Frozen final tests and copied artifacts are required')
    report = []
    selected = [('core', RAW / 'CORE_FINAL2_TESTS' / 'core')]
    selected.extend((name, RAW / 'FINAL_TESTS' / name) for name in
                    ('profile_bundle', 'native_go', 'existing_docker_candidate'))
    selected.append(('static_host_session', RAW / 'FINAL3_TESTS' / 'static_host_session'))
    for name, group in selected:
        result = json.loads((group / 'result.json').read_text(encoding='utf-8'))
        report.append({'group': name, 'exit_code': result['exit_code'],
                       'stdout_sha256': result['stdout_sha256'],
                       'stderr_sha256': result['stderr_sha256']})
    rows = []
    for path in sorted(RAW.rglob('*')):
        if path.is_file():
            data = path.read_bytes()
            rows.append({'path': path.relative_to(RAW).as_posix(),
                         'bytes': len(data), 'sha256': sha(data)})
    requests = []
    fake_request_count = 0
    for session in sorted((RAW / 'FINAL3_ARTIFACTS').iterdir()):
        if not session.is_dir() or not (session / 'RESEARCH_ONLY_MANIFEST.json').is_file():
            continue
        material = json.loads((session / 'RESEARCH_ONLY_MANIFEST.json').read_text(
            encoding='utf-8'))
        first = sorted((session / 'host_requests').glob('*.json'))
        fake_request_count += len(first)
        if not first:
            continue
        payload = json.loads(first[0].read_text(encoding='utf-8'))
        requests.append({'scene': material['scene_research_only'],
            'method': 'evidence_package_v1' if 'Phase A' in payload['system'] else 'N',
            'request': first[0].relative_to(RAW).as_posix(),
            'canonical_sha256': sha(json.dumps(payload, sort_keys=True,
                ensure_ascii=False, separators=(',', ':')).encode('utf-8')),
            'model': payload['model'], 'max_tokens': payload['max_tokens'],
            'message_count': len(payload['messages']), 'tool_count': len(payload['tools']),
            'temperature_present': 'temperature' in payload,
            'public_prefix_sha256': material['public']['sha256'],
            'book_sha256': material['book_sha256'],
            'workspace_tree_sha256': material['workspace_tree_sha256']})
    comparison = HERE / 'STATIC_FIRST_REQUEST_COMPARISON.json'
    comparison.write_text(json.dumps({'status': 'zero_model_actual_pre_send_payloads',
        'allowed_differences': ['system method prompt', 'A/B stage', 'frontier tool schema',
                                'request-local review identity and dynamically archived references'],
        'requests': requests}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    changed = subprocess.run(['git', 'diff', '--name-only', BASE, CODE], cwd=ROOT,
                             capture_output=True, check=True).stdout.decode().splitlines()
    source_identity = []
    for relative in changed:
        committed = subprocess.run(['git', 'show', CODE + ':' + relative], cwd=ROOT,
                                   capture_output=True, check=True).stdout
        blob = subprocess.run(['git', 'rev-parse', CODE + ':' + relative], cwd=ROOT,
                              capture_output=True, check=True).stdout.decode().strip()
        working = (ROOT / relative).read_bytes()
        source_identity.append({'path': relative, 'git_blob': blob,
                                'committed_byte_sha256': sha(committed),
                                'working_byte_sha256': sha(working),
                                'bytes_equal': committed == working})
    manifest = HERE / 'STATIC_FINISH_FILE_SHA256.json'
    manifest.write_text(json.dumps({'base': BASE, 'code_commit': CODE,
        'scope': 'selected zero-model test and host-static artifacts, not a host image',
        'tests': report, 'source_identity': source_identity, 'files': rows,
        'final3_pre_send_fake_request_count': fake_request_count,
        'first_request_comparison_sha256': sha(comparison.read_bytes())},
        indent=2, ensure_ascii=False) + '\n',
        encoding='utf-8')
    diff = subprocess.run(['git', 'diff', BASE, CODE, '--',
        'GenericAgent-main/monitor_agent_core/agent.py',
        'GenericAgent-main/monitor_agent_core/evidence_package_v1.py',
        'GenericAgent-main/tests/test_evidence_package_v1.py',
        'method_discovery/curator_supervisor_convergence_v0/evidence_package_v1_20261012'],
        cwd=ROOT, capture_output=True, check=True).stdout.decode('utf-8')
    sections = [
        'STATIC HOST DIAGNOSTIC FINISH - ZERO-MODEL AUDIT',
        '\n== Completion report ==\n' + (HERE / 'STATIC_FINISH_REPORT.md').read_text(encoding='utf-8'),
        'Base remote archive: ' + BASE,
        'Frozen implementation commit: ' + CODE,
        'Scope: new static diagnosis on certified C01/C02 cutoff materials, not historical online replay.',
        'No real Task, Supervisor, provider API, native evaluator, training or scoring-model call was authorized.',
        'Live MonitorRuntime evidence-package launch gate remains unchanged and disabled.',
        'Actual fake-post attempts and Docker sessions are in the raw files below; no real endpoint is configured.',
        'Final targeted static-host fake pre-send attempts: ' + str(fake_request_count),
        'C01: cursor 120, Task turn 61, no completion handoff at cutoff.',
        'C02: cursor 161, Task turn 83, completion handoff identity certified from cutoff request.',
        'N and candidate share public task, cutoff events, Book, static note, image/mount and model fields.',
        'Their system method instructions, A/B stages and frontier tools intentionally differ.',
        'The false-premise and environment-blocked additional cutoffs remain uncertified; no live static batch is authorized.',
        'Private Go hashes are bounded before/after identities, not a complete dependency proof. New private commands stale prior Go receipts.',
        'The candidate live Task+Supervisor shared-container deployment is not certified.',
        'Preliminary failures preserved: regex searched the wrong historical message for C02 handoff; corrected to unique handoff span.',
        'Preliminary failures preserved: package "." rejected by tightened validation; corrected without accepting option-like package names.',
        'Preliminary failure preserved: old test expected lowercase incomplete-process error; implementation message corrected.',
        'The first frozen static-host run received Docker no-such-object for an --rm container; its raw output is retained under FINAL_TESTS. The cause is not established. FINAL3_TESTS is the targeted final run with an explicit live window.',
        '\n== Test group results ==\n' + json.dumps(report, indent=2),
        '\n== Raw file SHA-256 manifest ==\n' + manifest.read_text(encoding='utf-8'),
        '\n== Actual first request comparison ==\n' + comparison.read_text(encoding='utf-8'),
        '\n== Complete scoped implementation diff ==\n' + diff,
    ]
    for path in sorted(RAW.rglob('*')):
        if not path.is_file() or path.suffix not in {'.txt', '.json', '.jsonl', '.log', '.sh', '.sha256'}:
            continue
        relative = path.relative_to(RAW).as_posix()
        raw = path.read_bytes()
        try:
            body = raw.decode('utf-8')
        except UnicodeDecodeError:
            body = '[non-UTF-8 bytes retained separately; sha256=' + sha(raw) + ']'
        sections.append('\n== ' + relative + ' ==\n' + body)
    output = HERE / 'STATIC_FINISH_AUDIT.txt'
    output.write_text('\n\n'.join(sections), encoding='utf-8')
    print(json.dumps({'package': str(output), 'bytes': output.stat().st_size,
                      'sha256': sha(output.read_bytes()),
                      'manifest_sha256': sha(manifest.read_bytes()), 'tests': report},
                     ensure_ascii=False))


if __name__ == '__main__':
    main()
