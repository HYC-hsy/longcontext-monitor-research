"""Frozen ADER Roadmap execution with archived-M1, zero-model identity gate."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RUNNER_ROOT = Path(r'E:\longcontext-m1-746a695')
ADER_ROOT = Path(r'E:\longcontext-ader-746a695')
sys.path.insert(0, str(RUNNER_ROOT / 'long_context_bench'))
from scripts import run_ultralong_m12_proofs as runner
from scripts.isolated_run_bundle import build_bundle

M1 = '746a695adac4325d6440941d384d543d1364fef9'
ADER = '16ddee55ead5f48ef955e5b76bbfae0f7e7698a5'
BATCH = 'ader-real-dev-pilot-20261001'
REFERENCE = ROOT / 'method_discovery/runs/cprr_real_dev_pilot_20260930'
REFERENCE_LOCAL = ROOT / 'long_context_bench/output/cprr_real_dev_pilot_20260930'
RECORDS = {
    'ader-real-dev-pilot-20261001-01': ('fyn-2.2.0-roadmap', 'r1',
                                         'cprr-real-dev-pilot-20260930-01', 500, 10000),
    'ader-real-dev-pilot-20261001-02': ('ktx-0.13.0-roadmap', 'r4',
                                         'cprr-real-dev-pilot-20260930-04', 300, 7200),
}
TASK_PROFILE_SHA = 'ed09a811b654b83097bee77942704eae2539d67291bf55aa34476692081ff02e'
MONITOR_PROFILE_SHA = 'cc5f784b069034f44bc4527d15acd70191b1f7fc5810556c087b7b35e0ae00f1'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def frozen_source(destination):
    actual = subprocess.check_output(['git', '-C', str(ADER_ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    dirty = subprocess.check_output(['git', '-C', str(ADER_ROOT), 'status', '--porcelain',
                                     '--untracked-files=no'], text=True)
    if actual != ADER or dirty:
        raise RuntimeError('frozen ADER source identity mismatch')
    changed = subprocess.check_output(['git', '-C', str(ADER_ROOT), 'diff', '--name-only',
                                       M1, ADER, '--', 'GenericAgent-main'], text=True).splitlines()
    if set(changed) != {
            'GenericAgent-main/monitor_agent_core/agent.py',
            'GenericAgent-main/monitor_agent_core/working_context.py',
            'GenericAgent-main/tests/test_monitor_dcec.py'}:
        raise RuntimeError('ADER source has unreviewed files: ' + repr(changed))
    archive = subprocess.check_output(['git', '-C', str(ADER_ROOT), 'archive', '--format=zip',
                                       ADER, 'GenericAgent-main'])
    destination.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(io.BytesIO(archive)) as stream:
        stream.extractall(destination)
    ga = destination / 'GenericAgent-main'
    (ga / 'temp').mkdir(exist_ok=True)
    key = RUNNER_ROOT / 'GenericAgent-main/mykey.py'
    profile = RUNNER_ROOT / 'monitor_config/models.local.json'
    if sha(key.read_bytes()) != TASK_PROFILE_SHA:
        raise RuntimeError('Task private profile changed')
    if sha(profile.read_bytes()) != MONITOR_PROFILE_SHA:
        raise RuntimeError('Supervisor private profile changed')
    shutil.copyfile(key, ga / 'mykey.py')
    (destination / 'monitor_config').mkdir()
    shutil.copyfile(profile, destination / 'monitor_config/models.local.json')
    return ga, {
        'commit': actual, 'git_archive_sha256': sha(archive),
        'task_profile_sha256': sha(key.read_bytes()),
        'monitor_profile_sha256': sha(profile.read_bytes()),
        'production_diff': ['monitor_agent_core/agent.py', 'monitor_agent_core/working_context.py'],
    }


def common_environment(turns):
    for key in list(os.environ):
        if key.startswith('GA_'):
            del os.environ[key]
    os.environ.update(
        GA_BASELINE_CONDITION='original', GA_RUN_ISOLATION='no-network-unix-inference-v1',
        GA_MONITOR_ENABLED='1', GA_MONITOR_CONFIG='claude_monitor_opus48',
        GA_LLM_CONFIG_NAME='native_claude_cc_vibe_opus48', GA_MONITOR_DCEC='1',
        GA_MONITOR_SEMANTIC_CONTINUITY='1', GA_MONITOR_DCEC_WORKING_CHARS='4000',
        GA_MONITOR_INDEPENDENT_C='0', GA_PROVIDER_MAX_RETRIES='8',
        GA_MAX_TURNS=str(turns), GA_MONITOR_EXPECTED_MODEL='claude-opus-4-8',
        GA_KEEP_HARBOR_ENV='1')


def configure_runner(ga, output):
    runner.m4.GA_ROOT = ga
    runner.m4.GA_RUNTIME = ROOT / 'bench_runtime/m2/linux'
    os.environ['GA_METHOD_EXPECTED_SOURCE_SHA256'] = runner.m4.tree_hash(ga, ga_mode=True)
    runner.SOURCES['roadmapbench']['task_root'] = ROOT / 'long_context_bench/.cache/m12_roadmap_tasks'
    runner.SOURCES['roadmapbench']['proposal'] = ROOT / 'long_context_bench/tasks/ultralong_m12_roadmapbench_proposal.jsonl'
    runner.WORK_ROOT = output
    runner.JOBS_ROOT, runner.RUNS_ROOT, runner.OTEL_ROOT = (
        output / name for name in ('jobs', 'runs', 'otel'))
    runner.COLLECTOR_NAME = 'ader-real-dev-pilot-otel'


def file_hashes(root):
    return {p.relative_to(root).as_posix(): sha(p.read_bytes())
            for p in root.rglob('*') if p.is_file()}


def identity_gate(run_id, task, ref_label, ref_id, turns, seconds, output):
    gate_root = output / 'identity_gate' / run_id
    ga, source_identity = frozen_source(gate_root / 'source_input')
    common_environment(turns)
    configure_runner(ga, gate_root)
    preflight = runner.preflight('roadmapbench', 0, task)
    reference = json.loads((REFERENCE / ref_label / 'proof/manifest.json').read_text(encoding='utf-8'))
    old = reference['source_identity']
    compare = {
        'task_id': (preflight['task_id'], old['task_id']),
        'task_tree_sha256': (preflight['task_tree_sha256'], old['task_tree_sha256']),
        'source_revision': (preflight['source_revision'], old['source_revision']),
        'image': (preflight['image'], old['image']),
        'harbor': (preflight['harbor'], old['harbor']),
        'runtime': (preflight['runtime'], old['runtime']),
        'model': (preflight['model'], old['model']),
        'adapter': (preflight['adapter'], old['adapter']),
    }
    mismatches = [name for name, (actual, prior) in compare.items() if actual != prior]
    if reference['integration_budget_sec'] != seconds:
        mismatches.append('integration_budget_sec')
    trial_config = json.loads((REFERENCE / ref_label / 'trial/config.json').read_text(encoding='utf-8'))
    prior_agent = trial_config['agent']
    expected_kwargs = {
        'max_turns': turns, 'timeout_sec': seconds,
        'llm_config_name': 'native_claude_cc_vibe_opus48',
        'monitor_enabled': True, 'monitor_config': 'claude_monitor_opus48',
        'baseline_condition': 'original', 'condition_id': 'original',
    }
    for key, expected in expected_kwargs.items():
        if prior_agent['kwargs'].get(key) != expected:
            mismatches.append('archived_agent_kwargs.' + key)
    if prior_agent['model_name'] != 'claude-opus-4-8':
        mismatches.append('archived_agent_model')
    if reference['agent_protocol']['task_id'] != 'roadmapbench:' + task:
        mismatches.append('agent_task_id')
    prior_bundle = REFERENCE_LOCAL / 'isolated_bundles' / ref_id / 'source'
    if not prior_bundle.is_dir():
        raise RuntimeError('archived M1 local isolated source is unavailable')
    copied, compose = build_bundle(
        gate_root / 'bundle', ga, runner.m4.GA_RUNTIME,
        preflight['runtime']['python_home'], os.environ['GA_LLM_CONFIG_NAME'],
        os.environ['GA_MONITOR_CONFIG'], runner.COLLECTOR_PORT,
        monitor_profile_path=ga.parent / 'monitor_config/models.local.json')
    isolation = json.loads((compose.parent / 'isolation_identity.json').read_text(encoding='utf-8'))
    reference_isolation = json.loads(
        (REFERENCE / ref_label / 'source_identity/isolation_identity.json').read_text(encoding='utf-8'))
    for key in ('profile', 'model_names', 'secrets_in_evidence', 'task_network_mode',
                'gateway_transport_sha256'):
        if isolation[key] != reference_isolation[key]:
            mismatches.append('isolation.' + key)
    before, after = file_hashes(prior_bundle), file_hashes(copied)
    source_diff = sorted(path for path in before.keys() | after.keys()
                         if before.get(path) != after.get(path))
    if source_diff != ['monitor_agent_core/agent.py', 'monitor_agent_core/working_context.py']:
        mismatches.append('isolated_source_diff')
    report = {
        'run_id': run_id, 'reference_run_id': ref_id,
        'status': 'PASS' if not mismatches else 'FAIL',
        'source_identity': source_identity, 'task_max_turns': turns,
        'integration_budget_seconds': seconds,
        'comparison': {k: {'ader': v[0], 'archived_m1': v[1], 'match': v[0] == v[1]}
                       for k, v in compare.items()},
        'isolation': {k: isolation[k] for k in ('profile', 'snapshot_sha256', 'model_names',
                                                'secrets_in_evidence', 'task_network_mode',
                                                'gateway_transport_sha256')},
        'isolated_source_diff': source_diff, 'mismatches': mismatches,
        'planned_treatment': {'supervisor_commit': ADER, 'dcec': True,
                              'independent_child': False},
        'model_requests': 0,
    }
    path = HERE / ('IDENTITY_GATE_' + run_id[-2:] + '.json')
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True, choices=RECORDS)
    parser.add_argument('--output-root', required=True)
    parser.add_argument('--gate-only', action='store_true')
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    task, label, reference_id, turns, seconds = RECORDS[args.run_id]
    registration = json.loads((HERE / 'PREREGISTRATION.json').read_text(encoding='utf-8'))
    row = [x for x in registration['records'] if x['run_id'] == args.run_id]
    if (registration['batch_id'] != BATCH or len(row) != 1
            or row[0]['task'] != 'roadmapbench:' + task
            or row[0]['reference_run_id'] != reference_id
            or row[0]['task_max_turns'] != turns
            or row[0]['integration_budget_seconds'] != seconds):
        raise RuntimeError('run differs from preregistration')
    output = Path(args.output_root).resolve()
    if args.gate_only == args.execute:
        raise ValueError('select exactly one of --gate-only and --execute')
    if args.gate_only:
        report = identity_gate(args.run_id, task, label, reference_id, turns, seconds, output)
        print(json.dumps({'run_id': args.run_id, 'gate': report['status'],
                          'mismatches': report['mismatches']}, indent=2))
        if report['status'] != 'PASS':
            raise RuntimeError('zero-model identity gate failed')
        return
    if any((output / name / args.run_id).exists() for name in ('jobs', 'runs', 'isolated_bundles')):
        raise RuntimeError('record already started: no record-level rerun')
    if (output / 'archive_pause.json').exists():
        raise RuntimeError('earlier archive failure pauses this batch')
    gate = json.loads((HERE / ('IDENTITY_GATE_' + args.run_id[-2:] + '.json')).read_text(encoding='utf-8'))
    if gate['status'] != 'PASS' or gate['run_id'] != args.run_id or gate['mismatches']:
        raise RuntimeError('zero-model identity gate is not passed')
    ga, identity = frozen_source(output / 'source_inputs' / args.run_id)
    if identity != gate['source_identity']:
        raise RuntimeError('execution source differs from identity gate')
    (output / 'source_inputs' / args.run_id / 'source_identity.json').write_text(
        json.dumps(identity, indent=2), encoding='utf-8')
    common_environment(turns)
    configure_runner(ga, output)
    result = runner.run_proof('roadmapbench', args.run_id, 0, seconds, task)
    (output / 'source_inputs' / args.run_id / 'result.json').write_text(
        json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
