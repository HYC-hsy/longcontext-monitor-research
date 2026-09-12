from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "prepare_harbor_lhtb_structured_pass_m12.py"
SPEC = importlib.util.spec_from_file_location(
    "prepare_harbor_lhtb_structured_pass_m12", SCRIPT
)
m12 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m12)


def test_structured_pass_patch_identity_and_dependency():
    m12.validate(m12.DEFAULT_HARBOR_ROOT)
    assert m12.state(m12.DEFAULT_HARBOR_ROOT) in {
        "unapplied", "legacy-applied", "applied"
    }


def test_structured_pass_uses_native_boolean_only():
    source = m12.PATCH.read_text(encoding="utf-8")
    assert "/app/output/verification_result.json" in source
    assert 'payload.get("passed") is True' in source
    assert 'stdout = result.stdout or ""' in source
    assert ">= 0.7" not in source
