"""One authorized CRS-v0.2 Fyne replacement; fail closed before model sends."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from method_discovery.curator_supervisor_convergence_v0.crs_v01_fyne_gate_infra_replacement_20261007 import launch as inherited
from method_discovery.uc_r5_execution_bridge import file_sha


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
RUN_ID = 'crs-v02-fyne-mechanism-gate-b-only-r1-infra-replacement-4'
PRIVATE = Path(r'E:\crs_fyne_gate_v02_private_20261007')
CANDIDATE = '03cc3ff9868ac1cc2b96f98bc077d7d50de4df09'
CAMPAIGN = Path(r'E:\LongContext\long_context_bench\output\crs_v02_fyne_mechanism_gate')
EXPECTED_FIELDS = {'release_blocking_state', 'grounding', 'ground_refs',
                   'exclusion_reason', 'observation_refs'}

inherited.ROOT = ROOT
inherited.REPO = REPO
inherited.RUN_ID = RUN_ID
inherited.PRIVATE = PRIVATE
inherited.CANDIDATE = CANDIDATE
inherited.CAMPAIGN = CAMPAIGN
inherited.PLAN = ROOT / 'PLAN.json'
inherited.MANIFEST = ROOT / 'RUNNER_MANIFEST.json'
inherited.BUNDLE = ROOT / 'BUNDLE_FREEZE.json'


def _crs_v02_source_gate(bundle):
    source = PRIVATE / 'GenericAgent-main'
    ase = source / 'monitor_agent_core/ase_v0.py'
    blob = subprocess.check_output(['git', 'hash-object', str(ase)], cwd=REPO, text=True).strip()
    baseline = subprocess.check_output(['git', 'rev-parse',
        'dfec10511bdafe97e8a0041cb95d19f5bed4de9b:GenericAgent-main/monitor_agent_core/ase_v0.py'],
        cwd=REPO, text=True).strip()
    if blob != baseline:
        raise RuntimeError('ASE source differs from baseline')
    parsed = ast.parse(ase.read_text(encoding='utf-8'))
    prompt = next(node.value.value for node in parsed.body if isinstance(node, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == 'SYSTEM_PROMPT' for t in node.targets))
    if hashlib.sha256(prompt.encode('utf-8')).hexdigest() != bundle['system_prompt_sha256']:
        raise RuntimeError('SYSTEM_PROMPT identity mismatch')
    isolation = PRIVATE / 'bundle_frozen/isolation_identity.json'
    if (json.loads(isolation.read_text(encoding='utf-8'))['snapshot_sha256'] != bundle['bundle_source_sha256']
            or file_sha(isolation) != bundle['bundle_manifest_sha256']):
        raise RuntimeError('Frozen isolation bundle identity mismatch')
    deployed = PRIVATE / 'bundle_frozen/source/monitor_agent_core/models.local.json'
    if file_sha(deployed) != bundle['deployed_supervisor_profile_sha256']:
        raise RuntimeError('Deployed Supervisor profile identity mismatch')
    # The private source is a Git archive of the exact candidate; verify the
    # production modules relied upon by this interface again at send gate.
    for relative in ('agent.py', 'crs_v0.py', 'ase_v0.py', 'runtime.py', 'cfs_v0.py',
                     'provider.py', 'workspace.py'):
        actual = subprocess.check_output(['git', 'hash-object',
            str(source / 'monitor_agent_core' / relative)], cwd=REPO, text=True).strip()
        expected = subprocess.check_output(['git', 'rev-parse',
            f'{CANDIDATE}:GenericAgent-main/monitor_agent_core/{relative}'],
            cwd=REPO, text=True).strip()
        if actual != expected:
            raise RuntimeError(f'Candidate source identity mismatch: {relative}')
    sys.path.insert(0, str(source))
    from monitor_agent_core.agent import MONITOR_TOOLS, MonitorAgent, crs_tools
    from monitor_agent_core.provider import MonitorProviderClient
    from monitor_agent_core.workspace import MonitorWorkspace
    if not Path(sys.modules['monitor_agent_core.agent'].__file__).resolve().is_relative_to(source.resolve()):
        raise RuntimeError('Wrong MonitorAgent imported for preflight')
    local, root = MONITOR_TOOLS, crs_tools()
    names = ['file_read', 'file_write', 'file_patch', 'code_run', 'wait', 'intervene', 'allow_complete']
    release = root[-1]['function']
    if ([t['function']['name'] for t in local] != names
            or [t['function']['name'] for t in root] != names
            or local[:6] != root[:6]
            or set(release['parameters']['required']) != EXPECTED_FIELDS
            or set(release['parameters']['properties']) != EXPECTED_FIELDS
            or 'contrast' in release['parameters']['properties']):
        raise RuntimeError('CRS local/root schema mismatch')
    config = json.loads(deployed.read_text(encoding='utf-8'))['claude_monitor_opus48']
    with TemporaryDirectory(prefix='crs-v02-offline-') as temporary:
        base = Path(temporary)
        evidence, task = base / 'evidence', base / 'task'
        evidence.mkdir(); task.mkdir()
        (evidence / 'original_task.txt').write_text('Public smoke task.', encoding='utf-8')
        workspace = MonitorWorkspace(evidence, base / 'monitor', {'workspace': task})
        client = MonitorProviderClient('claude_monitor_opus48', config)
        monitor = MonitorAgent(client, workspace)
        if (monitor.ase_v0 is not True or monitor.crs is None or monitor.control_echo is None
                or monitor.situation.include_supervisory_control is not False
                or monitor.cqs is not None or monitor.system_prompt != prompt):
            raise RuntimeError('Curator/CRS deployed smoke mismatch')
    # These tests use scripted responses only, with no provider or Task request.
    tests = ['tests/test_crs_v0.py::test_scripted_root_code_receipt_handle_flat_proposal_and_confirmation',
             'tests/test_crs_v0.py::test_original_task_line_range_and_actionable_invalid_ref',
             'tests/test_crs_v0.py::test_local_provider_schema_is_baseline_ase_and_only_root_allow_changes']
    checked = subprocess.run([sys.executable, '-m', 'pytest', *tests, '-q'],
                             cwd=REPO / 'GenericAgent-main', capture_output=True, text=True)
    if checked.returncode != 0:
        raise RuntimeError('Scripted zero-model CRS preflight failed: ' + checked.stdout[-2000:])


inherited._crs_source_gate = _crs_v02_source_gate


def launch(authorization_path: Path):
    return inherited.launch(authorization_path)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--authorization', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(launch(args.authorization), ensure_ascii=False, default=str))
