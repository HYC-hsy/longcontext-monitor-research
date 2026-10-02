"""Research-only archive of zero-network deployed worker assembly evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalized_request(request: dict) -> dict:
    """Remove only random review IDs and probe-local filesystem identities."""
    value = json.loads(json.dumps(request))
    value["review_id"] = "<REVIEW_ID>"
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True)
    raw = re.sub(r"\.monitor_original_task_[0-9a-f]{32}\.txt",
                 ".monitor_original_task_<ID>.txt", raw)
    raw = re.sub(r"/probe/(?:BASE_C0|FYNE_C0|C0|RP|AP|RB|AB)/",
                 "/probe/<GROUP>/", raw)
    raw = re.sub(r"uc-r5-l2-(?:base-c0|fyne-c0|c0|rp|ap|rb|ab)-precheck",
                 "<PROBE_ID>", raw)
    return json.loads(raw)


def collect(source: Path, destination: Path, groups: list[str]) -> dict:
    if destination.exists():
        raise FileExistsError(destination)
    destination.mkdir(parents=True)
    inventory = {}
    for group in groups:
        src = source / group
        assert (src / "research_l2_summary.json").is_file(), group
        dst = destination / group
        copied = []
        relative_files = [
            "research_l2_summary.json", "task_identity.json", "runtime_receipts.jsonl",
            "monitor_private/audit/research_send_guard.json",
            "monitor_private/audit/research_provider_ready/manifest.jsonl",
            "monitor_private/audit/dialogue.jsonl",
            "monitor_private/audit/provider_history.json",
            "monitor_private/audit/provider_usage.jsonl",
            "monitor_private/audit/request_attempts.jsonl",
            "monitor_private/audit/reviews.jsonl",
            "monitor_private/audit/workspace_transitions.jsonl",
        ]
        relative_files += [str(p.relative_to(src)).replace("\\", "/") for p in sorted(
            (src / "monitor_private/audit/research_provider_ready").glob("request-*.json"))]
        for rel in relative_files:
            origin = src / rel
            assert origin.is_file(), origin
            target = dst / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(origin, target)
            data = target.read_bytes()
            copied.append({"path": rel, "bytes": len(data), "sha256": digest(data)})
        checkpoints = src / "monitor_private/audit/live_checkpoints"
        checkpoint_files = []
        if checkpoints.is_dir():
            for item in sorted(p for p in checkpoints.rglob("*") if p.is_file()):
                data = item.read_bytes()
                checkpoint_files.append({"path": str(item.relative_to(checkpoints)).replace("\\", "/"),
                                         "bytes": len(data), "sha256": digest(data)})
        inventory[group] = {
            "archived_files": copied,
            "local_unuploaded_root_checkpoint": {
                "path": str(checkpoints.resolve()),
                "files": checkpoint_files,
                "aggregate_manifest_sha256": digest(json.dumps(checkpoint_files, sort_keys=True).encode()),
                "total_bytes": sum(item["bytes"] for item in checkpoint_files),
            },
        }
    (destination / "MANIFEST.json").write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n",
                                                encoding="utf-8")
    return inventory


def compare_c0(source: Path, destination: Path) -> dict:
    rows = []
    for index in (1, 2):
        rel = f"monitor_private/audit/research_provider_ready/request-{index:02d}.json"
        candidate = json.loads((source / "C0" / rel).read_text(encoding="utf-8"))
        baseline = json.loads((source / "BASE_C0" / rel).read_text(encoding="utf-8"))
        left = normalized_request(candidate)
        right = normalized_request(baseline)
        rows.append({"request": index, "equal_after_mechanical_normalization": left == right,
                     "candidate_normalized_sha256": digest(json.dumps(left, sort_keys=True, ensure_ascii=False).encode()),
                     "baseline_normalized_sha256": digest(json.dumps(right, sort_keys=True, ensure_ascii=False).encode()),
                     "different_top_level_keys": [key for key in sorted(set(left) | set(right))
                                                  if left.get(key) != right.get(key)]})
    result = {"normalizations": ["review_id", "random original task filename UUID",
                                    "probe-local /probe/<group>/ roots", "probe ID"],
              "requests": rows, "all_equal": all(row["equal_after_mechanical_normalization"] for row in rows)}
    (destination / "C0_BASELINE_COMPARISON.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    groups = ["C0", "RP", "AP", "RB", "AB", "BASE_C0", "FYNE_C0"]
    inventory = collect(args.source, args.destination, groups)
    comparison = compare_c0(args.source, args.destination)
    print(json.dumps({"groups": {k: len(v["archived_files"]) for k, v in inventory.items()},
                      "c0_baseline_equal": comparison["all_equal"]}, sort_keys=True))


if __name__ == "__main__":
    main()
