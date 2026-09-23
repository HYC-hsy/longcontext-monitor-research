"""Run the single pre-dev-set observation-boundary acceptance.

This wrapper reuses the audited CLAW-SWE launch path and changes only the
scientific candidate identity and output locations.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "method_discovery" / "run_dcec_v1_claw_swe_generalization.py"
MANIFEST = ROOT / "method_discovery" / "runs" / "dcec_predev_boundary_sphinx_20260923_manifest.json"


def load_base():
    spec = importlib.util.spec_from_file_location("dcec_generalization_base", BASE)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load audited CLAW-SWE launch path")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def execute() -> dict:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    base = load_base()
    run_id = manifest["run_id"]
    campaign_root = ROOT / manifest["campaign_root"]
    base.MANIFEST = MANIFEST
    base.RUN_ID = run_id
    base.INSTANCE_ID = "sphinx-doc__sphinx-8551"
    base.CAMPAIGN_ROOT = campaign_root
    base.M3_ROOT = campaign_root / "claw_swe"
    base.LOCKS = campaign_root / "claw_swe_method_locks.jsonl"
    base.BUNDLE_ROOT = campaign_root / "isolated_bundles" / run_id
    base.RESULT_PATH = campaign_root / "launch_result.json"
    base.GATEWAY_LOG = campaign_root / "gateway_transport.log"
    base.MECHANISM_COMMIT = manifest["candidate_implementation"]
    base.MECHANISM_HASHES = manifest["mechanism_source_hashes"]
    base.EXPECTED_GA_HASH = manifest["generic_agent_python_source_sha256"]
    base.DCEC_ENV.update({
        "GA_EXPERIMENT_ID": run_id,
        "GA_CONDITION_ID": "dcec-predev-boundary",
    })
    base.M3_ROOT.mkdir(parents=True, exist_ok=True)
    return base.execute()


if __name__ == "__main__":
    print(json.dumps(execute(), ensure_ascii=False, indent=2))
