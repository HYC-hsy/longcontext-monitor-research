"""Lossless, deterministic projection of the frozen C02 B request's early history."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from method_discovery.curator_supervisor_convergence_v0.diagnostic_static_adapter_v1_20261009.adapter import canonical, save_json


HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "diagnostic_static_adapter_v1_20261009" / "C02_B_STATIC_REQUEST.json"
SOURCE_CANONICAL_SHA = "31635aae9700c23c7357ecbc4cc4ebf8d4cdb8d4b8a1d55c47f19dccb876c72a"
PREFIX = "Historical records in original order. These are records, not newly executed tools. Current review input follows in the next messages.\n"
KEEP = {("user", "text"), ("user", "tool_result"), ("assistant", "tool_use")}
REMOVE = {("assistant", "thinking"), ("assistant", "redacted_thinking"), ("assistant", "text")}
FIELDS = {
    ("user", "text"): {"type", "text"},
    ("user", "tool_result"): {"type", "tool_use_id", "content"},
    ("assistant", "tool_use"): {"type", "id", "name", "input"},
    ("assistant", "thinking"): {"type", "thinking", "signature"},
    ("assistant", "redacted_thinking"): {"type", "data"},
    ("assistant", "text"): {"type", "text"},
}
PAYLOAD = {"text": "text", "tool_result": "content", "tool_use": "input"}


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def source_request() -> tuple[dict, dict]:
    raw = SOURCE.read_bytes()
    request = json.loads(raw)
    if len(request["messages"]) != 96 or digest(canonical(request)) != SOURCE_CANONICAL_SHA:
        raise RuntimeError("Frozen C02 B request identity mismatch")
    if set(request) != {"max_tokens", "messages", "model", "output_config", "stream",
                        "system", "thinking", "tools"}:
        raise RuntimeError("Unexpected provider request field")
    return request, {"source_path": str(SOURCE), "source_raw_sha256": digest(raw),
                     "source_canonical_sha256": digest(canonical(request))}


def _validate_block(message: dict, block: dict) -> str:
    if set(message) != {"role", "content"} or not isinstance(message["content"], list):
        raise RuntimeError("Unexpected message fields")
    key = (message["role"], block.get("type"))
    if key not in KEEP | REMOVE or set(block) != FIELDS[key]:
        raise RuntimeError(f"Unhandled block fields: {key} {sorted(block)}")
    if key == ("assistant", "tool_use"):
        if not isinstance(block["id"], str) or not isinstance(block["input"], dict):
            raise RuntimeError("Malformed historical tool_use")
    elif key == ("user", "tool_result"):
        if not isinstance(block["tool_use_id"], str) or not isinstance(block["content"], str):
            raise RuntimeError("Malformed historical tool_result")
    elif key[1] == "text" and not isinstance(block["text"], str):
        raise RuntimeError("Malformed historical text")
    return "retain" if key in KEEP else "remove_early_assistant_thinking_or_free_text"


def _identity(messages: list[dict]) -> dict:
    calls, returns = {}, {}
    for mi, message in enumerate(messages):
        if set(message) != {"role", "content"} or not isinstance(message["content"], list):
            raise RuntimeError("Unexpected message structure")
        for bi, block in enumerate(message["content"]):
            key = (message["role"], block.get("type"))
            if key in {( "assistant", "tool_use")}:
                ident = block["id"]
                if ident in calls:
                    raise RuntimeError("Duplicate tool_use id")
                calls[ident] = (mi, bi)
            elif key == ("user", "tool_result"):
                ident = block["tool_use_id"]
                if ident in returns or ident not in calls or calls[ident] >= (mi, bi):
                    raise RuntimeError("Unmatched or duplicate tool_result")
                returns[ident] = (mi, bi)
    if set(calls) != set(returns):
        raise RuntimeError("Unreturned historical tool_use")
    return {"tool_use_count": len(calls), "tool_result_count": len(returns),
            "pairs": [{"id": k, "call": list(v), "return": list(returns[k])}
                      for k, v in calls.items()]}


def render(messages: list[dict]) -> tuple[str, list[dict]]:
    if len(messages) != 88:
        raise RuntimeError("Early-history boundary mismatch")
    raw = bytearray(PREFIX.encode("utf-8"))
    rows = []
    for mi, message in enumerate(messages):
        for bi, block in enumerate(message["content"]):
            rule = _validate_block(message, block)
            row = {"message_index": mi, "block_index": bi, "role": message["role"],
                   "type": block["type"], "rule": rule,
                   "source_block_sha256": digest(canonical(block)),
                   "tool_use_id": block.get("id"), "tool_result_id": block.get("tool_use_id")}
            if rule == "retain":
                key = PAYLOAD[block["type"]]
                payload = canonical(block[key]) if key == "input" else block[key].encode("utf-8")
                metadata = canonical({"message_index": mi, "block_index": bi,
                                      "role": message["role"], "type": block["type"],
                                      "payload_key": key,
                                      "other_fields": {k: v for k, v in block.items() if k != key}})
                record = f"@RECORD {len(metadata)} {len(payload)}\n".encode() + metadata + payload
                begin = len(raw)
                raw.extend(record)
                row.update({"render_start": begin, "render_end": len(raw),
                            "render_bytes": len(record), "render_sha256": digest(record)})
            else:
                row.update({"render_start": None, "render_end": None,
                            "render_bytes": 0, "render_sha256": None})
            rows.append(row)
    if (sum(r["rule"] == "retain" for r in rows),
        sum(r["rule"] != "retain" for r in rows)) != (182, 50):
        raise RuntimeError("Projection count mismatch")
    return raw.decode("utf-8"), rows


def parse_rendered(text: str) -> list[dict]:
    """Parse only the actual provider-visible text; no source/manifest access."""
    raw = text.encode("utf-8")
    prefix = PREFIX.encode("utf-8")
    if not raw.startswith(prefix):
        raise RuntimeError("Historical record wrapper mismatch")
    pos = len(prefix)
    result = []
    while pos < len(raw):
        end = raw.find(b"\n", pos)
        if end < 0:
            raise RuntimeError("Unterminated record length header")
        header = raw[pos:end]
        parts = header.split(b" ")
        if len(parts) != 3 or parts[0] != b"@RECORD" or not all(p.isdigit() for p in parts[1:]):
            raise RuntimeError("Ambiguous record delimiter")
        meta_len, payload_len = map(int, parts[1:])
        start = end + 1
        finish = start + meta_len + payload_len
        if finish > len(raw):
            raise RuntimeError("Truncated record")
        meta = json.loads(raw[start:start + meta_len])
        payload = raw[start + meta_len:finish]
        if set(meta) != {"message_index", "block_index", "role", "type", "payload_key", "other_fields"}:
            raise RuntimeError("Record metadata fields changed")
        key = meta["payload_key"]
        if key != PAYLOAD.get(meta["type"]):
            raise RuntimeError("Record payload key mismatch")
        value = json.loads(payload) if key == "input" else payload.decode("utf-8")
        block = dict(meta["other_fields"])
        block[key] = value
        if block.get("type") != meta["type"]:
            raise RuntimeError("Record block type mismatch")
        row = {"message_index": meta["message_index"], "block_index": meta["block_index"],
               "role": meta["role"], "block": block}
        if result and (row["message_index"], row["block_index"]) <= (
                result[-1]["message_index"], result[-1]["block_index"]):
            raise RuntimeError("Record order mismatch")
        result.append(row)
        pos = finish
    if len(result) != 182:
        raise RuntimeError("Incomplete rendered history")
    return result


def project() -> tuple[dict, dict, dict]:
    source, identity = source_request()
    _identity(source["messages"])
    text, rows = render(source["messages"][:88])
    projected = copy.deepcopy(source)
    projected["messages"] = [{"role": "user", "content": [{"type": "text", "text": text}]}] + copy.deepcopy(source["messages"][88:])
    parsed = parse_rendered(projected["messages"][0]["content"][0]["text"])
    kept = [row for row in rows if row["rule"] == "retain"]
    for want, got in zip(kept, parsed):
        if (want["message_index"], want["block_index"], want["role"],
            want["source_block_sha256"]) != (
                got["message_index"], got["block_index"], got["role"], digest(canonical(got["block"]))):
            raise RuntimeError("Provider-visible reverse reconstruction differs from source")
    if projected["messages"][1:] != source["messages"][88:]:
        raise RuntimeError("Native current-review tail changed")
    pair_identity = _identity(source["messages"][88:])
    manifest = {**identity, "format": "UTF-8 length-delimited records with raw text/result payload and canonical JSON tool input",
                "prefix_utf8_sha256": digest(PREFIX.encode("utf-8")),
                "rendered_history_sha256": digest(text.encode("utf-8")),
                "rendered_history_bytes": len(text.encode("utf-8")),
                "source_early_tool_pairs": _identity(source["messages"][:88]),
                "native_tail_tool_pairs": pair_identity,
                "retained_count": len(kept), "removed_count": len(rows)-len(kept),
                "reverse_parsed_from_request": True, "blocks": rows,
                "H_canonical_sha256": digest(canonical(source)),
                "R_canonical_sha256": digest(canonical(projected))}
    return source, projected, manifest


def freeze(destination: Path) -> dict:
    if destination.exists():
        raise RuntimeError("Projection freeze destination already exists")
    source, projected, manifest = project()
    destination.mkdir(parents=True)
    save_json(destination / "H_REQUEST.json", source)
    save_json(destination / "R_REQUEST.json", projected)
    save_json(destination / "PROJECTION_MANIFEST.json", manifest)
    return manifest
