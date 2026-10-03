"""Research-only b01 entry: rotate gateway auth after frozen bundle checks.

The original authorized entry, bridge, runner, transport, profiles, and model
inputs are unchanged. A private, operator-attested replacement credential is
required before any trial construction. No credential value is logged here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from method_discovery import uc_r5_execution_entry as entry
from method_discovery.uc_r5_b01_freeze import ORDER, OUT, sha


RESUME_AUTH = OUT / "RESUME_AUTHORIZATION.json"
PRIVATE_ROOT = Path(r"E:\uc_r5_cmp_private_20261003")
PRIVATE_ENV = "UC_R5_B01_PRIVATE_CREDENTIALS"


def code_hash() -> str:
    data = Path(__file__).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def replacement_from_private(path: Path) -> str:
    resolved = path.resolve(strict=True)
    root = PRIVATE_ROOT.resolve(strict=True)
    if root not in resolved.parents or not resolved.is_file() or resolved.is_symlink():
        raise RuntimeError("Private credential source is not an approved private file")
    data = json.loads(resolved.read_text(encoding="utf-8"))
    if (data.get("schema") != "uc-r5-b01-rotated-credential/1"
            or data.get("prior_credential_revoked") is not True
            or not isinstance(data.get("revocation_receipt_ref"), str)
            or not data["revocation_receipt_ref"]):
        raise RuntimeError("Private rotation attestation is incomplete")
    credentials = data.get("credentials")
    if not isinstance(credentials, dict) or set(credentials) != {"monitor"}:
        raise RuntimeError("Private route credential set differs from authorization")
    value = credentials["monitor"]
    if (not isinstance(value, str) or not value or value != value.strip()
            or "\n" in value or "\r" in value or value.startswith("Bearer ")):
        raise RuntimeError("Private replacement credential has invalid form")
    return "Bearer " + value


def replace_gateway_auth(config_path: Path, replacement: str,
                         allowed: dict[str, str]) -> dict:
    """Replace exact JSON-encoded header values, preserving every other byte."""
    original = config_path.read_bytes()
    config = json.loads(original)
    if set(allowed) != {"monitor"} or allowed["monitor"] != "Authorization":
        raise RuntimeError("Unsupported route/header whitelist")
    models = config.get("models")
    if not isinstance(models, dict) or "monitor" not in models:
        raise RuntimeError("Authorized Monitor route missing from gateway")
    headers = models["monitor"].get("headers")
    if not isinstance(headers, dict) or set(headers) != {"Authorization"}:
        raise RuntimeError("Monitor header shape differs from frozen route")
    old = headers["Authorization"]
    if (not isinstance(old, str) or not old.startswith("Bearer ")
            or replacement == old or not replacement.startswith("Bearer ")):
        raise RuntimeError("Auth replacement is absent, identical, or changes format")
    old_encoded = json.dumps(old).encode("utf-8")
    new_encoded = json.dumps(replacement).encode("utf-8")
    if original.count(old_encoded) != 1:
        raise RuntimeError("Old authorization value is not uniquely localized")
    updated = original.replace(old_encoded, new_encoded, 1)
    expected = json.loads(original)
    expected["models"]["monitor"]["headers"]["Authorization"] = replacement
    if json.loads(updated) != expected or updated.replace(new_encoded, old_encoded, 1) != original:
        raise RuntimeError("Gateway change exceeds the authorized auth value")
    config_path.write_bytes(updated)
    if config_path.read_bytes() != updated:
        raise RuntimeError("Gateway auth write did not persist")
    return {
        "route": "monitor", "header": "Authorization",
        "before_config_sha256": hashlib.sha256(original).hexdigest(),
        "after_config_sha256": hashlib.sha256(updated).hexdigest(),
        "changed_field_count": 1,
        "other_config_bytes_unchanged": True,
    }


def authorized_overlay(original_overlay, replacement: str,
                       allowed: dict[str, str]):
    def overlay(*args, **kwargs):
        frozen_builder = original_overlay(*args, **kwargs)
        bridge_spec_path = Path(args[4]) if len(args) > 4 else Path(kwargs["bridge_spec_path"])

        def build(*build_args, **build_kwargs):
            # Original build performs frozen bundle/profile/snapshot checks first.
            source, compose = frozen_builder(*build_args, **build_kwargs)
            config_path = compose.parent / "gateway" / "config.json"
            receipt = replace_gateway_auth(config_path, replacement, allowed)
            spec = json.loads(bridge_spec_path.read_text(encoding="utf-8"))
            archive = Path(spec["archive_dir"])
            archive.mkdir(parents=True, exist_ok=True)
            receipt.update({"run_id": spec["slot"]["run_id"],
                            "generated_gateway_config": str(config_path),
                            "generated_bundle_source_sha256": spec["generated_bundle_source_sha256"],
                            "generated_monitor_profile_sha256": spec["generated_monitor_profile_sha256"]})
            entry.save_json(archive / "auth_replacement_receipt.json", receipt)
            return source, compose

        return build
    return overlay


def launch(run_id: str, authorization_path: Path) -> dict:
    auth = json.loads(RESUME_AUTH.read_text(encoding="utf-8"))
    allowed_ids = [item for _, item in ORDER]
    if (auth.get("execution_authorized") is not True
            or auth.get("scope") != "b01"
            or auth.get("run_order") != allowed_ids
            or auth.get("helper_source_sha256") != code_hash()
            or auth.get("runner_manifest_sha256") != sha(OUT / "RUNNER_MANIFEST.json")
            or auth.get("credential_source_env") != PRIVATE_ENV
            or auth.get("allowed_route_headers") != {"monitor": "Authorization"}
            or auth.get("original_authorization_sha256", {}).get(run_id) != sha(authorization_path)):
        raise RuntimeError("Resume authorization identity mismatch")
    slot, _ = entry.load_authorized_slot(run_id, authorization_path)
    if slot["condition"] not in {condition for condition, rid in ORDER if rid == run_id}:
        raise RuntimeError("Resume slot condition mismatch")
    private_path = os.environ.get(PRIVATE_ENV)
    if not private_path:
        raise RuntimeError("Private rotated credential source is unavailable")
    replacement = replacement_from_private(Path(private_path))
    original_overlay = entry.overlay_bundle
    entry.overlay_bundle = authorized_overlay(original_overlay, replacement,
                                              auth["allowed_route_headers"])
    try:
        return entry.launch(run_id, authorization_path)
    finally:
        entry.overlay_bundle = original_overlay


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--authorization", type=Path, required=True)
    args = parser.parse_args()
    result = launch(args.run_id, args.authorization)
    print(json.dumps(result, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
