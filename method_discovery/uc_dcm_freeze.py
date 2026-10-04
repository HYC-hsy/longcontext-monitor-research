"""Materialize the authorized DCM block once; no model request."""

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
ROOT = REPO / 'method_discovery/runs/dcm_v0_20261005'
PLAN = ROOT / 'PLAN.json'
MANIFEST = ROOT / 'RUNNER_MANIFEST.json'
FOUR_SLOT = ROOT / 'FOUR_SLOT_PLAN.md'
PREVIOUS = REPO / 'method_discovery/runs/cfs_v0_20261004/PLAN.json'
READINESS = REPO / 'method_discovery/runs/uc_r5_cmp_readiness_20261003/ENVIRONMENT_DRAFT.json'
PRIVATE = Path(r'E:\dcm_v0_private_20261005')
CAMPAIGN = Path(r'E:\LongContext\long_context_bench\output\dcm_v0_20261005')
SOURCE_BASE = Path(r'E:\cfs_v0_private_20261004\launch_CFS\GenericAgent-main')
CFS_CANDIDATE = '74a06444b9f78299dceabdb6a42fa44317462b65'
CANDIDATE = 'dd4c180d4adf82ea8cc4229787e4af3fe8b7b645'
PLAN_COMMIT = 'f9546b6e5df008392defac782bc6fa86756bdd5a'
ORDER = (
    ('fyn-2.2.0-roadmap', 'CFS', '3361dec4537bdbac59a89b2982a5d20e'),
    ('fyn-2.2.0-roadmap', 'CFS+DCM', 'caea820b492d9a880dddf13a0649f2fd'),
    ('ktx-0.13.0-roadmap', 'CFS+DCM', '20c3ea3c5675f07f201f6b1d48762011'),
    ('ktx-0.13.0-roadmap', 'CFS', 'db2086fac2811aff752f70f7a73f2d5e'),
)


def write_once(path, value):
    if path.exists():
        raise RuntimeError(f'Frozen artifact exists: {path}')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode())


def main():
    if PLAN.exists() or MANIFEST.exists() or PRIVATE.exists() or CAMPAIGN.exists():
        raise RuntimeError('DCM deployment or campaign already materialized')
    if subprocess.run(['git', 'diff', '--quiet', CANDIDATE, '--', 'GenericAgent-main'],
                      cwd=REPO).returncode:
        raise RuntimeError('Candidate source differs from frozen implementation')
    changed = subprocess.run(
        ['git', 'diff', '--name-only', CFS_CANDIDATE, CANDIDATE, '--', 'GenericAgent-main'],
        cwd=REPO, capture_output=True, text=True, check=True).stdout.splitlines()
    expected = {'GenericAgent-main/monitor_agent_core/agent.py',
                'GenericAgent-main/monitor_agent_core/dcm_v0.py',
                'GenericAgent-main/tests/test_dcm_v0.py'}
    if set(changed) != expected:
        raise RuntimeError('DCM overlay differs from the frozen implementation inventory')
    sys.path.insert(0, str(Path(r'E:\LongContext\long_context_bench')))
    from scripts.isolated_run_bundle import build_bundle, digest_tree
    from scripts import run_harbor_tb2_m4 as m4

    old = json.loads(PREVIOUS.read_text(encoding='utf-8'))['slots']
    common = json.loads(READINESS.read_text(encoding='utf-8'))['common']
    if common['GA_MAX_TURNS'] != '180':
        raise RuntimeError('Inherited Task turn ceiling changed')
    common['GA_MAX_TURNS'] = '300'
    deployments = {}
    for arm in ('CFS', 'CFS+DCM'):
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
                config.get('monitor_executable_interpretation_surface') is not False or
                config.get('monitor_coarse_to_fine_surface') is not True or
                config.get('monitor_research_view', 'off') != 'off' or
                config.get('monitor_research_intent', 'off') != 'off'):
            raise RuntimeError('Inherited profile is not the frozen CFS manual condition')
        config['monitor_decision_conditioned_measurement'] = arm == 'CFS+DCM'
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
            'monitor_executable_interpretation_surface': False,
            'monitor_coarse_to_fine_surface': True,
            'monitor_decision_conditioned_measurement': arm == 'CFS+DCM',
            'view': 'off', 'intent': 'off',
        }
    if (deployments['CFS']['ga_source_tree_hash_runner_scope'] !=
            deployments['CFS+DCM']['ga_source_tree_hash_runner_scope']):
        raise RuntimeError('Arms do not share one source tree')

    slots, runs = [], []
    for position, (task_id, arm, run_id) in enumerate(ORDER, 1):
        old_slot = next(row for row in old if row['runner']['task_id'] == task_id
                        and row['condition'] == 'CFS')
        live_root = Path(r'E:\runs') / run_id
        if live_root.exists() or any((CAMPAIGN / name / run_id).exists()
                                     for name in ('jobs', 'runs', 'bridge')):
            raise RuntimeError(f'Run identity already used: {run_id}')
        slot = copy.deepcopy(old_slot)
        slot.update(block='dcm-v0', position=position, ordinal=position, condition=arm,
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
    plan = {'schema': 'dcm-v0-four-trial-execution/1', 'execution_authorized': False,
            'authorization_source': 'main-thread DCM-v0 four-slot execution authorization',
            'candidate_commit': CANDIDATE, 'plan_commit': PLAN_COMMIT,
            'four_slot_plan_sha256': file_sha(FOUR_SLOT),
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
    write_once(ROOT / 'EXECUTION_AUTHORIZATION.json', {
        'authorization_source': 'current main research thread', 'execution_authorized': True,
        'candidate_commit': CANDIDATE, 'plan_commit': PLAN_COMMIT,
        'four_slot_plan_sha256': file_sha(FOUR_SLOT), 'plan_sha256': file_sha(PLAN),
        'runner_manifest_sha256': file_sha(MANIFEST),
        'run_order': plan['run_order'], 'scope': 'four fresh trials once each; no rerun or extra slot'})
    print(json.dumps({'plan_sha256': file_sha(PLAN), 'run_order': plan['run_order'],
                      'code_hash': deployments['CFS']['ga_source_tree_hash_runner_scope'],
                      'profile_hashes': {arm: row['monitor_profile_sha256'] for arm, row in deployments.items()},
                      'task_max_turns': 300}, indent=2))


if __name__ == '__main__':
    main()
