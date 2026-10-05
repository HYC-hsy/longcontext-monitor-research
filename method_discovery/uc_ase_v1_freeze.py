"""Freeze the authorized ASE-v1-core Kitex/Fyne pair without model requests."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys

from method_discovery.uc_ase_freeze import write_once
from method_discovery.uc_r5_execution_bridge import file_sha
from method_discovery import uc_r5_execution_entry as inherited


REPO = Path(__file__).resolve().parent.parent
ROOT = REPO / 'method_discovery/runs/ase_v1_core_20261006/discovery_01'
PLAN = ROOT / 'PLAN.json'
MANIFEST = ROOT / 'RUNNER_MANIFEST.json'
PRIOR = REPO / 'method_discovery/runs/ase_v0_20261005/discovery_01_recharged/PLAN.json'
PRIOR_MANIFEST = PRIOR.parent / 'RUNNER_MANIFEST.json'
PRIVATE = Path(r'E:\ase_v1_core_private_20261006')
CAMPAIGN = Path(r'E:\LongContext\long_context_bench\output\ase_v1_core_discovery_20261006')
SOURCE_BASE = Path(r'E:\ase_v0_private_recharged_20261005\launch_ASE\GenericAgent-main')
PARENT = '0889a51c6f176836b04b19279b8c99ce674e17a4'
CANDIDATE = '9fc129ca5fd971f1ffb3aceb4ef2bb6af3b269d0'
ORDER = (
    ('ktx-0.13.0-roadmap', '3eadc5f1ade2481ca63fe261fb911e0c'),
    ('fyn-2.2.0-roadmap', '90106d91d7d84fdfb5c32859f3a03ad0'),
)
OVERLAY = {
    'GenericAgent-main/monitor_agent_core/agent.py',
    'GenericAgent-main/monitor_agent_core/ase_v0.py',
    'GenericAgent-main/monitor_agent_core/runtime.py',
    'GenericAgent-main/tests/test_ase_v0.py',
}


def main():
    if any(path.exists() for path in (ROOT, PRIVATE, CAMPAIGN)):
        raise RuntimeError('Fresh plan, private deployment or campaign already exists')
    if subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO, capture_output=True,
                      text=True, check=True).stdout.strip() != CANDIDATE:
        raise RuntimeError('Candidate HEAD mismatch')
    if subprocess.run(['git', 'diff', '--quiet', CANDIDATE, '--',
                       'GenericAgent-main', 'long_context_bench'], cwd=REPO).returncode:
        raise RuntimeError('Candidate source differs from frozen implementation')
    changed = set(subprocess.run(['git', 'diff', '--name-only', PARENT, CANDIDATE,
                                  '--', 'GenericAgent-main'], cwd=REPO,
                                 capture_output=True, text=True, check=True).stdout.splitlines())
    if changed != OVERLAY:
        raise RuntimeError('ASE-v1 overlay path identity mismatch')

    sys.path.insert(0, str(Path(r'E:\LongContext\long_context_bench')))
    from scripts.isolated_run_bundle import build_bundle, digest_tree
    from scripts import run_harbor_tb2_m4 as m4

    prior = json.loads(PRIOR.read_text(encoding='utf-8'))
    old_slots = prior['slots']
    if m4.tree_hash(SOURCE_BASE, ga_mode=True) != old_slots[0]['deployment']['ga_source_tree_hash_runner_scope']:
        raise RuntimeError('ASE-v0 private source identity mismatch')
    previous_env = json.loads(PRIOR_MANIFEST.read_text(encoding='utf-8'))['runs'][0]['environment']
    if previous_env['GA_MAX_TURNS'] != '300' or previous_env['GA_MONITOR_DCEC'] != '0':
        raise RuntimeError('Inherited task budget or ASE environment changed')

    source = PRIVATE / 'launch_ASE' / 'GenericAgent-main'
    shutil.copytree(SOURCE_BASE, source)
    for relative in sorted(OVERLAY):
        target = source / relative.removeprefix('GenericAgent-main/')
        shutil.copy2(REPO / relative, target)
    profile = source.parent / 'monitor_config/models.local.json'
    profile.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE_BASE.parent / 'monitor_config/models.local.json', profile)
    profiles = json.loads(profile.read_text(encoding='utf-8'))
    config = profiles['claude_monitor_opus48']
    if config.get('model') != 'claude-opus-4-8' or config.get('monitor_adaptive_supervisory_environment') is not True:
        raise RuntimeError('Inherited model or ASE condition mismatch')
    if config.get('monitor_ase_meta_regulation', False) is not False:
        raise RuntimeError('Experimental meta-regulation was enabled')
    config['monitor_ase_meta_regulation'] = False
    profile.write_text(json.dumps(profiles, ensure_ascii=False), encoding='utf-8')
    bundle = PRIVATE / 'bundle_ASE'
    copied, _ = build_bundle(bundle, source, m4.GA_RUNTIME, m4.python_home().name,
                             'native_claude_cc_vibe_opus48', 'claude_monitor_opus48', 15340,
                             monitor_profile_path=profile)
    deployed = json.loads((copied / 'monitor_agent_core/models.local.json').read_text(encoding='utf-8'))[
        'claude_monitor_opus48']
    if deployed.get('monitor_adaptive_supervisory_environment') is not True or deployed.get(
            'monitor_ase_meta_regulation') is not False:
        raise RuntimeError('Deployed ASE-v1-core switch mismatch')
    deployment = copy.deepcopy(old_slots[0]['deployment'])
    deployment.update(ga_host_root=str(source), monitor_profile_path=str(profile),
                      monitor_profile_sha256=file_sha(profile), bundle_source=str(copied),
                      bundle_snapshot_sha256=digest_tree(copied),
                      bundle_deployed_profile_sha256=file_sha(copied / 'monitor_agent_core/models.local.json'),
                      ga_source_tree_hash_runner_scope=m4.tree_hash(source, ga_mode=True),
                      monitor_ase_meta_regulation=False)
    slots, runs = [], []
    for position, (task_id, run_id) in enumerate(ORDER, 1):
        old = next(row for row in old_slots if row['runner']['task_id'] == task_id)
        live_root = Path(r'E:\runs') / run_id
        if live_root.exists():
            raise RuntimeError(f'Live root already used: {run_id}')
        slot = copy.deepcopy(old)
        slot.update(block='ase-v1-core-discovery-01', position=position, ordinal=position,
                    condition='ASE-v1-core', candidate_commit=CANDIDATE,
                    run_id=run_id, live_root=str(live_root), status='not_started')
        slot['deployment'] = copy.deepcopy(deployment)
        slot['output'] = {'campaign_root': str(CAMPAIGN),
                          'jobs_subdir': f'jobs/{run_id}', 'runs_subdir': f'runs/{run_id}'}
        slot['runner']['run_id_argument'] = run_id
        slots.append(slot)
        env = dict(previous_env)
        env.update(GA_HOST_ROOT=str(source), BENCHMARK_CAMPAIGN_ROOT=str(CAMPAIGN),
                   GA_METHOD_EXPECTED_SOURCE_SHA256=deployment['ga_source_tree_hash_runner_scope'])
        runs.append({'run_id': run_id, 'environment': env})
    plan = {'schema': 'ase-v1-core-two-trial-discovery/1', 'execution_authorized': False,
            'authorization_source': 'current main research thread', 'candidate_commit': CANDIDATE,
            'condition': {'monitor_adaptive_supervisory_environment': True,
                          'monitor_ase_meta_regulation': False},
            'run_order': [run_id for _, run_id in ORDER], 'slots': slots,
            'source_overlay_paths': sorted(OVERLAY),
            'stop_rule': 'stop after confirmed infrastructure-invalid slot; never rerun'}
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
        'execution_authorized': True, 'authorization_source': 'current main research thread',
        'candidate_commit': CANDIDATE, 'plan_sha256': file_sha(PLAN),
        'runner_manifest_sha256': file_sha(MANIFEST), 'run_order': plan['run_order'],
        'scope': 'Kitex then Fyne once each; no other trial'})
    print(json.dumps({'run_order': plan['run_order'], 'plan_sha256': file_sha(PLAN),
                      'profile_sha256': deployment['monitor_profile_sha256'],
                      'source_hash': deployment['ga_source_tree_hash_runner_scope']}, indent=2))


if __name__ == '__main__':
    main()
