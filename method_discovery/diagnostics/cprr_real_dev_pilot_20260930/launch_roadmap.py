"""Frozen-source Roadmap admission for the CPRR development pilot.

Uses the existing native proof runner. No Task/Monitor implementation is patched.
"""
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
# The common launcher/transport is the same frozen M1 tree used by the recent
# Fyne stability run, not the later research-branch checkout.
RUNNER_ROOT = Path(r'E:\longcontext-m1-746a695')
sys.path.insert(0, str(RUNNER_ROOT / 'long_context_bench'))
from scripts import run_ultralong_m12_proofs as runner

M1 = '746a695adac4325d6440941d384d543d1364fef9'
CPRR = '22755819b0a332389883f30e46e93f457a4c036c'
RECORDS = {
    'cprr-real-dev-pilot-20260930-01': ('fyn-2.2.0-roadmap', M1, 500, 10000),
    'cprr-real-dev-pilot-20260930-02': ('fyn-2.2.0-roadmap', CPRR, 500, 10000),
    'cprr-real-dev-pilot-20260930-03': ('ktx-0.13.0-roadmap', CPRR, 300, 7200),
    'cprr-real-dev-pilot-20260930-04': ('ktx-0.13.0-roadmap', M1, 300, 7200),
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def source(path, expected, destination):
    path = Path(path).resolve(strict=True)
    actual = subprocess.check_output(['git', '-C', str(path), 'rev-parse', 'HEAD'], text=True).strip()
    if actual != expected:
        raise RuntimeError('wrong frozen source commit: ' + actual)
    if subprocess.check_output(['git', '-C', str(path), 'status', '--porcelain', '--untracked-files=no']):
        raise RuntimeError('frozen tracked source is dirty')
    archive = subprocess.check_output(['git', '-C', str(path), 'archive', '--format=zip', 'HEAD', 'GenericAgent-main'])
    destination.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(io.BytesIO(archive)) as stream:
        stream.extractall(destination)
    ga = destination / 'GenericAgent-main'
    (ga / 'temp').mkdir(exist_ok=True)
    # Exact pre-existing private dual-role routing; copied only into ignored run output.
    private = Path(r'E:\longcontext-m1-746a695')
    key = private / 'GenericAgent-main/mykey.py'
    profiles = private / 'monitor_config/models.local.json'
    if sha(key.read_bytes()) != 'ed09a811b654b83097bee77942704eae2539d67291bf55aa34476692081ff02e':
        raise RuntimeError('historical private Task profile identity changed')
    shutil.copyfile(key, ga / 'mykey.py')
    config_dir = destination / 'monitor_config'
    config_dir.mkdir()
    shutil.copyfile(profiles, config_dir / 'models.local.json')
    return ga, dict(commit=actual, git_archive_sha256=sha(archive),
        task_profile_sha256=sha(key.read_bytes()), monitor_profile_sha256=sha(profiles.read_bytes()))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True, choices=RECORDS)
    parser.add_argument('--source', required=True)
    parser.add_argument('--output-root', required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    task, commit, turns, seconds = RECORDS[args.run_id]
    prereg = json.loads((HERE / 'PREREGISTRATION.json').read_text(encoding='utf-8'))
    rows = [row for row in prereg['records'] if row['run_id'] == args.run_id]
    if (prereg['batch_id'] != 'cprr-real-dev-pilot-20260930' or len(rows) != 1
            or rows[0]['task'] != 'roadmapbench:' + task
            or rows[0]['arm'] != ('m1' if commit == M1 else 'cprr')
            or rows[0]['turns'] != turns or rows[0]['seconds'] != seconds):
        raise RuntimeError('run does not match preregistration')
    out = Path(args.output_root).resolve()
    if (out / 'jobs' / args.run_id).exists() or (out / 'runs' / args.run_id).exists() or (out / 'isolated_bundles' / args.run_id).exists():
        raise RuntimeError('record already started: no record-level rerun')
    if not args.execute:
        print(json.dumps(dict(run_id=args.run_id, task=task, source=commit, turns=turns, seconds=seconds, execute=False)))
        return
    if (out / 'archive_pause.json').exists():
        raise RuntimeError('earlier archive failure pauses this panel')
    ga, identity = source(args.source, commit, out / 'source_inputs' / args.run_id)
    (out / 'source_inputs' / args.run_id / 'source_identity.json').write_text(json.dumps(identity, indent=2))
    for key in list(os.environ):
        if key.startswith('GA_'):
            del os.environ[key]
    os.environ.update(GA_BASELINE_CONDITION='original', GA_RUN_ISOLATION='no-network-unix-inference-v1',
        GA_MONITOR_ENABLED='1', GA_MONITOR_CONFIG='claude_monitor_opus48',
        GA_LLM_CONFIG_NAME='native_claude_cc_vibe_opus48', GA_MONITOR_DCEC='1',
        GA_MONITOR_SEMANTIC_CONTINUITY='1', GA_MONITOR_DCEC_WORKING_CHARS='4000',
        GA_PROVIDER_MAX_RETRIES='8', GA_MAX_TURNS=str(turns),
        GA_MONITOR_EXPECTED_MODEL='claude-opus-4-8', GA_KEEP_HARBOR_ENV='1')
    runner.m4.GA_ROOT = ga
    runner.m4.GA_RUNTIME = ROOT / 'bench_runtime/m2/linux'
    os.environ['GA_METHOD_EXPECTED_SOURCE_SHA256'] = runner.m4.tree_hash(ga, ga_mode=True)
    runner.SOURCES['roadmapbench']['task_root'] = ROOT / 'long_context_bench/.cache/m12_roadmap_tasks'
    runner.SOURCES['roadmapbench']['proposal'] = ROOT / 'long_context_bench/tasks/ultralong_m12_roadmapbench_proposal.jsonl'
    runner.WORK_ROOT = out
    runner.JOBS_ROOT, runner.RUNS_ROOT, runner.OTEL_ROOT = (out / name for name in ('jobs', 'runs', 'otel'))
    runner.COLLECTOR_NAME = 'cprr-real-dev-pilot-otel'
    result = runner.run_proof('roadmapbench', args.run_id, 0, seconds, task)
    (out / 'source_inputs' / args.run_id / 'result.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
