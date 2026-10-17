"""Post-run mechanical report; never reads profile bytes or calls a model."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
REPO = next(path for path in HERE.parents if (path / '.git').exists())
PRIVATE = Path('E:/pma_d1v1_phase2_run_20261017')
CONTROL = Path('E:/pma_d1v1_phase2_control_20261017/manifest.json')
BASELINE = '4e7af45ca362fea604237c5b246e32e41d00de20'
RUN_CODE = 'a648df8b19ca3f3d81082908cb07a4b2bbedeeca'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, content: str) -> None:
    path.write_text(content, encoding='utf-8')


def build() -> None:
    if not (PRIVATE / 'authorization_revoked.json').is_file():
        raise RuntimeError('private run has no one-use revocation receipt')
    manifest = json.loads(CONTROL.read_text(encoding='utf-8'))
    statuses = json.loads((PRIVATE / 'status_table.json').read_text(encoding='utf-8'))['rows']
    results = [json.loads(path.read_text(encoding='utf-8'))
               for path in sorted(PRIVATE.glob('*/result.json'))]
    if (manifest['code_identity']['commit'] != RUN_CODE or
            len(statuses) != 18 or len(results) != 18 or
            [row['order'] for row in results] != list(range(1, 19))):
        raise RuntimeError('run identity or result count differs from frozen plan')
    private_hashes = [{'path': path.relative_to(PRIVATE).as_posix(),
                       'bytes': path.stat().st_size, 'sha256': sha(path)}
                      for path in sorted(PRIVATE.rglob('*')) if path.is_file()]
    write(HERE / 'PRIVATE_FILE_HASHES.json',
          json.dumps(private_hashes, ensure_ascii=False, indent=2) + '\n')
    diff = subprocess.run(('git', 'diff', '--binary', BASELINE, RUN_CODE, '--',
                           'method_discovery/curator_supervisor_convergence_v0/'
                           'pma_full_upstream_ga_v1_20261013'), cwd=REPO,
                          capture_output=True, check=True).stdout
    (HERE / 'IMPLEMENTATION_DIFF.patch').write_bytes(diff)

    classes = Counter(row.get('output_class') for row in results)
    variants = Counter(row['variant'] for row in results)
    statuses_by_type = Counter(row['status'] for row in statuses)
    usage = {}
    for variant in ('U', 'V1', 'D1'):
        selected = [row for row in results if row['variant'] == variant]
        usage[variant] = {}
        for field in ('prompt_tokens', 'completion_tokens', 'cache_tokens', 'cost_usd'):
            values = [(row.get('returned_usage') or {}).get(field) for row in selected]
            usage[variant][field] = sum(values) if all(v is not None for v in values) else 'unknown'
        usage[variant]['elapsed_seconds_sum'] = sum(
            row['ended_epoch'] - row['started_epoch'] for row in selected)
    table = '\n'.join(
        f"{row['order']:02d} arm={row['arm']} step={row['pma_step']} "
        f"variant={row['variant']} status={row['status']} "
        f"class={result.get('output_class', 'unknown')} "
        f"logical={result.get('logical_requests', 'unknown')} "
        f"litellm={result.get('observable_litellm_calls', 'unknown')}"
        for row, result in zip(statuses, results, strict=True))
    summary = (
        'U/V1/D1 archived Phase-2 screen — mechanical report, 2026-10-17\n'
        f'Frozen run code SHA: {RUN_CODE}\n'
        f'Comparison baseline: {BASELINE}\n'
        f'Frozen manifest SHA-256: {sha(CONTROL)}\n'
        f'Batch ID: {manifest["batch_id"]}\n'
        f'Profile SHA-256: {manifest["profile_sha256"]}\n'
        'Profile: Anthropic/messages claude-opus-4-8, adaptive/high, max_tokens=8192, '
        'temperature=1; active read_timeout=300 seconds; original upstream retry '
        'up to three attempts. Profile timeout=30 and max_retries=8 are not '
        'additional active limits.\n'
        'Only six archived public PMA Phase-2 prompts were used, each U→V1→D1. '
        'This is not historical sampling replication or Task execution.\n'
        f'Statuses: {dict(statuses_by_type)}\n'
        f'Variants: {dict(variants)}\n'
        f'Output classes: {dict(classes)}\n'
        f'Logical requests: {sum(row["logical_requests"] for row in results)}\n'
        f'Observable LiteLLM calls: {sum(row["observable_litellm_calls"] for row in results)}\n'
        'Deeper provider-network attempts: unknown. No outer replay.\n'
        'Returned LiteLLM usage/cost fields (cost is not an invoice):\n'
        + json.dumps(usage, ensure_ascii=False, indent=2) + '\n'
        'Task, Phase 1, native evaluator, training, scorer calls: 0. '
        'No reminder was delivered to Task.\n'
        'One-use authorization removed: '
        + str(not Path('E:/pma_d1v1_phase2_control_20261017/authorization.json').exists())
        + '\nOriginal private records retained locally, not uploaded; their file identities '
        'are in PRIVATE_FILE_HASHES.json. Public allowlist projection contains '
        'full visible request and response files, but no private endpoint, key, '
        'raw lower-level choices, or unknown transport logs.\n'
        'No semantic quality or method superiority conclusion is made.\n\n'
        '18-ITEM STATUS TABLE\n' + table + '\n')
    write(HERE / 'MECHANICAL_SUMMARY.txt', summary)
    test_output = (HERE / 'TEST_RAW_FINAL.txt').read_text(encoding='utf-8')
    public_audit = (HERE / 'public_run/AUDIT.txt').read_text(encoding='utf-8')
    full = (summary + '\n=== FULL ZERO-MODEL TEST OUTPUT ===\n' + test_output +
            '\n=== FULL LIMITED IMPLEMENTATION DIFF ===\n' +
            diff.decode('utf-8', errors='replace') +
            '\n=== FULL PUBLIC REQUEST/RESPONSE AUDIT ===\n' + public_audit)
    write(HERE / 'FULL_AUDIT.txt', full)


def hashes() -> None:
    items = []
    for path in sorted(HERE.rglob('*')):
        if (not path.is_file() or path.name == 'DELIVERY_FILE_HASHES.json' or
                '__pycache__' in path.parts or path.suffix == '.pyc'):
            continue
        relative = path.relative_to(REPO).as_posix()
        blob = subprocess.run(('git', 'show', ':' + relative), cwd=REPO,
                              capture_output=True, check=True).stdout
        items.append({'path': path.relative_to(HERE).as_posix(),
                      'worktree_bytes': path.stat().st_size,
                      'worktree_sha256': sha(path),
                      'git_blob_bytes': len(blob),
                      'git_blob_sha256': hashlib.sha256(blob).hexdigest()})
    write(HERE / 'DELIVERY_FILE_HASHES.json',
          json.dumps(items, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'files': len(items), 'worktree_vs_git_differ': sum(
        row['worktree_sha256'] != row['git_blob_sha256'] for row in items)}))


if __name__ == '__main__':
    if len(sys.argv) == 1:
        build()
    elif sys.argv[1:] == ['--hash-only']:
        hashes()
    else:
        raise SystemExit('usage: python -m build_delivery [--hash-only]')
