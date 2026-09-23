"""Deterministic lifecycle checks for the single DCEC control slot.

The slot is a small syntactic affordance inside ``monitor/working.md``.  It
does not decide whether an observation is adequate or whether a task is done.
"""

from __future__ import annotations

import json
import re


PREFIX = "DCEC-CONTROL/1 "
MAX_SLOT_BYTES = 512
MAX_RECEIPTS = 4
ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,96}$")


def inactive_slot():
    return {"v": 1, "id": None, "status": "none", "op": "none", "from": None, "receipts": []}


def canonical_slot(slot: dict) -> str:
    value = json.dumps(slot, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    line = PREFIX + value
    if len(line.encode("utf-8")) > MAX_SLOT_BYTES:
        raise ValueError("DCEC control slot exceeds 512 UTF-8 bytes")
    return line


def parse_slot(text: str) -> dict:
    first = (text.splitlines()[0] if text.splitlines() else "").strip()
    if not first.startswith(PREFIX):
        raise ValueError("working.md must begin with DCEC-CONTROL/1 slot")
    try:
        slot = json.loads(first[len(PREFIX):])
    except json.JSONDecodeError as exc:
        raise ValueError("malformed DCEC control slot JSON") from exc
    if not isinstance(slot, dict):
        raise ValueError("DCEC control slot must be an object")
    validate_slot_shape(slot)
    if canonical_slot(slot) != first:
        raise ValueError("DCEC control slot is not canonical JSON")
    return slot


def validate_slot_shape(slot: dict) -> None:
    required = {"v", "id", "status", "op", "from", "receipts"}
    if set(slot) != required or slot["v"] != 1:
        raise ValueError("DCEC control slot fields are not exactly v,id,status,op,from,receipts")
    if slot["status"] not in {"none", "requested", "running", "interrupted", "completed"}:
        raise ValueError("invalid DCEC dependency status")
    if slot["op"] not in {"none", "create", "retain", "replace", "discharge"}:
        raise ValueError("invalid DCEC dependency operation")
    if slot["status"] == "none":
        if slot["id"] is not None or slot["receipts"]:
            raise ValueError("inactive DCEC slot cannot carry id or receipts")
        if slot["op"] != "discharge" and slot["from"] is not None:
            raise ValueError("inactive DCEC slot may carry from only for discharge")
    else:
        if not isinstance(slot["id"], str) or not ID_RE.fullmatch(slot["id"]):
            raise ValueError("active DCEC slot requires an opaque id")
    if slot["from"] is not None and (not isinstance(slot["from"], str) or not ID_RE.fullmatch(slot["from"])):
        raise ValueError("DCEC slot from must be an opaque id or null")
    if not isinstance(slot["receipts"], list) or len(slot["receipts"]) > MAX_RECEIPTS:
        raise ValueError("DCEC slot receipts must contain at most four ids")
    if any(not isinstance(item, str) or not ID_RE.fullmatch(item) for item in slot["receipts"]):
        raise ValueError("DCEC slot receipts must be opaque ids")


def ensure_slot(text: str, slot: dict | None = None) -> str:
    """Return text with a canonical slot, preserving natural-language prose."""
    slot = inactive_slot() if slot is None else slot
    first = (text.splitlines()[0] if text.splitlines() else "").strip()
    if first.startswith(PREFIX):
        # A claimed control line must be valid; do not hide malformed
        # lifecycle declarations in natural-language prose.
        parse_slot(text)
        return text
    try:
        parse_slot(text)
        return text
    except ValueError:
        return canonical_slot(slot) + ("\n" + text if text else "")


def validate_transition(old: dict, new: dict, known_receipts: set[str]) -> str:
    """Validate only syntax/lifecycle/receipt identity; return transition kind."""
    validate_slot_shape(new)
    for receipt in new["receipts"]:
        if receipt not in known_receipts:
            raise ValueError(f"unknown DCEC receipt_id: {receipt}")
    if old == new:
        return "unchanged"
    old_id, new_id = old.get("id"), new.get("id")
    if old_id is None:
        if new_id is None:
            if new["op"] != "none":
                raise ValueError("inactive slot may only remain inactive")
            return "prose_only"
        if new["op"] != "create" or new["from"] is not None:
            raise ValueError("inactive dependency requires op=create")
        return "create"
    if new_id is None:
        if new["op"] != "discharge" or new["from"] != old_id:
            raise ValueError("active dependency may clear only with explicit discharge")
        return "discharge"
    if new["op"] == "retain":
        if new_id != old_id or new["from"] not in (None, old_id):
            raise ValueError("retain must keep the active dependency id")
        return "retain"
    if new["op"] == "replace":
        if new_id == old_id or new["from"] != old_id:
            raise ValueError("replace requires from=old id and a distinct successor")
        return "replace"
    raise ValueError("active dependency changes require retain, replace or discharge")


def slot_and_prose(text: str):
    lines = text.splitlines()
    return (lines[0] if lines else ""), ("\n".join(lines[1:]) if len(lines) > 1 else "")
