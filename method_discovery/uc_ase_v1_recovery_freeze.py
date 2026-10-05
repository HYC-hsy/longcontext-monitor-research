"""Freeze a fresh ASE-v1-core pair after the archived host-memory failure."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess

from method_discovery.uc_ase_freeze import write_once
from method_discovery.uc_r5_execution_bridge import file_sha
from method_discovery import uc_ase_v1_freeze as previous
from method_discovery import uc_r5_execution_entry as bridge


REPO = previous.REPO
ROOT = REPO / 'method_discovery/runs/ase_v1_core_20261006/discovery_02_recovery'
PLAN = ROOT / 'PLAN.json'
MANIFEST = ROOT / 'RUNNER_MANIFEST.json'
CAMPAIGN = Path(r'E:\LongContext\long_context_bench\output\ase_v1_core_discovery_recovery_20261006')
CANDIDATE = previous.CANDIDATE
ORDER = (
    ('ktx-0.13.0-roadmap', '6975bbdaf84a413f9ab5b2812df8e2c2'),
    ('fyn-2.2.0-roadmap', 'd0aa87ad623246b781826570e10d4340'),
)


def main() -> None:
    if any(path.exists() for path in (ROOT, CAMPAIGN)):
        raise RuntimeError('Recovery plan or campaign already exists')
    if subprocess.run(['git', 'diff', '--quiet', CANDIDATE, 'HEAD', '--',
                       'GenericAgent-main', 'long_context_bench'], cwd=REPO).returncode:
        raise RuntimeError('Frozen candidate or runner source changed')
    old = json.loads(previous.PLAN.read_text(encoding='utf-8'))
    old_manifest = json.loads(previous.MANIFEST.read_text(encoding='utf-8'))
    if old['candidate_commit'] != CANDIDATE or old['run_order'] != [run for _, run in previous.ORDER]:
        raise RuntimeError('Original ASE-v1 plan identity mismatch')
    if file_sha(previous.MANIFEST) != json.loads(
            (previous.ROOT / f"AUTH_{previous.ORDER[0][1]}.json").read_text(
                encoding='utf-8'))['runner_manifest_sha256']:
        raise RuntimeError('Original manifest changed')
    sys_source = Path(old['slots'][0]['deployment']['ga_host_root'])
    sys_bundle = Path(old['slots'][0]['deployment']['bundle_source'])
    from scripts.isolated_run_bundle import digest_tree
    from scripts import run_harbor_tb2_m4 as m4
    if m4.tree_hash(sys_source, ga_mode=True) != old['slots'][0]['deployment'][
            'ga_source_tree_hash_runner_scope']:
        raise RuntimeError('Private deployed source changed')
    if digest_tree(sys_bundle) != old['slots'][0]['deployment']['bundle_snapshot_sha256']:
        raise RuntimeError('Private bundle changed')
    profile = Path(old['slots'][0]['deployment']['monitor_profile_path'])
    if file_sha(profile) != old['slots'][0]['deployment']['monitor_profile_sha256']:
        raise RuntimeError('Private profile changed')
    slots, runs = [], []
    for position, (task_id, run_id) in enumerate(ORDER, 1):
        former = next(slot for slot in old['slots'] if slot['runner']['task_id'] == task_id)
        if (Path(r'E:\runs', run_id).exists() or any((CAMPAIGN / name / run_id).exists()
              for name in ('jobs', 'runs', 'bridge'))):
            raise RuntimeError(f'Fresh run identity already used: {run_id}')
        slot = copy.deepcopy(former)
        slot.update(block='ase-v1-core-discovery-02-recovery', position=position,
                    ordinal=position, run_id=run_id, live_root=str(Path(r'E:\runs', run_id)),
                    status='not_started')
        slot['runner']['run_id_argument'] = run_id
        slot['output'] = {'campaign_root': str(CAMPAIGN),
                          'jobs_subdir': f'jobs/{run_id}', 'runs_subdir': f'runs/{run_id}'}
        slots.append(slot)
        prior_env = next(row['environment'] for row in old_manifest['runs']
                         if row['run_id'] == former['run_id'])
        env = dict(prior_env)
        env['BENCHMARK_CAMPAIGN_ROOT'] = str(CAMPAIGN)
        runs.append({'run_id': run_id, 'environment': env})
    plan = {'schema': 'ase-v1-core-fresh-recovery/1', 'execution_authorized': False,
            'authorization_source': 'user renewed ASE-v1-core Kitex/Fyne authorization',
            'candidate_commit': CANDIDATE,
            'condition': old['condition'], 'run_order': [run for _, run in ORDER],
            'slots': slots, 'prior_failed_run_id': previous.ORDER[0][1],
            'prior_failure_archive_commit': 'a92fbe8f05607c44065d983436b96743d3c966c2',
            'host_memory_condition': 'pagefile absent; user accepted retry without reboot',
            'stop_rule': 'stop after confirmed infrastructure-invalid slot; no automatic rerun'}
    write_once(PLAN, plan)
    write_once(MANIFEST, {'secrets_included': False, 'runs': runs})
    for slot in slots:
        write_once(ROOT / f"AUTH_{slot['run_id']}.json", {
            'execution_authorized': True, 'run_id': slot['run_id'],
            'candidate_commit': CANDIDATE, 'plan_sha256': file_sha(PLAN),
            'runner_manifest': str(MANIFEST.resolve()),
            'runner_manifest_sha256': file_sha(MANIFEST),
            'bridge_source_sha256': bridge.bridge_source_hash(),
            'task_model': 'claude-opus-4-8'})
    write_once(ROOT / 'EXECUTION_AUTHORIZATION.json', {
        'execution_authorized': True,
        'authorization_source': 'user renewed ASE-v1-core Kitex/Fyne authorization',
        'candidate_commit': CANDIDATE, 'plan_sha256': file_sha(PLAN),
        'runner_manifest_sha256': file_sha(MANIFEST),
        'run_order': plan['run_order'], 'scope': 'fresh Kitex then Fyne once each',
        'prior_failure_not_scientific_replaced': True})
    print(json.dumps({'run_order': plan['run_order'], 'plan_sha256': file_sha(PLAN),
                      'manifest_sha256': file_sha(MANIFEST)}, indent=2))


if __name__ == '__main__':
    import sys
    sys.path.insert(0, str(Path(r'E:\LongContext\long_context_bench')))
    main()
