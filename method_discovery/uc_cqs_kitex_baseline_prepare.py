"""Freeze one authorized CQS-off Kitex baseline from the Stage-1 deployment."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys

from method_discovery.uc_r5_execution_bridge import file_sha
from method_discovery import uc_r5_execution_entry as bridge


REPO = Path(__file__).resolve().parent.parent
ROOT = REPO / 'method_discovery/runs/cqs_kitex_stage2_baseline_20261005'
PRIVATE = Path(r'E:\cqs_kitex_baseline_private_20261005')
CAMPAIGN = Path(r'E:\LongContext\long_context_bench\output\cqs_kitex_stage2_baseline_20261005')
PREVIOUS = REPO / 'method_discovery/runs/cqs_v0_20261005/PLAN.json'
READINESS = REPO / 'method_discovery/runs/uc_r5_cmp_readiness_20261003/ENVIRONMENT_DRAFT.json'
RUN_ID = '32a93bfa62564ff9a7530510f259540d'
CANDIDATE = 'cab01032c82d817b1b9ba28e18ef2504bd4a87a7'


def write_once(path: Path, value: dict) -> None:
    if path.exists():
        raise RuntimeError(f'Frozen artifact exists: {path}')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')


def main() -> None:
    plan_path = ROOT / 'PLAN.json'
    manifest_path = ROOT / 'RUNNER_MANIFEST.json'
    if any(path.exists() for path in (plan_path, manifest_path, PRIVATE, CAMPAIGN, Path(r'E:\runs') / RUN_ID)):
        raise RuntimeError('Baseline identity, deployment, or output already used')
    if subprocess.run(['git', 'diff', '--quiet', CANDIDATE, '--',
                       'GenericAgent-main', 'long_context_bench'], cwd=REPO).returncode:
        raise RuntimeError('Frozen CQS candidate source differs from implementation commit')
    prior = json.loads(PREVIOUS.read_text(encoding='utf-8'))
    source_slot = next(row for row in prior['slots'] if row['run_id'] == 'f74b27efdeff45cc96bf9b70dac8e97a')
    sys.path.insert(0, str(Path(r'E:\LongContext\long_context_bench')))
    from scripts.isolated_run_bundle import build_bundle, digest_tree
    from scripts import run_harbor_tb2_m4 as m4

    source_base = Path(source_slot['deployment']['ga_host_root'])
    if m4.tree_hash(source_base, ga_mode=True) != source_slot['deployment']['ga_source_tree_hash_runner_scope']:
        raise RuntimeError('Frozen CQS Stage-1 deployment code identity mismatch')
    source_profile = Path(source_slot['deployment']['monitor_profile_path'])
    if file_sha(source_profile) != source_slot['deployment']['monitor_profile_sha256']:
        raise RuntimeError('Frozen CQS Stage-1 profile identity mismatch')
    source = PRIVATE / 'launch_BASE' / 'GenericAgent-main'
    shutil.copytree(source_base, source)
    if m4.tree_hash(source, ga_mode=True) != source_slot['deployment']['ga_source_tree_hash_runner_scope']:
        raise RuntimeError('Copied candidate code differs from CQS-on source')
    profile = source.parent / 'monitor_config/models.local.json'
    profile.parent.mkdir(parents=True, exist_ok=True)
    profiles = json.loads(source_profile.read_text(encoding='utf-8'))
    monitor = profiles['claude_monitor_opus48']
    if monitor.get('monitor_control_question_state') is not True:
        raise RuntimeError('Source condition was not CQS-on')
    monitor['monitor_control_question_state'] = False
    profile.write_text(json.dumps(profiles, ensure_ascii=False), encoding='utf-8')
    baseline_profiles = json.loads(profile.read_text(encoding='utf-8'))
    baseline_profiles['claude_monitor_opus48']['monitor_control_question_state'] = True
    if baseline_profiles != profiles | {'claude_monitor_opus48': dict(monitor, monitor_control_question_state=True)}:
        raise RuntimeError('Non-CQS profile change detected')
    if baseline_profiles != json.loads(source_profile.read_text(encoding='utf-8')):
        raise RuntimeError('Private profiles differ beyond the CQS boolean')
    bundle = PRIVATE / 'bundle_BASE'
    copied, _ = build_bundle(bundle, source, m4.GA_RUNTIME, m4.python_home().name,
                             'native_claude_cc_vibe_opus48', 'claude_monitor_opus48', 15340,
                             monitor_profile_path=profile)
    deployment = copy.deepcopy(source_slot['deployment'])
    deployment.update(
        ga_host_root=str(source), monitor_profile_path=str(profile),
        monitor_profile_sha256=file_sha(profile), bundle_source=str(copied),
        bundle_snapshot_sha256=digest_tree(copied),
        bundle_deployed_profile_sha256=file_sha(copied / 'monitor_agent_core/models.local.json'),
        monitor_control_question_state=False,
        ga_source_tree_hash_runner_scope=m4.tree_hash(source, ga_mode=True),
    )
    slot = copy.deepcopy(source_slot)
    slot.update(block='cqs-kitex-stage2-diagnostic-baseline', position=1, ordinal=1,
                condition='CFS+DCM; CQS off', run_id=RUN_ID,
                live_root=str(Path(r'E:\runs') / RUN_ID), status='not_started')
    slot['deployment'] = deployment
    slot['output'] = {'campaign_root': str(CAMPAIGN), 'jobs_subdir': f'jobs/{RUN_ID}',
                      'runs_subdir': f'runs/{RUN_ID}'}
    slot['runner']['run_id_argument'] = RUN_ID
    common = json.loads(READINESS.read_text(encoding='utf-8'))['common']
    common['GA_MAX_TURNS'] = '300'
    environment = dict(common)
    environment.update(GA_BASELINE_CONDITION='original', GA_HOST_ROOT=str(source),
                       BENCHMARK_CAMPAIGN_ROOT=str(CAMPAIGN),
                       GA_METHOD_EXPECTED_SOURCE_SHA256=deployment['ga_source_tree_hash_runner_scope'],
                       GA_EXPERIMENT_HARNESS_SHA256=slot['runner']['execution_harness_sha256'])
    plan = {
        'schema': 'cqs-kitex-stage2-single-baseline/1', 'execution_authorized': False,
        'authorization_source': 'current main research thread; one fresh Kitex CFS+DCM baseline',
        'candidate_commit': CANDIDATE, 'scientific_base_archive': 'd1c508acf04fa49a1a5d5aa58e6d8386551a061e',
        'source_cqs_run_id': source_slot['run_id'], 'run_order': [RUN_ID], 'slots': [slot],
        'only_profile_semantic_difference': 'monitor_control_question_state: true -> false',
        'working_exposure_evidence': 'MonitorAgent._active_working_context calls dcec_working_context when self.cqs is None',
    }
    write_once(plan_path, plan)
    write_once(manifest_path, {'secrets_included': False,
                               'runs': [{'run_id': RUN_ID, 'environment': environment}]})
    write_once(ROOT / f'AUTH_{RUN_ID}.json', {
        'execution_authorized': True, 'run_id': RUN_ID, 'candidate_commit': CANDIDATE,
        'plan_sha256': file_sha(plan_path), 'runner_manifest': str(manifest_path.resolve()),
        'runner_manifest_sha256': file_sha(manifest_path),
        'bridge_source_sha256': bridge.bridge_source_hash(), 'task_model': 'claude-opus-4-8',
    })
    write_once(ROOT / 'EXECUTION_AUTHORIZATION.json', {
        'execution_authorized': True, 'authorization_source': 'current main research thread',
        'scope': 'one fresh Kitex CFS+DCM, CQS-off diagnostic baseline; no rerun or other Stage-2 trial',
        'run_id': RUN_ID, 'candidate_commit': CANDIDATE,
        'plan_sha256': file_sha(plan_path), 'runner_manifest_sha256': file_sha(manifest_path),
    })
    print(json.dumps({'run_id': RUN_ID, 'plan_sha256': file_sha(plan_path),
                      'manifest_sha256': file_sha(manifest_path),
                      'code_tree_sha256': deployment['ga_source_tree_hash_runner_scope'],
                      'private_profile_sha256': deployment['monitor_profile_sha256'],
                      'condition': slot['condition']}, indent=2))


if __name__ == '__main__':
    main()
