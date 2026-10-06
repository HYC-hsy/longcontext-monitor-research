"""Offline byte-integrity and secret-boundary check for the one completed run."""

from __future__ import annotations

import json
from pathlib import Path

from method_discovery import uc_path_control_archive as raw
from method_discovery.curator_supervisor_convergence_v0.crs_v01_fyne_gate_infra_replacement_20261007 import archive_result as archive


def check() -> dict:
    root = archive.DESTINATION
    manifest = json.loads((root / "RAW_FILE_MANIFEST.json").read_text(encoding="utf-8"))
    copied = 0
    absent = []
    for record in manifest["copied"]:
        if record.get("status") != "copied":
            absent.append(record["archive"])
            continue
        path = root / record["archive"]
        if not path.is_file() or path.stat().st_size != record["bytes"]:
            raise RuntimeError(f"Archived source size/presence mismatch: {record['archive']}")
        if raw.digest(path) != record["sha256"]:
            raise RuntimeError(f"Archived source SHA mismatch: {record['archive']}")
        copied += 1
    for record in manifest["local_only_large_artifacts"]:
        path = Path(record["path"])
        if not path.is_file() or path.stat().st_size != record["bytes"]:
            raise RuntimeError("Local-only terminal capture missing or resized")
        if raw.digest(path) != record["sha256"]:
            raise RuntimeError("Local-only terminal capture SHA mismatch")
    final = json.loads((root / "task_final/MANIFEST.json").read_text(encoding="utf-8"))
    if raw.digest(Path(final["source_capture"])) != final["source_capture_sha256"]:
        raise RuntimeError("Final workspace capture SHA mismatch")
    for record in final["files"]:
        path = root / "task_final" / record["path"]
        if not path.is_file() or path.stat().st_size != record["bytes"]:
            raise RuntimeError(f"Final task artifact missing or resized: {record['path']}")
        if raw.digest(path) != record["sha256"]:
            raise RuntimeError(f"Final task artifact SHA mismatch: {record['path']}")
    gateway_config = archive.CAMPAIGN / "isolated_bundles" / archive.RUN_ID / "gateway/config.json"
    gateway = json.loads(gateway_config.read_text(encoding="utf-8"))
    secrets = [value.encode() for route in gateway["models"].values()
               for value in route["headers"].values() if value]
    for path in root.rglob("*"):
        if path.is_file() and any(secret in path.read_bytes() for secret in secrets):
            raise RuntimeError("Private credential found in archive")
    result = {
        "schema": "crs-v01-fyne-archive-integrity/1",
        "run_id": archive.RUN_ID,
        "copied_source_records_verified": copied,
        "absent_source_records": sorted(set(absent)),
        "local_only_capture_records_verified": len(manifest["local_only_large_artifacts"]),
        "final_task_files_verified": len(final["files"]),
        "gateway_credential_scan": "passed_no_matching_private_header_value",
        "trial_end_binding_present": (root / "bridge/evidence/trial_end_binding.json").is_file(),
        "pre_verifier_capture_sha256": final["source_capture_sha256"],
        "measurement_trace_index_sha256": raw.digest(root / "MEASUREMENT_TRACE_INDEX.json"),
        "crs_trace_index_sha256": raw.digest(root / "CRS_TRACE_INDEX.json"),
    }
    if not result["trial_end_binding_present"]:
        raise RuntimeError("Trial-end binding missing")
    return result


if __name__ == "__main__":
    result = check()
    raw.write(archive.DESTINATION / "ARCHIVE_INTEGRITY.json", result)
    print(json.dumps(result, ensure_ascii=False))
