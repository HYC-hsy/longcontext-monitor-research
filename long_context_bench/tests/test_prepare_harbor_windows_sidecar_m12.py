from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "prepare_harbor_windows_sidecar_m12.py"
SPEC = importlib.util.spec_from_file_location(
    "prepare_harbor_windows_sidecar_m12", SCRIPT
)
m12 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m12)


def test_sidecar_patch_identity_and_runtime_state():
    m12.validate(m12.DEFAULT_HARBOR_ROOT)
    assert m12.state(m12.DEFAULT_HARBOR_ROOT) in {"unapplied", "applied"}


def test_sidecar_patch_normalizes_both_executable_scripts():
    source = m12.PATCH.read_text(encoding="utf-8")
    assert "/opt/egress-sidecar/entrypoint.sh" in source
    assert "/usr/local/bin/network-policy" in source
    assert "sed -i 's/\\r$//'" in source
