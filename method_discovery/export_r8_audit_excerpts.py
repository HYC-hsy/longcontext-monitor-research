"""Export two short, de-identified R8 audit excerpts without model calls."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _events(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _arguments(event: dict) -> dict:
    raw = event.get("arguments")
    if not isinstance(raw, str):
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}
    return value if isinstance(value, dict) else {"raw": raw}


def export(root: Path) -> dict:
    prompt = _events(root / "r7_root_completion" / "scope_prompt_control" / "audit.jsonl")
    interface = _events(root / "r7_root_completion" / "scope_decision_interface" / "audit.jsonl")
    theme_call = next(event for event in prompt
                      if event.get("event") == "tool_call"
                      and event.get("name") == "file_read"
                      and _arguments(event).get("path") == "task/workspace/theme/json.go")
    theme_result = next(event for event in prompt
                        if event.get("event") == "tool_result"
                        and event.get("tool_id") == theme_call.get("tool_id"))
    prompt_finish = next(event for event in reversed(prompt)
                         if event.get("event") == "tool_call"
                         and event.get("name") == "finish_parent_decision")
    finish_args = _arguments(prompt_finish)

    attempts = []
    for index, event in enumerate(interface):
        if event.get("event") != "tool_call" or event.get("name") != "finish_scoped_decision":
            continue
        result = next((candidate for candidate in interface[index + 1:]
                       if candidate.get("event") == "tool_result"
                       and candidate.get("tool_id") == event.get("tool_id")), None)
        args = _arguments(event)
        attempts.append({
            "proposed_outcome": args.get("outcome"),
            "proposed_local_update": args.get("local_update"),
            "proposed_decision_basis": args.get("decision_basis"),
            "proposed_remaining_limits": args.get("remaining_limits"),
            "engineering_result": (result or {}).get("data"),
        })

    data = theme_result.get("data") or {}
    return {
        "source": "R8 frozen local audit; no model call performed",
        "scope_prompt_root": {
            "file_read_arguments": _arguments(theme_call),
            "file_read_result": {
                "path": data.get("path"), "start": data.get("start"),
                "lines": data.get("lines"), "total_lines": data.get("total_lines"),
                "truncated": data.get("truncated"),
                "more_lines_after_range": data.get("more_lines_after_range"),
                "sha256": data.get("sha256"),
            },
            "unsupported_missing_claim": "Missing FromJSONReader function entirely",
            "actual_frozen_fact": (
                "FromJSONReader begins at line 105, outside the returned 1-100 range; "
                "its signature still conflicts with the requirement because it adds base fyne.Theme."
            ),
            "final_outcome": finish_args.get("outcome"),
        },
        "scoped_interface_root": {
            "attempts": attempts,
            "interpretation_boundary": (
                "These are rejected proposals, not completed decisions. Format/provenance "
                "rejection must not be counted as improved semantic judgment."
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--r8-result", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = export(args.r8_result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps({"status": "created", "output": str(args.output),
                      "interface_attempts": len(payload["scoped_interface_root"]["attempts"])},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
