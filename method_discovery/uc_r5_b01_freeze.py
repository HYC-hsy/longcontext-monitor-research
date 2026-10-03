"""One-time, zero-model materialization of the authorized b01 runner inputs.

This does not launch a trial. The frozen 30-slot allocation remains the source
of run identities and private deployment roots.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
READINESS = REPO / "method_discovery/runs/uc_r5_cmp_readiness_20261003"
CAMPAIGN = REPO / "method_discovery/runs/uc_r5_comparison_v1_20261003"
OUT = CAMPAIGN / "execution_b01"
ORDER = [
    ("RP", "25f65dbd77c41d3a039c91f5"),
    ("C0", "4c6f3cc92c004853597a6191"),
    ("RB", "a0a6731649989ee253e68d52"),
    ("AB", "ea81a096dcf814c01e3f15db"),
    ("AP", "507ea384d720c364131a44cb"),
]
PREREG_SHA = "657ebd27c48f248bc6bcceb66d95e5040fafe1d3f6ff7b972ad8fa1390d52ce0"
CHECKLIST_SHA = "54f9840c6e93bd7fa5584f13cabea0eadd3488ed79e70492660aa17a7616c40d"
CANDIDATE = "232281d650d062bdc6a6030f40ccb904c1ac0851"
BRIDGE = "3858cd28ca2d25e5a4d6378b6dcd033624b1d54a"
BRIDGE_SOURCE_SHA = "1a9d6431c13bf89b9da6d7f8e09ac73b86ff30395f365f6fe05a7ebd0f2cb06f"
SOURCE_SHA = "21bca97c077317d11467a28405ecd2abdb4aa8a0f3c97b74574626cba5be30c4"
HARNESS_SHA = "1c2256113d5fc8ab43e307a9edf29b16c6defeb1d5f5e69d954784cea1618bd6"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_once(path: Path, obj: object) -> None:
    if path.exists():
        raise RuntimeError(f"Refusing to replace frozen file: {path}")
    path.write_bytes((json.dumps(obj, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))


def main() -> None:
    prereg = CAMPAIGN / "PREREGISTRATION.json"
    checklist_path = CAMPAIGN / "SLOT_EXECUTION_CHECKLIST.json"
    if sha(prereg) != PREREG_SHA or sha(checklist_path) != CHECKLIST_SHA:
        raise RuntimeError("Frozen preregistration/checklist hash mismatch")
    if OUT.exists() and any(OUT.iterdir()):
        raise RuntimeError("b01 execution inputs already exist")
    slots = json.loads(checklist_path.read_text(encoding="utf-8"))["proposed_slots"]
    common = json.loads((READINESS / "ENVIRONMENT_DRAFT.json").read_text(encoding="utf-8"))["common"]
    runs = []
    for position, (condition, run_id) in enumerate(ORDER, 1):
        matches = [s for s in slots if s["run_id"] == run_id]
        if len(matches) != 1:
            raise RuntimeError(f"Slot identity not unique: {run_id}")
        slot = matches[0]
        if (slot["block"], slot["position"], slot["condition"], slot["repetition"],
                slot["task"], slot["candidate_commit"], slot["status"]) != (
                "b01", position, condition, 2, "roadmapbench:ktx-0.13.0-roadmap",
                CANDIDATE, "not_started"):
            raise RuntimeError(f"Frozen slot metadata mismatch: {run_id}")
        env = dict(common)
        env.update({
            "GA_BASELINE_CONDITION": "original",
            "GA_HOST_ROOT": slot["deployment"]["ga_host_root"],
            "BENCHMARK_CAMPAIGN_ROOT": slot["output"]["campaign_root"],
            "GA_METHOD_EXPECTED_SOURCE_SHA256": SOURCE_SHA,
            "GA_EXPERIMENT_HARNESS_SHA256": HARNESS_SHA,
        })
        runs.append({"run_id": run_id, "environment": env})
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = OUT / "RUNNER_MANIFEST.json"
    write_once(manifest, {"secrets_included": False, "runs": runs})
    manifest_sha = sha(manifest)
    for _, run_id in ORDER:
        write_once(OUT / f"AUTH_{run_id}.json", {
            "execution_authorized": True,
            "preregistration_sha256": PREREG_SHA,
            "slot_checklist_sha256": CHECKLIST_SHA,
            "run_id": run_id,
            "candidate_commit": CANDIDATE,
            "bridge_implementation_commit": BRIDGE,
            "bridge_source_sha256": BRIDGE_SOURCE_SHA,
            "task_model": "claude-opus-4-8",
            "runner_manifest": str(manifest.resolve()),
            "runner_manifest_sha256": manifest_sha,
        })
    print(json.dumps({"manifest": str(manifest.resolve()), "sha256": manifest_sha,
                      "runs": [r["run_id"] for r in runs]}, indent=2))


if __name__ == "__main__":
    main()
