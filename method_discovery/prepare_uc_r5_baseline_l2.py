"""Build a private, zero-model C0 baseline bundle from frozen production."""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


BASE = "6c72477fce3350c82baf74a9ca8a96c87742be5b"


def prepare(frozen: Path, historical: Path, private: Path):
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=frozen,
                                   text=True).strip()
    if head != BASE:
        raise ValueError(f"frozen worktree identity mismatch: {head}")
    target = private / "baseline_staged_source"
    bundle = private / "baseline_bundle_C0"
    if target.exists() or bundle.exists():
        raise FileExistsError("baseline private targets already exist")
    shutil.copytree(frozen / "GenericAgent-main", target,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.local.json"))
    shutil.copy2(historical / "GenericAgent-main" / "mykey.py", target / "mykey.py")
    sys.path.insert(0, str(historical / "long_context_bench"))
    from scripts.isolated_run_bundle import build_bundle, digest_tree
    source, _ = build_bundle(
        bundle, target, historical / "bench_runtime" / "m2" / "linux",
        "cpython-3.12.12-linux-x86_64-gnu", "native_claude_cc_vibe_opus48",
        "claude_monitor_opus48", 15340,
        monitor_profile_path=private / "profile_C0.json")
    deployed = json.loads((source / "monitor_agent_core" / "models.local.json").read_text())
    assert deployed["claude_monitor_opus48"]["monitor_research_view"] == "off"
    assert deployed["claude_monitor_opus48"]["monitor_research_intent"] == "off"
    return {"frozen_commit": head, "bundle_source": str(source),
            "bundle_snapshot_sha256": digest_tree(source)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--frozen", type=Path, required=True)
    parser.add_argument("--historical", type=Path, required=True)
    parser.add_argument("--private", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.frozen, args.historical, args.private), sort_keys=True))
