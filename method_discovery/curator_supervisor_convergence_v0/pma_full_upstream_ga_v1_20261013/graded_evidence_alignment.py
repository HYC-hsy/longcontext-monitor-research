"""Graded visible-source association. No grade establishes semantic support.

Legacy literal alignment is unchanged. Only quotes without literal candidates
enter formatting normalization, then bounded upstream LCS candidate discovery.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re

from gap_evidence import BoundRef, sha256
from gap_evidence_alignment import align_evidence
from vendor.langextract_3a68580.alignment import _find_token_occurrences


@dataclass(frozen=True)
class GradedQuoteAlignment:
    quote: str
    source_hint: str | None
    status: str
    reason: str | None
    candidates: tuple[BoundRef, ...]
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class GradedEvidenceAlignment:
    status: str
    reason: str | None
    items: tuple[GradedQuoteAlignment, ...]
    bound_refs: tuple[BoundRef, ...]


# Deliberately not a general escape decoder: do not transform paths, arbitrary
# backslashes, case, punctuation, Unicode composition or language identifiers.
_FORMAT = re.compile(r"\\\r?\n[ \t]*|[ \t\r\n\f\v]+")
_OMISSION = re.compile(r"\[(?:hidden gap|omitted|truncated)(?:[^\]]*)\]|<omitted>|\.\.\.|…", re.I)


def normalize_formatting(text):
    """Return normalized text, per-character original intervals, transform names.

    Only ASCII whitespace and backslash-newline continuations fold to a space.
    Mapping is in Python Unicode code points; no hidden spans are concatenated.
    """
    chars, offsets, changes = [], [], set()
    position = 0
    for match in _FORMAT.finditer(text):
        for index in range(position, match.start()):
            chars.append(text[index])
            offsets.append((index, index + 1))
        value = match.group()
        change = ("line_continuation" if value.startswith("\\") else
                  "ascii_whitespace")
        if value != " ":
            changes.add(change)
        # Merge consecutive formatting runs, retaining their complete extent.
        if chars and chars[-1] == " " and offsets[-1][1] == match.start():
            offsets[-1] = (offsets[-1][0], match.end())
        else:
            chars.append(" ")
            offsets.append((match.start(), match.end()))
        position = match.end()
    for index in range(position, len(text)):
        chars.append(text[index])
        offsets.append((index, index + 1))
    return "".join(chars), offsets, sorted(changes)


def aggregate_status(items):
    statuses = {item.status if hasattr(item, "status") else item["status"] for item in items}
    for status in ("unbound", "fuzzy_candidate", "normalized_multiple", "normalized_unique",
                   "exact_multiple", "exact_unique"):
        if status in statuses:
            return status
    return "unbound"


def _ref(visible, start, end):
    row = visible.snapshot.record
    excerpt = visible.snapshot.blob.text[start:end]
    return BoundRef(row.source_id, row.source_kind, row.role, row.order,
                    start, end, row.text_sha256, sha256(excerpt),
                    visible.visibility_ref, row.parent_revision_id,
                    row.parent_wrapper_source_id)


def _normalized_candidates(quote, catalog):
    target, _, quote_changes = normalize_formatting(quote)
    refs, details = {}, []
    if not target.strip():
        return (), {}
    for visible in catalog.values():
        for offset, end in visible.visible_spans:
            chunk = visible.snapshot.blob.text[offset:end]
            normalized, mapping, changes = normalize_formatting(chunk)
            for index in _find_token_occurrences(normalized, target):
                start = offset + mapping[index][0]
                stop = offset + mapping[index + len(target) - 1][1]
                ref = _ref(visible, start, stop)
                if ref in refs:
                    continue
                refs[ref] = None
                excerpt = visible.snapshot.blob.text[start:stop]
                details.append({"source_id": ref.source_id, "start": start, "end": stop,
                                "original_excerpt": excerpt,
                                "difference": "formatting_only_not_semantic_verification",
                                "source_transforms": normalize_formatting(excerpt)[2]})
    return tuple(refs), {"normalization": "controlled_ascii_continuation_v1",
                         "quote_transforms": quote_changes, "candidate_details": details}


def candidate_grade_valid(quote, excerpt, status):
    """Check a claimed association grade, not uniqueness or semantic truth."""
    if status in {"exact_unique", "exact_multiple"}:
        return excerpt == quote
    if status in {"normalized_unique", "normalized_multiple"}:
        return bool(quote.strip()) and not _OMISSION.search(quote) and (
            normalize_formatting(quote)[0] == normalize_formatting(excerpt)[0])
    return False


def align_graded_evidence(evidence, catalog):
    literal = align_evidence(evidence, catalog)
    items, refs = [], {}
    for item in literal.items:
        candidates, metadata = item.candidates, {}
        status, reason = item.status, item.reason
        if not candidates and item.quote:
            if _OMISSION.search(item.quote):
                reason = "omission_marker_approximation_refused"
            else:
                candidates, metadata = _normalized_candidates(item.quote, catalog)
                if candidates:
                    status = "normalized_unique" if len(candidates) == 1 else "normalized_multiple"
                    reason = None
        items.append(GradedQuoteAlignment(item.quote, item.source_hint, status,
                                          reason, candidates, metadata))
        refs.update(dict.fromkeys(candidates))
    status = aggregate_status(items)
    reason = "no_evidence" if not items else "unbound_quotes" if status == "unbound" else None
    return GradedEvidenceAlignment(status, reason, tuple(items), tuple(refs))
