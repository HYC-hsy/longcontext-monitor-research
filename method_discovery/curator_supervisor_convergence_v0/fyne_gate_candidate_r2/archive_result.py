"""Mechanical archive of the single completed Fyne replacement run; no model calls."""

from __future__ import annotations

import json
from pathlib import Path
import shutil

from method_discovery import uc_path_control_archive as raw


RUN_ID = "curator-supervisor-fyne-gate-v0-candidate-r2-infra-replacement"
CAMPAIGN = Path(r"E:\LongContext\long_context_bench\output\curator_supervisor_fyne_gate_v0")
ROOT = Path(__file__).resolve().parent
DESTINATION = ROOT / "archive" / RUN_ID


def main() -> None:
    if DESTINATION.exists():
        raise RuntimeError("Archive destination already exists")
    manifest = json.loads((CAMPAIGN / "runs" / RUN_ID / "manifest.json").read_text(encoding="utf-8"))
    if manifest["run_id"] != RUN_ID or not manifest["valid"]:
        raise RuntimeError("Trial identity or validity failure")
    trials = [p for p in (CAMPAIGN / "jobs" / RUN_ID).iterdir() if p.is_dir()]
    if len(trials) != 1:
        raise RuntimeError("Expected exactly one trial")
    trial = trials[0]
    raw.CAMPAIGN = CAMPAIGN
    raw.RECORDS = DESTINATION.parent
    temporary_name = DESTINATION.parent / f"01_{RUN_ID}"
    if temporary_name.exists():
        raise RuntimeError("Base archive destination already exists")
    summary = raw.record_one({"run_id": RUN_ID, "position": 1,
                              "condition": "curator_candidate", "task": "fyn-2.2.0-roadmap"})
    temporary_name.rename(DESTINATION)
    archive_manifest = json.loads((DESTINATION / "RAW_FILE_MANIFEST.json").read_text(encoding="utf-8"))

    def copy(source: Path, relative: str) -> None:
        if not source.is_file():
            archive_manifest["copied"].append({"source": str(source), "archive": relative,
                                                "status": "absent", "reason": "source file unavailable"})
            return
        target = DESTINATION / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        if raw.digest(source) != raw.digest(target):
            raise RuntimeError(f"Copy hash mismatch: {relative}")
        archive_manifest["copied"].append({"source": str(source), "archive": relative,
                                            "status": "copied", "bytes": target.stat().st_size,
                                            "sha256": raw.digest(target)})

    audit = trial / "agent/monitor/monitor_private/audit"
    private = trial / "agent/monitor/monitor_private"
    bridge = CAMPAIGN / "bridge" / RUN_ID
    copy(CAMPAIGN / "isolated_bundles" / RUN_ID / "isolation_identity.json", "identity/isolation_identity.json")
    copy(trial / "agent/monitor/monitor_private/reference.md", "monitor/private/reference.md")
    copy(trial / "agent/monitor/monitor_private/working.md", "monitor/private/working.md")
    copy(trial / "agent/agent_process_return_code.txt", "agent/agent_process_return_code.txt")
    copy(trial / "agent/isolated_transport.log", "agent/isolated_transport.log")
    copy(trial / "agent/monitor/monitor_private/audit/provider_history.json", "monitor/audit/provider_history.json")
    for folder in ("cfs_deltas", "history_transforms", "continuation_responses"):
        for source in sorted((audit / folder).glob("*.json*")):
            copy(source, f"monitor/audit/{folder}/{source.name}")
    for source in sorted((bridge / "evidence").glob("*")):
        if source.is_file() and source.suffix not in (".tar", ".zip"):
            copy(source, f"bridge/evidence/{source.name}")
    for source in sorted((trial / "artifacts").glob("*")):
        if source.is_file():
            copy(source, f"trial/artifacts/{source.name}")
    for source in sorted((trial / "verifier").glob("*")):
        if source.is_file():
            copy(source, f"verifier/{source.name}")
    for source in sorted((trial / "agent/monitor/monitor_private/audit/live_checkpoints").glob("checkpoint-*/*.json")):
        copy(source, f"monitor/root_checkpoints/{source.parent.name}/{source.name}")
    for source in sorted((bridge / "evidence").glob("*.tar")):
        archive_manifest["local_only_large_artifacts"].append({
            "path": str(source), "bytes": source.stat().st_size, "sha256": raw.digest(source)})
    raw.write(DESTINATION / "RAW_FILE_MANIFEST.json", archive_manifest)
    summary["archive_path"] = str(DESTINATION)
    summary["isolation_snapshot_sha256"] = manifest["source_identity"]["isolation"]["snapshot_sha256"]
    summary["native_result"] = manifest["rewards"]
    summary["archive_integrity"] = "copied hashes verified; local-only large artifact hashes recorded"
    raw.write(DESTINATION / "MECHANICAL_SUMMARY.json", summary)
    print(json.dumps({"archive": str(DESTINATION), "summary": summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()
