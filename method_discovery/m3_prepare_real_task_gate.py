"""Prepare, but never execute, a paired M2-C versus M3-A real-task gate."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

METHOD_DIR = Path(__file__).resolve().parent
if str(METHOD_DIR) not in sys.path:
    sys.path.insert(0, str(METHOD_DIR))
from m1_prepare_real_task_batch import ROOT, BENCH, tree_hash


R0_TASKS = ROOT / "method_discovery" / "r0_real_tasks" / "tasks.jsonl"
CONDITIONS = ("m2c_control", "m3a_human_loop")


def environment(source_hash: str, condition: str) -> dict[str, str]:
    if condition not in CONDITIONS:
        raise ValueError(f"unsupported M3 condition {condition!r}")
    values = {
        "GA_BASELINE_CONDITION": "original",
        "GA_EXPERIMENT_ID": "m3-decision-centered-control-v1",
        "GA_CONDITION_ID": condition.replace("_", "-"),
        "GA_LLM_CONFIG_NAME": "native_claude_cc_vibe",
        "GA_MAX_TURNS": "500",
        "GA_M0_MONITOR_ENABLED": "1",
        "GA_M0_MONITOR_CONFIG": "native_oai_cc_vibe_gpt56_sol_high",
        "GA_M0_MONITOR_EXPECTED_MODEL": "gpt-5.6-sol",
        "GA_M0_MAX_INSPECTIONS": "12",
        "GA_M0_RECENT_TRAJECTORY_TURNS": "0",
        "GA_PROVIDER_MAX_RETRIES": "8",
        "GA_M1_WORKSPACE_ENABLED": "1",
        "GA_M1_ACTIVE_RECONSTRUCTION_ENABLED": "1",
        "GA_M2_SEMANTIC_IMPACT_ENABLED": "1",
        "GA_METHOD_EXPECTED_SOURCE_SHA256": source_hash,
    }
    if condition == "m3a_human_loop":
        values["GA_M3_HUMAN_LOOP_ENABLED"] = "1"
    return values


def _task(task_id: str) -> tuple[dict[str, Any], bytes]:
    registry_bytes = R0_TASKS.read_bytes()
    registry = [json.loads(line) for line in registry_bytes.splitlines() if line.strip()]
    task = next((row for row in registry if row.get("global_task_id") == task_id), None)
    if task is None or task.get("split") != "method_dev":
        raise ValueError("M3 gate requires a registered method_dev task")
    return task, registry_bytes


def run_spec(task: dict[str, Any], condition: str, source_hash: str,
             run_suffix: str = "r1") -> dict[str, Any]:
    source, local_id = task["global_task_id"].split(":", 1)
    slug = local_id.replace(":", "-").replace("/", "-").replace("__", "-")
    run_id = f"m3-{condition}-{slug}-{run_suffix}"
    env = environment(source_hash, condition)
    env["BENCHMARK_CAMPAIGN_ROOT"] = str(
        BENCH / "output" / "m3_real_tasks" / "m3a_first_gate" / condition / slug
    )
    return {
        "task_id": task["global_task_id"],
        "task_role": "m3_common_candidate_gate",
        "condition": condition,
        "run_id": run_id,
        "cwd": str(BENCH),
        "environment": env,
        "argv": [
            sys.executable, "scripts/run_ultralong_m12_proofs.py",
            "--source", source, "--task-id", local_id,
            "--run-id", run_id, "--llm-no", "0", "--max-agent-seconds", "10000",
        ],
        "executes_on_prepare": False,
    }


def build_manifest(task_id: str, run_suffix: str = "r1",
                   conditions: tuple[str, ...] = CONDITIONS) -> dict[str, Any]:
    if not conditions or any(condition not in CONDITIONS for condition in conditions):
        raise ValueError("conditions must be a non-empty subset of registered M3 conditions")
    task, registry_bytes = _task(task_id)
    source_hash = tree_hash(ROOT / "GenericAgent-main")
    runs = [run_spec(task, condition, source_hash, run_suffix)
            for condition in conditions]
    return {
        "schema_version": "m3-real-run-manifest/1",
        "status": "prepared_not_executed",
        "candidate": "+".join(conditions),
        "intended_difference": (
            "only GA_M3_HUMAN_LOOP_ENABLED differs between paired conditions"
            if len(conditions) == 2 else "single preregistered condition"
        ),
        "task_registry_sha256": hashlib.sha256(registry_bytes).hexdigest(),
        "generic_agent_source_sha256": source_hash,
        "run_count": len(runs),
        "secrets_included": False,
        "online_native_checker": False,
        "native_evaluation": "post_termination_only",
        "runs": runs,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--run-suffix", default="r1")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--condition", action="append", choices=CONDITIONS)
    args = parser.parse_args()
    manifest = build_manifest(
        args.task_id, args.run_suffix, tuple(args.condition or CONDITIONS)
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({
        "output": str(args.output), "runs": manifest["run_count"],
        "status": manifest["status"],
        "generic_agent_source_sha256": manifest["generic_agent_source_sha256"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
