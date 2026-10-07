"""Archive the one incomplete B+J+I trial without invoking native evaluation."""

from __future__ import annotations

import json
from pathlib import Path
import shutil

from method_discovery import uc_path_control_archive as raw
from method_discovery.curator_supervisor_convergence_v0.crs_rhr_rer_fyne_gate_replacement_20261007 import archive_result


ROOT = Path(__file__).resolve().parent
RUN_ID = archive_result.RUN_ID
CAMPAIGN = archive_result.CAMPAIGN
DESTINATION = archive_result.DESTINATION


def main() -> None:
    if DESTINATION.exists():
        raise RuntimeError("Archive destination already exists; refusing overwrite")
    run = CAMPAIGN / "runs" / RUN_ID
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    trials = [path for path in (CAMPAIGN / "jobs" / RUN_ID).iterdir() if path.is_dir()]
    if len(trials) != 1 or manifest.get("run_id") != RUN_ID:
        raise RuntimeError("Run/trial identity mismatch")
    trial = trials[0]
    incomplete = trial / "agent/monitor/completion_incomplete.json"
    if manifest.get("valid") is not False or not incomplete.is_file():
        raise RuntimeError("This archive path is only for an invalid incomplete review")
    if any((trial / "verifier").iterdir()):
        raise RuntimeError("Verifier directory is nonempty; inspect before archiving")

    raw.CAMPAIGN = CAMPAIGN
    raw.RECORDS = DESTINATION.parent
    temporary = DESTINATION.parent / f"01_{RUN_ID}"
    if temporary.exists():
        raise RuntimeError("Temporary archive destination already exists")
    raw.record_one({"run_id": RUN_ID, "position": 1,
                    "condition": "crs_v02_plus_rhr_v0_plus_rer_v0",
                    "task": "fyn-2.2.0-roadmap"})
    temporary.rename(DESTINATION)
    archive_result.build_index()

    copied = json.loads((DESTINATION / "RAW_FILE_MANIFEST.json").read_text(encoding="utf-8"))

    def copy(source: Path, relative: str) -> None:
        if not source.is_file():
            copied["copied"].append({"source": str(source), "archive": relative,
                                     "status": "absent", "reason": "source file unavailable"})
            return
        target = DESTINATION / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        if raw.digest(source) != raw.digest(target):
            raise RuntimeError(f"Copied bytes changed: {relative}")
        copied["copied"].append({"source": str(source), "archive": relative,
                                 "status": "copied", "bytes": target.stat().st_size,
                                 "sha256": raw.digest(target)})

    copy(trial / "exception.txt", "trial/exception.txt")
    copy(trial / "agent/agent_process_return_code.txt", "agent/agent_process_return_code.txt")
    copy(incomplete, "monitor/completion_incomplete.json")
    copy(trial / "agent/monitor/monitor_private/reference.md", "monitor/private/reference.md")
    copy(trial / "agent/monitor/monitor_private/audit/provider_history.json",
         "monitor/audit/provider_history.json")
    copy(CAMPAIGN / "isolated_bundles" / RUN_ID / "isolation_identity.json",
         "identity/isolation_identity.json")
    for source in sorted((trial / "agent/monitor/monitor_private/audit/cfs_deltas").glob("*.json")):
        copy(source, f"monitor/audit/cfs_deltas/{source.name}")
    for source in sorted((CAMPAIGN / "bridge" / RUN_ID / "evidence").glob("*.json")):
        copy(source, f"bridge/evidence/{source.name}")
    for source in sorted((trial / "agent/monitor/monitor_private/audit/live_checkpoints")
                         .glob("checkpoint-*/*.json")):
        copy(source, f"monitor/root_checkpoints/{source.parent.name}/{source.name}")
    for source in sorted((trial / "agent/monitor/monitor_private/audit/commands").glob("*/*")):
        if source.is_file():
            copy(source, f"monitor/commands/{source.parent.name}/{source.name}")

    failure_tar = trial / "agent/failure_workspace/workspace.tar"
    capture = CAMPAIGN / "bridge" / RUN_ID / "evidence/pre_verification_app.tar"
    for source in (failure_tar, capture):
        if source.is_file():
            copied["local_only_large_artifacts"].append({
                "path": str(source), "bytes": source.stat().st_size,
                "sha256": raw.digest(source)})
    raw.write(DESTINATION / "RAW_FILE_MANIFEST.json", copied)

    summary_path = DESTINATION / "MECHANICAL_SUMMARY.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary.update({
        "run_status": "invalid_monitor_review_incomplete",
        "native_evaluator_executed": False,
        "native_result": None,
        "failure_reason": json.loads(incomplete.read_text(encoding="utf-8")),
        "archive_path": str(DESTINATION),
    })
    raw.write(summary_path, summary)
    print(json.dumps({"archive": str(DESTINATION),
                      "status": summary["run_status"],
                      "native_evaluator_executed": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
