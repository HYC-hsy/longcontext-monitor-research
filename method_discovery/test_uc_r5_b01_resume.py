"""Local fake-credential tests; no provider, Harbor trial, or verifier."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from method_discovery import uc_r5_b01_resume_entry as resume


def gateway() -> dict:
    return {"models": {
        "claude-opus-4-8": {"base": "https://example.invalid", "headers": {
            "Authorization": "Bearer task-test-secret"}, "paths": ["/v1/messages"],
            "model": "claude-opus-4-8", "tls": {"verify": True}},
        "monitor": {"base": "https://example.invalid", "headers": {
            "Authorization": "Bearer monitor-test-secret"}, "paths": ["/v1/messages"],
            "model": "claude-opus-4-8", "tls": {"verify": True}},
    }, "telemetry": "http://example.invalid/trace"}


def test_only_monitor_auth_bytes_change(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    original = json.dumps(gateway()).encode()
    path.write_bytes(original)
    receipt = resume.replace_gateway_auth(path, "Bearer replacement-test-secret",
                                          {"monitor": "Authorization"})
    updated = path.read_bytes()
    assert updated.replace(b"Bearer replacement-test-secret",
                           b"Bearer monitor-test-secret") == original
    assert json.loads(updated)["models"]["claude-opus-4-8"] == gateway()["models"]["claude-opus-4-8"]
    assert receipt["other_config_bytes_unchanged"] is True
    assert receipt["changed_field_count"] == 1
    assert "secret" not in json.dumps(receipt)


@pytest.mark.parametrize("change", ["missing_route", "wrong_header", "same_secret", "extra_header"])
def test_unauthorized_or_missing_target_fails(tmp_path: Path, change: str) -> None:
    value = gateway()
    allowed = {"monitor": "Authorization"}
    replacement = "Bearer replacement-test-secret"
    if change == "missing_route":
        del value["models"]["monitor"]
    elif change == "wrong_header":
        allowed = {"monitor": "x-api-key"}
    elif change == "same_secret":
        replacement = "Bearer monitor-test-secret"
    elif change == "extra_header":
        value["models"]["monitor"]["headers"]["x-extra"] = "test"
    path = tmp_path / "config.json"
    raw = json.dumps(value).encode()
    path.write_bytes(raw)
    with pytest.raises(RuntimeError):
        resume.replace_gateway_auth(path, replacement, allowed)
    assert path.read_bytes() == raw


def test_builder_checks_then_auth_replacement_before_return(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    gateway_dir = bundle / "gateway"
    gateway_dir.mkdir(parents=True)
    config = gateway_dir / "config.json"
    config.write_text(json.dumps(gateway()), encoding="utf-8")
    compose = bundle / "compose.json"
    compose.write_text("{}", encoding="utf-8")
    spec = tmp_path / "bridge_spec.private.json"
    evidence = tmp_path / "evidence"
    spec.write_text(json.dumps({"archive_dir": str(evidence),
                                "slot": {"run_id": "opaque-test"},
                                "generated_bundle_source_sha256": "source-hash",
                                "generated_monitor_profile_sha256": "profile-hash"}), encoding="utf-8")
    calls = []

    def original_overlay(*args, **kwargs):
        calls.append("original_overlay")

        def build(*build_args, **build_kwargs):
            calls.append("frozen_build_checks")
            assert json.loads(config.read_text())["models"]["monitor"]["headers"]["Authorization"] == "Bearer monitor-test-secret"
            return bundle / "source", compose
        return build

    wrapped = resume.authorized_overlay(original_overlay,
                                        "Bearer replacement-test-secret",
                                        {"monitor": "Authorization"})
    build = wrapped(object(), object(), object(), {"run_id": "opaque-test"}, spec)
    assert calls == ["original_overlay"]
    build()
    assert calls == ["original_overlay", "frozen_build_checks"]
    receipt = json.loads((evidence / "auth_replacement_receipt.json").read_text())
    assert receipt["run_id"] == "opaque-test"
    assert receipt["generated_bundle_source_sha256"] == "source-hash"
    assert json.loads(config.read_text())["models"]["monitor"]["headers"]["Authorization"] == "Bearer replacement-test-secret"


def test_private_rotation_attestation_required(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(resume, "PRIVATE_ROOT", tmp_path)
    path = tmp_path / "private.json"
    path.write_text(json.dumps({"schema": "uc-r5-b01-rotated-credential/1",
                                "prior_credential_revoked": False,
                                "revocation_receipt_ref": "operator-ref",
                                "credentials": {"monitor": "replacement-test-secret"}}), encoding="utf-8")
    with pytest.raises(RuntimeError):
        resume.replacement_from_private(path)
    data = json.loads(path.read_text())
    data["prior_credential_revoked"] = True
    path.write_text(json.dumps(data), encoding="utf-8")
    assert resume.replacement_from_private(path) == "Bearer replacement-test-secret"


def test_missing_private_source_stops_before_original_entry(monkeypatch) -> None:
    invoked = []
    monkeypatch.delenv(resume.PRIVATE_ENV, raising=False)
    monkeypatch.setattr(resume.entry, "launch", lambda *args: invoked.append(args))
    with pytest.raises(RuntimeError, match="Private rotated credential source is unavailable"):
        resume.launch("25f65dbd77c41d3a039c91f5",
                      resume.OUT / "AUTH_25f65dbd77c41d3a039c91f5.json")
    assert invoked == []
