"""Serial host-only invocation of the five independently authorized b01 slots.

Each slot is launched through the unchanged independent entry in a fresh
interpreter. This file does not implement a task, Monitor, or evaluator loop.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

from method_discovery.uc_r5_b01_freeze import ORDER, OUT, REPO, sha
from method_discovery.uc_r5_execution_entry import load_authorized_slot


CAMPAIGN = Path(r"E:\LongContext\long_context_bench\output\uc_r5_comparison_v1_20261003")
HOST_RECORDS = CAMPAIGN / "b01_host_execution"
EXPECTED_MANIFEST_SHA = "a53755b8bf93f696c32c9706a5c7136a662a2f1f672cc506bf132c655dd38adb"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def receipt_status(run_id: str) -> dict:
    evidence = CAMPAIGN / "bridge" / run_id / "evidence"
    names = ("agent_start_identity", "pre_verification_capture",
             "verification_release", "trial_end_binding", "inference_send_accounting")
    return {name: (evidence / f"{name}.json").exists() for name in names}


def recorded_budget_end(run_id: str) -> bool:
    """Recognize only an explicit terminal AgentTimeoutError, not a low score."""
    manifest = CAMPAIGN / "runs" / run_id / "manifest.json"
    if not manifest.exists():
        return False
    row = json.loads(manifest.read_text(encoding="utf-8"))
    result_path = Path(row.get("trial_result") or "")
    if not result_path.is_file():
        return False
    result = json.loads(result_path.read_text(encoding="utf-8"))
    exception = result.get("exception_info") or {}
    errors = row.get("validation_errors") or []
    return (exception.get("exception_type") == "AgentTimeoutError"
            and not any("model identity" in str(error).lower()
                        or "source mismatch" in str(error).lower()
                        or "checker" in str(error).lower()
                        for error in errors))


def main() -> int:
    manifest = OUT / "RUNNER_MANIFEST.json"
    if sha(manifest) != EXPECTED_MANIFEST_SHA:
        raise RuntimeError("Frozen b01 runner manifest differs before launch")
    # Check all five authorizations and unused roots before the first trial.
    for _, run_id in ORDER:
        slot, _ = load_authorized_slot(run_id, OUT / f"AUTH_{run_id}.json")
        if Path(slot["live_root"]).exists():
            raise RuntimeError(f"Slot live root was already used: {run_id}")
        if any((CAMPAIGN / name / run_id).exists() for name in ("jobs", "runs", "bridge")):
            raise RuntimeError(f"Slot output was already used: {run_id}")
    HOST_RECORDS.mkdir(parents=True, exist_ok=False)
    progress: list[dict] = []
    for condition, run_id in ORDER:
        entry = {"run_id": run_id, "condition_host_only": condition,
                 "started_at": now(), "status": "running"}
        progress.append(entry)
        save(HOST_RECORDS / "progress.json", progress)
        log_path = HOST_RECORDS / f"{run_id}.entry.log"
        print(f"START {run_id} ({condition}) {entry['started_at']}", flush=True)
        with log_path.open("wb") as log:
            completed = subprocess.run(
                [sys.executable, "-m", "method_discovery.uc_r5_b01_bundle_entry",
                 "--run-id", run_id, "--authorization",
                 str((OUT / f"AUTH_{run_id}.json").resolve())],
                cwd=REPO, stdout=log, stderr=subprocess.STDOUT,
            )
        entry["ended_at"] = now()
        entry["entry_exit_code"] = completed.returncode
        entry["entry_log"] = str(log_path)
        entry["receipts_present"] = receipt_status(run_id)
        receipts_ok = all(entry["receipts_present"].values())
        budget_end = completed.returncode != 0 and recorded_budget_end(run_id)
        entry["explicit_agent_timeout"] = budget_end
        entry["status"] = (
            "completed" if completed.returncode == 0 and receipts_ok else
            "completed_budget" if budget_end and receipts_ok else
            "paused_for_infrastructure_review"
        )
        save(HOST_RECORDS / "progress.json", progress)
        print(f"END {run_id} status={entry['status']} exit={completed.returncode}", flush=True)
        if entry["status"] not in {"completed", "completed_budget"}:
            print("BATCH STOP: preserve this slot; no skip or rerun", flush=True)
            return 2
    print("B01 COMPLETE: all five authorized slots executed once", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
