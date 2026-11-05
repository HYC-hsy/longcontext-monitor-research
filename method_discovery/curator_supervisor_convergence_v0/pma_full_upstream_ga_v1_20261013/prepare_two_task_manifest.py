"""Freeze the two new tasks without reusing six-task lifecycle evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
from tempfile import TemporaryDirectory

from long_context_bench.scripts.isolated_run_bundle import digest_tree

from .export_official_evaluator import COMMIT, export_task
from .offline_launcher import image_identity
from .six_task_assets import descriptor, materialize_public
from .two_task_plan import ORDER, SCHEMA


ROOT = Path(__file__).resolve().parents[3]
HARBOR_COMMIT = '459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc'
SOURCE_FILES = (
    'GenericAgent-main/agent_loop.py',
    'GenericAgent-main/llmcore.py',
    'GenericAgent-main/pma_upstream_bridge.py',
    'long_context_bench/adapters/harbor_ga_agent.py',
    'long_context_bench/scripts/isolated_run_bundle.py',
    *('method_discovery/curator_supervisor_convergence_v0/'
      'pma_full_upstream_ga_v1_20261013/' + name for name in (
          'episode.py', 'event_spool.py', 'worker_main.py', 'harbor_adapter.py',
          'pma_harbor_hooks.py', 'live_launcher.py', 'offline_launcher.py',
          'native_shared_verifier.py', 'six_task_assets.py',
          'export_official_evaluator.py', 'two_task_plan.py',
          'prepare_two_task_manifest.py', 'two_task_preflight.py',
          'vendor/pma_89e5c0d/src/memory_agent/memory/memory_agent.py',
          'vendor/pma_89e5c0d/src/memory_agent/memory_enabled_agent.py',
    )),
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> bytes:
    return subprocess.run(['git', *args], cwd=ROOT, check=True,
                          capture_output=True).stdout


def source_identity() -> tuple[str, dict[str, str]]:
    head = _git('rev-parse', 'HEAD').decode('ascii').strip()
    if _git('status', '--porcelain', '--untracked-files=no'):
        raise RuntimeError('two-task production worktree is not clean')
    hashes = {}
    for name in SOURCE_FILES:
        current = _sha(ROOT / name)
        committed = hashlib.sha256(_git('show', f'HEAD:{name}')).hexdigest()
        if current != committed:
            raise RuntimeError(f'two-task source differs from committed bytes: {name}')
        hashes[name] = current
    return head, hashes


def prepare(source: Path, task_profile: Path, pma_profile: Path,
            preflight: Path) -> dict:
    head, sources = source_identity()
    report = json.loads(preflight.read_text(encoding='utf-8'))
    if (report.get('code_commit') != head or
            report.get('harbor_commit') != HARBOR_COMMIT or
            report.get('passed') is not True or
            set(report.get('fixtures', {})) != {row[1] for row in ORDER} or
            report.get('nginx_service_preserved') is not True or
            report.get('extra_writer_rejected') is not True):
        raise RuntimeError('current two-task zero-model preflight not established')
    task_settings = runpy.run_path(str(task_profile))['native_claude_cc_vibe_opus48']
    pma_settings = json.loads(pma_profile.read_text(encoding='utf-8'))[
        'claude_monitor_opus48']
    if (task_settings.get('model'), pma_settings.get('model')) != (
            'claude-opus-4-8', 'claude-opus-4-8'):
        raise RuntimeError('frozen Task/PMA model identity differs')
    assets = {}
    for _, task, _, _ in ORDER:
        desc = descriptor(source, task)
        with TemporaryDirectory(prefix='pma-two-public-') as directory:
            root = Path(directory)
            public = root / 'public'
            materialize_public(source, task, public, desc['public_members'])
            (public / 'tests').mkdir()
            (public / 'solution').mkdir()
            tests = root / 'tests'
            tests.mkdir()
            export_task(source, task, tests)
            public_hash, tests_hash = digest_tree(public), digest_tree(tests)
            test_sh_hash = _sha(tests / 'test.sh')
        image = image_identity(desc['image_tag'])
        if (image['platform'] != 'linux/amd64' or
                len(image['repo_digests']) != 1):
            raise RuntimeError(f'{task}: fixed image identity unavailable')
        assets[task] = {**desc, 'image_id': image['image_id'],
                        'repo_digest': image['repo_digests'][0],
                        'platform': image['platform'],
                        'public_task_tree_sha256': public_hash,
                        'official_evaluator_members': desc['evaluator_members'],
                        'native_tests_tree_sha256': tests_hash,
                        'native_test_sh_sha256': test_sh_hash}
    config = {'method': 'GA_plus_simple_predictive_PMA',
              'condition': 'B', 'agent_wall_seconds': 14400,
              'task_turns_max': 300, 'harbor_whole_trial_retries': 0,
              'evaluation': 'native_Harbor_SHARED',
              'task_profile_name': 'native_claude_cc_vibe_opus48',
              'pma_profile_name': 'claude_monitor_opus48'}
    config_hash = hashlib.sha256(json.dumps(config, sort_keys=True,
        separators=(',', ':')).encode('utf-8')).hexdigest()
    return {'schema': SCHEMA, 'status': 'prepared_not_executed',
            'execution_authorized': False, 'code_commit': head,
            'official_source_git_commit': COMMIT,
            'harbor_commit': HARBOR_COMMIT,
            'source_files_sha256': sources,
            'task_profile_sha256': _sha(task_profile),
            'pma_profile_sha256': _sha(pma_profile),
            'resolved_models_public': {
                'task': {key: task_settings.get(key) for key in
                         ('model', 'max_tokens', 'temperature', 'max_retries')},
                'pma': {key: pma_settings.get(key) for key in
                        ('model', 'max_tokens', 'temperature', 'max_retries',
                         'provider', 'api_mode', 'thinking_type',
                         'reasoning_effort', 'connect_timeout', 'read_timeout')}},
            'config': config, 'config_sha256': config_hash,
            'native_shared_certification': {
                'preflight_path': str(preflight.resolve(strict=True)),
                'preflight_sha256': _sha(preflight)},
            'assets': assets,
            'planned_order': [dict(order=o, task=t, repeat=r, condition=c)
                              for o, t, r, c in ORDER]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--official-source-git', type=Path, required=True)
    parser.add_argument('--task-profile-file', type=Path, required=True)
    parser.add_argument('--pma-profile-file', type=Path, required=True)
    parser.add_argument('--preflight', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    manifest = prepare(args.official_source_git, args.task_profile_file,
                       args.pma_profile_file, args.preflight)
    args.output.write_text(json.dumps(manifest, indent=2, ensure_ascii=False),
                           encoding='utf-8')
    print(json.dumps({'code_commit': manifest['code_commit'],
                      'schema': manifest['schema'],
                      'tasks': list(manifest['assets'])}))


if __name__ == '__main__':
    main()
