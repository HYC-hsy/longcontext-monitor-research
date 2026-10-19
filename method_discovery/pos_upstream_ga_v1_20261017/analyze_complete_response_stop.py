"""Read-only, bounded summary of a stopped complete-response run."""
from __future__ import annotations

import argparse
from collections import Counter, deque
import json
from pathlib import Path


def scan(path: Path) -> dict:
    counts: Counter[str] = Counter()
    categories: Counter[str] = Counter()
    roles: Counter[str] = Counter()
    tool_count = 0
    usage: Counter[str] = Counter()
    last: deque[dict] = deque(maxlen=15)
    n = 0
    with path.open(encoding="utf-8", errors="replace") as stream:
        for n, line in enumerate(stream, 1):
            try:
                row = json.loads(line)
            except ValueError:
                counts["INVALID_JSON"] += 1
                continue
            kind = str(row.get("event_type", row.get("event", row.get("kind", "UNKNOWN"))))
            counts[kind] += 1
            if kind == "pos_role_request":
                roles[str(row.get("role", "unknown"))] += 1
            payload = row.get("payload")
            if isinstance(payload, dict):
                if kind == "provider_usage":
                    for key in ("input_tokens", "output_tokens", "cache_creation_input_tokens",
                                "cache_read_input_tokens", "cached_input_tokens"):
                        value = payload.get(key)
                        if isinstance(value, int) and not isinstance(value, bool):
                            usage[key] += value
                if kind == "action_selected" and isinstance(payload.get("tool_call_ids"), list):
                    tool_count += len(payload["tool_call_ids"])
                for key in ("category", "outcome", "status", "error_type"):
                    value = payload.get(key)
                    if isinstance(value, (str, int, float, bool)) and len(str(value)) < 120:
                        categories[f"{kind}.{key}={value}"] += 1
            safe = {"line": n, "event_type": kind,
                    "timestamp": row.get("timestamp", row.get("time")),
                    "llm_call_id": row.get("llm_call_id"),
                    "role": row.get("role"), "step": row.get("step"),
                    "operation": row.get("operation")}
            if isinstance(payload, dict):
                for key in ("status", "outcome", "classification", "reason", "error_type",
                            "attempt", "attempt_index", "accepted", "response_complete"):
                    value = payload.get(key)
                    if isinstance(value, (str, int, float, bool)) and len(str(value)) < 120:
                        safe[key] = value
            last.append(safe)
    return {"source": str(path), "lines": n, "event_counts": counts,
            "selected_tool_calls": tool_count,
            "pos_role_requests": roles,
            "observable_usage_sums": usage,
            "categories": categories,
            "last": list(last)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()
    print(json.dumps([scan(path) for path in args.paths], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
