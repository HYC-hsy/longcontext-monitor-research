"""Graded visible-source association. No grade establishes semantic support.

Legacy literal alignment is unchanged. Only quotes without literal candidates
enter formatting normalization, then bounded upstream LCS candidate discovery.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re

from gap_evidence import BoundRef, sha256
from gap_evidence_alignment import align_evidence, _validate_catalog
from vendor.langextract_3a68580.alignment import _find_token_occurrences
from vendor.langextract_3a68580.tokenizer import RegexTokenizer
from vendor.langextract_3a68580.fuzzy import _best_lcs_spans, _accept_lcs_match

FUZZY_WORK_LIMIT = 2_000_000


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
                if _OMISSION.search(visible.snapshot.blob.text[start:stop]):
                    continue
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
        return bool(quote.strip()) and not _OMISSION.search(quote) and not _OMISSION.search(excerpt) and (
            normalize_formatting(quote)[0] == normalize_formatting(excerpt)[0])
    if status == "fuzzy_candidate" and quote and not _OMISSION.search(quote) and not _OMISSION.search(excerpt):
        source, _ = _tokens(excerpt)
        target, _ = _tokens(quote)
        if len(source) * len(target) ** 2 > FUZZY_WORK_LIMIT:
            return False
        return any(_accept_lcs_match(span, len(target))
                   for span in _best_lcs_spans(source, target).values())
    return False


def _tokens(text):
    tokens = RegexTokenizer().tokenize(text).tokens
    return [text[t.char_interval.start_pos:t.char_interval.end_pos] for t in tokens], tokens


def _fuzzy_candidates(quote, catalog, budget):
    target, _ = _tokens(quote)
    refs, details = {}, []
    skipped, searched, used = 0, 0, 0
    for visible in catalog.values():
        for offset, end in visible.visible_spans:
            chunk = visible.snapshot.blob.text[offset:end]
            source, tokens = _tokens(chunk)
            work = len(source) * len(target) ** 2
            if work > budget - used:
                skipped += 1
                continue
            used += work
            searched += 1
            # No upstream lowercasing/stemming: raw lexical equality is only a
            # locator, never proof. Upstream discards duplicate equal spans.
            spans = _best_lcs_spans(source, target)
            for count in sorted(spans, reverse=True):
                span = spans[count]
                if not _accept_lcs_match(span, len(target)):
                    continue
                start = offset + tokens[span.start].char_interval.start_pos
                stop = offset + tokens[span.end].char_interval.end_pos
                if _OMISSION.search(visible.snapshot.blob.text[start:stop]):
                    continue
                ref = _ref(visible, start, stop)
                if ref not in refs:
                    refs[ref] = None
                    details.append({"source_id": ref.source_id, "start": start, "end": stop,
                                    "original_excerpt": visible.snapshot.blob.text[start:stop],
                                    "difference": "lexical_lcs_candidate_not_semantic_verification",
                                    "matches": span.matches, "extraction_tokens": len(target),
                                    "coverage": span.matches / len(target),
                                    "density": span.matches / span.span_len})
                # Best acceptable span per chunk, not exhaustive alternatives.
                break
    state = "partial" if skipped and searched else "not_searched" if skipped else "complete"
    return tuple(refs), {"algorithm": "langextract_lcs_raw_tokens",
                         "candidate_enumeration": "non_exhaustive",
                         "candidate_details": details,
                         "fuzzy_search": {"status": state, "work_limit": FUZZY_WORK_LIMIT,
                                          "work_used": used, "skipped_chunks": skipped,
                                          "searched_chunks": searched}}, used


def align_graded_evidence(evidence, catalog):
    _validate_catalog(catalog)
    literal = align_evidence(evidence, catalog)
    items, refs = [], {}
    remaining_work = FUZZY_WORK_LIMIT
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
                else:
                    candidates, metadata, used = _fuzzy_candidates(item.quote, catalog, remaining_work)
                    remaining_work -= used
                    if candidates:
                        status, reason = "fuzzy_candidate", None
                    elif metadata["fuzzy_search"]["skipped_chunks"]:
                        reason = "approximate_work_limit_not_searched"
        items.append(GradedQuoteAlignment(item.quote, item.source_hint, status,
                                          reason, candidates, metadata))
        refs.update(dict.fromkeys(candidates))
    status = aggregate_status(items)
    reason = "no_evidence" if not items else "unbound_quotes" if status == "unbound" else None
    return GradedEvidenceAlignment(status, reason, tuple(items), tuple(refs))


def quote_metadata_valid(item, resolver):
    """Validate serialized metadata against retained original source slices.

    Full-catalog search completeness cannot be reconstructed from retained refs;
    fuzzy search counts are bounded diagnostics, not a uniqueness guarantee.
    Source integrity and BoundRef validity are checked by the owning store.
    """
    try:
        status, quote = item["status"], item["quote"]
        metadata = item.get("metadata", {})
        if status.startswith("exact_"):
            return metadata == {}
        if status == "unbound":
            if not metadata:
                return True
            return (not metadata.get("candidate_details") and
                    _search_metadata_valid(metadata))
        candidates = item["candidates"]
        details = metadata["candidate_details"]
        if len(details) != len(candidates) or not candidates:
            return False
        normalized = status in {"normalized_unique", "normalized_multiple"}
        if normalized:
            if set(metadata) != {"normalization", "quote_transforms", "candidate_details"}:
                return False
            if metadata["normalization"] != "controlled_ascii_continuation_v1":
                return False
            if metadata["quote_transforms"] != normalize_formatting(quote)[2]:
                return False
        elif status != "fuzzy_candidate" or not _search_metadata_valid(metadata):
            return False
        for ref, detail in zip(candidates, details):
            visible = resolver[ref["visibility_ref"]]
            excerpt = visible.snapshot.blob.text[ref["start"]:ref["end"]]
            expected = {"source_id": ref["source_id"], "start": ref["start"],
                        "end": ref["end"], "original_excerpt": excerpt}
            if normalized:
                expected.update(difference="formatting_only_not_semantic_verification",
                                source_transforms=normalize_formatting(excerpt)[2])
            else:
                source, _ = _tokens(excerpt)
                target, _ = _tokens(quote)
                if len(source) * len(target) ** 2 > FUZZY_WORK_LIMIT:
                    return False
                spans = _best_lcs_spans(source, target)
                accepted = [spans[k] for k in sorted(spans, reverse=True)
                            if _accept_lcs_match(spans[k], len(target))]
                if not accepted:
                    return False
                span = accepted[0]
                expected.update(difference="lexical_lcs_candidate_not_semantic_verification",
                                matches=span.matches, extraction_tokens=len(target),
                                coverage=span.matches / len(target),
                                density=span.matches / span.span_len)
            if detail != expected:
                return False
        return True
    except (KeyError, TypeError, AttributeError, IndexError):
        return False


def _search_metadata_valid(metadata):
    if set(metadata) != {"algorithm", "candidate_enumeration", "candidate_details", "fuzzy_search"}:
        return False
    if metadata["algorithm"] != "langextract_lcs_raw_tokens" or metadata["candidate_enumeration"] != "non_exhaustive":
        return False
    search = metadata["fuzzy_search"]
    if set(search) != {"status", "work_limit", "work_used", "skipped_chunks", "searched_chunks"}:
        return False
    if any(type(search[k]) is not int or search[k] < 0
           for k in ("work_limit", "work_used", "skipped_chunks", "searched_chunks")):
        return False
    if search["work_limit"] != FUZZY_WORK_LIMIT or search["work_used"] > FUZZY_WORK_LIMIT:
        return False
    expected = ("partial" if search["skipped_chunks"] and search["searched_chunks"] else
                "not_searched" if search["skipped_chunks"] else "complete")
    return search["status"] == expected
