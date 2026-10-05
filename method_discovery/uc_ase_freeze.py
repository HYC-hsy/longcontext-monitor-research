"""Freeze only the authorized Kitex-then-Fyne ASE-v0 discovery pair; no model call."""

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
ROOT = REPO / 'method_discovery/runs/ase_v0_20261005/discovery_01'
PLAN = ROOT / 'PLAN.json'
MANIFEST = ROOT / 'RUNNER_MANIFEST.json'
PREVIOUS = REPO / 'method_discovery/runs/cqs_v0_20261005/PLAN.json'
READINESS = REPO / 'method_discovery/runs/uc_r5_cmp_readiness_20261003/ENVIRONMENT_DRAFT.json'
PRIVATE = Path(r'E:\ase_v0_private_20261005')
CAMPAIGN = Path(r'E:\LongContext\long_context_bench\output\ase_v0_discovery_20261005')
SOURCE_BASE = Path(r'E:\cqs_v0_private_20261005\launch_CQS\GenericAgent-main')
CQS_IMPL = 'cab01032c82d817b1b9ba28e18ef2504bd4a87a7'
CANDIDATE = '0889a51c6f176836b04b19279b8c99ce674e17a4'
MECHANISM = '5ab7d83ab6bb5db2ddb90251fd7b75ad1ca0f7c3'
ORDER = (
    ('ktx-0.13.0-roadmap', 'fd962a22d2bc4af195d90e9de9ee34cd'),
    ('fyn-2.2.0-roadmap', '05b98c58e31a43a597d142fee3e26392'),
)


def write_once(path, value):
    if path.exists():
        raise RuntimeError(f'Frozen artifact exists: {path}')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode())


