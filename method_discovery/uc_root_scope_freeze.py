"""One-time four-slot root-scope materialization; no model or verifier calls."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

from method_discovery.uc_r5_execution_bridge import file_sha
from method_discovery import uc_r5_execution_entry as inherited


REPO = Path(__file__).resolve().parent.parent
ROOT = REPO / 'method_discovery/runs/uc_root_scope_v1_20261004'
PLAN = ROOT / 'PLAN.json'
MANIFEST = ROOT / 'RUNNER_MANIFEST.json'
PREVIOUS = REPO / 'method_discovery/runs/uc_path_control_v0_20261003/PLAN.json'
READINESS = REPO / 'method_discovery/runs/uc_r5_cmp_readiness_20261003/ENVIRONMENT_DRAFT.json'
PRIVATE = Path(r'E:\uc_root_scope_private_20261004')
CAMPAIGN = Path(r'E:\LongContext\long_context_bench\output\uc_root_scope_v1_20261004')
SOURCE_BASE = Path(r'E:\uc_path_control_private_20261003\launch_PATH\GenericAgent-main')
SOURCES = ('monitor_agent_core/agent.py', 'monitor_agent_core/loop.py',
           'monitor_agent_core/runtime.py', 'monitor_agent_core/workspace.py',
           'monitor_agent_core/root_scope_v1.py', 'tests/test_root_scope_v1.py')
ORDER = (('fyn-2.2.0-roadmap', 'RETAIN'), ('fyn-2.2.0-roadmap', 'ISOLATE'),
         ('ktx-0.13.0-roadmap', 'ISOLATE'), ('ktx-0.13.0-roadmap', 'RETAIN'))
CANDIDATE = '0a5f42561066ee7fa00a86d446fdb448ddd643d1'


def write_once(path, value):
    if path.exists():
        raise RuntimeError(f'Frozen artifact exists: {path}')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode())


def main():
    if PLAN.exists() or MANIFEST.exists() or PRIVATE.exists():
        raise RuntimeError('Root-scope plan or private launch material already exists')
    if subprocess.run(['git', 'diff', '--quiet', CANDIDATE, '--', 'GenericAgent-main'],
                      cwd=REPO).returncode:
        raise RuntimeError('Candidate production source differs from the frozen implementation')
    sys.path.insert(0, str(Path(r'E:\LongContext\long_context_bench')))
    from scripts.isolated_run_bundle import build_bundle, digest_tree
    from scripts import run_harbor_tb2_m4 as m4
    old = json.loads(PREVIOUS.read_text(encoding='utf-8'))['slots']
    common = json.loads(READINESS.read_text(encoding='utf-8'))['common']
    deployments = {}
    for mode in ('RETAIN', 'ISOLATE'):
        source = PRIVATE / f'launch_{mode}' / 'GenericAgent-main'
        shutil.copytree(SOURCE_BASE, source)
        for relative in SOURCES:
            target = source / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO / 'GenericAgent-main' / relative, target)
        profile = source.parent / 'monitor_config/models.local.json'
        profile.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SOURCE_BASE.parent / 'monitor_config/models.local.json', profile)
        profiles = json.loads(profile.read_text(encoding='utf-8'))
        config = profiles['claude_monitor_opus48']
        if (config.get('monitor_dcec') is not True or
                config.get('monitor_path_control_v0') is not True or
                config.get('monitor_research_view', 'off') != 'off' or
                config.get('monitor_research_intent', 'off') != 'off'):
            raise RuntimeError('Inherited private profile is not the frozen PATH profile')
        config['monitor_root_scope_v1'] = {'RETAIN': 'retained', 'ISOLATE': 'isolated'}[mode]
        profile.write_text(json.dumps(profiles, ensure_ascii=False), encoding='utf-8')
        bundle = PRIVATE / f'bundle_{mode}'
        copied, _ = build_bundle(
            bundle, source, m4.GA_RUNTIME, m4.python_home().name,
            'native_claude_cc_vibe_opus48', 'claude_monitor_opus48', 15340,
            monitor_profile_path=profile)
        deployments[mode] = {
            'ga_host_root': str(source), 'monitor_profile_path': str(profile),
            'monitor_profile_sha256': file_sha(profile),
            'bundle_source': str(copied), 'bundle_snapshot_sha256': digest_tree(copied),
            'bundle_deployed_profile_sha256': file_sha(copied / 'monitor_agent_core/models.local.json'),
            'ga_source_tree_hash_runner_scope': m4.tree_hash(source, ga_mode=True),
            'configured_monitor_model': config['model'],
            'monitor_path_control_v0': True, 'monitor_root_scope_v1': config['monitor_root_scope_v1'],
            'view': 'off', 'intent': 'off',
        }
    if (deployments['RETAIN']['ga_source_tree_hash_runner_scope'] !=
            deployments['ISOLATE']['ga_source_tree_hash_runner_scope']):
        raise RuntimeError('Two arms do not share one production code tree')
    slots, runs = [], []
    for position, (task_id, mode) in enumerate(ORDER, 1):
        old_slot = next(row for row in old if row['runner']['task_id'] == task_id)
        slot = copy.deepcopy(old_slot)
        run_id = uuid.uuid4().hex[:24]
        live_root = Path(r'E:\runs') / run_id
        if live_root.exists() or (CAMPAIGN / 'jobs' / run_id).exists():
            raise RuntimeError('Generated live identity already used')
        slot.update({'block': 'root-scope-v1', 'position': position, 'ordinal': position,
                     'condition': mode, 'candidate_commit': CANDIDATE,
                     'run_id': run_id, 'live_root': str(live_root), 'status': 'not_started'})
        slot['deployment'] = copy.deepcopy(deployments[mode])
        slot['output'] = {'campaign_root': str(CAMPAIGN),
                          'jobs_subdir': f'jobs/{run_id}', 'runs_subdir': f'runs/{run_id}'}
        slot['runner']['run_id_argument'] = run_id
        slots.append(slot)
        env = dict(common)
        env.update({'GA_BASELINE_CONDITION': 'original',
                    'GA_HOST_ROOT': slot['deployment']['ga_host_root'],
                    'BENCHMARK_CAMPAIGN_ROOT': str(CAMPAIGN),
                    'GA_METHOD_EXPECTED_SOURCE_SHA256': slot['deployment']['ga_source_tree_hash_runner_scope'],
                    'GA_EXPERIMENT_HARNESS_SHA256': slot['runner']['execution_harness_sha256']})
        runs.append({'run_id': run_id, 'environment': env})
    sys.path.insert(0, str(REPO / 'GenericAgent-main'))
    from monitor_agent_core.root_scope_v1 import ROOT_SYSTEM_PROMPT
    plan = {'schema': 'root-scope-v1-four-trial-plan/1', 'execution_authorized': False,
            'candidate_commit': CANDIDATE, 'parent_commit': '37f5a194ec98e15d70fc51126512b327189f430e',
            'run_order': [slot['run_id'] for slot in slots], 'task_condition_order': list(ORDER),
            'slots': slots, 'root_system_sha256': hashlib.sha256(ROOT_SYSTEM_PROMPT.encode()).hexdigest(),
            'input_rule': 'Full public task and current handoff; fixed last-two complete excerpts for result-bearing public events and each private audit stream; full source locators; no PATH public window in root.',
            'raw_response_audit': 'Tool-call original gateway body unavailable in the accessible prior archive; no Task execution-chain change.',
            'real_model_calls_before_freeze': 0}
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
                      'code_hash': deployments['RETAIN']['ga_source_tree_hash_runner_scope']}, indent=2))


if __name__ == '__main__':
    main()
