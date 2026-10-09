"""Generate research-side request/visibility inventories; zero provider calls."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile

from .adapter import HERE, ORDER, LIMITS, COMMON_NOTE, materialize, request, request_checks, save_json
from method_discovery.curator_supervisor_convergence_v0.diagnostic_flex_preflight_v0_20261009 import freeze_inputs


FROZEN = {"B_SYSTEM.txt": "b0f2cf6982cefc5ef1c4a556104a511453dde02fc550e986719f460177cfdaee",
          "F_SYSTEM.txt": "18c73247e6485097e3d31424c3ffd1c34c3c137a9c26bdd83b22b4f3e20d77b1",
          "PROMPT_DIFF.patch": "af0201a38c07bfc76a8ca75cd373604e571d2c5e33d7cd967bf297a769e02bdf"}


def run() -> None:
    for name, expected in FROZEN.items():
        actual = hashlib.sha256((freeze_inputs.HERE / name).read_bytes()).hexdigest()
        if actual != expected:
            raise RuntimeError(f"Frozen stage-0 material changed: {name}")
    comparisons = {}
    for scene in ("C01", "C02"):
        comparisons[scene] = request_checks(scene)
        for arm in ("B", "F"):
            save_json(HERE / f"{scene}_{arm}_STATIC_REQUEST.json", request(scene, arm))
    with tempfile.TemporaryDirectory(prefix="static-diagnostic-freeze-") as temporary:
        for scene in ("C01", "C02"):
            manifest = materialize(scene, Path(temporary) / scene)
            save_json(HERE / f"{scene}_VISIBILITY_MANIFEST.json", manifest)
    save_json(HERE / "REQUEST_COMPARISON.json", comparisons)
    save_json(HERE / "RUN_ORDER_AND_LIMITS.json", {
        "status": "offline_only_no_live_entry",
        "order": [{"scene": scene, "repeat": repeat, "first": first, "second": second}
                  for scene, repeat, first, second in ORDER],
        "total_attempts": 12,
        "limits_per_attempt": LIMITS,
        "same_environment_note": COMMON_NOTE,
        "accepted_wrong_judgment": "retain as method outcome, not infrastructure invalid",
        "budget_exhausted_without_control": "retain complete trace as undecided, never relabel wait",
        "no_model_visible_countdown": True,
        "isolation_certified": False,
        "live_provider_entry": "NoLiveProvider always raises"
    })


if __name__ == "__main__":
    run()
