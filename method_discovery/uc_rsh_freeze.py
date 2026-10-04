"""Materialize only the authorized RSH four-slot identities; no model request."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys

from method_discovery.uc_dcm_freeze import write_once
from method_discovery.uc_r5_execution_bridge import file_sha
from method_discovery import uc_r5_execution_entry as inherited


REPO = Path(__file__).resolve().parent.parent
ROOT = REPO / 'method_discovery/runs/rsh_v0_20261005'
PLAN = ROOT / 'PLAN.json'
MANIFEST = ROOT / 'RUNNER_MANIFEST.json'
FOUR_SLOT = ROOT / 'FOUR_SLOT_PLAN.md'
PREVIOUS = REPO / 'method_discovery/runs/dcm_v0_20261005/PLAN.json'
READINESS = REPO / 'method_discovery/runs/uc_r5_cmp_readiness_20261003/ENVIRONMENT_DRAFT.json'
PRIVATE = Path(r'E:\rsh_v0_private_20261005')
CAMPAIGN = Path(r'E:\LongContext\long_context_bench\output\rsh_v0_20261005')
SOURCE_BASE = Path(r'E:\dcm_v0_private_20261005\launch_CFS+DCM\GenericAgent-main')
DCM_CANDIDATE = 'dd4c180d4adf82ea8cc4229787e4af3fe8b7b645'
CANDIDATE = '0f02c15c0c849bf255fad4cfcc768c58e2c4ad60'
PLAN_COMMIT = 'ff64d9303956b35795460e6fde6d308374f33a50'
ORDER = (
    ('fyn-2.2.0-roadmap', 'CFS+DCM', 'fe003754af944ef6b1ae1724bdbd346f'),
    ('fyn-2.2.0-roadmap', 'CFS+DCM+RSH', '4ae60f105e16438397c26d5c10359a8e'),
    ('ktx-0.13.0-roadmap', 'CFS+DCM+RSH', '7a4444cdb19d46e79b4d7f821cb61a97'),
    ('ktx-0.13.0-roadmap', 'CFS+DCM', '718c280577bd47028bad72b100717333'),
)


def main():
    if PLAN.exists() or MANIFEST.exists() or PRIVATE.exists() or CAMPAIGN.exists():
        raise RuntimeError('RSH deployment or campaign already materialized')
    if subprocess.run(['git', 'diff', '--quiet', CANDIDATE, '--', 'GenericAgent-main'],
                      cwd=REPO).returncode:
        raise RuntimeError('Candidate source differs from frozen implementation')
    changed = subprocess.run(
        ['git', 'diff', '--name-only', DCM_CANDIDATE, CANDIDATE, '--',
         'GenericAgent-main/monitor_agent_core'], cwd=REPO, capture_output=True,
        text=True, check=True).stdout.splitlines()
    expected = {'GenericAgent-main/monitor_agent_core/agent.py',
                'GenericAgent-main/monitor_agent_core/rsh_v0.py'}
    if set(changed) != expected:
        raise RuntimeError('RSH source overlay differs from reviewed inventory')
    sys.path.insert(0, str(Path(r'E:\LongContext\long_context_bench')))
    from scripts.isolated_run_bundle import build_bundle, digest_tree
    from scripts import run_harbor_tb2_m4 as m4

    previous = json.loads(PREVIOUS.read_text(encoding='utf-8'))['slots']
    dcm_deployment = next(row['deployment'] for row in previous
                          if row['condition'] == 'CFS+DCM')
    if m4.tree_hash(SOURCE_BASE, ga_mode=True) != dcm_deployment['ga_source_tree_hash_runner_scope']:
        raise RuntimeError('Inherited DCM source tree differs from frozen deployment')
    common = json.loads(READINESS.read_text(encoding='utf-8'))['common']
    if common['GA_MAX_TURNS'] != '180':
        raise RuntimeError('Inherited Task turn ceiling changed')
    common['GA_MAX_TURNS'] = '300'
    deployments = {}
    for arm in ('CFS+DCM', 'CFS+DCM+RSH'):
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
        fixed = {'monitor_dcec': True, 'monitor_path_control_v0': True,
                 'monitor_verification_loop_v0': True,
                 'monitor_verification_runtime_managed': False,
                 'monitor_root_scope_v1': 'off',
                 'monitor_executable_interpretation_surface': False,
                 'monitor_coarse_to_fine_surface': True,
                 'monitor_decision_conditioned_measurement': True}
        if any(config.get(key) != value for key, value in fixed.items()):
            raise RuntimeError('Inherited profile is not frozen DCM manual condition')
        if config.get('monitor_research_view', 'off') != 'off' or config.get(
                'monitor_research_intent', 'off') != 'off':
            raise RuntimeError('Research view/intent unexpectedly enabled')
        config['monitor_release_support_horizon'] = arm == 'CFS+DCM+RSH'
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
            'configured_monitor_model': config['model'], **fixed,
            'monitor_release_support_horizon': arm == 'CFS+DCM+RSH',
            'view': 'off', 'intent': 'off',
        }
    if (deployments['CFS+DCM']['ga_source_tree_hash_runner_scope'] !=
            deployments['CFS+DCM+RSH']['ga_source_tree_hash_runner_scope']):
        raise RuntimeError('Arms do not share one candidate source tree')

    slots, runs = [], []
    for position, (task_id, arm, run_id) in enumerate(ORDER, 1):
        old_slot = next(row for row in previous if row['runner']['task_id'] == task_id
                        and row['condition'] == 'CFS+DCM')
        live_root = Path(r'E:\runs') / run_id
        if live_root.exists() or any((CAMPAIGN / name / run_id).exists()
                                     for name in ('jobs', 'runs', 'bridge')):
            raise RuntimeError(f'Run identity already used: {run_id}')
        slot = copy.deepcopy(old_slot)
        slot.update(block='rsh-v0', position=position, ordinal=position,
                    condition=arm, candidate_commit=CANDIDATE, run_id=run_id,
                    live_root=str(live_root), status='not_started')
        slot['deployment'] = copy.deepcopy(deployments[arm])
        slot['output'] = {'campaign_root': str(CAMPAIGN),
                          'jobs_subdir': f'jobs/{run_id}', 'runs_subdir': f'runs/{run_id}'}
        slot['runner']['run_id_argument'] = run_id
        slot['runner']['task_max_turns'] = 300
        slots.append(slot)
        env = dict(common)
        env.update(GA_BASELINE_CONDITION='original',
                   GA_HOST_ROOT=slot['deployment']['ga_host_root'],
                   BENCHMARK_CAMPAIGN_ROOT=str(CAMPAIGN),
                   GA_METHOD_EXPECTED_SOURCE_SHA256=slot['deployment']['ga_source_tree_hash_runner_scope'],
                   GA_EXPERIMENT_HARNESS_SHA256=slot['runner']['execution_harness_sha256'])
        runs.append({'run_id': run_id, 'environment': env})
    plan = {'schema': 'rsh-v0-four-trial-execution/1', 'execution_authorized': False,
            'authorization_source': 'main-thread RSH-v0 four-slot execution authorization',
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
                      'code_hash': deployments['CFS+DCM']['ga_source_tree_hash_runner_scope'],
                      'profile_hashes': {arm: row['monitor_profile_sha256']
                                         for arm, row in deployments.items()},
                      'task_max_turns': 300}, indent=2))


if __name__ == '__main__':
    main()
