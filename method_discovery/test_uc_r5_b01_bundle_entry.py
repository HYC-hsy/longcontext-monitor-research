"""Offline bundle-byte reconciliation tests; no Docker or model request."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from method_discovery import uc_r5_b01_bundle_entry as compat


CURRENT = Path(__file__).resolve().parent.parent / "long_context_bench/adapters/isolated_transport.py"
STAGED = Path(r"E:\uc_r5_cmp_private_20261003\bundle_RP\source\isolated_transport.py")


def fixture(tmp_path: Path):
    source = tmp_path / "generated" / "source"
    source.mkdir(parents=True)
    (source / "isolated_transport.py").write_bytes(CURRENT.read_bytes())
    (source / "unchanged.py").write_bytes(b"answer = 1\n")
    staged = tmp_path / "staged"
    staged.mkdir()
    (staged / "isolated_transport.py").write_bytes(STAGED.read_bytes())
    compose = source.parent / "compose.json"
    compose.write_text("{}", encoding="utf-8")
    identity = {"snapshot_sha256": compat.digest_tree(source), "profile": "test"}
    (compose.parent / "isolation_identity.json").write_text(json.dumps(identity), encoding="utf-8")
    expected = tmp_path / "expected"
    expected.mkdir()
    (expected / "isolated_transport.py").write_bytes(STAGED.read_bytes())
    (expected / "unchanged.py").write_bytes(b"answer = 1\n")
    slot = {"run_id": "opaque-test", "deployment": {
        "bundle_source": str(staged),
        "bundle_snapshot_sha256": compat.digest_tree(expected),
    }}
    return source, compose, slot


def test_exact_staged_bytes_restore_frozen_bundle_identity(tmp_path: Path) -> None:
    source, compose, slot = fixture(tmp_path)
    before_other = (source / "unchanged.py").read_bytes()
    receipt = compat.reconcile(source, compose, slot)
    assert receipt["after_bundle_sha256"] == slot["deployment"]["bundle_snapshot_sha256"]
    assert (source / "isolated_transport.py").read_bytes() == STAGED.read_bytes()
    assert (source / "unchanged.py").read_bytes() == before_other
    assert json.loads((compose.parent / "isolation_identity.json").read_text())["snapshot_sha256"] == compat.digest_tree(source)
    assert receipt["other_source_files_changed"] == 0


def test_non_newline_or_other_source_change_still_fails(tmp_path: Path) -> None:
    source, compose, slot = fixture(tmp_path)
    (source / "unchanged.py").write_bytes(b"answer = 2\n")
    identity_path = compose.parent / "isolation_identity.json"
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    identity["snapshot_sha256"] = compat.digest_tree(source)
    identity_path.write_text(json.dumps(identity), encoding="utf-8")
    with pytest.raises(RuntimeError, match="still differs"):
        compat.reconcile(source, compose, slot)


def test_unexpected_transport_bytes_fail_before_gate(tmp_path: Path) -> None:
    source, compose, slot = fixture(tmp_path)
    (source / "isolated_transport.py").write_bytes(b"different code\n")
    with pytest.raises(RuntimeError, match="not the preregistered"):
        compat.reconcile(source, compose, slot)


def test_original_overlay_gate_is_still_invoked(tmp_path: Path) -> None:
    source, compose, slot = fixture(tmp_path)
    spec = tmp_path / "bridge_spec.json"
    archive = tmp_path / "evidence"
    spec.write_text(json.dumps({"archive_dir": str(archive)}), encoding="utf-8")
    events = []

    def original_builder(*args, **kwargs):
        events.append("original_build")
        return source, compose

    def original_overlay(builder, *args):
        def build(*build_args, **build_kwargs):
            result = builder(*build_args, **build_kwargs)
            events.append("original_identity_gate")
            assert compat.digest_tree(result[0]) == slot["deployment"]["bundle_snapshot_sha256"]
            return result
        return build

    overlay = compat.scoped_overlay(original_overlay, slot)
    build = overlay(original_builder, None, None, slot, spec)
    build()
    assert events == ["original_build", "original_identity_gate"]
    assert json.loads((archive / "bundle_line_ending_receipt.json").read_text())["run_id"] == "opaque-test"
