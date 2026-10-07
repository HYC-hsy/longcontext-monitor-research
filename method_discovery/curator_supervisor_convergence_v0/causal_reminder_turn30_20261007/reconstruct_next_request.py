"""Reconstruct the original Task turn-31 payload without a provider send.

The turn-31 request is used only as an equality oracle. Construction uses the
turn-30 raw request and the two exact public turn-30 event records.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from .materialize import ARCHIVE, CONTROL, PUBLIC_EVENTS, jsonl, sha_file


PREVIOUS_ID = "a868880b69dc4bd0bb67149d7ff269bc"
NEXT_ID = "f2bc63a1d6a842ffad4f831b1715690f"
PREVIOUS_SHA256 = "1b6170aaa48a8583ae60efccbe42a60c5a45cde2157dbba6ee8fd2d7457337cd"
NEXT_SHA256 = "77411c4ad82dd989db0331f019b56f464b68fa8ee089f237706319c003ce446e"


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def request_path(request_id: str) -> Path:
    return CONTROL / f"{request_id}.request.json"


def raw_request(request_id: str, expected_sha256: str) -> dict:
    path = request_path(request_id)
    if sha_file(path) != expected_sha256:
        raise RuntimeError(f"Unbound raw Task request: {request_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def bound_first_send(request_id: str, expected_sha256: str) -> tuple[Path, dict]:
    path = ARCHIVE / f"bridge/evidence/first_send_{request_id}.json"
    row = json.loads(path.read_text(encoding="utf-8"))
    if (row["request_id"] != request_id or row["request_sha256"] != expected_sha256
            or row["role"] != "task" or row["request_bytes"] != request_path(request_id).stat().st_size):
        raise RuntimeError(f"Task request not bound to source archive: {request_id}")
    return path, row


def turn30_events() -> tuple[dict, dict]:
    rows = jsonl(PUBLIC_EVENTS)
    before = next(row for row in rows if row["archive_sequence"] == 57)
    after = next(row for row in rows if row["archive_sequence"] == 58)
    if (before["task_turn"] != 30 or before["boundary"] != "post_model_pre_tool"
            or after["task_turn"] != 30 or after["boundary"] != "post_tool_pre_next_llm"
            or len(before["tool_calls"]) != 1 or len(after["tool_results"]) != 1):
        raise RuntimeError("Turn-30 public boundary is not exact")
    call = before["tool_calls"][0]
    result = after["tool_results"][0]
    if (call["name"] != "update_working_checkpoint" or call["id"] != result["tool_use_id"]
            or json.loads(result["content"]).get("result") != "working key_info updated"):
        raise RuntimeError("Turn-30 working checkpoint call/result mismatch")
    return before, after


def reconstruct() -> tuple[dict, dict, dict]:
    bound_first_send(PREVIOUS_ID, PREVIOUS_SHA256)
    bound_first_send(NEXT_ID, NEXT_SHA256)
    previous = raw_request(PREVIOUS_ID, PREVIOUS_SHA256)
    before, after = turn30_events()
    result = copy.deepcopy(previous)
    messages = result["messages"]
    if len(messages) != 49 or messages[46]["role"] != "user":
        raise RuntimeError("Previous provider history shape changed")
    if messages[46]["content"][1].pop("cache_control", None) != {"type": "ephemeral"}:
        raise RuntimeError("Expected rolling cache breakpoint missing")
    call = before["tool_calls"][0]
    arguments = {key: value for key, value in call["args"].items() if not key.startswith("_")}
    messages.append({"role": "assistant", "content": [
        {"type": "text", "text": before["text"]},
        {"type": "tool_use", "id": call["id"], "name": call["name"], "input": arguments},
    ]})
    receipt = after["tool_results"][0]
    messages.append({"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": receipt["tool_use_id"], "content": receipt["content"]},
        {"type": "text", "text": after["next_prompt"], "cache_control": {"type": "ephemeral"}},
    ]})
    return previous, result, {"call": call, "result": receipt, "next_prompt": after["next_prompt"]}


def comparison() -> tuple[dict, dict, dict, dict]:
    previous, reconstructed, working = reconstruct()
    original = raw_request(NEXT_ID, NEXT_SHA256)
    all_keys = sorted(set(original) | set(reconstructed))
    mismatch = [{"field": key, "source": "turn30_request_plus_public_turn30_events"}
                for key in all_keys if original.get(key) != reconstructed.get(key)]
    report = {
        "original_raw_request_sha256": NEXT_SHA256,
        "original_model_visible_sha256": sha(original),
        "reconstructed_model_visible_sha256": sha(reconstructed),
        "model_visible_equal": not mismatch,
        "exact_equal_fields": [key for key in all_keys if key not in {row["field"] for row in mismatch}],
        "ignored_transport_fields": [],
        "mismatches": mismatch,
        "source_previous_request_sha256": PREVIOUS_SHA256,
        "source_public_event_archive_sequences": [57, 58],
    }
    return original, reconstructed, working, report
