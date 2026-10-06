"""Byte integrity and credential boundary for the terminated invalid trial."""

import json
from pathlib import Path
import runpy

from method_discovery import uc_path_control_archive as raw
from method_discovery.curator_supervisor_convergence_v0.crs_v01_fyne_gate_infra_replacement_20261007 import archive_invalid


def check():
    root = archive_invalid.DESTINATION
    manifest = json.loads((root / "RAW_FILE_MANIFEST.json").read_text(encoding="utf-8"))
    verified, absent = 0, []
    for record in manifest["copied"]:
        path = root / record["archive"]
        if record.get("status") != "copied":
            absent.append(record["archive"])
            continue
        if not path.is_file() or path.stat().st_size != record["bytes"]:
            raise RuntimeError("Archive byte-count mismatch: " + record["archive"])
        if raw.digest(path) != record["sha256"]:
            raise RuntimeError("Archive SHA mismatch: " + record["archive"])
        verified += 1
    for record in manifest["local_only_large_artifacts"]:
        path = Path(record["path"])
        if not path.is_file() or path.stat().st_size != record["bytes"]:
            raise RuntimeError("Local-only artifact missing or resized")
        if raw.digest(path) != record["sha256"]:
            raise RuntimeError("Local-only artifact SHA mismatch")
    gateway = json.loads((archive_invalid.CAMPAIGN / "isolated_bundles" /
                          archive_invalid.RUN_ID / "gateway/config.json").read_text(encoding="utf-8"))
    secrets = [value.encode() for route in gateway["models"].values()
               for value in route["headers"].values() if value]
    private = Path(r"E:\crs_fyne_gate_private_20261007")
    monitor_profile = json.loads((private / "monitor_config/models.local.json").read_text(
        encoding="utf-8"))["claude_monitor_opus48"]
    task_profile = runpy.run_path(str(private / "GenericAgent-main/mykey.py"))[
        "native_claude_cc_vibe_opus48"]
    endpoints = [value.encode() for value in (monitor_profile.get("apibase"),
                                               task_profile.get("apibase")) if value]
    for path in root.rglob("*"):
        if path.is_file():
            content = path.read_bytes()
            if any(secret in content for secret in secrets):
                raise RuntimeError("Private gateway credential value in archive")
            if any(endpoint in content for endpoint in endpoints):
                raise RuntimeError("Private upstream endpoint in archive")
    termination = json.loads((root / "TERMINATION.json").read_text(encoding="utf-8"))
    if termination["native_evaluator_executed"] or termination["valid"]:
        raise RuntimeError("Invalid trial incorrectly marked as evaluated/valid")
    if raw.digest(root / termination["exception_path"]) != termination["exception_sha256"]:
        raise RuntimeError("Exception transcript changed")
    return {"schema": "crs-v01-invalid-archive-integrity/1",
            "run_id": archive_invalid.RUN_ID,
            "copied_records_verified": verified,
            "absent_records": sorted(set(absent)),
            "local_only_records_verified": len(manifest["local_only_large_artifacts"]),
            "gateway_credential_scan": "passed",
            "private_endpoint_scan": "passed",
            "trial_valid": False,
            "native_evaluator_executed": False}


if __name__ == "__main__":
    result = check()
    raw.write(archive_invalid.DESTINATION / "ARCHIVE_INTEGRITY.json", result)
    print(json.dumps(result, ensure_ascii=False))
