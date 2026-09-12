from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "prepare_harbor_lhtb_m12.py"
SPEC = importlib.util.spec_from_file_location("prepare_harbor_lhtb_m12", SCRIPT)
m12 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m12)


def result(returncode=0, stdout="", stderr=""):
    return SimpleNamespace(
        returncode=returncode, stdout=stdout, stderr=stderr
    )


def test_patch_identity_is_fixed():
    assert m12.PATCH.is_file()
    m12.validate_identity(m12.DEFAULT_HARBOR_ROOT)


def test_patch_state_distinguishes_unapplied(monkeypatch, tmp_path):
    calls = iter([result(0), result(1, stderr="not reversed")])
    monkeypatch.setattr(m12, "run_git", lambda *_args: next(calls))
    assert m12.patch_state(tmp_path) == "unapplied"


def test_patch_state_rejects_diverged_source(monkeypatch, tmp_path):
    calls = iter([result(1, stderr="forward"), result(1, stderr="reverse")])
    monkeypatch.setattr(m12, "run_git", lambda *_args: next(calls))
    with pytest.raises(RuntimeError, match="neither cleanly applicable"):
        m12.patch_state(tmp_path)
