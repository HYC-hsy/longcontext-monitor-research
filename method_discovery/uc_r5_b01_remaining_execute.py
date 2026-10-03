"""Serial host-only continuation of the three unused b01 slots."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys

from method_discovery.uc_r5_b01_freeze import OUT, REPO, sha
from method_discovery.uc_r5_b01_execute import (
    CAMPAIGN, EXPECTED_MANIFEST_SHA, receipt_status, recorded_budget_end,
)
from method_discovery.uc_r5_execution_entry import load_authorized_slot


REMAINING = (
    ("RB", "a0a6731649989ee253e68d52"),
    ("AB", "ea81a096dcf814c01e3f15db"),
    ("AP", "507ea384d720c364131a44cb"),
)
HOST_RECORDS = CAMPAIGN / "b01_remaining_host_execution"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save(path: Path, rows: list[dict]) -> None:
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    if sha(OUT / "RUNNER_MANIFEST.json") != EXPECTED_MANIFEST_SHA:
        raise RuntimeError("Frozen b01 runner manifest differs before continuation")
    if HOST_RECORDS.exists():
        raise RuntimeError("Continuation host output was already used")
    for _, run_id in REMAINING:
        slot, _ = load_authorized_slot(run_id, OUT / f"AUTH_REMAINING_{run_id}.json")
        if Path(slot["live_root"]).exists():
            raise RuntimeError(f"Slot live root was already used: {run_id}")
        if any((CAMPAIGN / name / run_id).exists() for name in ("jobs", "runs", "bridge")):
            raise RuntimeError(f"Slot output was already used: {run_id}")
    HOST_RECORDS.mkdir(parents=True, exist_ok=False)
    progress: list[dict] = []
    for condition, run_id in REMAINING:
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
                 str((OUT / f"AUTH_REMAINING_{run_id}.json").resolve())],
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
            print("CONTINUATION STOP: preserve this slot; no skip or rerun", flush=True)
            return 2
    print("B01 REMAINING COMPLETE: three unused slots executed once", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
