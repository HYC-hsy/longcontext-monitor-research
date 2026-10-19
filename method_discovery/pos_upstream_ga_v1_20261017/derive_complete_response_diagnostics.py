"""Add narrow aggregate and terminal metadata to a stopped-run public archive."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from .analyze_complete_response_stop import scan


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    target = args.archive.resolve(strict=True)
    index_path = target / "FILE_HASHES.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    if index["schema"] != "pos-ga-complete-response-stop-public-v1":
        raise RuntimeError("unexpected archive schema")
    first = source / "01_adaptive-rejection-sampler"
    run_id = json.loads((first / "run_identity.json").read_text(encoding="utf-8"))["run_id"]
    run = first / "runs" / run_id
    trial = [path for path in (run / "jobs").glob("*/*") if
             (path / "agent/research_events.jsonl").is_file()]
    if len(trial) != 1:
        raise RuntimeError("Task trial not unique")
    task = scan(trial[0] / "agent/research_events.jsonl")
    role_path = run / "control/pos_archive/events.jsonl"
    role = scan(role_path)
    provider_path = run / "control/pos_archive/events.provider.jsonl"
    provider = scan(provider_path)
    omitted = {entry["line"] for row in index["files"] if row["path"] ==
               "01/pos/events.provider.jsonl" for entry in row["omissions"]}
    omitted_types: Counter[str] = Counter()
    with provider_path.open(encoding="utf-8", errors="replace") as stream:
        for number, line in enumerate(stream, 1):
            if number in omitted:
                omitted_types[str(json.loads(line).get("event_type", "UNKNOWN"))] += 1
    terminal = []
    with role_path.open("rb") as stream:
        for number, raw in enumerate(stream, 1):
            if number < 6633:
                continue
            row = json.loads(raw)
            item = {"source_line": number, "source_line_bytes": len(raw),
                    "source_line_sha256": hashlib.sha256(raw).hexdigest(),
                    "time": row.get("time"), "event": row.get("event"),
                    "role": row.get("role"), "step": row.get("step"),
                    "operation": row.get("operation"), "status": row.get("status")}
            if row.get("error_type") == "TimeoutError" and row.get("error") == (
                    "PoS role deadline elapsed before send"):
                item["error_type"] = row["error_type"]
                item["safe_error_category"] = "role_deadline_elapsed_before_send"
            terminal.append(item)
    report = {"schema": "pos-ga-complete-response-stop-diagnostics-v1",
              "task": task, "pos_roles": role, "pos_provider": provider,
              "provider_public_omitted_lines": len(omitted),
              "provider_public_omitted_by_event": omitted_types,
              "terminal_role_excerpt": terminal}
    output = target / "DIAGNOSTICS.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8", newline="\n")
    raw = output.read_bytes()
    index["files"].append({"path": "DIAGNOSTICS.json", "derived_from": [
        "01/task/research_events.jsonl", "01/pos/events.jsonl",
        "01/pos/events.provider.jsonl"], "public_parts": [{"path": "DIAGNOSTICS.json",
        "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}],
        "redactions": 0, "omissions": []})
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8", newline="\n")
    print(json.dumps({"diagnostics_sha256": hashlib.sha256(raw).hexdigest(),
                      "index_sha256": hashlib.sha256(index_path.read_bytes()).hexdigest(),
                      "omitted_by_event": omitted_types}))


if __name__ == "__main__":
    main()
