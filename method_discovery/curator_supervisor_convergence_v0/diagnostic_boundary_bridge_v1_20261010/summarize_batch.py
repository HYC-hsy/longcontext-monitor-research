"""Mechanical slot accounting only; no B/H versus R quality judgment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .bootstrap import DIALOGUE_CUTOFF
from .freeze_inputs import digest
from .run_batch import cutoff_dialogue_prefix_sha256


CONTROL = {"wait", "intervene", "allow_complete"}


def load_lines(path):
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def summarize(root: Path):
    batch = json.loads((root / "BATCH_RESULT.json").read_text(encoding="utf-8"))
    rows = []
    expected_prefix = cutoff_dialogue_prefix_sha256()
    for slot in batch["slots"]:
        name = slot["slot"]
        base = root / name
        events = load_lines(base / "audit/events.jsonl")
        dialogue_path = base / "fixture/monitor_private/audit/dialogue.jsonl"
        dialogue_bytes = dialogue_path.read_bytes()
        prefix = b"".join(dialogue_bytes.splitlines(keepends=True)[:DIALOGUE_CUTOFF])
        if digest(prefix) != expected_prefix:
            raise RuntimeError("Historical dialogue prefix changed in " + name)
        dialogue = load_lines(dialogue_path)[DIALOGUE_CUTOFF:]
        responses = [(index, row) for index, row in enumerate(events, 1)
                     if row.get("kind") == "provider_response"]
        calls = [(index, response.get("index"), block) for index, response in responses
                 for block in response.get("blocks", []) if block.get("type") == "tool_use"]
        controls = [(line, request, block) for line, request, block in calls
                    if block.get("name") in CONTROL]
        usages = [row.get("usage", {}) for _, row in responses]
        usage_keys = sorted({key for usage in usages for key in usage if isinstance(usage[key], (int, float))})
        usage = {key: sum(item.get(key, 0) for item in usages) for key in usage_keys}
        kinds = sorted({row.get("event") for row in dialogue if row.get("event")})
        lifecycle = {kind: sum(row.get("event") == kind for row in dialogue) for kind in kinds
                     if kind.startswith(("crs_", "rhr_", "rer_"))}
        counts = {kind: sum(block.get("name") == kind for _, _, block in calls)
                  for kind in sorted({block.get("name") for _, _, block in calls})}
        first = controls[0] if controls else None
        rows.append({"slot": name, "arm": slot["arm"], "terminal": slot["terminal"],
                     "first_control_proposal": ({"audit_event_line": first[0],
                                                 "provider_request_index": first[1],
                                                 "tool_use_id": first[2].get("id"),
                                                 "name": first[2].get("name")}
                                                if first else None),
                     "final_simulated_action": slot.get("action"),
                     "outer_model_cycles": slot.get("outer_model_cycles"),
                     "provider_requests": slot.get("provider_requests"),
                     "accepted_responses": slot.get("accepted_responses"),
                     "tool_calls_proposed_by_name": counts,
                     "native_lifecycle_event_counts": lifecycle,
                     "provider_usage_observed": usage,
                     "root_subreviews": slot.get("root_subreviews", []),
                     "wall_seconds": slot.get("wall_seconds"),
                     "dialogue_prefix_sha256": digest(prefix),
                     "terminal_error_type": slot.get("error_type")})
    return {"planned_slots": batch["planned_count"], "started_slots": len(rows),
            "unstarted_slots": batch["unstarted"], "slots": rows,
            "semantic_endpoint_categories_A_to_D": "not_assigned_development_side",
            "interpretation": "mechanical_counting_only"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError("Summary output already exists")
    value = summarize(args.run_root.resolve(strict=True))
    args.output.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"started_slots": value["started_slots"],
                      "unstarted_slots": len(value["unstarted_slots"])}))


if __name__ == "__main__":
    main()
