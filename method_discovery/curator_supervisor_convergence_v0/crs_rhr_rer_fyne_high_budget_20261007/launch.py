"""One B+J+I high-budget Fyne slot; frozen identity gates before any send."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess

from method_discovery.curator_supervisor_convergence_v0.crs_rhr_rer_fyne_gate_replacement_20261007 import launch as previous
from method_discovery.uc_r5_execution_bridge import file_sha


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
RUN_ID = 'crs-rhr-rer-v0-fyne-bji-high-budget-r1'
CANDIDATE = '05e36f80bdcc5cf274981755f13ab7bb14451e37'
PRIVATE = Path(r'E:\crs_rhr_rer_fyne_high_budget_private_20261007')
CAMPAIGN = Path(r'E:\LongContext\long_context_bench\output\crs_rhr_rer_fyne_mechanism_gate')
PLAN = ROOT / 'PLAN.json'
MANIFEST = ROOT / 'RUNNER_MANIFEST.json'
BUNDLE = ROOT / 'BUNDLE_FREEZE.json'

# The audited bridge/execution path is reused. Only this one slot's source,
# output, and explicitly authorized host-turn ceilings differ.
base, v01 = previous.base, previous.v01
for module in (previous, base, v01):
    for name in ('ROOT', 'REPO', 'RUN_ID', 'CANDIDATE', 'PRIVATE', 'CAMPAIGN',
                 'PLAN', 'MANIFEST', 'BUNDLE'):
        setattr(module, name, globals()[name])


def _json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _git(*args):
    return subprocess.check_output(['git', *args], cwd=REPO, text=True).strip()


def source_gate(bundle):
    previous.source_gate(bundle)
    if _git('rev-parse', 'HEAD:GenericAgent-main') != _git('rev-parse', f'{CANDIDATE}:GenericAgent-main'):
        raise RuntimeError('Checked-out production tree differs from audited candidate')
    for relative in ('agentmain.py', 'monitor_agent_core/runtime.py'):
        source = PRIVATE / 'GenericAgent-main' / relative
        if _git('hash-object', str(source)) != _git('rev-parse', f'{CANDIDATE}:GenericAgent-main/{relative}'):
            raise RuntimeError(f'High-budget candidate source mismatch: {relative}')
    if file_sha(PRIVATE / 'candidate.tar') != bundle['candidate_archive_sha256']:
        raise RuntimeError('Candidate Git archive identity mismatch')


def load_authorized_slot(run_id, authorization_path):
    if run_id != RUN_ID:
        raise RuntimeError('Only the one high-budget Fyne slot is authorized')
    env = _json(MANIFEST)['runs'][0]['environment']
    prior = _json(REPO / 'method_discovery/curator_supervisor_convergence_v0/'
                  'crs_rhr_rer_fyne_gate_replacement_20261007/RUNNER_MANIFEST.json')['runs'][0]['environment']
    changed = {key for key in set(env) | set(prior) if env.get(key) != prior.get(key)}
    expected_changes = {'GA_CONDITION_ID', 'GA_HOST_ROOT', 'GA_METHOD_EXPECTED_SOURCE_SHA256',
                        'GA_MONITOR_MAX_REVIEW_TURNS', 'GA_MONITOR_ROOT_MAX_REVIEW_TURNS'}
    if changed != expected_changes or env.get('GA_MONITOR_MAX_REVIEW_TURNS') != '300' or env.get('GA_MONITOR_ROOT_MAX_REVIEW_TURNS') != '300':
        raise RuntimeError(f'High-budget runner environment drift: {sorted(changed)}')
    plan = _json(PLAN)
    if (plan['ordinary_review_turn_ceiling'] != 300
            or plan['root_handoff_cumulative_turn_ceiling'] != 300
            or plan['candidate_source_commit'] != CANDIDATE):
        raise RuntimeError('High-budget plan identity mismatch')
    slot, auth = previous.load_authorized_slot(run_id, authorization_path)
    bundle = _json(BUNDLE)
    source_gate(bundle)
    if slot['candidate_commit'] != CANDIDATE or slot['deployment']['bundle_snapshot_sha256'] != bundle['bundle_source_sha256']:
        raise RuntimeError('Candidate/isolation slot identity mismatch')
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
