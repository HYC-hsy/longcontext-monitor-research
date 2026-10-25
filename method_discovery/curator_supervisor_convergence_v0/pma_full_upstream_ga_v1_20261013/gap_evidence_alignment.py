"""Host-owned, visible-only evidence alignment, not semantic verification.

Genuine LangExtract token candidates/character offsets are reused; see the
vendored REUSE.md. Unlike its ordered DP, retain every literal candidate.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from gap_evidence import (
    BoundRef, SourceScopeError, VisibleSource, _digest, _key, _require,
    _snapshot_valid, _text, sha256,
)
from vendor.langextract_3a68580.alignment import (
    _find_token_occurrences, _tokenize_with_lowercase,
)
from vendor.langextract_3a68580.tokenizer import RegexTokenizer


@dataclass(frozen=True)
class QuoteAlignment:
    quote: str
    source_hint: str | None
    status: str
    reason: str | None
    candidates: tuple[BoundRef, ...]


@dataclass(frozen=True)
class EvidenceAlignment:
    status: str
    reason: str | None
    items: tuple[QuoteAlignment, ...]
    bound_refs: tuple[BoundRef, ...]


def _validate_catalog(catalog):
    _require(isinstance(catalog, Mapping), "invalid_source_catalog")
    requests = set()
    for handle, visible in catalog.items():
        _require(_text(handle) and isinstance(visible, VisibleSource),
                 "invalid_visible_source")
        try:
            _require(_snapshot_valid(visible.snapshot), "invalid_source_snapshot")
            row, text = visible.snapshot.record, visible.snapshot.blob.text
            _require(visible.display_transform == "literal" and
                     _text(visible.cycle_id) and _digest(visible.request_sha256),
                     "invalid_visible_source")
            spans = visible.visible_spans
            _require(bool(spans) and all(len(s) == 2 and
                     all(type(i) is int for i in s) and
                     0 <= s[0] < s[1] <= len(text) for s in spans),
                     "invalid_visible_spans")
            _require(visible.visibility_ref == sha256(_key(
                visible.cycle_id, visible.request_sha256, row.source_id, spans)),
                "invalid_visibility_ref")
            _require(row.source_kind == "memory" or handle == row.handle,
                     "public_alias_forbidden")
            requests.add((visible.cycle_id, visible.request_sha256))
        except (AttributeError, TypeError, IndexError) as exc:
            raise SourceScopeError("invalid_visible_source") from exc
    _require(len(requests) <= 1, "mixed_request_catalog")


def _literal_intervals(quote, chunk, tokenized, source_tokens, quote_tokens):
    """Upstream token locations plus exhaustive literal completion.

    Upstream lowercase/whitespace token equality is only a locator. Postcheck
    every candidate. Literal completion covers substrings inside a token,
    whitespace-only strings and overlapping repeated punctuation. It does not
    normalize the quote or inspect anything outside the supplied visible chunk.
    """
    intervals = set()
    for start in _find_token_occurrences(source_tokens, quote_tokens):
        # Adapted from resolver.py:1275-1281, without monotonic selection.
        start_token = tokenized.tokens[start]
        end_token = tokenized.tokens[start + len(quote_tokens) - 1]
        a = start_token.char_interval.start_pos
        b = end_token.char_interval.end_pos
        if chunk[a:b] == quote:
            intervals.add((a, b))
    # The same unmodified upstream Sequence matcher also accepts strings as
    # character sequences. This completes cases the word tokenizer cannot
    # represent; no independent handwritten substring matcher is used.
    for start in _find_token_occurrences(chunk, quote):
        intervals.add((start, start + len(quote)))
    return sorted(intervals)


def align_evidence(evidence, catalog) -> EvidenceAlignment:
    """Return per-quote exact_unique/exact_multiple/unbound, never guessed IDs.

    Evidence is a list of {quote: str, source?: nonempty str}. The source hint
    is retained for diagnostics only: it neither filters nor ranks candidates.
    Multiple matches preserve all typed origins and positions. Partial success
    retains found refs but aggregate status is unbound. Empty evidence is a
    normal no_evidence result. Malformed input or source integrity errors raise
    SourceScopeError before returning any result. No I/O, model calls or fuzzy
    evidence promotion occurs here.
    """
    _require(isinstance(evidence, list), "invalid_evidence")
    for item in evidence:
        _require(isinstance(item, dict) and "quote" in item and
                 set(item) <= {"quote", "source"} and
                 isinstance(item["quote"], str) and
                 ("source" not in item or _text(item["source"])),
                 "invalid_evidence_item")
    _validate_catalog(catalog)
    if not evidence:
        return EvidenceAlignment("unbound", "no_evidence", (), ())
    tokenizer = RegexTokenizer()
    # Request-local cache only; every chunk retains its original typed source.
    chunks = []
    for visible in catalog.values():
        for a, b in visible.visible_spans:
            chunk = visible.snapshot.blob.text[a:b]
            tokens = tokenizer.tokenize(chunk)
            lowercase = [chunk[t.char_interval.start_pos:t.char_interval.end_pos].lower()
                         for t in tokens.tokens]
            chunks.append((visible, a, chunk, tokens, lowercase))
    items, all_refs = [], {}
    for item in evidence:
        quote = item["quote"]
        refs = {}
        if quote:
            quote_hash = sha256(quote)
            quote_tokens = list(_tokenize_with_lowercase(quote))
            for visible, offset, chunk, tokens, lowercase in chunks:
                row = visible.snapshot.record
                for a, b in _literal_intervals(quote, chunk, tokens, lowercase, quote_tokens):
                    ref = BoundRef(row.source_id, row.source_kind, row.role, row.order,
                                   offset + a, offset + b, row.text_sha256,
                                   quote_hash, visible.visibility_ref,
                                   row.parent_revision_id, row.parent_wrapper_source_id)
                    refs[ref] = None
        candidates = tuple(refs)
        status = "unbound" if not candidates else (
            "exact_unique" if len(candidates) == 1 else "exact_multiple")
        reason = ("empty_quote" if not quote else "quote_not_visible") if not candidates else None
        items.append(QuoteAlignment(quote, item.get("source"), status, reason, candidates))
        all_refs.update(refs)
    status = "unbound" if any(i.status == "unbound" for i in items) else (
        "exact_multiple" if any(i.status == "exact_multiple" for i in items) else "exact_unique")
    reason = "unbound_quotes" if status == "unbound" else None
    return EvidenceAlignment(status, reason, tuple(items), tuple(all_refs))
