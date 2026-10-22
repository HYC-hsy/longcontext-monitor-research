"""Conservative, add-only infrastructure reuse planner; not an execution permit.

Run ``python -m experiment_runner.runtime_reuse --help``. The baseline must be a
trusted local checkout whose existing committed A/B evidence passes its original
single_run_certification verifier. No certificate is rewritten. Existing current
manifest, task/config, one-use authorization and safety gates remain mandatory.
This adapter does NOT change single_run.py's source-equality checks: integrating
its output requires recording baseline proof separately from current run identity.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

D = 'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/'
PROMPT_PATH = D + 'gap_prompts.py'
VERIFIER_MODULE = D.rstrip('/').replace('/', '.') + '.single_run_certification'
ALWAYS_REQUIRED = ['current_source_manifest', 'current_task_and_config_validation',
                   'one_use_authorization', 'existing_safety_gates']


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fingerprint(value) -> str:
    return digest(json.dumps(value, sort_keys=True, separators=(',', ':'),
                             allow_nan=False).encode())


def prompt_parts(data: bytes) -> tuple[str, str]:
    """Normalize ONLY known literal text slots. Never import/execute prompts.

    Replacement search keys stay in the runtime AST, preserving row order and
    matching semantics. Expressions, calls, f-strings and changed container types
    are not text slots. Unknown assignments and all executable AST stay intact.
    """
    tree = ast.parse(data)
    texts = []
    found = set()
    for node in tree.body:
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)):
            continue
        name = node.targets[0].id
        if name not in {'MAINTENANCE', 'ATTENTION', 'PHASE2_REPLACEMENTS'}:
            continue
        if name in found:
            raise ValueError('duplicate prompt assignment')
        found.add(name)
        if name in {'MAINTENANCE', 'ATTENTION'}:
            slots = [node.value]
        else:
            if not isinstance(node.value, ast.Tuple) or not node.value.elts:
                raise ValueError('replacement table must be a nonempty tuple')
            slots = []
            keys = []
            for row in node.value.elts:
                if not isinstance(row, ast.Tuple) or len(row.elts) != 2:
                    raise ValueError('replacement rows must be pairs')
                if not all(isinstance(v, ast.Constant) and type(v.value) is str
                           for v in row.elts):
                    raise ValueError('replacement pairs must be literal strings')
                keys.append(row.elts[0].value)
                slots.append(row.elts[1])
            if len(set(keys)) != len(keys):
                raise ValueError('ambiguous replacement search keys')
        for slot in slots:
            if not isinstance(slot, ast.Constant) or type(slot.value) is not str:
                raise ValueError('prompt text must be a literal string')
            texts.append([name, slot.value])
            slot.value = '<prompt-text>'
    if found != {'MAINTENANCE', 'ATTENTION', 'PHASE2_REPLACEMENTS'}:
        raise ValueError('known prompt slots missing')
    return digest(ast.dump(tree, include_attributes=False).encode()), fingerprint(texts)


def _git(root, *args):
    return subprocess.run(['git', '-C', str(root), *args], check=True,
                          capture_output=True).stdout


def tracked_snapshot(root: Path) -> dict[str, dict]:
    """Read every tracked regular file, reject untracked files and symlinks.

    Do not restrict to an old SOURCE_FILES list: additions must affect identity.
    Ignored build products are not tracked source. Deployments must additionally
    enforce the existing clean checkout/package and dependency/image gates.
    """
    root = root.resolve(strict=True)
    if _git(root, 'ls-files', '--others', '--exclude-standard', '-z'):
        raise ValueError('untracked files: commit or remove them before planning')
    # Git owns executable identity. Windows stat bits are not Git modes.
    check_worktree_mode = (os.name == 'posix' and
        subprocess.run(['git', '-C', str(root), 'config', '--bool', 'core.filemode'],
                       capture_output=True).stdout.strip() == b'true')
    rows = {}
    for raw in _git(root, 'ls-files', '--stage', '-z').split(b'\0'):
        if not raw:
            continue
        meta, raw_path = raw.split(b'\t', 1)
        mode, _, stage = meta.decode().split()
        path = raw_path.decode('utf-8')
        if stage != '0' or mode not in {'100644', '100755'}:
            raise ValueError(f'unsupported tracked entry: {path}')
        local = root / path
        if local.is_symlink() or not local.is_file():
            raise ValueError(f'missing or symlink source: {path}')
        data = local.read_bytes()
        actual_mode = mode
        if check_worktree_mode:
            actual_mode = '100755' if local.stat().st_mode & 0o111 else '100644'
        rows[path] = {'sha256': digest(data), 'mode': actual_mode, 'data': data}
    return rows


def _validate_snapshot(rows):
    if not rows or PROMPT_PATH not in rows:
        raise ValueError('complete source snapshot including gap_prompts.py required')
    for name, row in rows.items():
        p = PurePosixPath(name)
        if p.is_absolute() or '..' in p.parts or p.as_posix() != name:
            raise ValueError('noncanonical source path')
        if (set(row) != {'sha256', 'mode', 'data'} or
                row['mode'] not in {'100644', '100755'} or
                not isinstance(row['data'], bytes) or
                digest(row['data']) != row['sha256']):
            raise ValueError(f'source hash/metadata mismatch: {name}')


def compare_sources(baseline, current, *, baseline_config, current_config,
                    non_runtime_paths=(), verified_evidence_paths=()):
    """Pure classifier; caller must supply exhaustive tracked snapshots.

    non_runtime_paths must name exact, reviewed Markdown documentation, NOT
    extension globs or directory exclusions. verified_evidence_paths is reserved
    for exact paths returned by the baseline verifier, never arbitrary config.
    This pure classifier does not itself assert that proof was verified.
    """
    _validate_snapshot(baseline)
    _validate_snapshot(current)
    docs = frozenset(non_runtime_paths)
    evidence = frozenset(verified_evidence_paths)
    if any(not p.endswith('.md') or p not in set(baseline) | set(current)
           or any(c in p for c in '*?[]') for p in docs):
        raise ValueError('documentation exclusions must name reviewed Markdown paths')
    if any(p not in baseline or p.endswith('.py') for p in evidence):
        raise ValueError('evidence exclusions must name verified baseline artifacts')
    excluded = docs | evidence
    identities = []
    for rows, config in ((baseline, baseline_config), (current, current_config)):
        actual = {p: [v['sha256'], v['mode']] for p, v in sorted(rows.items())}
        runtime = {p: v[:] for p, v in actual.items() if p not in excluded}
        try:
            runtime[PROMPT_PATH][0], prompt = prompt_parts(rows[PROMPT_PATH]['data'])
        except (ValueError, SyntaxError, UnicodeError):
            # Invalid shape is never eligible, even if identical on both sides.
            prompt = None
        identities.append({'source_fingerprint': fingerprint(actual),
                           'source_manifest': actual,
                           'runtime_fingerprint': fingerprint(runtime),
                           'prompt_fingerprint': prompt,
                           'config_fingerprint': fingerprint(config)})
    before, after = identities
    changed = sorted(p for p in set(baseline) | set(current)
                     if before['source_manifest'].get(p) != after['source_manifest'].get(p))
    runtime_changed = (before['runtime_fingerprint'] != after['runtime_fingerprint']
                       or before['prompt_fingerprint'] is None
                       or after['prompt_fingerprint'] is None)
    config_changed = before['config_fingerprint'] != after['config_fingerprint']
    kind = ('runtime_changed' if runtime_changed else 'config_changed' if config_changed
            else 'prompt_text_only' if before['prompt_fingerprint'] != after['prompt_fingerprint']
            else 'non_runtime_only' if changed else 'unchanged')
    full = runtime_changed or config_changed
    return {'classification': kind, 'baseline': before, 'current': after,
            'changed_paths': changed, 'full_check_required': full,
            'infrastructure_reuse_candidate': not full,
            'proof_verified': False, 'execution_authorized': False,
            'required_checks': ALWAYS_REQUIRED +
                (['full_harbor_fake_chain'] if full else
                 ['verify_baseline_evidence', 'short_prompt_contract_tests']),
            'integration_status': 'adapter_only_existing_gates_unchanged'}


def verify_baseline(root: Path, evidence: str) -> dict:
    """Invoke the existing verifier IN the trusted baseline, not a success JSON.

    The caller must trust baseline code just as for its normal offline tests.
    This reads committed evidence; it does not run Harbor, Task or model calls.
    """
    root = root.resolve(strict=True)
    path = (root / evidence).resolve(strict=True)
    relative = path.relative_to(root).as_posix()
    if _git(root, 'status', '--porcelain', '--untracked-files=normal'):
        raise ValueError('baseline checkout must be clean and committed')
    commit = _git(root, 'rev-parse', 'HEAD').decode().strip()
    code = ('import json,sys; sys.path.insert(0, sys.argv[2]); '
            'from pathlib import Path; from ' + VERIFIER_MODULE +
            ' import verify_evidence; print(json.dumps(verify_evidence('
            'Path(sys.argv[1]), require_committed=True, '
            'research_candidate="pma_gap_memory_v0")))')
    result = subprocess.run([sys.executable, '-I', '-c', code, str(path), str(root)], cwd=root,
                            check=True, capture_output=True, text=True)
    proof = json.loads(result.stdout)
    if set(proof.get('outcomes', {})) != {'A', 'B'} or not proof.get('file_sha256'):
        raise ValueError('baseline verifier returned incomplete evidence')
    for p, sha in proof['file_sha256'].items():
        file = (path / p).resolve(strict=True)
        file.relative_to(path)
        if digest(file.read_bytes()) != sha:
            raise ValueError('verified evidence hash mismatch')
    return {'commit': commit, 'evidence_path': relative,
            'verifier': VERIFIER_MODULE + '.verify_evidence',
            'proof': proof, 'proof_fingerprint': fingerprint(proof)}


def verify_short_gate(current: Path, binding: dict, current_config_sha256: str) -> dict:
    """Recompute baseline proof and run pinned gap tests; never trust a passed flag.

    This is only for a later prompt-literal edit on an otherwise identical,
    committed checkout/config. It cannot certify the current cache integration.
    """
    if not isinstance(binding, dict) or set(binding) != {
            'baseline_checkout', 'baseline_evidence', 'baseline_config', 'documentation'}:
        raise ValueError('invalid runtime reuse binding')
    if not isinstance(binding['documentation'], list) or any(
            not isinstance(p, str) for p in binding['documentation']):
        raise ValueError('invalid runtime reuse documentation list')
    current = Path(current).resolve(strict=True)
    baseline = Path(binding['baseline_checkout']).resolve(strict=True)
    if _git(current, 'status', '--porcelain', '--untracked-files=normal'):
        raise ValueError('current checkout must be clean and committed')
    baseline_config = json.loads(Path(binding['baseline_config']).read_text(encoding='utf-8'))
    if fingerprint(baseline_config) != current_config_sha256:
        raise ValueError('baseline and current experiment configuration differ')
    proof = verify_baseline(baseline, binding['baseline_evidence'])
    evidence_paths = [proof['evidence_path'] + '/' + p for p in proof['proof']['file_sha256']]
    plan = compare_sources(tracked_snapshot(baseline), tracked_snapshot(current),
        baseline_config=current_config_sha256, current_config=current_config_sha256,
        non_runtime_paths=binding['documentation'],
        verified_evidence_paths=evidence_paths)
    if plan['full_check_required'] or plan['classification'] not in {
            'prompt_text_only', 'non_runtime_only', 'unchanged'}:
        raise ValueError('runtime or configuration changed; full Harbor check required')
    vendor = current / D / 'vendor/pma_89e5c0d'
    env = {**os.environ, 'PYTHONPATH': os.pathsep.join((str(current),
        str(current / D), str(vendor / 'src'), str(vendor / 'external/harbor/src')))}
    command = [sys.executable, '-B', '-m', 'unittest', 'discover', '-s',
        str(current / D / 'tests'), '-p', 'test_gap*.py', '-v']
    tested = subprocess.run(command, cwd=current, env=env, capture_output=True,
                            text=True, timeout=180)
    if tested.returncode:
        raise ValueError('short prompt/agent/host checks failed: ' + tested.stderr[-1000:])
    count = re.search(r'Ran (\d+) tests? in ', tested.stderr)
    if count is None or int(count.group(1)) < 3 or 'OK' not in tested.stderr:
        raise ValueError('short checks did not report a complete passing suite')
    return {'kind': 'verified_prompt_runtime_reuse_v1',
            'baseline_proof': proof, 'classification': plan['classification'],
            'baseline_source_fingerprint': plan['baseline']['source_fingerprint'],
            'current_source_fingerprint': plan['current']['source_fingerprint'],
            'current_runtime_fingerprint': plan['current']['runtime_fingerprint'],
            'current_prompt_fingerprint': plan['current']['prompt_fingerprint'],
            'config_sha256': current_config_sha256,
            'short_checks': {'command': command[2:], 'return_code': tested.returncode,
                'tests': int(count.group(1)), 'result': 'OK'},
            'execution_authorized': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--current', type=Path, required=True)
    parser.add_argument('--evidence', required=True, help='baseline-relative evidence directory')
    parser.add_argument('--baseline-config', type=Path, required=True)
    parser.add_argument('--current-config', type=Path, required=True)
    parser.add_argument('--documentation', action='append', default=[],
                        help='exact reviewed baseline/current Markdown path, never a glob')
    args = parser.parse_args(argv)
    try:
        proof = verify_baseline(args.baseline, args.evidence)
        baseline = tracked_snapshot(args.baseline)
        current = tracked_snapshot(args.current)
        docs = args.documentation
        if any(not p.endswith('.md') or p not in set(baseline) | set(current)
               or any(c in p for c in '*?[]') for p in docs):
            raise ValueError('documentation exclusions must name reviewed Markdown files')
        evidence_paths = [proof['evidence_path'] + '/' + p
                          for p in proof['proof']['file_sha256']]
        plan = compare_sources(baseline, current,
            baseline_config=json.loads(args.baseline_config.read_text()),
            current_config=json.loads(args.current_config.read_text()),
            non_runtime_paths=docs, verified_evidence_paths=evidence_paths)
        plan['proof_verified'] = True
        plan['baseline_proof'] = proof
        plan['required_checks'] = [c for c in plan['required_checks']
                                   if c != 'verify_baseline_evidence']
        print(json.dumps(plan, sort_keys=True, indent=2))
        return 0
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(json.dumps({'error': str(exc), 'full_check_required': True,
                          'execution_authorized': False}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
