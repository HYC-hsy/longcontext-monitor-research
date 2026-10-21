"""Immutable host sources and request-local, literal evidence bindings."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


class ContractError(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code + (": " + detail if detail else ""))
        self.code = code


def canonical(value: object) -> bytes:
    """Canonical JSON bytes: sorted keys, original array order, UTF-8, no NaN."""
    def check(item: object) -> None:
        if isinstance(item, str):
            if any(0xD800 <= ord(char) <= 0xDFFF for char in item):
                raise ContractError("invalid_unicode")
        elif isinstance(item, dict):
            if any(not isinstance(key, str) for key in item):
                raise ContractError("non_string_key")
            for key, value in item.items():
                check(key)
                check(value)
        elif isinstance(item, list):
            for value in item:
                check(value)
        elif isinstance(item, float):
            raise ContractError("non_integer_metadata", "floating JSON values are not canonical")
        elif item is not None and not isinstance(item, (bool, int)):
            raise ContractError("unsupported_json_value", type(item).__name__)
    check(value)
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def strict_loads(raw: str) -> object:
    def pairs(items: list[tuple[str, object]]) -> dict:
        result = {}
        for key, value in items:
            if key in result:
                raise ContractError("duplicate_key", key)
            result[key] = value
        return result
    def constant(value: str) -> None:
        raise ContractError("nonstandard_constant", value)
    try:
        value = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, TypeError) as error:
        if isinstance(error, ContractError):
            raise
        raise ContractError("malformed_output", type(error).__name__) from error
    canonical(value)
    return value


def fields(value: object, required: set[str], optional: set[str] | None = None) -> dict:
    if type(value) is not dict:
        raise ContractError("wrong_object_type")
    actual = set(value)
    missing = required - actual
    extra = actual - required - (optional or set())
    if missing or extra:
        raise ContractError("schema_fields", f"missing={sorted(missing)} extra={sorted(extra)}")
    return value


def nonempty(value: object, name: str) -> str:
    if type(value) is not str or not value:
        raise ContractError("invalid_text", name)
    canonical(value)
    return value


def integer(value: object, name: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ContractError("invalid_integer", name)
    return value


SOURCE_KINDS = {"user_requirement", "user_report", "executed_action",
                "tool_result", "agent_report"}


def validate_leaf(leaf: object) -> dict:
    leaf = fields(leaf, {"source_id", "event_id", "field_path", "source_kind",
                         "ga_turn", "event_seq", "truncated", "text", "text_sha256"})
    for name in ("source_id", "event_id", "field_path"):
        nonempty(leaf[name], name)
    if leaf["source_kind"] not in SOURCE_KINDS:
        raise ContractError("invalid_source_kind")
    integer(leaf["ga_turn"], "ga_turn")
    integer(leaf["event_seq"], "event_seq")
    if type(leaf["truncated"]) is not bool or type(leaf["text"]) is not str:
        raise ContractError("invalid_source_field")
    expected = hashlib.sha256(leaf["text"].encode("utf-8")).hexdigest()
    if leaf["text_sha256"] != expected:
        raise ContractError("source_hash_mismatch", leaf["source_id"])
    canonical(leaf)
    return leaf


def validate_source_ref(ref: object, ledger: dict[str, dict], *,
                        allowed_kinds: set[str] | None = None) -> dict:
    ref = fields(ref, {"source_id", "start", "end", "quote"})
    source_id = nonempty(ref["source_id"], "source_id")
    start = integer(ref["start"], "start")
    end = integer(ref["end"], "end", 1)
    quote = nonempty(ref["quote"], "quote")
    leaf = ledger.get(source_id)
    if leaf is None:
        raise ContractError("source_unavailable", source_id)
    if allowed_kinds is not None and leaf["source_kind"] not in allowed_kinds:
        raise ContractError("source_role_misuse", source_id)
    if end <= start or end > len(leaf["text"]) or leaf["text"][start:end] != quote:
        raise ContractError("quote_mismatch", source_id)
    return ref


@dataclass(frozen=True)
class VisibleSpan:
    evidence_id: str
    source_id: str
    start: int
    end: int
    source_window_id: str
    purpose: str
    exact_stored_ref: bool = False


class SourceCatalog:
    """A request-specific map; a cache hit never skips visibility or role checks."""

    def __init__(self, ledger: dict[str, dict], window_id: str) -> None:
        self.ledger = ledger
        self.window_id = nonempty(window_id, "source_window_id")
        self.visible: dict[str, VisibleSpan] = {}
        self.literal_cache: set[tuple] = set()

    def add(self, source_id: str, start: int, end: int, purpose: str,
            *, exact_stored_ref: bool = False) -> VisibleSpan:
        leaf = self.ledger.get(source_id)
        if leaf is None:
            raise ContractError("source_unavailable", source_id)
        integer(start, "start")
        integer(end, "end", 1)
        if start >= end or end > len(leaf["text"]):
            raise ContractError("invalid_visible_span", source_id)
        nonempty(purpose, "purpose")
        identity = [source_id, leaf["text_sha256"], start, end, self.window_id,
                    purpose, exact_stored_ref]
        evidence_id = "ev_" + digest(identity)[:24]
        span = VisibleSpan(evidence_id, source_id, start, end, self.window_id,
                           purpose, exact_stored_ref)
        previous = self.visible.get(evidence_id)
        if previous is not None and previous != span:
            raise ContractError("evidence_id_collision")
        self.visible[evidence_id] = span
        return span

    def resolve(self, ref: object, *, purpose: str,
                allowed_kinds: set[str] | None = None) -> dict:
        ref = fields(ref, {"evidence_id", "quote"})
        evidence_id = nonempty(ref["evidence_id"], "evidence_id")
        quote = nonempty(ref["quote"], "quote")
        span = self.visible.get(evidence_id)
        if span is None or span.source_window_id != self.window_id:
            raise ContractError("invisible_reference", evidence_id)
        if span.purpose != purpose:
            raise ContractError("source_purpose_mismatch", evidence_id)
        leaf = self.ledger[span.source_id]
        if allowed_kinds is not None and leaf["source_kind"] not in allowed_kinds:
            raise ContractError("source_role_misuse", span.source_id)
        domain = leaf["text"][span.start:span.end]
        positions = [index for index in range(len(domain) - len(quote) + 1)
                     if domain.startswith(quote, index)]
        if not positions:
            raise ContractError("quote_mismatch", evidence_id)
        if len(positions) != 1:
            raise ContractError("ambiguous_quote", evidence_id)
        local_start = positions[0]
        result = {"source_id": span.source_id, "start": span.start + local_start,
                  "end": span.start + local_start + len(quote), "quote": quote}
        cache_key = (span.source_id, leaf["text_sha256"],
                     "decoded-unicode-codepoint-v1", result["start"], result["end"],
                     hashlib.sha256(quote.encode("utf-8")).hexdigest())
        self.literal_cache.add(cache_key)
        return result
