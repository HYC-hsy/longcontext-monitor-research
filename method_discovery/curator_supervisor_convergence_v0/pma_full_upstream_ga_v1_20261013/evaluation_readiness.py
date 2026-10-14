"""Read-only, zero-model check of future PMA live evaluation prerequisites.

This deliberately never authorizes execution. A fresh live state-preservation
contract and Harbor integration test are required before native evaluation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tomllib

from .export_official_evaluator import COMMIT, official_members


HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "FOUR_RUN_MANIFEST_OFFICIAL_EVALUATOR_V2_DRAFT.json"
BENCH_ADAPTER_SHA = "8a4513c6b28befe747d581d22e94cd2715f20234c63115e0ea424a56d033c3a0"


def check(source_git: Path, harbor_python: Path, bench_root: Path) -> dict:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    result = {"schema": "pma-live-evaluation-readiness-v1", "ready": False,
              "model_calls": 0, "native_evaluator_calls": 0,
              "manifest_sha256": hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
              "official_commit": COMMIT, "tasks": {}, "blockers": []}
    host = subprocess.run([str(harbor_python.resolve(strict=True)), "-c",
        "import harbor,importlib.metadata; "
        "print(importlib.metadata.version('harbor')); print(harbor.__file__)"] ,
        capture_output=True, text=True, timeout=30)
    result["harbor"] = {"return_code": host.returncode,
                         "stdout": host.stdout.strip(), "stderr": host.stderr.strip()}
    if host.returncode:
        result["blockers"].append("installed_harbor_unreadable")
    adapter = bench_root.resolve(strict=True) / "adapters" / "harbor_ga_agent.py"
    result["task_adapter_sha256"] = hashlib.sha256(adapter.read_bytes()).hexdigest()
    if result["task_adapter_sha256"] != BENCH_ADAPTER_SHA:
        result["blockers"].append("actual_harbor_adapter_byte_identity_mismatch")
    for task, expected in manifest["assets"].items():
        asset = {"image": expected["repo_digest"]}
        try:
            members = [{k: v for k, v in item.items() if k != "raw"}
                       for item in official_members(source_git.resolve(strict=True), task)]
            asset["official_members_match"] = members == expected["official_evaluator_members"]
            cfg = tomllib.loads((HERE / "assets/public" / task / "task.toml").read_text())
            asset["verifier_environment_mode"] = cfg["verifier"].get("environment_mode", "shared_default")
            image = subprocess.run(["docker", "image", "inspect", expected["repo_digest"],
                                    "--format", "{{.Id}}"], capture_output=True,
                                   text=True, timeout=30)
            asset["image_id_match"] = image.returncode == 0 and image.stdout.strip() == expected["image_id"]
        except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
            asset["error"] = type(exc).__name__ + ":" + str(exc)
        result["tasks"][task] = asset
        if not asset.get("official_members_match") or not asset.get("image_id_match"):
            result["blockers"].append(task + ":asset_or_image_identity")
        if asset.get("verifier_environment_mode") == "shared_default":
            result["blockers"].append(task + ":shared_verifier_inherits_task_isolation")
    result["blockers"].append("full_task_writable_layer_and_mount_state_transition_uncertified")
    result["blockers"].append("container_tests_readback_and_synthetic_harbor_evaluation_uncertified")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-git", type=Path, required=True)
    parser.add_argument("--harbor-python", type=Path, required=True)
    parser.add_argument("--bench-root", type=Path, required=True)
    args = parser.parse_args()
    result = check(args.source_git, args.harbor_python, args.bench_root)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["ready"] else 2)


if __name__ == "__main__":
    main()
