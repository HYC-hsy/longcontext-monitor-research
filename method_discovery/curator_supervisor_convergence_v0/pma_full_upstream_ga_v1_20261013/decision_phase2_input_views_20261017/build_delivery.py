"""Post-run, no-model audit assembly for the 54-row D1 input-view screen."""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from decision_phase2_screen import CASES, VIEW_SCHEMA, request_for, slot_name


HERE = Path(__file__).resolve().parent
REPO = next(parent for parent in HERE.parents if (parent / '.git').exists())
PRIVATE = Path('E:/pma_d1views_run_20261017')
CONTROL = Path('E:/pma_d1views_control_20261017')
RUN_CODE = 'e42c71b7e040a7cff55ea244f89a4c06800e8f6a'
BASELINE = '597c8a56ca2908f5c7bc06ceb5f0d22b37563ba5'
OLD_PUBLIC = HERE.parent / 'decision_phase2_live18_20261017/public_run'


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n',
                    encoding='utf-8')


def build() -> None:
    manifest_path = CONTROL / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if (manifest['schema'] != VIEW_SCHEMA or
            manifest['code_identity']['commit'] != RUN_CODE or
            manifest['output_root'] != str(PRIVATE.resolve()) or
            not (PRIVATE / 'authorization_revoked.json').is_file() or
            (CONTROL / 'authorization.json').exists()):
        raise RuntimeError('frozen run identity, revocation or private root mismatch')
    plan = manifest['planned_order']
    statuses = json.loads((PRIVATE / 'status_table.json').read_text(encoding='utf-8'))['rows']
    if len(plan) != 54 or len(statuses) != len(plan):
        raise RuntimeError('plan/status row mismatch')
    consumed = json.loads((PRIVATE / 'authorization_consumed.json').read_text(encoding='utf-8'))
    revoked = json.loads((PRIVATE / 'authorization_revoked.json').read_text(encoding='utf-8'))
    if (consumed['batch_id'] != manifest['batch_id'] or
            revoked['batch_id'] != manifest['batch_id'] or
            consumed['manifest_sha256'] != digest(manifest_path)):
        raise RuntimeError('one-use authorization receipts do not match manifest')
    save(HERE / 'AUTHORIZATION_PUBLIC.json', {
        'batch_id': manifest['batch_id'],
        'manifest_sha256': consumed['manifest_sha256'],
        'authorization_sha256': consumed['authorization_sha256'],
        'authorization_source': 'user_message_2026-10-17_D1_input_views_54_once',
        'issued_for_code_commit': consumed['code_commit'],
        'profile_sha256': consumed['profile_sha256'],
        'authorization_file_removed': not (CONTROL / 'authorization.json').exists(),
        'consumed_epoch': consumed['epoch'], 'revoked_epoch': revoked['epoch']})
    private_hashes = [{'path': path.relative_to(PRIVATE).as_posix(),
                       'bytes': path.stat().st_size, 'sha256': digest(path)}
                      for path in sorted(PRIVATE.rglob('*')) if path.is_file()]
    save(HERE / 'PRIVATE_FILE_HASHES.json', private_hashes)
    diff = subprocess.run(('git', 'diff', '--binary', BASELINE, RUN_CODE, '--',
                           'method_discovery/curator_supervisor_convergence_v0/'
                           'pma_full_upstream_ga_v1_20261013'), cwd=REPO,
                          check=True, capture_output=True).stdout
    (HERE / 'IMPLEMENTATION_DIFF.patch').write_bytes(diff)

    table = []
    input_proof = []
    classes = Counter()
    usage = defaultdict(lambda: defaultdict(list))
    for number, (row, state) in enumerate(zip(plan, statuses, strict=True), 1):
        slot = PRIVATE / slot_name(row, number, manifest['schema'])
        result_path = slot / 'result.json'
        result = json.loads(result_path.read_text(encoding='utf-8')) if result_path.is_file() else None
        if result is None:
            classification = 'unknown'
            logical = observable = 'unknown' if slot.exists() else 0
        else:
            if result.get('order') != number or result.get('run_id') != row['run_id']:
                raise RuntimeError('result identity mismatch')
            classification = result.get('output_class', 'unknown')
            logical = result.get('logical_requests', 'unknown')
            observable = result.get('observable_litellm_calls', 'unknown')
            classes[classification] += 1
            for key in ('prompt_tokens', 'completion_tokens', 'cache_tokens', 'cost_usd'):
                usage[row['input_view']][key].append((result.get('returned_usage') or {}).get(key))
            usage[row['input_view']]['elapsed_seconds'].append(
                result['ended_epoch'] - result['started_epoch'])
        table.append({'order': number, 'arm': row['arm'], 'pma_step': row['pma_step'],
                      'occurrence': row['occurrence'], 'input_view': row['input_view'],
                      'run_id': row['run_id'], 'status': state['status'],
                      'output_class': classification, 'logical_requests': logical,
                      'observable_litellm_calls': observable})
        if (slot / 'requests.jsonl').is_file():
            actual = json.loads((slot / 'requests.jsonl').read_text(encoding='utf-8').splitlines()[0])
            expected_prompt, expected_system, expected_projection = request_for(row)
            if actual['prompt'] != expected_prompt or actual['system'] != expected_system:
                raise RuntimeError('actual request bytes differ from frozen projection')
            identity = json.loads((slot / 'projection_identity.json').read_text(encoding='utf-8'))
            if identity != expected_projection:
                raise RuntimeError('saved field provenance differs from source')
            input_proof.append({'order': number, 'run_id': row['run_id'],
                                'source_path': row['source_path'],
                                'source_file_sha256': row['source_file_sha256'],
                                'archive_index': row['archive_index'],
                                'request_prompt_sha256': row['request_prompt_sha256'],
                                'request_system_sha256': row['request_system_sha256'],
                                'actual_request_file_sha256': digest(slot / 'requests.jsonl'),
                                'projection_identity_file_sha256': digest(slot / 'projection_identity.json'),
                                'projection': identity})
    for case_index, (arm, step) in enumerate(CASES):
        selected = [row for row in input_proof if row['projection']['view'] == 'F'
                    and table[row['order'] - 1]['arm'] == arm
                    and table[row['order'] - 1]['pma_step'] == step]
        if len(selected) != 3:
            raise RuntimeError('missing F request for archived case')
        old = json.loads((OLD_PUBLIC / f'{case_index * 3 + 3:02d}-d1/request.json')
                         .read_text(encoding='utf-8'))
        old_hash = hashlib.sha256(old['prompt'].encode('utf-8')).hexdigest()
        if any(row['request_prompt_sha256'] != old_hash for row in selected):
            raise RuntimeError('F prompt is not the previous D1 request')
    save(HERE / 'INPUT_PROJECTION_INDEX.json', input_proof)
    save(HERE / 'STATUS_AND_COUNTS.json', table)
    grouped = {}
    for view in ('F', 'EB', 'E'):
        selected = [row for row in table if row['input_view'] == view]
        grouped[view] = {'status': dict(Counter(row['status'] for row in selected)),
                         'output_class': dict(Counter(row['output_class'] for row in selected)),
                         'logical_requests': sum(row['logical_requests'] for row in selected
                                                 if isinstance(row['logical_requests'], int)),
                         'observable_litellm_calls': sum(row['observable_litellm_calls']
                                                         for row in selected if isinstance(
                                                             row['observable_litellm_calls'], int))}
        for key, values in usage[view].items():
            grouped[view][key] = sum(values) if len(values) == len(selected) and all(
                value is not None for value in values) else 'unknown'
    summary = (
        'D1 archived Phase-2 input-source diagnostic — mechanical facts only\n'
        f'Frozen run code: {RUN_CODE}\nComparison baseline: {BASELINE}\n'
        f'Manifest SHA-256: {digest(manifest_path)}\nBatch ID: {manifest["batch_id"]}\n'
        f'Profile SHA-256: {manifest["profile_sha256"]}\n'
        'Effective profile: Anthropic/messages, claude-opus-4-8, adaptive/high, '
        'max_tokens=8192, temperature=1, read_timeout=300 seconds, original '
        'upstream up to three attempts. Profile timeout=30 and max_retries=8 '
        'are not extra active limits. Deeper network attempts: unknown.\n'
        f'All statuses: {dict(Counter(row["status"] for row in table))}\n'
        f'All output classes: {dict(classes)}\n'
        'Per-view usage fields are returned LiteLLM values, not an invoice; '
        'missing values remain unknown:\n'
        + json.dumps(grouped, ensure_ascii=False, indent=2) + '\n'
        'Phase 1, Task, evaluator, training and scoring calls: 0. No reminder '
        'delivered to Task. No model output was input to another call.\n'
        'The six cases are exposed archival prefixes; 54 calls are not 54 '
        'independent tasks and do not show Task benefit. Tool returns are not '
        'independently certified truths. No method winner is inferred.\n'
        'Private originals remain local, not uploaded. Their hashes and sizes '
        'appear in PRIVATE_FILE_HASHES.json. Public projections exclude private '
        'endpoint, key, raw lower choices, and unsupported transport fields.\n\n'
        '54-ROW STATUS TABLE\n'
        + '\n'.join(f"{row['order']:02d} {row['arm']}/{row['pma_step']} "
                    f"r{row['occurrence']} {row['input_view']} {row['status']} "
                    f"class={row['output_class']} logical={row['logical_requests']} "
                    f"litellm={row['observable_litellm_calls']}" for row in table) + '\n')
    (HERE / 'MECHANICAL_SUMMARY.txt').write_text(summary, encoding='utf-8')
    test = (HERE / 'TEST_RAW_FINAL.txt').read_text(encoding='utf-8')
    public = (HERE / 'public_run/AUDIT.txt').read_text(encoding='utf-8')
    (HERE / 'FULL_AUDIT.txt').write_text(
        summary + '\n=== FULL LIMITED IMPLEMENTATION DIFF ===\n'
        + diff.decode('utf-8', errors='replace')
        + '\n=== RAW ZERO-MODEL TEST OUTPUT ===\n' + test
        + '\n=== FULL PUBLIC REQUEST/RESPONSE AUDIT ===\n' + public,
        encoding='utf-8')
    print(json.dumps({'status_rows': len(table), 'projection_rows': len(input_proof),
                      'private_files_hashed': len(private_hashes), 'classes': dict(classes)},
                     ensure_ascii=False))


def hashes() -> None:
    items = []
    for path in sorted(HERE.rglob('*')):
        if (not path.is_file() or path.name == 'DELIVERY_FILE_HASHES.json' or
                '__pycache__' in path.parts or path.suffix == '.pyc'):
            continue
        relative = path.relative_to(REPO).as_posix()
        result = subprocess.run(('git', 'show', ':' + relative), cwd=REPO,
                                check=True, capture_output=True).stdout
        items.append({'path': path.relative_to(HERE).as_posix(),
                      'worktree_bytes': path.stat().st_size,
                      'worktree_sha256': digest(path), 'git_blob_bytes': len(result),
                      'git_blob_sha256': hashlib.sha256(result).hexdigest()})
    save(HERE / 'DELIVERY_FILE_HASHES.json', items)
    print(json.dumps({'files': len(items), 'worktree_vs_git_differ': sum(
        row['worktree_sha256'] != row['git_blob_sha256'] for row in items)}))


if __name__ == '__main__':
    if len(sys.argv) == 1:
        build()
    elif sys.argv[1:] == ['--hash-only']:
        hashes()
    else:
        raise SystemExit('usage: python -m build_delivery [--hash-only]')
