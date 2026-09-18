"""Prepare a fresh Fyne pair: existing Supervisor with C disabled/enabled.

This only writes a frozen manifest. It never starts a task.
"""
from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "method_discovery/artifacts/claude_monitor_20260913/fyne_independent_r1_manifest.json"
GA = ROOT / "GenericAgent-main"
from m1_prepare_real_task_batch import tree_hash
sys.path.insert(0, str(ROOT / "long_context_bench"))
from scripts.run_ultralong_m12_proofs import execution_harness_hash


def build(output: Path, suffix: str) -> dict:
    template = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    source_hash = tree_hash(GA)
    runs = []
    for enabled, label in (("0", "c_off"), ("1", "c_on")):
        row = deepcopy(template["runs"][0])
        row["run_id"] = f"independent-c-fyne-2.2.0-roadmap-{label}-{suffix}"
        row["condition"] = f"independent_c_{label}"
        env = dict(row["environment"])
        env.update({
            "GA_EXPERIMENT_ID": "independent-c-online-fyne-v1",
            "GA_CONDITION_ID": f"independent-c-{label}",
            "GA_METHOD_EXPECTED_SOURCE_SHA256": source_hash,
            "GA_EXPERIMENT_HARNESS_SHA256": execution_harness_hash(),
            "GA_MONITOR_INDEPENDENT_C": enabled,
            "GA_MONITOR_INDEPENDENT_C_TOTAL_REQUESTS": "6",
            "GA_MONITOR_INDEPENDENT_C_MAX_REQUESTS": "3",
            "BENCHMARK_CAMPAIGN_ROOT": str(
                ROOT / "long_context_bench/output/independent_c_online_20260919" / label
            ),
        })
        row["environment"] = env
        row["task_role"] = "existing_supervisor_optional_c"
        row["argv"] = [
            "D:\\python\\envs\\ga_bench\\python.exe",
            "scripts/run_ultralong_m12_proofs.py",
            "--experiment-manifest", str(output.resolve()),
            "--source", "roadmapbench", "--task-id", "fyn-2.2.0-roadmap",
            "--run-id", row["run_id"], "--llm-no", "0",
            "--max-agent-seconds", "10000",
        ]
        runs.append(row)
    result = {
        "schema_version": "independent-c-online-fyne-pair/1",
        "status": "prepared_not_executed",
        "secrets_included": False,
        "online_native_checker": False,
        "native_evaluation": "post_termination_only",
        "intended_difference": "GA_MONITOR_INDEPENDENT_C only",
        "generic_agent_source_sha256": source_hash,
        "execution_harness_sha256": execution_harness_hash(),
        "runs": runs,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--suffix", default="r1")
    args = parser.parse_args()
    data = build(args.output, args.suffix)
    print(json.dumps({"output": str(args.output), "runs": [r["run_id"] for r in data["runs"]]}, ensure_ascii=False))
