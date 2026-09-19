"""Create the small complete synthetic checkpoint for scoped-decision calibration."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "GenericAgent-main"))

from monitor_agent_core.checkpoint import load_root_checkpoint  # noqa: E402
from scoped_decision_diagnostic import build_synthetic_checkpoint  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-checkpoint", type=Path, required=True)
    parser.add_argument("--fixture-root", type=Path, required=True)
    parser.add_argument("--checkpoint-parent", type=Path, required=True)
    args = parser.parse_args()
    result = build_synthetic_checkpoint(
        source_checkpoint=args.source_checkpoint, fixture_root=args.fixture_root,
        checkpoint_parent=args.checkpoint_parent)
    loaded = load_root_checkpoint(result)
    check = json.loads((result / "task" / "public_check.json").read_text(encoding="utf-8"))
    print(json.dumps({
        "status": "created", "path": str(result),
        "manifest_sha256": loaded["complete"]["manifest_sha256"],
        "identity": loaded["identity"], "bounded_check": check,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
