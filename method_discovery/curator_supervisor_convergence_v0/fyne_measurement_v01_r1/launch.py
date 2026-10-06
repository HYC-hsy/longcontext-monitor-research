"""Single authorized measurement-prompt Fyne slot; reuse the audited launcher."""

from pathlib import Path

from method_discovery.curator_supervisor_convergence_v0.fyne_gate_candidate_r1 import launch as base


ROOT = Path(__file__).resolve().parent
RUN_ID = "curator-supervisor-fyne-measurement-v01-r1"
base.ROOT = ROOT
base.PLAN = ROOT / "PLAN.json"
base.MANIFEST = ROOT / "RUNNER_MANIFEST.json"
base.BUNDLE = ROOT / "BUNDLE_FREEZE.json"
base.RUN_ID = RUN_ID
base.CANDIDATE = "dfec10511bdafe97e8a0041cb95d19f5bed4de9b"
base.PRIVATE = Path(r"E:\curator_fyne_measurement_v01_private_20261006")
base.CAMPAIGN = Path(r"E:\LongContext\long_context_bench\output\curator_supervisor_fyne_measurement_v01")


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser()
    parser.add_argument("--authorization", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(base.launch(args.authorization), ensure_ascii=False, default=str))
