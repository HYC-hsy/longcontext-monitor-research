"""One-slot authorized entry using the existing runner and trial bridge."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from method_discovery import uc_cqs_entry as inherited
from method_discovery import uc_r5_execution_entry as bridge_entry
from method_discovery.uc_r5_execution_bridge import file_sha, save_json
from method_discovery.uc_cqs_kitex_baseline_prepare import REPO, ROOT


PLAN = ROOT / 'PLAN.json'
MANIFEST = ROOT / 'RUNNER_MANIFEST.json'


def load_authorized_slot(run_id: str, authorization_path: Path):
    inherited.PLAN = PLAN
    inherited.MANIFEST = MANIFEST
    return inherited.load_authorized_slot(run_id, authorization_path)


def launch(run_id: str, authorization_path: Path):
    slot, auth = load_authorized_slot(run_id, authorization_path)
    bridge_entry.FROZEN_CANDIDATE = slot['candidate_commit']
    frozen_identity = bridge_entry.require_frozen_source_and_harbor()
    campaign = Path(slot['output']['campaign_root'])
    if Path(slot['live_root']).exists() or any((campaign / name / run_id).exists()
                                                for name in ('jobs', 'runs', 'bridge')):
        raise RuntimeError('Baseline run identity or output already used')
    control_dir = campaign / 'bridge' / run_id / 'control'
    archive_dir = campaign / 'bridge' / run_id / 'evidence'
    control_dir.mkdir(parents=True, exist_ok=False)
    archive_dir.mkdir(parents=True, exist_ok=False)
    spec_path = campaign / 'bridge' / run_id / 'bridge_spec.private.json'
    save_json(spec_path, {
        'execution_authorized': True, 'slot': slot, 'task_model': auth['task_model'],
        'control_dir': str(control_dir), 'archive_dir': str(archive_dir),
        'authorization_path': str(authorization_path.resolve()),
        'authorization_sha256': file_sha(authorization_path),
        'plan_sha256': file_sha(PLAN), 'frozen_source_and_harbor': frozen_identity,
    })
    bench = Path(r'E:\LongContext\long_context_bench')
    sys.path.insert(0, str(bench))
    from scripts import run_ultralong_m12_proofs as runner
    from scripts import run_harbor_tb2_m4 as m4

    runner.apply_experiment_manifest(MANIFEST, run_id)
    common = json.loads((REPO / 'method_discovery/runs/uc_r5_cmp_readiness_20261003/ENVIRONMENT_DRAFT.json'
                         ).read_text(encoding='utf-8'))['common']
    common['GA_MAX_TURNS'] = '300'
    for name, value in common.items():
        if os.environ.get(name) != value:
            raise RuntimeError(f'Effective common runtime configuration mismatch: {name}')
    if Path(os.environ['BENCHMARK_CAMPAIGN_ROOT']).resolve() != campaign.resolve():
        raise RuntimeError('Effective campaign root mismatch')
    if Path(os.environ['GA_HOST_ROOT']).resolve() != Path(slot['deployment']['ga_host_root']).resolve():
        raise RuntimeError('Authorized source root mismatch')
    if file_sha(Path(slot['deployment']['monitor_profile_path'])) != slot['deployment']['monitor_profile_sha256']:
        raise RuntimeError('Private Monitor profile mismatch')
    if os.environ.get('GA_RUN_ISOLATION') != 'no-network-unix-inference-v1':
        raise RuntimeError('Isolation profile mismatch')
    m4.GA_ROOT = Path(os.environ['GA_HOST_ROOT'])
    runner.build_bundle = bridge_entry.overlay_bundle(
        runner.build_bundle, REPO / 'method_discovery/uc_r5_bridge_gateway.py',
        control_dir, slot, spec_path)
    os.environ['UC_R5_BRIDGE_SPEC'] = str(spec_path)
    os.environ['PYTHONPATH'] = os.pathsep.join([str(REPO), os.environ.get('PYTHONPATH', '')])
    original_run = m4.run
    harbor_exe = str(m4.HARBOR_EXE)

    def run_with_hooks(command, *args, **kwargs):
        if len(command) < 3 or command[0] != harbor_exe or command[1:3] != ['jobs', 'start']:
            return original_run(command, *args, **kwargs)
        harbor_python = str(Path(harbor_exe).with_name('python.exe'))
        guarded = [harbor_python, str(REPO / 'method_discovery/uc_cqs_kitex_baseline_harbor_cli.py'),
                   *command[1:]]
        return original_run(guarded, *args, **kwargs)

    m4.run = run_with_hooks
    try:
        return runner.run_proof(source=slot['runner']['source'], run_id=run_id,
                                llm_no=slot['runner']['llm_no'],
                                max_agent_seconds=slot['runner']['max_agent_seconds'],
                                task_id=slot['runner']['task_id'])
    finally:
        m4.run = original_run
        os.environ.pop('UC_R5_BRIDGE_SPEC', None)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--authorization', type=Path, required=True)
    args = parser.parse_args()
    if args.run_id != json.loads(PLAN.read_text(encoding='utf-8'))['run_order'][0]:
        raise RuntimeError('Outside authorized single-slot baseline')
    print(json.dumps(launch(args.run_id, args.authorization), ensure_ascii=False, default=str))


if __name__ == '__main__':
    main()