def main():
    if PLAN.exists() or MANIFEST.exists() or PRIVATE.exists() or CAMPAIGN.exists():
        raise RuntimeError('ASE deployment or campaign already materialized')
    if subprocess.run(['git', 'diff', '--quiet', CANDIDATE, '--',
                       'GenericAgent-main', 'long_context_bench'], cwd=REPO).returncode:
        raise RuntimeError('Candidate source differs from frozen implementation')
    changed = subprocess.run(
        ['git', 'diff', '--name-only', CQS_IMPL, CANDIDATE, '--', 'GenericAgent-main'],
        cwd=REPO, capture_output=True, text=True, check=True).stdout.splitlines()
    expected = {'GenericAgent-main/monitor_agent_core/agent.py',
                'GenericAgent-main/monitor_agent_core/ase_v0.py',
                'GenericAgent-main/tests/test_ase_v0.py'}
    if set(changed) != expected:
        raise RuntimeError('ASE overlay differs from frozen implementation inventory')
    sys.path.insert(0, str(Path(r'E:\LongContext\long_context_bench')))
    from scripts.isolated_run_bundle import build_bundle, digest_tree
    from scripts import run_harbor_tb2_m4 as m4

    old = json.loads(PREVIOUS.read_text(encoding='utf-8'))['slots']
    old_hash = old[0]['deployment']['ga_source_tree_hash_runner_scope']
    if m4.tree_hash(SOURCE_BASE, ga_mode=True) != old_hash:
        raise RuntimeError('Inherited CQS private source identity mismatch')
    common = json.loads(READINESS.read_text(encoding='utf-8'))['common']
    if common['GA_MAX_TURNS'] != '180':
        raise RuntimeError('Inherited Task turn ceiling changed')
    common['GA_MAX_TURNS'] = '300'

    source = PRIVATE / 'launch_ASE' / 'GenericAgent-main'
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
    if config['model'] != 'claude-opus-4-8':
        raise RuntimeError('Inherited Monitor model changed')
    required_old = {
        'monitor_dcec': True, 'monitor_path_control_v0': True,
        'monitor_verification_loop_v0': True, 'monitor_verification_runtime_managed': False,
        'monitor_coarse_to_fine_surface': True, 'monitor_decision_conditioned_measurement': True,
        'monitor_control_question_state': True,
        'monitor_executable_interpretation_surface': False,
        'monitor_release_support_horizon': False, 'monitor_root_scope_v1': 'off',
        'monitor_research_view': 'off', 'monitor_research_intent': 'off',
    }
    if any(config.get(key) != value for key, value in required_old.items()):
        raise RuntimeError('Inherited private profile is not frozen CQS condition')
    for key in ('monitor_dcec', 'monitor_path_control_v0', 'monitor_verification_loop_v0',
                'monitor_coarse_to_fine_surface', 'monitor_decision_conditioned_measurement',
                'monitor_control_question_state'):
        config[key] = False
    config['monitor_adaptive_supervisory_environment'] = True
    expected_switches = {
        'monitor_adaptive_supervisory_environment': True,
        'monitor_dcec': False, 'monitor_path_control_v0': False,
        'monitor_verification_loop_v0': False, 'monitor_coarse_to_fine_surface': False,
        'monitor_decision_conditioned_measurement': False, 'monitor_control_question_state': False,
        'monitor_executable_interpretation_surface': False,
        'monitor_release_support_horizon': False, 'monitor_root_scope_v1': 'off',
        'monitor_research_view': 'off', 'monitor_research_intent': 'off',
    }
    if any(config.get(key) != value for key, value in expected_switches.items()):
        raise RuntimeError('ASE condition mismatch')
    profile.write_text(json.dumps(profiles, ensure_ascii=False), encoding='utf-8')
    bundle = PRIVATE / 'bundle_ASE'
    copied, _ = build_bundle(bundle, source, m4.GA_RUNTIME, m4.python_home().name,
                             'native_claude_cc_vibe_opus48', 'claude_monitor_opus48', 15340,
                             monitor_profile_path=profile)
    deployment = {
        'ga_host_root': str(source), 'monitor_profile_path': str(profile),
        'monitor_profile_sha256': file_sha(profile),
        'bundle_source': str(copied), 'bundle_snapshot_sha256': digest_tree(copied),
        'bundle_deployed_profile_sha256': file_sha(copied / 'monitor_agent_core/models.local.json'),
        'ga_source_tree_hash_runner_scope': m4.tree_hash(source, ga_mode=True),
        'configured_monitor_model': config['model'], **expected_switches,
    }
    slots, runs = [], []
    for position, (task_id, run_id) in enumerate(ORDER, 1):
        prior = next(row for row in old if row['runner']['task_id'] == task_id)
        live_root = Path(r'E:\runs') / run_id
        if live_root.exists() or any((CAMPAIGN / name / run_id).exists()
                                     for name in ('jobs', 'runs', 'bridge')):
            raise RuntimeError(f'Run identity already used: {run_id}')
        slot = copy.deepcopy(prior)
        slot.update(block='ase-v0-discovery-01', position=position, ordinal=position,
                    condition='ASE-v0', candidate_commit=CANDIDATE,
                    run_id=run_id, live_root=str(live_root), status='not_started')
        slot['deployment'] = copy.deepcopy(deployment)
        slot['output'] = {'campaign_root': str(CAMPAIGN),
                          'jobs_subdir': f'jobs/{run_id}', 'runs_subdir': f'runs/{run_id}'}
        slot['runner']['run_id_argument'] = run_id
        slot['runner']['task_max_turns'] = 300
        slots.append(slot)
        env = dict(common)
        env.update(GA_BASELINE_CONDITION='original', GA_HOST_ROOT=deployment['ga_host_root'],
                   BENCHMARK_CAMPAIGN_ROOT=str(CAMPAIGN),
                   GA_METHOD_EXPECTED_SOURCE_SHA256=deployment['ga_source_tree_hash_runner_scope'],
                   GA_EXPERIMENT_HARNESS_SHA256=slot['runner']['execution_harness_sha256'])
        runs.append({'run_id': run_id, 'environment': env})
    plan = {'schema': 'ase-v0-two-trial-discovery/1', 'execution_authorized': False,
            'authorization_source': 'main-thread ASE-v0 discovery authorization',
            'candidate_commit': CANDIDATE, 'mechanism_commit': MECHANISM,
            'run_order': [row[1] for row in ORDER], 'slots': slots,
            'source_overlay_paths': changed,
            'stop_rule': 'stop after any confirmed infrastructure-invalid slot; no rerun or replacement'}
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
        'candidate_commit': CANDIDATE, 'mechanism_commit': MECHANISM,
        'plan_sha256': file_sha(PLAN), 'runner_manifest_sha256': file_sha(MANIFEST),
        'run_order': plan['run_order'], 'scope': 'Kitex then Fyne once each; no other trial'})
    print(json.dumps({'plan_sha256': file_sha(PLAN), 'run_order': plan['run_order'],
                      'code_hash': deployment['ga_source_tree_hash_runner_scope'],
                      'profile_hash': deployment['monitor_profile_sha256'],
                      'task_max_turns': 300}, indent=2))


if __name__ == '__main__':
    main()
