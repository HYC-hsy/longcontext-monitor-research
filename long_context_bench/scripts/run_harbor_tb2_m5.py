"""M5 registry, native Harbor smoke, and TB2/TBLite selection workflow."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

from scripts import run_harbor_tb2_m4 as m4
from scripts.build_candidate_registry import _terminal_candidates
TB_ROOT = Path(os.environ.get("TB2_ROOT", r"E:\LongContext\Ref_Benchmark\Terminal-Bench"))
WORK_ROOT = Path(os.environ.get("TB2_M5_WORK_ROOT", ROOT / "output" / "m5_harbor_tb2"))
JOBS_ROOT = WORK_ROOT / "jobs"
RUNS_ROOT = WORK_ROOT / "runs"
OTEL_ROOT = WORK_ROOT / "otel"
SMOKES_ROOT = WORK_ROOT / "smokes"
REGISTRY_PATH = ROOT / "tasks" / "tb2_m5_development.jsonl"
LOCKS_PATH = ROOT / "tasks" / "tb2_m5_locks.jsonl"
OBLIGATIONS_PATH = ROOT / "tasks" / "tb2_m5_obligations.json"
RESULTS_PATH = ROOT / "tasks" / "tb2_m5_smoke_results.jsonl"
SELECTED_PATH = ROOT / "tasks" / "tb2_m5_selected.jsonl"
CORE_PATH = ROOT / "tasks" / "tb2_m5_core.jsonl"
COLLECTOR_PORT = 14320
COLLECTOR_NAME = "m5-otel-collector"
PULL_ATTEMPTS = 2
PULL_TIMEOUT_SEC = 300
TB_COMMIT = m4.TB_COMMIT
TOP_20 = (
    "schemelike-metacircular-eval",
    "sam-cell-seg",
    "feal-differential-cryptanalysis",
    "bn-fit-modify",
    "video-processing",
    "make-doom-for-mips",
    "make-mips-interpreter",
    "model-extraction-relu-logits",
    "adaptive-rejection-sampler",
    "path-tracing",
    "install-windows-3.11",
    "torch-pipeline-parallelism",
    "fix-code-vulnerability",
    "torch-tensor-parallelism",
    "rstan-to-pystan",
    "mcmc-sampling-stan",
    "git-multibranch",
    "portfolio-optimization",
    "modernize-scientific-stack",
    "distribution-search",
)
FORMAL_12 = (
    "schemelike-metacircular-eval",
    "sam-cell-seg",
    "bn-fit-modify",
    "video-processing",
    "make-mips-interpreter",
    "model-extraction-relu-logits",
    "install-windows-3.11",
    "torch-pipeline-parallelism",
    "fix-code-vulnerability",
    "git-multibranch",
    "portfolio-optimization",
    "modernize-scientific-stack",
)
CORE_6 = (
    "schemelike-metacircular-eval",
    "sam-cell-seg",
    "make-mips-interpreter",
    "model-extraction-relu-logits",
    "torch-pipeline-parallelism",
    "portfolio-optimization",
)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def task_config(task_id: str) -> dict[str, Any]:
    return tomllib.loads((TB_ROOT / task_id / "task.toml").read_text(encoding="utf-8"))


def task_tree_sha256(task_id: str) -> str:
    return m4.tree_hash(TB_ROOT / task_id)


def configure_m4_paths() -> None:
    m4.WORK_ROOT = WORK_ROOT
    m4.JOBS_ROOT = JOBS_ROOT
    m4.RUNS_ROOT = RUNS_ROOT
    m4.OTEL_ROOT = OTEL_ROOT
    m4.COLLECTOR_NAME = COLLECTOR_NAME
    m4.COLLECTOR_PORT = COLLECTOR_PORT


def docker(args: list[str], timeout: int = 600) -> subprocess.CompletedProcess[str]:
    return m4.run(["docker", *args], timeout)


def image_identity(task_id: str, *, pull: bool) -> dict[str, Any]:
    image = task_config(task_id)["environment"]["docker_image"]
    inspected = docker(["image", "inspect", image], 60)
    if inspected.returncode and pull:
        pulled = None
        for attempt in range(1, PULL_ATTEMPTS + 1):
            try:
                pulled = docker(["pull", image], PULL_TIMEOUT_SEC)
            except subprocess.TimeoutExpired:
                pulled = subprocess.CompletedProcess(
                    ["docker", "pull", image],
                    124,
                    "",
                    f"pull attempt {attempt} exceeded {PULL_TIMEOUT_SEC}s",
                )
            if pulled.returncode == 0:
                break
            if attempt < PULL_ATTEMPTS:
                time.sleep(attempt * 5)
        assert pulled is not None
        if pulled.returncode:
            raise RuntimeError(f"failed to pull {image}: {pulled.stderr[-2000:]}")
        inspected = docker(["image", "inspect", image], 60)
    if inspected.returncode:
        return {"tag": image, "available": False, "image_id": None, "immutable_ref": None}
    info = json.loads(inspected.stdout)[0]
    repo_digests = sorted(info.get("RepoDigests") or [])
    repository = image.rsplit(":", 1)[0]
    immutable = next((item for item in repo_digests if item.startswith(repository + "@")), None)
    if immutable is None:
        raise RuntimeError(f"image has no matching RepoDigest: {image}")
    return {
        "tag": image,
        "available": True,
        "image_id": info["Id"],
        "immutable_ref": immutable,
        "size_bytes": info.get("Size"),
    }


def configure_task(task_id: str, *, pull: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    configure_m4_paths()
    config = task_config(task_id)
    image = image_identity(task_id, pull=pull)
    if not image["available"]:
        raise RuntimeError(f"task image is not local: {image['tag']}")
    m4.TASK_ID = task_id
    m4.TASK_ROOT = TB_ROOT / task_id
    m4.IMAGE_TAG = image["tag"]
    m4.IMAGE_ID = image["image_id"]
    m4.IMAGE_REF = image["immutable_ref"]
    return config, image


def build_registry() -> list[dict[str, Any]]:
    obligations = json.loads(OBLIGATIONS_PATH.read_text(encoding="utf-8"))
    candidates = _terminal_candidates(TB_ROOT, 20)
    ids = tuple(row["source"]["task_id"] for row in candidates)
    if ids != TOP_20:
        raise RuntimeError(f"top-20 selection drifted: {ids}")
    locks = []
    for row in candidates:
        task_id = row["source"]["task_id"]
        config = task_config(task_id)
        environment = config["environment"]
        local_image = image_identity(task_id, pull=False)
        row["schema_version"] = "tb2-m5-development/1"
        row["status"] = "development_candidate"
        row["execution"].update({
            "ready_for_smoke": local_image["available"],
            "allow_internet": environment.get("allow_internet", False),
            "cpus": environment.get("cpus"),
            "memory_mb": environment.get("memory_mb"),
            "storage_mb": environment.get("storage_mb"),
            "gpus": environment.get("gpus", 0),
            "local_image_identity": local_image,
        })
        row["obligation_design"] = {
            "status": "annotated",
            "minimum_required": 2,
            "obligations": obligations[task_id]["obligations"],
        }
        row["m5_audit"] = {
            "task_form": obligations[task_id]["task_form"],
            "stability_risks": obligations[task_id]["stability_risks"],
            "task_tree_sha256": task_tree_sha256(task_id),
        }
        locks.append({
            "schema_version": "tb2-m5-lock/1",
            "candidate_id": row["candidate_id"],
            "task_id": task_id,
            "terminal_bench_commit": TB_COMMIT,
            "task_tree_sha256": row["m5_audit"]["task_tree_sha256"],
            "image": local_image,
            "agent_timeout_sec": config["agent"]["timeout_sec"],
            "verifier_timeout_sec": config["verifier"]["timeout_sec"],
        })
    write_jsonl(REGISTRY_PATH, candidates)
    write_jsonl(LOCKS_PATH, locks)
    return candidates


def task_preflight(task_id: str, llm_no: int, *, pull: bool) -> dict[str, Any]:
    config, image = configure_task(task_id, pull=pull)
    identity = m4.preflight(llm_no)
    identity["schema_version"] = "harbor-tb2-m5-preflight/1"
    identity["m5"] = {
        "native_agent_timeout_sec": config["agent"]["timeout_sec"],
        "native_verifier_timeout_sec": config["verifier"]["timeout_sec"],
        "image": image,
    }
    return identity


def result_path(mode: str, task_id: str, repetition: int) -> Path:
    return SMOKES_ROOT / mode / f"{task_id}--r{repetition}.json"


def classify_failure(exc: Exception, job_dir: Path | None) -> str:
    details = [str(exc)]
    if job_dir and job_dir.exists():
        for path in job_dir.glob("*/exception.txt"):
            try:
                details.append(path.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                pass
    text = "\n".join(details).lower()
    if "agenttimeouterror" in text or "agent execution timed out" in text:
        return "agent_timeout"
    if "verifiertimeouterror" in text or "verifier execution timed out" in text:
        return "verifier_timeout"
    if "pull" in text or "image" in text or "environment" in text:
        return "environment_failure"
    if "timeout" in text:
        return "timeout"
    if job_dir and list(job_dir.glob("*/result.json")):
        return "agent_or_verifier_failure"
    return "launcher_failure"


def run_one(
    task_id: str,
    mode: str,
    repetition: int,
    llm_no: int,
    max_agent_seconds: int,
    *,
    run_id_override: str | None = None,
    destination_override: Path | None = None,
) -> dict[str, Any]:
    destination = destination_override or result_path(mode, task_id, repetition)
    if destination.exists():
        return json.loads(destination.read_text(encoding="utf-8"))
    run_id = run_id_override or f"m5-{mode}-{task_id}-r{repetition}"
    job_dir = JOBS_ROOT / run_id
    started = now()
    identity = None
    smoke_agent = None
    try:
        identity = task_preflight(task_id, llm_no, pull=True)
        native_agent = int(identity["m5"]["native_agent_timeout_sec"])
        native_verifier = int(identity["m5"]["native_verifier_timeout_sec"])
        smoke_agent = (
            max_agent_seconds
            if os.environ.get("TB2_M5_ALLOW_EXTENDED_AGENT_TIMEOUT") == "1"
            else min(native_agent, max_agent_seconds)
        )
        if mode == "ga":
            job = m4.harbor_job(
                run_id,
                "adapters.harbor_ga_agent:M4GenericAgent",
                identity,
                agent_timeout_sec=smoke_agent,
                launcher_timeout_sec=smoke_agent + native_verifier + 900,
                agent_timeout_multiplier=smoke_agent / native_agent,
            )
            manifest = m4.finalize_ga(run_id, identity)
            reward = manifest["reward"]
            trace = manifest["trace"]
            trial_file = Path(manifest["trial_result"])
            trial = json.loads(trial_file.read_text(encoding="utf-8"))
        else:
            job = m4.harbor_job(
                run_id,
                mode,
                launcher_timeout_sec=native_agent + native_verifier + 900,
            )
            trial_file, trial = m4.trial_result(job)
            reward = trial["verifier_result"]["rewards"]["reward"]
            trace = None
        record = {
            "schema_version": "tb2-m5-smoke/1",
            "candidate_id": f"tb2:{task_id}",
            "task_id": task_id,
            "mode": mode,
            "repetition": repetition,
            "run_id": run_id,
            "started_at": started,
            "finished_at": now(),
            "status": "completed",
            "failure_class": None,
            "reward": reward,
            "exception_info": trial.get("exception_info"),
            "trace": trace,
            "trial_result": str(trial_file.resolve()),
            "smoke_agent_timeout_sec": smoke_agent if mode == "ga" else None,
            "source_identity": identity,
        }
    except Exception as exc:
        record = {
            "schema_version": "tb2-m5-smoke/1",
            "candidate_id": f"tb2:{task_id}",
            "task_id": task_id,
            "mode": mode,
            "repetition": repetition,
            "run_id": run_id,
            "started_at": started,
            "finished_at": now(),
            "status": "failed",
            "failure_class": classify_failure(exc, job_dir),
            "reward": None,
            "error": str(exc),
            "smoke_agent_timeout_sec": smoke_agent if mode == "ga" else None,
            "source_identity": identity,
        }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return record


def refresh_results() -> list[dict[str, Any]]:
    rows = []
    if SMOKES_ROOT.exists():
        for path in sorted(SMOKES_ROOT.glob("*/*.json")):
            row = json.loads(path.read_text(encoding="utf-8"))
            if row.get("status") == "failed":
                job_dir = JOBS_ROOT / row["run_id"]
                row["diagnosed_failure_class"] = classify_failure(
                    RuntimeError(row.get("error", "")), job_dir
                )
            rows.append(row)
    write_jsonl(RESULTS_PATH, rows)
    return rows


def select_candidates() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    registry = {
        row["source"]["task_id"]: row for row in read_jsonl(REGISTRY_PATH)
    }
    results = read_jsonl(RESULTS_PATH)
    selected = []
    for task_id in FORMAL_12:
        row = registry[task_id]
        oracle = [
            item for item in results
            if item["task_id"] == task_id
            and item["mode"] == "oracle"
            and item["status"] == "completed"
            and item["reward"] == 1.0
        ]
        ga = [
            item for item in results
            if item["task_id"] == task_id
            and item["mode"] == "ga"
            and item["status"] == "completed"
            and item.get("trace", {}).get("span_count", 0) >= 10
        ]
        obligations = row["obligation_design"]["obligations"]
        if not oracle or not ga or len(obligations) != 2:
            raise RuntimeError(f"incomplete M5 selection evidence: {task_id}")
        trace = max(ga, key=lambda item: item["trace"]["span_count"])
        chosen = dict(row)
        chosen["status"] = "accepted_source_candidate"
        chosen["horizon_evidence"] = {
            **row["horizon_evidence"],
            "qualification": "pilot_observed",
            "actual_trace": {
                "run_id": trace["run_id"],
                "span_count": trace["trace"]["span_count"],
                "sha256": trace["trace"]["sha256"],
                "reward": trace["reward"],
            },
        }
        chosen["m5_selection"] = {
            "grandfathered": True,
            "selection_basis": "accepted_legacy_m5_source_allocation",
            "oracle_run_id": oracle[-1]["run_id"],
            "oracle_reward": 1.0,
            "ga_run_id": trace["run_id"],
            "ga_reward": trace["reward"],
            "core": task_id in CORE_6,
        }
        selected.append(chosen)
    core = []
    for row in selected:
        if row["source"]["task_id"] in CORE_6:
            item = dict(row)
            item["status"] = "accepted_source_core_candidate"
            core.append(item)
    write_jsonl(SELECTED_PATH, selected)
    write_jsonl(CORE_PATH, core)
    return selected, core


def run_batch(
    mode: str,
    tasks: list[str],
    repetitions: int,
    llm_no: int,
    max_agent_seconds: int,
) -> list[dict[str, Any]]:
    if mode == "ga":
        configure_m4_paths()
        m4.start_collector()
    rows = []
    try:
        for task_id in tasks:
            for repetition in range(1, repetitions + 1):
                row = run_one(task_id, mode, repetition, llm_no, max_agent_seconds)
                rows.append(row)
                print(json.dumps({
                    "task_id": task_id,
                    "mode": mode,
                    "repetition": repetition,
                    "status": row["status"],
                    "reward": row.get("reward"),
                    "failure_class": row.get("failure_class"),
                }), flush=True)
    finally:
        if mode == "ga":
            time.sleep(5)
            m4.stop_collector()
        refresh_results()
    return rows


def parse_tasks(value: str) -> list[str]:
    if value == "all":
        return list(TOP_20)
    tasks = [item.strip() for item in value.split(",") if item.strip()]
    unknown = sorted(set(tasks) - set(TOP_20))
    if unknown:
        raise ValueError(f"tasks are outside M5 registry: {unknown}")
    return tasks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action",
        choices=("build-registry", "oracle", "nop", "ga", "refresh", "select"),
    )
    parser.add_argument("--tasks", default="all")
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--llm-no", type=int, default=0)
    parser.add_argument("--max-agent-seconds", type=int, default=1800)
    args = parser.parse_args()
    if args.action == "build-registry":
        rows = build_registry()
        print(json.dumps({"count": len(rows), "registry": str(REGISTRY_PATH)}))
    elif args.action == "refresh":
        print(json.dumps({"count": len(refresh_results()), "results": str(RESULTS_PATH)}))
    elif args.action == "select":
        refresh_results()
        selected, core = select_candidates()
        print(json.dumps({"selected": len(selected), "core": len(core)}))
    else:
        rows = run_batch(
            args.action,
            parse_tasks(args.tasks),
            args.repetitions,
            args.llm_no,
            args.max_agent_seconds,
        )
        failed = sum(row["status"] != "completed" for row in rows)
        print(json.dumps({"runs": len(rows), "failed": failed}))
        if failed:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
