"""Export this episode's model-visible role exchange, never transport secrets.

This script reads a private archive supplied explicitly on the command line.
It exports only the already sent generation body (without metadata.user_id),
the visible text response, and a mechanical coverage comparison. It never
exports HTTP headers, endpoint, profile, hidden thinking, or private logs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


SENSITIVE = re.compile(
    r"(?i)(?:sk-[a-z0-9_-]{12,}|bearer\s+[a-z0-9._-]+|"
    r"authorization\s*[:=]|api[_-]?key\s*[:=]|https?://\S+)"
)
ROLES = ("maintenance", "audit", "candidate_repair", "audit")
BODY_KEYS = ("model", "system", "messages", "max_tokens", "thinking",
             "output_config", "context_management", "stream")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n").encode("utf-8")


def write_checked(path: Path, data: bytes) -> str:
    if SENSITIVE.search(data.decode("utf-8")):
        raise ValueError(f"sensitive-pattern review required: {path.name}")
    if path.exists():
        if path.read_bytes() != data:
            raise FileExistsError(f"refusing to overwrite different file: {path}")
    else:
        path.write_bytes(data)
    return sha(data)


def target_key(value: dict) -> tuple:
    return value.get("kind"), value.get("id"), value.get("revision")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider-events", type=Path, required=True)
    parser.add_argument("--role-calls", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    events = [json.loads(line) for line in args.provider_events.read_text(
        encoding="utf-8").splitlines() if line]
    calls = [json.loads(line) for line in args.role_calls.read_text(
        encoding="utf-8").splitlines() if line]
    ready = [event for event in events
             if event["event_type"] == "provider_request_ready"]
    returned = [event for event in events
                if event["event_type"] == "provider_response_content"]
    attempted = [call for call in calls if call["status"] == "attempted"]
    if not (len(ready) == len(returned) == len(attempted) == 4):
        raise ValueError("episode must have exactly four matched role exchanges")
    if tuple(call["role"] for call in attempted) != ROLES:
        raise ValueError("unexpected role sequence")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    index = {
        "scope": "visible generation requests and responses; no hidden thinking or HTTP transport",
        "private_source_sha256": {
            "provider_events.jsonl": sha(args.provider_events.read_bytes()),
            "role_calls.jsonl": sha(args.role_calls.read_bytes()),
        },
        "exports": [],
    }
    views = []
    outputs = []
    for number, (request, response, call) in enumerate(
            zip(ready, returned, attempted), start=1):
        if request["llm_call_id"] != response["llm_call_id"]:
            raise ValueError("request/response identity mismatch")
        body = request["payload"]["content"]
        if set(BODY_KEYS) - set(body):
            raise ValueError("missing generation body fields")
        visible_body = {key: body[key] for key in BODY_KEYS}
        blocks = response["payload"]["parsed_visible_blocks"]
        if len(blocks) != 1 or blocks[0]["type"] != "text":
            raise ValueError("unexpected visible response blocks")
        raw = blocks[0]["text"]
        if not isinstance(raw, str):
            raise ValueError("non-text response")
        stem = f"{number:02d}_{call['role']}"
        request_name = f"{stem}_request.json"
        view_name = f"{stem}_parsed_user_view.json"
        response_name = f"{stem}_visible_response.txt"
        request_hash = write_checked(args.output_dir / request_name,
                                     json_bytes(visible_body))
        view = json.loads(visible_body["messages"][0]["content"][0]["text"])
        view_hash = write_checked(args.output_dir / view_name, json_bytes(view))
        response_hash = write_checked(args.output_dir / response_name,
                                      raw.encode("utf-8"))
        index["exports"].append({
            "role": call["role"], "call_id": call["call_id"],
            "provider_call_id": request["llm_call_id"],
            "request_file": request_name, "request_public_sha256": request_hash,
            "request_private_logged_payload_sha256": request["payload"]["sha256"],
            "parsed_user_view_file": view_name,
            "parsed_user_view_public_sha256": view_hash,
            "response_file": response_name, "response_public_sha256": response_hash,
            "response_original_visible_utf8_sha256": response_hash,
        })
        views.append(view)
        if not raw.startswith("```json\n") or not raw.endswith("\n```"):
            raise ValueError("unexpected response envelope")
        outputs.append(json.loads(raw[8:-4]))
    expected = views[3]["required_coverage"]
    actual = outputs[3]["coverage"]
    expected_keys = [target_key(item) for item in expected]
    actual_keys = [target_key(item.get("target", {})) for item in actual]
    comparison = {
        "expected_required_coverage": expected,
        "actual_returned_coverage": actual,
        "expected_count": len(expected), "actual_count": len(actual),
        "target_identities_match": sorted(expected_keys) == sorted(actual_keys),
        "exact_structures_match": expected == actual,
        "missing_target_identities": [list(key) for key in expected_keys
                                      if key not in actual_keys],
        "extra_target_identities": [list(key) for key in actual_keys
                                    if key not in expected_keys],
        "note": "Identity match does not validate candidate semantics or audit correctness.",
    }
    index["coverage_comparison_sha256"] = write_checked(
        args.output_dir / "coverage_comparison.json", json_bytes(comparison))
    write_checked(args.output_dir / "INDEX.json", json_bytes(index))


if __name__ == "__main__":
    main()
