"""B01 research-side checkout line-ending reconciliation.

The frozen bundle snapshot was prepared with CRLF isolated_transport.py;
the frozen runner's raw-byte harness hash requires its LF checkout. This
wrapper calls the original authorized entry and restores only the staged
bundle's exact transport-file bytes between the original bundle builder and
the original bridge identity gate. No request, tool, or transport code is
changed, and the original gate still rejects any other bundle difference.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from method_discovery import uc_r5_execution_entry as entry
from method_discovery.uc_r5_b01_freeze import ORDER, OUT, sha


DECISION = OUT / "BUNDLE_COMPAT_DECISION.json"
TRANSPORT_SHA_LF = "0b7c4e010e01339e8e0853061f48f8f1fe9e4c382588d3058d3a0613d5a46e98"
TRANSPORT_SHA_STAGED = "4923dba1a7ecfe44452bd21de25cd8eade53e73f59fae836fabf8290d68e9077"


def source_hash() -> str:
    return hashlib.sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def digest_tree(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode() + b"\0")
            digest.update(path.read_bytes())
    return digest.hexdigest()


def reconcile(source: Path, compose: Path, slot: dict) -> dict:
    """Fail unless exactly the pinned newline-only source difference exists."""
    actual_file = source / "isolated_transport.py"
    staged_file = Path(slot["deployment"]["bundle_source"]) / "isolated_transport.py"
    actual = actual_file.read_bytes()
    staged = staged_file.read_bytes()
    if (hashlib.sha256(actual).hexdigest() != TRANSPORT_SHA_LF
            or hashlib.sha256(staged).hexdigest() != TRANSPORT_SHA_STAGED
            or actual.replace(b"\r\n", b"\n") != staged.replace(b"\r\n", b"\n")):
        raise RuntimeError("Transport bytes are not the preregistered newline-only difference")
    identity_path = compose.parent / "isolation_identity.json"
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    if identity.get("snapshot_sha256") != digest_tree(source):
        raise RuntimeError("Builder snapshot did not match its source before reconciliation")
    before = identity["snapshot_sha256"]
    actual_file.write_bytes(staged)
    after = digest_tree(source)
    if after != slot["deployment"]["bundle_snapshot_sha256"]:
        raise RuntimeError("Reconciled bundle still differs from frozen snapshot")
    identity["snapshot_sha256"] = after
    identity_path.write_text(json.dumps(identity, ensure_ascii=False, indent=2), encoding="utf-8")
    if json.loads(identity_path.read_text(encoding="utf-8"))["snapshot_sha256"] != after:
        raise RuntimeError("Reconciled identity did not persist")
    return {"run_id": slot["run_id"], "relative_path": "isolated_transport.py",
            "before_bundle_sha256": before, "after_bundle_sha256": after,
            "before_file_sha256": TRANSPORT_SHA_LF,
            "after_file_sha256": TRANSPORT_SHA_STAGED,
            "lf_normalized_content_equal": True,
            "other_source_files_changed": 0,
            "original_bridge_identity_gate_retained": True}


def scoped_overlay(original_overlay, slot: dict):
    def overlay(original_build, bridge_script, control_dir, actual_slot, bridge_spec_path):
        if actual_slot["run_id"] != slot["run_id"]:
            raise RuntimeError("Bundle reconciliation crossed slot identity")

        def reconciled_build(*args, **kwargs):
            source, compose = original_build(*args, **kwargs)
            receipt = reconcile(source, compose, slot)
            spec = json.loads(Path(bridge_spec_path).read_text(encoding="utf-8"))
            archive = Path(spec["archive_dir"])
            archive.mkdir(parents=True, exist_ok=True)
            entry.save_json(archive / "bundle_line_ending_receipt.json", receipt)
            return source, compose

        return original_overlay(reconciled_build, bridge_script, control_dir,
                                actual_slot, bridge_spec_path)
    return overlay


def launch(run_id: str, authorization: Path) -> dict:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    allowed = [value for _, value in ORDER]
    if (decision.get("scope") != "b01"
            or decision.get("run_order") != allowed
            or decision.get("helper_source_sha256") != source_hash()
            or decision.get("runner_manifest_sha256") != sha(OUT / "RUNNER_MANIFEST.json")
            or run_id not in allowed):
        raise RuntimeError("Bundle reconciliation authorization mismatch")
    slot, _ = entry.load_authorized_slot(run_id, authorization)
    original_overlay = entry.overlay_bundle
    entry.overlay_bundle = scoped_overlay(original_overlay, slot)
    try:
        return entry.launch(run_id, authorization)
    finally:
        entry.overlay_bundle = original_overlay


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--authorization", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(launch(args.run_id, args.authorization), ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
