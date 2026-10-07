"""Single authorized B+J+I Fyne run through the existing isolated runner."""

from __future__ import annotations

import json
from pathlib import Path
import runpy
import subprocess
import sys

from method_discovery.curator_supervisor_convergence_v0.crs_v02_fyne_gate_replacement_20261007 import launch as base
from method_discovery.uc_r5_execution_bridge import file_sha, frozen_task_tree_sha


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
RUN_ID = 'crs-rhr-rer-v0-fyne-bji-r1-infra-replacement-1'
CANDIDATE = '75c50df93a72390ef78661d7d686a578f2858754'
PRIVATE = Path(r'E:\crs_rhr_rer_fyne_private_20261007')
CAMPAIGN = Path(r'E:\LongContext\long_context_bench\output\crs_rhr_rer_fyne_mechanism_gate')
PLAN = ROOT / 'PLAN.json'
MANIFEST = ROOT / 'RUNNER_MANIFEST.json'
BUNDLE = ROOT / 'BUNDLE_FREEZE.json'
v01 = base.inherited

# Reuse the unchanged, audited execution and bridge implementation. Replace
# only one-slot identities and its pre-send source/profile gates.
for module in (base, v01):
    module.ROOT = ROOT
    module.REPO = REPO
    module.RUN_ID = RUN_ID
    module.CANDIDATE = CANDIDATE
    module.PRIVATE = PRIVATE
    module.CAMPAIGN = CAMPAIGN
    module.PLAN = PLAN
    module.MANIFEST = MANIFEST
    module.BUNDLE = BUNDLE


def _json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def source_gate(bundle):
    if not (PRIVATE / 'GenericAgent-main/temp').is_dir():
        raise RuntimeError('Read-only source requires the pre-existing empty temp directory')
    base._crs_v02_source_gate(bundle)
    source = PRIVATE / 'GenericAgent-main'
    deployed = PRIVATE / 'bundle_frozen/source/monitor_agent_core/models.local.json'
    if file_sha(PRIVATE / 'monitor_config/models.local.json') != bundle['private_supervisor_profile_sha256']:
        raise RuntimeError('Private Supervisor profile identity mismatch')
    profile = _json(PRIVATE / 'monitor_config/models.local.json')['claude_monitor_opus48']
    prior = _json(Path(r'E:\crs_rhr_fyne_private_20261007\monitor_config\models.local.json'))[
        'claude_monitor_opus48']
    without_rer = dict(profile)
    if without_rer.pop('monitor_root_epistemic_reestimation', None) is not True or without_rer != prior:
        raise RuntimeError('Supervisor profile differs from B+J beyond RER=true')
    effective = _json(deployed)['claude_monitor_opus48']
    if not (effective.get('model') == 'claude-opus-4-8'
            and effective.get('monitor_adaptive_supervisory_environment') is True
            and effective.get('monitor_contrastive_release_state') is True
            and effective.get('monitor_receding_horizon_release') is True
            and effective.get('monitor_root_epistemic_reestimation') is True
            and effective.get('monitor_live_intervention', True) is True
            and effective.get('monitor_semantic_continuity', True) is True
            and effective.get('monitor_ase_meta_regulation', False) is False):
        raise RuntimeError('Deployed B+J+I profile semantics mismatch')
    from monitor_agent_core.agent import MonitorAgent
    from monitor_agent_core.provider import MonitorProviderClient
    from monitor_agent_core.workspace import MonitorWorkspace
    from tempfile import TemporaryDirectory
    with TemporaryDirectory(prefix='crs-rhr-rer-offline-') as temporary:
        temporary = Path(temporary)
        evidence, task = temporary / 'evidence', temporary / 'task'
        evidence.mkdir(); task.mkdir()
        (evidence / 'original_task.txt').write_text('Public smoke task.', encoding='utf-8')
        workspace = MonitorWorkspace(evidence, temporary / 'private', {'workspace': task})
        monitor = MonitorAgent(MonitorProviderClient('claude_monitor_opus48', effective), workspace)
        if (monitor.crs is None or monitor.crs.receding_horizon is not True or
                monitor.crs.epistemic_reestimation is not True or monitor.rer_v0 is not True):
            raise RuntimeError('Deployed RER state machine not instantiated')
    task_profile = runpy.run_path(str(source / 'mykey.py'))['native_claude_cc_vibe_opus48']
    if task_profile.get('model') != 'claude-opus-4-8':
        raise RuntimeError('Task profile model mismatch')
    tests = [
        'tests/test_rer_v0.py::test_fresh_root_frame_is_protocol_closed_and_no_extra_model_response',
        'tests/test_rer_v0.py::test_new_focal_restarts_fresh_branch_and_restores_parent_after_intervention',
        'tests/test_rer_v0.py::test_task_book_mutation_survives_parent_restore_and_echo_is_pending',
        'tests/test_rer_v0.py::test_root_turn_budget_is_cumulative_across_reestimation_frames',
        'tests/test_rer_v0.py::test_provider_failure_clears_horizon_and_restores_parent',
        'tests/test_rhr_v0.py::test_baseline_without_rhr_retains_two_stage_release',
    ]
    checked = subprocess.run([r'D:\python\python.exe', '-m', 'pytest', *tests, '-q'],
                             cwd=REPO / 'GenericAgent-main', capture_output=True, text=True)
    if checked.returncode:
        raise RuntimeError('Scripted zero-model RER preflight failed: ' +
                           (checked.stdout + checked.stderr)[-2000:])


