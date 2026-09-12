"""Prepare, but never execute, one clean Monitor foundation real-task run."""
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
from m3_prepare_real_task_gate import R0_TASKS, execution_harness_hash


def environment(source_hash: str) -> dict[str, str]:
    return {
        "GA_RUN_ISOLATION": "no-network-unix-inference-v1",
        "GA_BASELINE_CONDITION": "original",
        "GA_EXPERIMENT_ID": "clean-monitor-foundation-v1",
        "GA_CONDITION_ID": "clean-monitor",
        "GA_LLM_CONFIG_NAME": "native_claude_cc_vibe",
        "GA_MAX_TURNS": "500",
        "GA_MONITOR_ENABLED": "1",
        "GA_MONITOR_CONFIG": "native_oai_cc_vibe_gpt56_sol_high",
        "GA_MONITOR_EXPECTED_MODEL": "gpt-5.6-sol",
        "GA_PROVIDER_MAX_RETRIES": "8",
        "GA_METHOD_EXPECTED_SOURCE_SHA256": source_hash,
        "GA_EXPERIMENT_HARNESS_SHA256": execution_harness_hash(),
    }


def registered_method_task(task_id: str) -> tuple[dict[str, Any], bytes]:
    registry_bytes = R0_TASKS.read_bytes()
    rows = [json.loads(line) for line in registry_bytes.splitlines() if line.strip()]
    task = next((row for row in rows if row.get("global_task_id") == task_id), None)
    if task is None or task.get("split") != "method_dev":
        raise ValueError("Clean Monitor gate requires a registered method_dev task")
    return task, registry_bytes


def build_manifest(task_id: str, run_suffix="r1", manifest_path: Path | None = None):
    task, registry_bytes = registered_method_task(task_id)
    source, local_id = task["global_task_id"].split(":", 1)
    slug = local_id.replace(":", "-").replace("/", "-").replace("__", "-")
    source_hash = tree_hash(ROOT / "GenericAgent-main")
    run_id = f"clean-monitor-{slug}-{run_suffix}"
    env = environment(source_hash)
    env["BENCHMARK_CAMPAIGN_ROOT"] = str(
        BENCH / "output" / "clean_monitor_real_tasks" / slug
    )
    run = {
        "task_id": task["global_task_id"],
        "task_role": "clean_monitor_foundation_gate",
        "condition": "clean_monitor",
        "run_id": run_id,
        "cwd": str(BENCH),
        "environment": env,
        "argv": [
            sys.executable, "scripts/run_ultralong_m12_proofs.py",
            *(["--experiment-manifest", str(manifest_path.resolve())]
              if manifest_path is not None else []),
            "--source", source, "--task-id", local_id,
            "--run-id", run_id, "--llm-no", "0", "--max-agent-seconds", "10000",
        ],
        "executes_on_prepare": False,
    }
    return {
        "schema_version": "clean-monitor-real-run-manifest/1",
        "status": "prepared_not_executed",
        "candidate": "clean-monitor-foundation",
        "task_registry_sha256": hashlib.sha256(registry_bytes).hexdigest(),
        "generic_agent_source_sha256": source_hash,
        "execution_harness_sha256": execution_harness_hash(),
        "run_count": 1,
        "secrets_included": False,
        "online_native_checker": False,
        "native_evaluation": "post_termination_only",
        "runs": [run],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--run-suffix", default="r1")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = build_manifest(args.task_id, args.run_suffix, args.output)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(args.output), "runs": 1, "status": manifest["status"],
        "generic_agent_source_sha256": manifest["generic_agent_source_sha256"],
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
