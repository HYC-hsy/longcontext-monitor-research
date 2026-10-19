"""Emit bounded public evidence from the local fake-HTTP profile-process test.

No private profile, endpoint, credential, raw hidden thinking, or full host log
is copied. Input hashes identify the untouched test artifacts; output hashes
identify the derived public bytes. Fail closed on unexpected model-visible text.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re


FORBIDDEN = re.compile(r"(?i)(?:https?://|synthetic_test_only|api[_-]?key|authorization|thinking_content)")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_lines(path: Path):
    raw = path.read_bytes()
    return [json.loads(line) for line in raw.splitlines()], {
        "source_file": str(path), "source_bytes": len(raw),
        "source_sha256": sha(raw),
    }


def emit(path: Path, rows: list[dict]) -> dict:
    raw = b"".join((json.dumps(row, ensure_ascii=False, sort_keys=True,
        separators=(",", ":")) + "\n").encode("utf-8") for row in rows)
    path.write_bytes(raw)
    return {"public_file": path.name, "public_bytes": len(raw),
            "public_sha256": sha(raw), "rows": len(rows)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    output = args.output.resolve(strict=False)
    output.mkdir(parents=True, exist_ok=False)
    provider, provider_source = read_lines(
        source / "control/pos_archive/events.provider.jsonl")
    events, events_source = read_lines(
        source / "control/pos_archive/events.jsonl")
    calls, calls_source = read_lines(source / "fake_host_calls.jsonl")
    provider_rows = []
    for line, row in enumerate(provider, 1):
        payload = row["payload"]
        clean = {"source_line": line, "event_type": row["event_type"],
                 "timestamp": row["timestamp"], "run_id": row["run_id"],
                 "task_id": row["task_id"], "llm_call_id": row["llm_call_id"],
                 "event_id": row["event_id"]}
        for key in ("sha256", "bytes", "model", "stream", "message_count",
                    "tool_count", "max_retries", "attempt", "status_code",
                    "outcome", "input_tokens", "output_tokens",
                    "hidden_thinking_excluded"):
            if key in payload:
                clean[key] = payload[key]
        if row["event_type"] == "provider_request_ready":
            content = payload["content"]
            if not isinstance(content, dict):
                raise ValueError(f"unexpected request shape at line {line}")
            # The provider envelope also contains transport metadata. Only
            # the actual model-visible fields and non-secret generation knobs.
            visible = {key: content[key] for key in ("model", "system",
                "messages", "max_tokens", "stream", "temperature", "thinking",
                "context_management") if key in content}
            if FORBIDDEN.search(json.dumps(visible, ensure_ascii=False)):
                raise ValueError(f"unsafe or unexpected request content at line {line}")
            clean["model_visible_content"] = visible
        provider_rows.append(clean)
    selected = {"pos_role_request", "pos_role_response", "candidate_pma_request",
                "candidate_pma_response", "belief_sentinel_audit_completed",
                "belief_candidate_validated", "belief_state_initialized"}
    event_rows = [{"source_line": line, "event": row["event"],
                   "run_id": row.get("run_id"), "task_id": row.get("task_id"),
                   "step": row.get("step"), "timestamp": row.get("timestamp")}
                  for line, row in enumerate(events, 1) if row.get("event") in selected]
    host_rows = [{"source_line": line, "phase": row["phase"],
                  "sequence": row["sequence"], "model": row["model"],
                  "max_tokens": row["max_tokens"], "temperature": row["temperature"],
                  "thinking": row["thinking"], "timeout": row["timeout"]}
                 for line, row in enumerate(calls, 1)]
    sources = {"provider": provider_source, "events": events_source,
               "host_fake_calls": calls_source}
    public = [emit(output / "provider_events.jsonl", provider_rows),
              emit(output / "role_event_index.jsonl", event_rows),
              emit(output / "host_fake_calls.jsonl", host_rows)]
    summary = {"schema": "candidate-profile-process-public-v1", "sources": sources,
               "files": public, "fake_http_calls": sum(row["event_type"] ==
                   "provider_request_attempt" for row in provider_rows),
               "fake_pma_calls": len(host_rows), "real_model_calls": 0,
               "redactions": ["provider_url", "authentication", "secret profile",
                   "hidden thinking", "raw non-request response content"]}
    (output / "FILE_HASHES.json").write_bytes(
        (json.dumps(summary, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
