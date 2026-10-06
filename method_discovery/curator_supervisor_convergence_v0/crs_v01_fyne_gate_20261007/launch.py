"""Authorized one-slot Fyne launcher; delegates to the frozen M12 runner/bridge."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys

from method_discovery import uc_r5_execution_entry as inherited
from method_discovery.uc_r5_execution_bridge import file_sha, save_json


REPO = Path(__file__).resolve().parents[3]
ROOT = Path(__file__).resolve().parent
PLAN = ROOT / 'PLAN.json'
MANIFEST = ROOT / 'RUNNER_MANIFEST.json'
BUNDLE = ROOT / 'BUNDLE_FREEZE.json'
RUN_ID = 'crs-v01-fyne-mechanism-gate-b-only-r1'
CANDIDATE = '397171fd77e6d9e00183115d693b0b83557be8da'
PRIVATE = Path(r'E:\crs_fyne_gate_private_20261007')
CAMPAIGN = Path(r'E:\LongContext\long_context_bench\output\crs_v01_fyne_mechanism_gate')


def _json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def _crs_source_gate(bundle):
    source = PRIVATE / 'GenericAgent-main'
    ase = source / 'monitor_agent_core' / 'ase_v0.py'
    blob = subprocess.check_output(['git', 'hash-object', str(ase)], cwd=REPO,
                                   text=True).strip()
    expected_blob = subprocess.check_output(
        ['git', 'rev-parse',
         'dfec10511bdafe97e8a0041cb95d19f5bed4de9b:GenericAgent-main/monitor_agent_core/ase_v0.py'],
        cwd=REPO, text=True).strip()
    if blob != expected_blob:
        raise RuntimeError('ASE source differs from scientific baseline')
    parsed = ast.parse(ase.read_text(encoding='utf-8'))
    prompt = next(node.value.value for node in parsed.body if isinstance(node, ast.Assign)
                  and any(isinstance(target, ast.Name) and target.id == 'SYSTEM_PROMPT'
                          for target in node.targets))
    if hashlib.sha256(prompt.encode('utf-8')).hexdigest() != bundle['system_prompt_sha256']:
        raise RuntimeError('Frozen SYSTEM_PROMPT SHA mismatch')
    if _json(PRIVATE / 'bundle_frozen/isolation_identity.json')['snapshot_sha256'] != bundle['bundle_source_sha256']:
        raise RuntimeError('Offline isolation snapshot mismatch')
    if file_sha(PRIVATE / 'bundle_frozen/isolation_identity.json') != bundle['bundle_manifest_sha256']:
        raise RuntimeError('Offline isolation manifest mismatch')
    if file_sha(PRIVATE / 'bundle_frozen/source/monitor_agent_core/models.local.json') != bundle['deployed_supervisor_profile_sha256']:
        raise RuntimeError('Deployed monitor profile mismatch')
    sys.path.insert(0, str(source))
    from monitor_agent_core.agent import MONITOR_TOOLS, crs_tools
    from monitor_agent_core.provider import MonitorProviderClient
    from monitor_agent_core.workspace import MonitorWorkspace
    from monitor_agent_core.agent import MonitorAgent
    from tempfile import TemporaryDirectory
    if not Path(sys.modules['monitor_agent_core.agent'].__file__).resolve().is_relative_to(source.resolve()):
        raise RuntimeError('CRS smoke imported a different MonitorAgent source')
    local, root = MONITOR_TOOLS, crs_tools()
    names = ['file_read', 'file_write', 'file_patch', 'code_run', 'wait', 'intervene', 'allow_complete']
    if ([tool['function']['name'] for tool in local] != names
            or [tool['function']['name'] for tool in root] != names
            or local[:6] != root[:6]
            or root[-1]['function']['parameters']['required'] != ['contrast']):
        raise RuntimeError('Local/root CRS tool schema mismatch')
    config = _json(PRIVATE / 'bundle_frozen/source/monitor_agent_core/models.local.json')['claude_monitor_opus48']
    with TemporaryDirectory(prefix='crs-offline-smoke-') as temp:
        base = Path(temp)
        evidence, task = base / 'evidence', base / 'task'
        evidence.mkdir()
        task.mkdir()
        (evidence / 'original_task.txt').write_text('Public smoke task.', encoding='utf-8')
        workspace = MonitorWorkspace(evidence, base / 'monitor', {'workspace': task})
        client = MonitorProviderClient('claude_monitor_opus48', config)
        agent = MonitorAgent(client, workspace)
        if (agent.ase_v0 is not True or agent.crs is None or agent.control_echo is None
                or agent.situation.include_supervisory_control is not False
                or agent.cqs is not None or agent.system_prompt != prompt):
            raise RuntimeError('Deployed CRS MonitorAgent smoke mismatch')
    task_profile = runpy.run_path(str(source / 'mykey.py'))['native_claude_cc_vibe_opus48']
    if task_profile.get('model') != 'claude-opus-4-8':
        raise RuntimeError('Task model profile mismatch')


def load_authorized_slot(run_id, authorization_path):
    if run_id != RUN_ID:
        raise RuntimeError('Only the frozen Fyne candidate slot is allowed')
    plan, bundle, manifest = _json(PLAN), _json(BUNDLE), _json(MANIFEST)
    auth = _json(Path(authorization_path))
    required = {
        'execution_authorized': True,
        'run_id': RUN_ID,
        'candidate_commit': CANDIDATE,
        'plan_sha256': file_sha(PLAN),
        'runner_manifest_sha256': file_sha(MANIFEST),
        'bundle_freeze_sha256': file_sha(BUNDLE),
        'task_model': 'claude-opus-4-8',
    }
    if any(auth.get(key) != value for key, value in required.items()):
        raise RuntimeError('Independent Fyne authorization mismatch')
    if (plan.get('execution_authorized') is not False
            or plan.get('candidate_run_authorized') is not False
            or manifest.get('execution_authorized') is not False
            or bundle['candidate_source_commit'] != CANDIDATE):
        raise RuntimeError('Frozen preparation identity mismatch')
    if len(manifest['runs']) != 1 or manifest['runs'][0]['run_id'] != RUN_ID:
        raise RuntimeError('Runner manifest is not the single Fyne slot')
    env = manifest['runs'][0]['environment']
    if env.get('GA_HOST_ROOT') != str(PRIVATE / 'GenericAgent-main'):
        raise RuntimeError('GA_HOST_ROOT mismatch')
    if file_sha(PRIVATE / 'monitor_config/models.local.json') != (
            '93bddaec67c195de6d1d51499baa90358c09f71a6ec885190fae8187382484f4'):
        raise RuntimeError('Runner-required private Supervisor profile mismatch')
    if env.get('GA_EXPERIMENT_HARNESS_SHA256') != (
            '1c2256113d5fc8ab43e307a9edf29b16c6defeb1d5f5e69d954784cea1618bd6'):
        raise RuntimeError('Frozen harness assignment mismatch')
    sys.path.insert(0, str(Path(r'E:\LongContext\long_context_bench')))
    from scripts import run_harbor_tb2_m4 as m4
    from scripts.run_ultralong_m12_proofs import execution_harness_hash
    from method_discovery.uc_r5_execution_bridge import frozen_task_tree_sha
    if m4.tree_hash(PRIVATE / 'GenericAgent-main', ga_mode=True) != bundle['generic_agent_source_sha256']:
        raise RuntimeError('Candidate source tree mismatch')
    if execution_harness_hash() != bundle['execution_harness_sha256']:
        raise RuntimeError('Execution harness changed')
    _crs_source_gate(bundle)
    profile = _json(PRIVATE / 'monitor_config/models.local.json')['claude_monitor_opus48']
    if not (profile.get('model') == 'claude-opus-4-8'
            and profile.get('monitor_adaptive_supervisory_environment') is True
            and profile.get('monitor_contrastive_release_state') is True
            and profile.get('monitor_live_intervention', True) is True
            and profile.get('monitor_ase_meta_regulation', False) is False
            and profile.get('monitor_semantic_continuity', True) is True):
        raise RuntimeError('Curator-Supervisor profile semantics changed')
    historical = ('monitor_dcec', 'monitor_path_control_v0', 'monitor_verification_loop_v0',
                  'monitor_coarse_to_fine_surface', 'monitor_decision_conditioned_measurement',
                  'monitor_control_question_state', 'monitor_executable_interpretation_surface',
                  'monitor_release_support_horizon', 'monitor_independent_probe')
    if any(profile.get(key, False) is not False for key in historical):
        raise RuntimeError('Historical Supervisor candidate switch enabled')
    if (profile.get('monitor_root_scope_v1', 'off') != 'off'
            or profile.get('monitor_research_view', 'off') != 'off'
            or profile.get('monitor_research_intent', 'off') != 'off'):
        raise RuntimeError('Historical root/research view enabled')
    task_dir = Path(r'E:\LongContext\long_context_bench\.cache\m12_roadmap_tasks\fyn-2.2.0-roadmap')
    instruction = (task_dir / 'instruction.md')
    public_input = REPO / 'method_discovery/runs/uc_r5_cmp_readiness_20261003/public_task_inputs/fyn-2.2.0-roadmap/actual_task_input.txt'
    task_identity = {
        'instruction_sha256': file_sha(instruction),
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


def launch(authorization_path):
    slot, auth = load_authorized_slot(RUN_ID, authorization_path)
    inherited.FROZEN_CANDIDATE = CANDIDATE
    frozen_identity = inherited.require_frozen_source_and_harbor()
    if (Path(r'E:\runs') / RUN_ID).exists() or any((CAMPAIGN / name / RUN_ID).exists()
                                                 for name in ('jobs', 'runs', 'bridge', 'isolated_bundles')):
        raise RuntimeError('Fyne run identity or output already used')
    control = CAMPAIGN / 'bridge' / RUN_ID / 'control'
    archive = CAMPAIGN / 'bridge' / RUN_ID / 'evidence'
    control.mkdir(parents=True, exist_ok=False)
    archive.mkdir(parents=True, exist_ok=False)
    spec_path = CAMPAIGN / 'bridge' / RUN_ID / 'bridge_spec.private.json'
    save_json(spec_path, {
        'execution_authorized': True, 'slot': slot, 'task_model': auth['task_model'],
        'control_dir': str(control), 'archive_dir': str(archive),
        'authorization_path': str(Path(authorization_path).resolve()),
        'authorization_sha256': file_sha(Path(authorization_path)),
        'plan_sha256': file_sha(PLAN), 'runner_manifest_sha256': file_sha(MANIFEST),
        'frozen_source_and_harbor': frozen_identity,
    })
    bench = Path(r'E:\LongContext\long_context_bench')
    sys.path.insert(0, str(bench))
    from scripts import run_ultralong_m12_proofs as runner
    from scripts import run_harbor_tb2_m4 as m4
    runner.apply_experiment_manifest(MANIFEST, RUN_ID)
    for name, value in _json(MANIFEST)['runs'][0]['environment'].items():
        if os.environ.get(name) != value:
            raise RuntimeError(f'Effective runtime environment mismatch: {name}')
    m4.GA_ROOT = PRIVATE / 'GenericAgent-main'
    runner.build_bundle = inherited.overlay_bundle(
        runner.build_bundle, REPO / 'method_discovery/uc_r5_bridge_gateway.py',
        control, slot, spec_path)
    os.environ['UC_R5_BRIDGE_SPEC'] = str(spec_path)
    os.environ['PYTHONPATH'] = os.pathsep.join([str(REPO), os.environ.get('PYTHONPATH', '')])
    original_run = m4.run
    harbor_exe = str(m4.HARBOR_EXE)

    def run_with_hooks(command, *args, **kwargs):
        if len(command) < 3 or command[0] != harbor_exe or command[1:3] != ['jobs', 'start']:
            return original_run(command, *args, **kwargs)
        harbor_python = str(Path(harbor_exe).with_name('python.exe'))
        return original_run([harbor_python, str(ROOT / 'harbor_cli.py'), *command[1:]],
                            *args, **kwargs)

    m4.run = run_with_hooks
    try:
        return runner.run_proof(source='roadmapbench', run_id=RUN_ID, llm_no=0,
                                max_agent_seconds=10000, task_id='fyn-2.2.0-roadmap')
    finally:
        m4.run = original_run
        os.environ.pop('UC_R5_BRIDGE_SPEC', None)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--authorization', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(launch(args.authorization), ensure_ascii=False, default=str))
