"""Strict model-only JSON envelope decoder; storage JSON remains strict."""

from __future__ import annotations

import hashlib
import re
from typing import Callable

from .source import ContractError, strict_loads


PROTOCOL = "model-json-envelope/1"
_SPACE = " \t\r\n"
_FENCE = re.compile(r"\A```(?:json)?\r?\n(?P<body>[\s\S]*?)\r?\n```\Z")


def decode_model_object(raw: str, *, record: Callable[[dict], None] | None = None) -> dict:
    """Decode one raw object or one exact fence without repairing its contents.

    Offsets are UTF-8 byte positions in the original provider text, end exclusive.
    The record callback is diagnostic only and must not alter acceptance.
    """
    if type(raw) is not str:
        raise ContractError("provider_nontext_response")
    left, right = 0, len(raw)
    while left < right and raw[left] in _SPACE:
        left += 1
    while right > left and raw[right - 1] in _SPACE:
        right -= 1
    trimmed = raw[left:right]
    kind = "raw_json"
    start, end = left, right
    failure_layer = None
    if trimmed.startswith("```") or trimmed.endswith("```"):
        match = _FENCE.fullmatch(trimmed)
        if match is None:
            kind = "rejected"
            failure_layer = "envelope"
        else:
            kind = "fenced_json"
            start = left + match.start("body")
            end = left + match.end("body")
    payload = raw[start:end] if failure_layer is None else None
    diagnostic = {
        "protocol": PROTOCOL,
        "envelope_kind": kind,
        "raw_utf8_sha256": hashlib.sha256(raw.encode("utf-8", "surrogatepass")).hexdigest(),
        "payload_utf8_sha256": (hashlib.sha256(payload.encode("utf-8", "surrogatepass")).hexdigest()
                                if payload is not None else None),
        "payload_byte_start": (len(raw[:start].encode("utf-8", "surrogatepass"))
                               if payload is not None else None),
        "payload_byte_end": (len(raw[:end].encode("utf-8", "surrogatepass"))
                             if payload is not None else None),
    }
    if failure_layer is not None:
        if record:
            record({**diagnostic, "failure_layer": failure_layer,
                    "error_code": "malformed_output"})
        raise ContractError("malformed_output", "model_envelope")
    try:
        value = strict_loads(payload)
        if type(value) is not dict:
            raise ContractError("wrong_object_type")
    except ContractError as error:
        if record:
            record({**diagnostic, "failure_layer": "json", "error_code": error.code})
        raise
    if record:
        record({**diagnostic, "failure_layer": None, "error_code": None})
    return value
