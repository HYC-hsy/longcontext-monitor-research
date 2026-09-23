"""Single final Sphinx targeted acceptance for the persistent dependency candidate."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "method_discovery" / "run_dcec_v1_claw_swe_generalization.py"
MANIFEST = ROOT / "method_discovery" / "runs" / "dcec_persistent_observation_sphinx_final_manifest.json"


def load_base():
    spec = importlib.util.spec_from_file_location("dcec_generalization_final", BASE)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load audited CLAW-SWE launch path")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def execute() -> dict:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    base = load_base()
    base.MANIFEST = MANIFEST
    base.TASK_AGENT_PROFILE = manifest["task_agent"]["profile"]
    base.DCEC_ENV["GA_LLM_CONFIG_NAME"] = base.TASK_AGENT_PROFILE
    base.RUN_ID = manifest["run_id"]
    base.INSTANCE_ID = "sphinx-doc__sphinx-8551"
    base.CAMPAIGN_ROOT = ROOT / manifest["campaign_root"]
    base.M3_ROOT = base.CAMPAIGN_ROOT / "claw_swe"
    base.LOCKS = base.CAMPAIGN_ROOT / "claw_swe_method_locks.jsonl"
    base.BUNDLE_ROOT = base.CAMPAIGN_ROOT / "isolated_bundles" / base.RUN_ID
    base.RESULT_PATH = base.CAMPAIGN_ROOT / "launch_result.json"
    base.GATEWAY_LOG = base.CAMPAIGN_ROOT / "gateway_transport.log"
    base.MECHANISM_COMMIT = manifest["candidate_implementation"]
    base.MECHANISM_HASHES = manifest["mechanism_source_hashes"]
    base.EXPECTED_GA_HASH = manifest["generic_agent_python_source_sha256"]
    base.DCEC_ENV.update({
        "GA_EXPERIMENT_ID": base.RUN_ID,
        "GA_CONDITION_ID": "dcec-persistent-observation-final-targeted",
    })
    base.M3_ROOT.mkdir(parents=True, exist_ok=True)
    return base.execute()


if __name__ == "__main__":
    print(json.dumps(execute(), ensure_ascii=False, indent=2))
