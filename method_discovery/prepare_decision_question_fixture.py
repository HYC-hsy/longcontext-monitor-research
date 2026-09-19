"""Materialize a reproducible, explicitly constructed diagnostic fixture.

The legacy independent-verification materialization predates the checkpoint
contract used by the three-way diagnostic.  This adapter copies only its
public task material, adds deterministic cursors to the event prefix, and
labels the inherited parent History as ``constructed_offline``.  It never
claims that the old History is a faithful provider snapshot.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)


def sanitize_history(src: Path, dst: Path, minimal: bool = False) -> None:
    """Remove inherited control calls from a constructed diagnostic history.

    The old snapshot is later than the intended checkpoint.  Keeping its
    intervene/allow_complete blocks would leak a post-hoc decision into the
    model-visible input, so the derived history is explicitly non-faithful.
    """
    raw = json.loads(src.read_text(encoding="utf-8"))
    if minimal:
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text("[]\n", encoding="utf-8")
        return
    removed_ids: set[str] = set()
    for message in raw:
        for block in message.get("content", []) if isinstance(message, dict) else []:
            if block.get("type") == "tool_use" and block.get("name") in {
                "intervene", "allow_complete", "task_control",
            }:
                if block.get("id"):
                    removed_ids.add(block["id"])
    clean = []
    for message in raw:
        if not isinstance(message, dict):
            continue
        blocks = message.get("content")
        if not isinstance(blocks, list):
            clean.append(message)
            continue
        kept = []
        for block in blocks:
            if block.get("type") == "tool_use" and block.get("name") in {
                "intervene", "allow_complete", "task_control",
            }:
                continue
            if block.get("type") == "tool_result" and block.get("tool_use_id") in removed_ids:
                continue
            kept.append(block)
        if kept:
            clean.append({**message, "content": kept})
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(clean, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def add_cursors(src: Path, dst: Path) -> int:
    rows = [json.loads(line) for line in src.read_text(encoding="utf-8").splitlines()]
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("w", encoding="utf-8", newline="\n") as stream:
        for cursor, row in enumerate(rows):
            row = dict(row)
            row["cursor"] = cursor
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(rows) - 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--legacy", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--minimal-history", action="store_true")
    args = parser.parse_args()
    if not args.minimal_history:
        raise ValueError(
            "Legacy post-hoc History is disabled. Use --minimal-history or provide "
            "a separately verified provider snapshot."
        )
    if args.output.exists():
        raise FileExistsError(args.output)

    legacy = args.legacy
    output = args.output
    output.mkdir(parents=True)
    copied = {}

    events = output / "task_evidence/public_events.jsonl"
    cursor = add_cursors(legacy / "task_evidence/public_events.jsonl", events)
    copied["task_evidence/public_events.jsonl"] = sha256(events)

    for name in ("original_task.txt", "build_observation.json"):
        dst = output / "task_evidence" / name
        copy(legacy / "task_evidence" / name, dst)
        copied[f"task_evidence/{name}"] = sha256(dst)

    history = output / "parent_context/provider_history.json"
    sanitize_history(legacy / "parent_context/provider_history.json", history,
                     minimal=args.minimal_history)
    copied["parent_context/provider_history.json"] = sha256(history)

    workspace_root = legacy / "workspace"
    for source in workspace_root.rglob("*"):
        if source.is_file():
            relative = source.relative_to(workspace_root).as_posix()
            dst = output / "workspace" / relative
            copy(source, dst)
            copied[f"workspace/{relative}"] = sha256(dst)

    archive = output / "research_archive/public_events_source.jsonl"
    copy(events, archive)
    copied["research_archive/public_events_source.jsonl"] = sha256(archive)

    config = json.loads(args.config.read_text(encoding="utf-8"))
    config["checkpoint"] = {
        "id": "fyn-2.2.0-roadmap-turn-60-constructed-r1",
        "model_visible": {
            "events": "task_evidence/public_events.jsonl",
            "parent_history": "parent_context/provider_history.json",
            "history_source_kind": "constructed_offline",
            "through_cursor": cursor,
        },
        "research_archive": {
            "events": "research_archive/public_events_source.jsonl",
        },
        "forbid_control_actions": ["intervene", "allow_complete", "task_control"],
    }
    config["diagnostic"] = {
        "total_calls": 6,
        "question_turns": 3,
        "investigation_turns": 2,
        "final_turns": 1,
    }
    for case in config.get("cases", []):
        if "acceptance_question" not in case and "question" in case:
            case["acceptance_question"] = case.pop("question")
    config["fixture_note"] = (
        "Constructed offline from materialized_r4. The parent History is not a "
        "faithful provider snapshot; use for diagnostic calibration only. "
        + ("This variant uses an empty clean History to prevent post-hoc leakage."
           if args.minimal_history else "")
    )
    config_path = output / "config.json"
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    copied["config.json"] = sha256(config_path)

    manifest = {
        "checkpoint": config["checkpoint"]["id"],
        "config_sha256": sha256(config_path),
        "model_visible_cursor": cursor,
        "artifact_sha256": copied,
        "source_legacy_materialization": str(legacy),
        "history_source_kind": "constructed_offline",
        "research_only": True,
    }
    (output / "materialization.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"output": str(output), "cursor": cursor, "files": len(copied)}, indent=2))


if __name__ == "__main__":
    main()
