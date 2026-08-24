"""Prepare, but never execute, the frozen M1 real-task comparison batch."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "long_context_bench"
PANEL = ROOT / "method_discovery" / "m1_real_tasks" / "panel.json"
DEFAULT_OUTPUT = (
    ROOT / "method_discovery" / "artifacts" / "m1_engineering_20260824"
    / "real_run_manifest.json"
)


def tree_hash(root: Path) -> str:
    """Match the method runner's stable GenericAgent source identity."""
    digest = hashlib.sha256()
    files = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in {".git", "__pycache__", ".pytest_cache"} for part in relative.parts):
            continue
        if "temp" in relative.parts or relative == Path("memory") / "file_access_stats.json":
            continue
        files.append(path)
    for path in sorted(files, key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix().encode()
        data = path.read_bytes()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def common_environment(source_hash: str, condition: str) -> dict[str, str]:
    values = {
        "GA_BASELINE_CONDITION": "original",
        "GA_EXPERIMENT_ID": "m1-persistent-workspace-v1",
        "GA_CONDITION_ID": f"m1-{condition}",
        "GA_LLM_CONFIG_NAME": "native_claude_cc_vibe",
        "GA_MAX_TURNS": "500",
        "GA_M0_MONITOR_ENABLED": "1",
        "GA_M0_MONITOR_CONFIG": "native_oai_cc_vibe_gpt56_sol_high",
        "GA_M0_MONITOR_EXPECTED_MODEL": "gpt-5.6-sol",
        "GA_M0_MAX_INSPECTIONS": "12",
        "GA_M0_RECENT_TRAJECTORY_TURNS": "0",
        "GA_METHOD_EXPECTED_SOURCE_SHA256": source_hash,
    }
    if condition == "treatment":
        values["GA_M1_WORKSPACE_ENABLED"] = "1"
    return values


def run_spec(task: dict[str, Any], condition: str, source_hash: str) -> dict[str, Any]:
    task_id = task["global_task_id"]
    source, local_id = task_id.split(":", 1)
    slug = local_id.replace(":", "-").replace("/", "-").replace("__", "-")
    run_id = f"m1-{condition}-{slug}-r1"
    env = common_environment(source_hash, condition)
    if source == "roadmapbench":
        env["BENCHMARK_CAMPAIGN_ROOT"] = str(
            BENCH / "output" / "m1_real_tasks" / condition / slug
        )
        argv = [
            sys.executable, "scripts/run_ultralong_m12_proofs.py",
            "--source", "roadmapbench", "--task-id", local_id,
            "--run-id", run_id, "--llm-no", "0",
            "--max-agent-seconds", "7200",
        ]
    elif source == "claw_swe":
        env["CLAW_SWE_M3_ROOT"] = str(
            BENCH / "output" / "m1_real_tasks" / condition / slug
        )
        env["CLAW_SWE_M3_LOCKS"] = str(
            ROOT / "method_discovery" / "m1_real_tasks" / "claw_swe_method_locks.jsonl"
        )
        argv = [
            sys.executable, "scripts/run_claw_swe_m3.py", "run",
            "--instance-id", local_id, "--run-id", run_id,
            "--timeout", "7200", "--llm-no", "0",
        ]
    elif source == "tb2":
        env["TB2_M5_WORK_ROOT"] = str(
            BENCH / "output" / "m1_real_tasks" / condition / slug
        )
        argv = [
            sys.executable, "scripts/run_harbor_tb2_m5.py", "ga",
            "--tasks", local_id, "--repetitions", "1", "--llm-no", "0",
            "--max-agent-seconds", "7200",
        ]
    else:
        raise ValueError(f"M1 runner is not prepared for source {source!r}")
    return {
        "task_id": task_id,
        "task_role": task["role"],
        "condition": condition,
        "run_id": run_id,
        "cwd": str(BENCH),
        "environment": env,
        "argv": argv,
        "executes_on_prepare": False,
    }


def build_manifest() -> dict[str, Any]:
    panel = json.loads(PANEL.read_text(encoding="utf-8"))
    if panel.get("schema_version") != "m1-real-task-panel/1":
        raise ValueError("unexpected M1 panel schema")
    tasks = panel.get("tasks", [])
    if (len(tasks) != 4 or len({row["source"] for row in tasks}) < 3
            or any(row.get("split") != "method_dev" for row in tasks)):
        raise ValueError("M1 panel no longer matches its frozen gate")
    source_hash = tree_hash(ROOT / "GenericAgent-main")
    runs = []
    for task in tasks:
        for condition in task["condition_order"]:
            if condition not in {"control", "treatment"}:
                raise ValueError(f"unsupported condition {condition!r}")
            runs.append(run_spec(task, condition, source_hash))
    return {
        "schema_version": "m1-real-run-manifest/1",
        "status": "prepared_not_executed",
        "panel_sha256": hashlib.sha256(PANEL.read_bytes()).hexdigest(),
        "generic_agent_source_sha256": source_hash,
        "run_count": len(runs),
        "secrets_included": False,
        "online_native_checker": False,
        "runs": runs,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    manifest = build_manifest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({
        "output": str(args.output),
        "runs": manifest["run_count"],
        "status": manifest["status"],
        "generic_agent_source_sha256": manifest["generic_agent_source_sha256"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
