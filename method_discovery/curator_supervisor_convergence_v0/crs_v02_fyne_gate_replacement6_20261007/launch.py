"""Replacement after a zero-model child-preflight failure; same candidate and bundle."""

from pathlib import Path

from method_discovery.curator_supervisor_convergence_v0.crs_v02_fyne_gate_replacement_20261007 import launch as base


ROOT = Path(__file__).resolve().parent
RUN_ID = 'crs-v02-fyne-mechanism-gate-b-only-r1-infra-replacement-6'
CANDIDATE = base.CANDIDATE
base.inherited.ROOT = ROOT
base.inherited.RUN_ID = RUN_ID
base.inherited.PLAN = ROOT / 'PLAN.json'
base.inherited.MANIFEST = ROOT / 'RUNNER_MANIFEST.json'
base.inherited.BUNDLE = base.ROOT / 'BUNDLE_FREEZE.json'


def launch(authorization_path):
    return base.inherited.launch(authorization_path)


if __name__ == '__main__':
    import argparse
    import json
    parser = argparse.ArgumentParser()
    parser.add_argument('--authorization', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(launch(args.authorization), ensure_ascii=False, default=str))