def load_authorized_slot(run_id, authorization_path):
    if run_id != RUN_ID:
        raise RuntimeError('Only the frozen B+J+I Fyne slot is allowed')
    plan, bundle, manifest = _json(PLAN), _json(BUNDLE), _json(MANIFEST)
    auth = _json(authorization_path)
    required = {'execution_authorized': True, 'run_id': RUN_ID,
                'candidate_commit': CANDIDATE, 'plan_sha256': file_sha(PLAN),
                'runner_manifest_sha256': file_sha(MANIFEST),
                'bundle_freeze_sha256': file_sha(BUNDLE),
                'task_model': 'claude-opus-4-8'}
    if any(auth.get(key) != value for key, value in required.items()):
        raise RuntimeError('B+J+I independent authorization identity mismatch')
    if (plan.get('execution_authorized') is not False
            or plan.get('candidate_run_authorized') is not False
            or manifest.get('execution_authorized') is not False
            or bundle['candidate_source_commit'] != CANDIDATE
            or len(manifest['runs']) != 1 or manifest['runs'][0]['run_id'] != RUN_ID):
        raise RuntimeError('B+J+I frozen preparation identity mismatch')
    env = manifest['runs'][0]['environment']
    if env.get('GA_HOST_ROOT') != str(PRIVATE / 'GenericAgent-main'):
        raise RuntimeError('GA_HOST_ROOT mismatch')
    if file_sha(PRIVATE / 'monitor_config/models.local.json') != bundle['private_supervisor_profile_sha256']:
        raise RuntimeError('Private Supervisor profile SHA mismatch')
    sys.path.insert(0, str(Path(r'E:\LongContext\long_context_bench')))
    from scripts import run_harbor_tb2_m4 as m4
    from scripts.run_ultralong_m12_proofs import execution_harness_hash
    if m4.tree_hash(PRIVATE / 'GenericAgent-main', ga_mode=True) != bundle['generic_agent_source_sha256']:
        raise RuntimeError('Candidate source tree mismatch')
    if execution_harness_hash() != bundle['execution_harness_sha256']:
        raise RuntimeError('Execution harness mismatch')
    if env.get('GA_EXPERIMENT_HARNESS_SHA256') != bundle['execution_harness_sha256']:
        raise RuntimeError('Runner manifest harness mismatch')
    source_gate(bundle)
    task_dir = Path(r'E:\LongContext\long_context_bench\.cache\m12_roadmap_tasks\fyn-2.2.0-roadmap')
    public_input = REPO / 'method_discovery/runs/uc_r5_cmp_readiness_20261003/public_task_inputs/fyn-2.2.0-roadmap/actual_task_input.txt'
    task_identity = {
        'instruction_sha256': file_sha(task_dir / 'instruction.md'),
        'task_tree_sha256': frozen_task_tree_sha(task_dir),
        'task_toml_sha256': file_sha(task_dir / 'task.toml'),
        'actual_task_input_sha256': file_sha(public_input),
        'monitor_original_task_sha256': file_sha(public_input),
    }
    expected = {
        'instruction_sha256': 'c0df6c1cdc6c2d61e7129bd515dcf1f5746e606b72fa9cdd13e101aa405c778c',
        'task_tree_sha256': '36991e23b078c5b14b5ea96b8026592932048abfe5e3321c483f0430578cbe1a',
        'task_toml_sha256': 'db81f4ee37e4f69e7ace0fa7b7cb6ab8b2cd3469463091b1bcf073da4237dd6d',
        'actual_task_input_sha256': 'cae5f11a98aa573cf93629b8fb0becc18f395c5bdad25e09b8927d06f0725080',
        'monitor_original_task_sha256': 'cae5f11a98aa573cf93629b8fb0becc18f395c5bdad25e09b8927d06f0725080',
    }
    if task_identity != expected:
        raise RuntimeError('Fyne public task identity changed')
    slot = {
        'run_id': RUN_ID, 'candidate_commit': CANDIDATE, 'task_identity': task_identity,
        'output': {'campaign_root': str(CAMPAIGN)},
        'image': {'id': 'sha256:b0da1cb31d367df38d05b81f98e68a94b0f7114efd3c82537633d1d92325efe1'},
        'deployment': {
            'ga_host_root': str(PRIVATE / 'GenericAgent-main'),
            'monitor_profile_path': str(PRIVATE / 'monitor_config/models.local.json'),
            'monitor_profile_sha256': file_sha(PRIVATE / 'monitor_config/models.local.json'),
            'bundle_snapshot_sha256': bundle['bundle_source_sha256'],
            'bundle_deployed_profile_sha256': bundle['deployed_supervisor_profile_sha256'],
            'configured_monitor_model': 'claude-opus-4-8',
        },
        'runner': {'source': 'roadmapbench', 'task_id': 'fyn-2.2.0-roadmap',
                   'llm_no': 0, 'max_agent_seconds': 10000},
    }
    return slot, auth


v01.load_authorized_slot = load_authorized_slot
v01._crs_source_gate = source_gate


def launch(authorization_path):
    return v01.launch(authorization_path)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--authorization', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(launch(args.authorization), ensure_ascii=False, default=str))
