"""Opt-in fixed original-M1 panel; delegates the reviewed native launch paths."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PILOT = ROOT / 'method_discovery/diagnostics/m1_p_launch_preparation_20260928'
sys.path.insert(0, str(PILOT))
import launch_pilot as native
from prepare_bundle import M1, TASK, sha

BATCH = 'm1-core4-dev-b01-20260929'
CASES = {
    'fyne-m1': ('roadmapbench:fyn-2.2.0-roadmap', 'm1-core4-b01-20260929-01'),
    'sphinx-m1': ('claw_swe:sphinx-doc__sphinx-8551', 'm1-core4-b01-20260929-02'),
    'kitex-m1': ('roadmapbench:ktx-0.13.0-roadmap', 'm1-core4-b01-20260929-03'),
    'ratatui-m1': ('roadmapbench:rat-0.22.0-roadmap', 'm1-core4-b01-20260929-04'),
}
RUNS = {k: v[1] for k, v in CASES.items()}


def execution_files():
    return [Path(__file__), HERE / 'sphinx_entry.py', HERE / 'run_serial.py', HERE / 'environment_preparation.json',
        HERE / 'SPHINX_ENVIRONMENT.txt', HERE / 'sphinx_registry.jsonl', PILOT / 'launch_pilot.py', PILOT / 'prepare_bundle.py',
        PILOT / 'pilot_archive_agent.py', PILOT / 'pilot_bootstrap.py', PILOT / 'resource_budget.py',
        ROOT / 'method_discovery/run_dcec_v1_claw_swe_generalization.py',
        HERE / 'launch_substrate/run_claw_swe_m3.py']


def identities():
    return {p.relative_to(ROOT).as_posix(): sha(p.read_bytes()) for p in execution_files()}


def validate(batch, record, run):
    if batch != BATCH or RUNS.get(record) != run:
        raise RuntimeError('unapproved core4 identity')


def authorize(path, record, batch_id=None, run_id=None):
    validate(batch_id, record, run_id)
    auth = json.loads(Path(path).read_text(encoding='utf-8'))
    head = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    if (auth.get('authorization') is not True or auth.get('batch_id') != BATCH
            or auth.get('record_run_ids') != RUNS or record not in auth.get('records', [])
            or auth.get('supervisor_commit') != M1 or auth.get('task_commit') != TASK
            or auth.get('execution_commit') != head or auth.get('execution_files') != identities()
            or auth.get('policy_enabled') is not False):
        raise RuntimeError('authorization does not bind frozen core4 execution')
    return auth


def configure_roadmap():
    # Only explicit task / batch identity changes; native adapter/bundle unchanged.
    native.ORDER = [(k, task.split(':', 1)[1], False) for k, (task, _) in CASES.items()
                    if task.startswith('roadmapbench:')]
    native.BATCH_ID = BATCH
    native.BATCH_RUNS = RUNS
    native.validate_identity = validate
    native.authorize = authorize


def profiles(path):
    values = json.loads(Path(path).read_text(encoding='utf-8'))
    common = native.common_profiles()
    if set(values) != set(common):
        raise RuntimeError('exactly two approved profiles required')
    for name, expected in common.items():
        cfg = values[name]
        if any(cfg.get(k) != v for k, v in expected.items()):
            raise RuntimeError('shared profile parameter mismatch')
        if set(cfg) - set(expected) - {'apikey', 'apibase', 'verify'}:
            raise RuntimeError('unapproved profile parameter')
        if not cfg.get('apikey') or not cfg.get('apibase', '').startswith('https://'):
            raise RuntimeError('approved HTTPS credentials missing')
    return values


def main():
    parser = argparse.ArgumentParser()
    for name in ('record', 'batch-id', 'run-id', 'supervisor-source', 'output-root'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--profiles')
    parser.add_argument('--authorization')
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    validate(args.batch_id, args.record, args.run_id)
    if not args.execute:
        print(json.dumps(dict(batch_id=BATCH, record=args.record, task_id=CASES[args.record][0],
            run_id=args.run_id, supervisor_commit=M1, task_commit=TASK, policy_enabled=False,
            shared_config=native.common_profiles(), model_requests=0), indent=2))
        return
    if not args.authorization:
        raise RuntimeError('explicit authorization required')
    authorize(args.authorization, args.record, args.batch_id, args.run_id)
    if (Path(args.output_root) / 'archive_pause.json').exists():
        raise RuntimeError('prior archive failure: panel paused')
    if (Path(args.output_root) / args.record).exists():
        raise RuntimeError('record already exists: no restart')
    prepared = json.loads((HERE / 'environment_preparation.json').read_text())
    if args.record == 'ratatui-m1' and not prepared.get('ratatui_ready'):
        raise RuntimeError('NOT STARTED / ENVIRONMENT BLOCKED: immutable Rust/lockfile incompatibility')
    if args.record == 'sphinx-m1':
        if not prepared.get('sphinx_loading_ready'):
            raise RuntimeError('Sphinx project environment unavailable')
        from sphinx_entry import execute
        execute(args, profiles(args.profiles))
    else:
        configure_roadmap()
        native.main()


if __name__ == '__main__':
    main()
