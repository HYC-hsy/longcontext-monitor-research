"""One separately authorized infrastructure replacement; no candidate change."""

from pathlib import Path

from method_discovery.curator_supervisor_convergence_v0.fyne_gate_candidate_r1 import launch as base


ROOT = Path(__file__).resolve().parent
RUN_ID = 'curator-supervisor-fyne-gate-v0-candidate-r2-infra-replacement'
base.ROOT = ROOT
base.PLAN = ROOT / 'PLAN.json'
base.MANIFEST = ROOT / 'RUNNER_MANIFEST.json'
base.BUNDLE = ROOT.parent / 'fyne_gate_candidate_r1' / 'BUNDLE_FREEZE.json'
base.RUN_ID = RUN_ID


if __name__ == '__main__':
    import argparse
    import json
    parser = argparse.ArgumentParser()
    parser.add_argument('--authorization', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(base.launch(args.authorization), ensure_ascii=False, default=str))
