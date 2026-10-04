"""Materialize the authorized EIS block without a model request."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys

from method_discovery.uc_r5_execution_bridge import file_sha
from method_discovery import uc_r5_execution_entry as inherited


REPO = Path(__file__).resolve().parent.parent
ROOT = REPO / 'method_discovery/runs/eis_v0_20261004'
PLAN = ROOT / 'PLAN.json'
MANIFEST = ROOT / 'RUNNER_MANIFEST.json'
PREVIOUS = REPO / 'method_discovery/runs/verification_loop_v0_20261004/PLAN.json'
READINESS = REPO / 'method_discovery/runs/uc_r5_cmp_readiness_20261003/ENVIRONMENT_DRAFT.json'
PRIVATE = Path(r'E:\eis_v0_private_20261004')
CAMPAIGN = Path(r'E:\LongContext\long_context_bench\output\eis_v0_20261004')
SOURCE_BASE = Path(r'E:\verification_loop_private_20261004\launch_MANUAL\GenericAgent-main')
CANDIDATE = '6fdde9d425740a802c34f114c518845b89e8a199'
BASE_CODE = '4e88eb471034aa5ae74528fb4758894549b2592e'
PLAN_COMMIT = '7eb4551e45e3cc82405862754b53fa044fbcc037'
ORDER = (
    ('fyn-2.2.0-roadmap', 'BASE', 'e832df5b0a8e4fb2bb2f4d5338ada5d4'),
    ('fyn-2.2.0-roadmap', 'EIS', '82b860b44c5e4bb8a81b9d01ead5703c'),
    ('ktx-0.13.0-roadmap', 'EIS', '3ab0193ad553424ba1a53b87fdec61e8'),
    ('ktx-0.13.0-roadmap', 'BASE', 'cbbd416ac6794ca38adf5b4c5d31e873'),
)


def write_once(path, value):
    if path.exists():
        raise RuntimeError(f'Frozen artifact exists: {path}')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode())


def main():
    if PLAN.exists() or MANIFEST.exists() or PRIVATE.exists():
        raise RuntimeError('EIS deployment already materialized')
    if subprocess.run(['git', 'diff', '--quiet', CANDIDATE, '--', 'GenericAgent-main'], cwd=REPO).returncode:
        raise RuntimeError('Candidate production source differs from implementation commit')
    changed = subprocess.run(
        ['git', 'diff', '--name-only', BASE_CODE, CANDIDATE, '--', 'GenericAgent-main'],
        cwd=REPO, capture_output=True, text=True, check=True).stdout.splitlines()
    if not changed or any(not path.startswith('GenericAgent-main/') for path in changed):
        raise RuntimeError('Unexpected EIS source inventory')
    for relative in ('monitor_agent_core/agent.py', 'monitor_agent_core/runtime.py'):
        expected = subprocess.run(['git', 'rev-parse', f'{BASE_CODE}:GenericAgent-main/{relative}'],
                                  cwd=REPO, capture_output=True, text=True, check=True).stdout.strip()
        actual = subprocess.run(['git', 'hash-object', str(SOURCE_BASE / relative)],
                                cwd=REPO, capture_output=True, text=True, check=True).stdout.strip()
        if actual != expected:
            raise RuntimeError(f'Inherited source base mismatch: {relative}')
    sys.path.insert(0, str(Path(r'E:\LongContext\long_context_bench')))
    from scripts.isolated_run_bundle import build_bundle, digest_tree
    from scripts import run_harbor_tb2_m4 as m4

    old = json.loads(PREVIOUS.read_text(encoding='utf-8'))['slots']
    common = json.loads(READINESS.read_text(encoding='utf-8'))['common']
    if common['GA_MAX_TURNS'] != '180':
        raise RuntimeError('Inherited Task turn ceiling changed')
    common['GA_MAX_TURNS'] = '300'
    deployments = {}
    for arm in ('BASE', 'EIS'):
        source = PRIVATE / f'launch_{arm}' / 'GenericAgent-main'
        shutil.copytree(SOURCE_BASE, source)
        for relative in changed:
            target = source / relative.removeprefix('GenericAgent-main/')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO / relative, target)
        profile = source.parent / 'monitor_config/models.local.json'
        profile.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SOURCE_BASE.parent / 'monitor_config/models.local.json', profile)
        profiles = json.loads(profile.read_text(encoding='utf-8'))
        config = profiles['claude_monitor_opus48']
        if (config.get('monitor_dcec') is not True or
                config.get('monitor_path_control_v0') is not True or
                config.get('monitor_verification_loop_v0') is not True or
                config.get('monitor_verification_runtime_managed') is not False or
                config.get('monitor_root_scope_v1') != 'off' or
                config.get('monitor_research_view', 'off') != 'off' or
                config.get('monitor_research_intent', 'off') != 'off'):
            raise RuntimeError('Inherited profile is not the frozen manual continuous-root profile')
        config['monitor_executable_interpretation_surface'] = arm == 'EIS'
        profile.write_text(json.dumps(profiles, ensure_ascii=False), encoding='utf-8')
        bundle = PRIVATE / f'bundle_{arm}'
        copied, _ = build_bundle(bundle, source, m4.GA_RUNTIME, m4.python_home().name,
                                 'native_claude_cc_vibe_opus48', 'claude_monitor_opus48', 15340,
                                 monitor_profile_path=profile)
        deployments[arm] = {
            'ga_host_root': str(source), 'monitor_profile_path': str(profile),
            'monitor_profile_sha256': file_sha(profile),
            'bundle_source': str(copied), 'bundle_snapshot_sha256': digest_tree(copied),
            'bundle_deployed_profile_sha256': file_sha(copied / 'monitor_agent_core/models.local.json'),
            'ga_source_tree_hash_runner_scope': m4.tree_hash(source, ga_mode=True),
            'configured_monitor_model': config['model'], 'monitor_dcec': True,
            'monitor_path_control_v0': True, 'monitor_root_scope_v1': 'off',
            'monitor_verification_loop_v0': True, 'monitor_verification_runtime_managed': False,
            'monitor_executable_interpretation_surface': arm == 'EIS',
            'view': 'off', 'intent': 'off',
        }
    if deployments['BASE']['ga_source_tree_hash_runner_scope'] != deployments['EIS']['ga_source_tree_hash_runner_scope']:
        raise RuntimeError('BASE and EIS do not share one code tree')

    slots, runs = [], []
    for position, (task_id, arm, run_id) in enumerate(ORDER, 1):
        old_slot = next(row for row in old if row['runner']['task_id'] == task_id)
        live_root = Path(r'E:\runs') / run_id
        if live_root.exists() or any((CAMPAIGN / name / run_id).exists()
                                     for name in ('jobs', 'runs', 'bridge')):
            raise RuntimeError(f'Run identity already used: {run_id}')
        slot = copy.deepcopy(old_slot)
        slot.update(block='eis-v0', position=position, ordinal=position, condition=arm,
                    candidate_commit=CANDIDATE, run_id=run_id, live_root=str(live_root),
                    status='not_started')
        slot['deployment'] = copy.deepcopy(deployments[arm])
        slot['output'] = {'campaign_root': str(CAMPAIGN),
                          'jobs_subdir': f'jobs/{run_id}', 'runs_subdir': f'runs/{run_id}'}
        slot['runner']['run_id_argument'] = run_id
        slot['runner']['task_max_turns'] = 300
        slots.append(slot)
        env = dict(common)
        env.update(GA_BASELINE_CONDITION='original', GA_HOST_ROOT=slot['deployment']['ga_host_root'],
                   BENCHMARK_CAMPAIGN_ROOT=str(CAMPAIGN),
                   GA_METHOD_EXPECTED_SOURCE_SHA256=slot['deployment']['ga_source_tree_hash_runner_scope'],
                   GA_EXPERIMENT_HARNESS_SHA256=slot['runner']['execution_harness_sha256'])
        runs.append({'run_id': run_id, 'environment': env})
    plan = {'schema': 'eis-v0-four-trial-plan/1', 'execution_authorized': False,
            'authorization_source': 'main-thread EIS-v0 four-slot authorization',
            'candidate_commit': CANDIDATE, 'plan_commit': PLAN_COMMIT,
            'run_order': [row[2] for row in ORDER], 'slots': slots,
            'source_overlay_paths': changed}
    write_once(PLAN, plan)
    write_once(MANIFEST, {'secrets_included': False, 'runs': runs})
    for slot in slots:
        write_once(ROOT / f"AUTH_{slot['run_id']}.json", {
            'execution_authorized': True, 'run_id': slot['run_id'],
            'candidate_commit': CANDIDATE, 'plan_sha256': file_sha(PLAN),
            'runner_manifest': str(MANIFEST.resolve()),
            'runner_manifest_sha256': file_sha(MANIFEST),
            'bridge_source_sha256': inherited.bridge_source_hash(),
            'task_model': 'claude-opus-4-8'})
    print(json.dumps({'plan_sha256': file_sha(PLAN), 'run_order': plan['run_order'],
                      'code_hash': deployments['BASE']['ga_source_tree_hash_runner_scope'],
                      'task_max_turns': 300}, indent=2))


if __name__ == '__main__':
    main()
