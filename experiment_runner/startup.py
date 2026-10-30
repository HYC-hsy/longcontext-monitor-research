"""Mechanical run identity and one-use legacy binding; no human audit claim."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
DRIVER = 'method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013'
EXTRA = ('experiment_runner/startup.py', 'experiment_runner/__main__.py',
         'experiment_runner/methods.py', 'experiment_runner/runtime_policy.py')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def code_identity(manifest):
    from importlib import import_module
    row = manifest['planned_order'][0]
    candidate = row.get('research_candidate', 'U')
    if row['condition'] == 'P':
        mod = import_module('method_discovery.pos_upstream_ga_v1_20261017.single_manifest')
        names = (*mod.SOURCE_FILES, *([mod.SHARED_SOURCE_FILE]
                 if candidate == 'pos_pma_shared_view_v1' else []))
    elif candidate == 'pma_stateful_memory_v1':
        names = import_module(DRIVER + '.stateful_certification').SOURCE_FILES
    else:
        mod = import_module(DRIVER + '.single_run_certification')
        names = (mod.EVIDENCE_GAP_SOURCE_FILES if candidate == 'pma_gap_evidence_v1' else
                 mod.GAP_SOURCE_FILES if candidate == 'pma_gap_memory_v0' else
                 mod.CANDIDATE_SOURCE_FILES if candidate != 'U' else mod.SOURCE_FILES)
    committed = import_module(DRIVER + '.prepare_six_task_manifest')._committed_source_sha
    sources = {name: committed(ROOT, name) for name in dict.fromkeys((*names, *EXTRA))}
    if row['condition'] == 'P':
        vendors = {'pos': mod.vendor_hashes(), 'pma': mod.pma_vendor_hashes()}
    else:
        vendors = import_module(DRIVER + '.single_run_certification').vendor_identity(ROOT)
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT,
                          capture_output=True, text=True, check=True).stdout.strip()
    return {'kind': 'committed_runtime_identity_v1', 'code_commit': head,
            'source_files': sources, 'vendor_files': vendors,
            'harbor_commit': '459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc',
            'validation': 'code_identity_only_no_new_lifecycle_certification'}


def verify_startup_identity(manifest):
    supplied = manifest.get('runtime_startup_identity')
    if supplied is None or supplied != code_identity(manifest):
        raise RuntimeError('prepared runtime source identity changed; prepare in a new output directory')
    return supplied


def bind_prepared_identity(directory):
    """Called during preparation: freeze committed code, never enable execution."""
    directory = Path(directory)
    path = directory / 'manifest.json'
    manifest = json.loads(path.read_text(encoding='utf-8'))
    manifest['runtime_startup_identity'] = code_identity(manifest)
    # This is an identity check, explicitly not a synthetic lifecycle certificate.
    manifest['status'] = 'prepared_not_executed'
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    identity_path = directory / 'run_identity.json'
    identity = json.loads(identity_path.read_text(encoding='utf-8'))
    identity['manifest_sha256'] = sha(path)
    identity_path.write_text(json.dumps(identity, indent=2) + '\n', encoding='utf-8')


def internal_binding(directory):
    """Validate exact prepared bytes/root before constructing a legacy run record."""
    directory = Path(directory).resolve(strict=True)
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    identity = json.loads((directory / 'run_identity.json').read_text(encoding='utf-8'))
    code = verify_startup_identity(manifest)
    run_id = identity.get('run_id')
    output = directory / 'runs'
    if (not isinstance(run_id, str) or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', run_id) is None or
            identity.get('execution_authorized') is not False or
            identity.get('plan_sha256') != sha(directory / 'plan.json') or
            identity.get('manifest_sha256') != sha(directory / 'manifest.json') or
            Path(identity.get('output_root', '')).resolve() != output or
            Path(identity.get('run_root', '')).resolve() != output / run_id):
        raise ValueError('prepared run identity/hash/root changed')
    if (directory / 'batch_result.json').exists() or (output.exists() and any(output.iterdir())):
        raise FileExistsError('slot already allocated or attempted; use a new result directory')
    row = manifest['planned_order'][0]
    bound = dict(row, run_id=run_id, run_root=str(output / run_id),
                 batch_id=run_id, config_sha256=manifest['config_sha256'])
    config = manifest['config']
    record = {'execution_authorized': True,
              'authorization_source': 'explicit_experiment_runner_run',
              'actor': 'experiment_runner', 'audited_code_commit': code['code_commit'],
              'manifest_sha256': identity['manifest_sha256'],
              'config_sha256': manifest['config_sha256'],
              'run_id': run_id, 'batch_id': run_id, 'output_root': str(output),
              'approved_arms': manifest['planned_order'], 'run_bindings': [bound],
              'zero_model_fixture_only': manifest.get('zero_model_fixture_only') is True,
              'candidate_profile_fixture_only': manifest.get('candidate_profile_fixture_only') is True}
    for name in ('task_complete_response_policy', 'agent_time_protocol',
                 'native_context_policy', 'research_capture_policy'):
        if name in config:
            record[name] = config[name]
    from importlib import import_module
    import_module(DRIVER + '.six_task_plan').validate_plan(manifest, record)
    return record
