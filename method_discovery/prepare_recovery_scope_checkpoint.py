"""Create the explicitly research-derived local-repair checkpoint."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "GenericAgent-main"))

from monitor_agent_core.checkpoint import load_root_checkpoint  # noqa: E402
from recovery_scope_diagnostic import build_repaired_checkpoint  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-checkpoint", type=Path, required=True)
    parser.add_argument("--checkpoint-parent", type=Path, required=True)
    parser.add_argument("--fixture-root", type=Path, required=True)
    args = parser.parse_args()
    source = load_root_checkpoint(args.source_checkpoint)
    source_version = source["complete"]["manifest_sha256"]
    result = build_repaired_checkpoint(
        source_checkpoint=args.source_checkpoint,
        checkpoint_parent=args.checkpoint_parent,
        fixture_root=args.fixture_root,
    )
    derived = load_root_checkpoint(result)
    update = json.loads(
        (result / "task" / "research_derived_local_repair.json").read_text(encoding="utf-8"))
    source_after = load_root_checkpoint(args.source_checkpoint)
    print(json.dumps({
        "status": "created",
        "path": str(result),
        "source_version_before": source_version,
        "source_version_after": source_after["complete"]["manifest_sha256"],
        "source_unchanged": source_version == source_after["complete"]["manifest_sha256"],
        "derived_version": derived["complete"]["manifest_sha256"],
        "changed_task_files": update["changed_task_files"],
        "limited_check": update["limited_check"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
