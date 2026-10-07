"""New authorized slot after the archived Docker/WSL infrastructure failure.

The scientific runner and source gates are inherited unchanged from the
previous CRS-v0.1 slot. Only the run identity and slot metadata differ.
"""

from __future__ import annotations

from pathlib import Path

from method_discovery.curator_supervisor_convergence_v0.crs_v01_fyne_gate_infra_replacement_20261007 import launch as inherited


ROOT = Path(__file__).resolve().parent
RUN_ID = 'crs-v01-fyne-mechanism-gate-b-only-r1-infra-replacement-2'
inherited.ROOT = ROOT
inherited.RUN_ID = RUN_ID
inherited.PLAN = ROOT / 'PLAN.json'
inherited.MANIFEST = ROOT / 'RUNNER_MANIFEST.json'


def load_authorized_slot(run_id, authorization_path):
    return inherited.load_authorized_slot(run_id, authorization_path)


def launch(authorization_path):
    return inherited.launch(authorization_path)


if __name__ == '__main__':
    import argparse
    import json

    parser = argparse.ArgumentParser()
    parser.add_argument('--authorization', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(launch(args.authorization), ensure_ascii=False, default=str))
