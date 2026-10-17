"""Generate reviewable offline evidence from committed D1/V1 fixtures.

This script makes no network or model calls. Generated files are mechanical
copies/projections of the frozen source diff, local unit-test output, and
already redacted synthetic fixture records.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
REPO = next(parent for parent in PROJECT.parents if (parent / '.git').exists())
BASELINE = '793a08abc570209c0781074c13f43b951142c51d'
TESTS = (
    'test_decision_reminder_agent', 'test_episode',
    'test_live_wiring', 'test_single_run_offline',
)


def command(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=REPO, capture_output=True, text=True,
                          encoding='utf-8', errors='replace', check=False)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hash_index() -> int:
    rows = []
    for file in sorted(ROOT.rglob('*')):
        if not file.is_file() or file.name == 'FILE_HASHES_ALL.json':
            continue
        repo_path = file.relative_to(REPO).as_posix()
        staged = subprocess.run(('git', 'show', ':' + repo_path), cwd=REPO,
                                capture_output=True, check=False)
        if staged.returncode:
            raise RuntimeError(f'not staged: {repo_path}')
        rows.append({'path': file.relative_to(ROOT).as_posix(),
                     'worktree_size': file.stat().st_size,
                     'worktree_sha256': digest(file),
                     'git_blob_size': len(staged.stdout),
                     'git_blob_sha256': hashlib.sha256(staged.stdout).hexdigest()})
    (ROOT / 'FILE_HASHES_ALL.json').write_text(json.dumps(rows, indent=2),
                                               encoding='utf-8')
    return len(rows)


def main() -> None:
    if len(sys.argv) == 2 and sys.argv[1] == '--hash-only':
        print(json.dumps({'hashed_files': hash_index()}, indent=2))
        return
    env = os.environ.copy()
    env['PYTHONPATH'] = os.pathsep.join((str(REPO),
        str(REPO / 'GenericAgent-main'), str(PROJECT),
        str(PROJECT / 'vendor/pma_89e5c0d/src'),
        str(PROJECT / 'vendor/pma_89e5c0d/external/harbor/src')))
    env['LITELLM_LOCAL_MODEL_COST_MAP'] = 'True'
    names = [f'method_discovery.curator_supervisor_convergence_v0.'
             f'pma_full_upstream_ga_v1_20261013.{name}' for name in TESTS]
    runner = ("import sys,unittest; import method_discovery."
        "curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013."
        "offline_launcher as m; sys.modules['offline_launcher']=m; "
        f"x=unittest.defaultTestLoader.loadTestsFromNames({names!r}); "
        "y=unittest.TextTestRunner(verbosity=1).run(x); "
        "sys.exit(not y.wasSuccessful())")
    tested = subprocess.run((sys.executable, '-c', runner), cwd=REPO,
                            env=env, capture_output=True, text=True,
                            encoding='utf-8', errors='replace', check=False)
    test_log = ROOT / 'TEST_RAW.txt'
    test_log.write_text('COMMAND: python -c <package-alias unittest runner>\n'
        'TEST MODULES: ' + ', '.join(TESTS) + '\n'
        f'EXIT CODE: {tested.returncode}\n\nSTDOUT:\n{tested.stdout}'
        f'\nSTDERR:\n{tested.stderr}', encoding='utf-8')
    if tested.returncode:
        raise RuntimeError('targeted offline regressions failed; raw output saved')

    changed = command('git', 'diff', '--binary', BASELINE, 'HEAD', '--',
                      'method_discovery/curator_supervisor_convergence_v0/'
                      'pma_full_upstream_ga_v1_20261013/*.py')
    if changed.returncode:
        raise RuntimeError(changed.stderr)
    patch = ROOT / 'IMPLEMENTATION_DIFF.patch'
    patch.write_text(changed.stdout, encoding='utf-8')

    screen = json.loads((ROOT / 'screen_fake/actual_requests.json').read_text(
        encoding='utf-8'))
    examples = []
    for variant in ('U', 'V1', 'D1'):
        row = next(row for row in screen if row['arm'] == '07' and
                   row['pma_step'] == 235 and row['variant'] == variant)
        examples.append(f'=== ARCHIVED PHASE2 {variant}, ARM 07 STEP 235 ===\n'
                        + json.dumps(row['request'], ensure_ascii=False, indent=2))
    for variant in ('u', 'v1', 'd1'):
        path = ROOT / f'certification_fixture_{variant}/B/memory_payload.jsonl'
        rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
        examples.append(f'=== REAL HARBOR FAKE B {variant.upper()} PHASES ===\n'
                        + json.dumps(rows, ensure_ascii=False, indent=2))
    samples = '\n\n'.join(examples) + '\n'
    (ROOT / 'REQUEST_SAMPLES.txt').write_text(samples, encoding='utf-8')

    results = []
    for variant in ('u', 'v1', 'd1'):
        base = ROOT / f'certification_fixture_{variant}'
        arms = {}
        for condition in ('A', 'B'):
            live = json.loads((base / condition / 'live_result.json').read_text(
                encoding='utf-8'))
            arms[condition] = {'research_candidate': live.get('research_candidate'),
                               'harbor_return_code': live.get('harbor_return_code'),
                               'worker_return_code': live.get('worker_return_code'),
                               'primary_failure': live.get('primary_failure'),
                               'fake_provider_captures': live.get('fake_provider_captures'),
                               'cleanup_confirmed': live.get('cleanup_confirmed')}
        results.append({'fixture': variant, 'arms': arms})
    head = command('git', 'rev-parse', 'HEAD').stdout.strip()
    summary = ('PMA D1/V1 OFFLINE AUDIT — 2026-10-17\n\n'
        f'Baseline: {BASELINE}\nAudit-generator HEAD: {head}\n'
        'Real Task/PMA/provider/native-evaluator/training/scoring calls: 0.\n'
        'Synthetic Harbor tests use fake transport and synthetic test.sh only.\n'
        'Original U PMA remains the default; D1/V1 are B-only, opt-in strategies.\n'
        'Original vendor files and GA model-visible task inputs were not edited.\n\n'
        'Reuse: upstream PMA 89e5c0d6aadfe531a1aee42fd290d48be89973dd '
        '(Apache-2.0) MemoryAgent.process, Phase 1/tool dispatch, UniversalMemory, '
        'BM25, parser, transport; local subclass overrides only Phase 2 call/prompt.\n'
        'PoS d6acb430, LivePlan 3c72ab7a, ReflAct EMNLP 2025 are design '
        'references only, no code copied or extra dependency installed.\n\n'
        'D1 changes Phase 2 system and final task instruction. V1 changes '
        'exactly three system lines and one task phrase. U untouched. '
        'Phase 1, bank, context order, model call count, output parser remain upstream.\n'
        'Historical Phase 2 screen: six archived redacted public prompts, '
        'U/V1/D1 once each, 18 fake calls. This is a fixed-string-input '
        'diagnostic, not a reconstruction of live post-bank state or an '
        'authorized 18-call real experiment.\n'
        'Host fixture: A and B for U/V1/D1 pass actual launcher/Harbor/Docker '
        'synthetic lifecycle; B has two fake PMA stages and reminder append '
        'into a subsequent GA request. No official benchmark evaluation.\n'
        'First archived example system hashes (U/V1/D1): '
        + ', '.join(f"{row['variant']}={hashlib.sha256(row['request']['system'].encode('utf-8')).hexdigest()}"
                    for row in screen[:3]) + '\n' +
        'The first D1 B fixture failed before any container/request because '
        'offline_launcher only admitted v4; ec3de05b fixed that v5 routing. '
        'The first direct top-level test invocation failed module alias import; '
        'the supported package-alias command is captured in TEST_RAW.\n'
        'Historical fixture_v5 is now rejected for changed source identity; '
        'new U/V1/D1 evidence is separately committed.\n\n'
        'Fixture mechanical results:\n'
        + json.dumps(results, ensure_ascii=False, indent=2)
        + '\n\nLimitations: no real endpoint compatibility or D1/V1 quality claim; '
        'archived prompts may contain prior PMA-influenced Task context; '
        'synthetic fake responses do not establish semantic usefulness.\n'
        'Private profile bytes, credentials and endpoints are excluded.\n\n'
        'PROMPTS AND EXAMPLES: REQUEST_SAMPLES.txt\n'
        'RAW TEST OUTPUT: TEST_RAW.txt\n'
        'FULL LIMITED CODE DIFF: IMPLEMENTATION_DIFF.patch\n'
        '18-REQUEST UNAUTHORIZED DRAFT: screen_draft/manifest.json\n'
        '18 FAKE ACTUAL REQUESTS: screen_fake/actual_requests.json\n'
        'HARBOR FAKE RAW EVIDENCE: certification_fixture_{u,v1,d1}/\n')
    summary += ('\n=== COMPLETE REQUEST SAMPLES ===\n' + samples +
                '\n=== COMPLETE RAW TEST OUTPUT ===\n' + test_log.read_text(encoding='utf-8') +
                '\n=== COMPLETE LIMITED CODE DIFF ===\n' + changed.stdout)
    (ROOT / 'AUDIT_D1_V1_OFFLINE.txt').write_text(summary, encoding='utf-8')
    print(json.dumps({'test_returncode': tested.returncode,
                      'audit_head': head}, indent=2))


if __name__ == '__main__':
    main()
