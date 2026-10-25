# LangExtract alignment reuse, pinned subset

Upstream: https://github.com/google/langextract/tree/3a68580f0aede0e96a2e1e03daa2a5f4011e4fcd

License: Apache-2.0, full upstream LICENSE included. Source headers retained.
The pinned repository's root NOTICE URL returned 404; no separate root notice was found.
UPSTREAM.json records full original source SHA256 and upstream test SHA256.
The original sources were independently fetched from pinned raw GitHub URLs.
The pre-existing research copies differ from these only in an extra trailing newline.

## Actual reused code, not conceptual attribution

- `tokenizer.py`: original `langextract/core/tokenizer.py:65-246` offset/token
  dataclasses, TokenType, Tokenizer interface, regular-expression definitions,
  RegexTokenizer implementation, default instance and tokenize wrapper.
  Modification: remove the debug-log decorator/import; omit unrelated exceptions,
  public export list, UnicodeTokenizer and sentence-detection implementation.
  The regex engine remains upstream's `regex`, not a rewritten stdlib substitute.
- `alignment.py`: original `langextract/resolver.py:1115-1133`
  `_find_token_occurrences`, verbatim. Original `:1287-1311`
  `_tokenize_with_lowercase`, verbatim; local imports point to the vendored tokenizer.
- `gap_evidence_alignment.py::_literal_intervals`: adapts original resolver
  `:1275-1281` first/last token to original-character offsets. Applies the visible
  chunk's offset when constructing BoundRef. End indices remain exclusive Python
  Unicode string indices, not bytes or UTF-16 code units.
- `tests/test_gap_langextract_alignment_reuse.py`: adapted original
  `tests/tokenizer_test.py:44-157` fixtures and `tests/resolver_test.py:2608-2619`
  repeated-aspirin fixture. Changed absl assertions to stdlib unittest; repeated
  mentions assert candidate preservation, deliberately not upstream DP assignment.
  This small adapted test set is not execution of LangExtract's full test suite.

Runtime path actually executes the vendored tokenizer and candidate enumeration
for each nonempty quote against each separately visible source chunk. A test
spies on the imported upstream candidate function to verify this seam executes.
This is selected alignment-code reuse, not reuse of LangExtract's full extraction
pipeline, model/provider layer, monotonic assignment DP, partial matcher or fuzzy
matcher. The only new dependency is `regex==2026.9.29`.

## Deliberate host adapter policies

LangExtract's token-exact status is lowercase token equality and ignores spacing.
It is therefore insufficient to establish that a quote is an original literal
substring. Every token candidate is postchecked against original characters.

Tokenization also cannot enumerate every possible literal quote: whitespace-only
quotes have no tokens; `ana` occurs twice inside the single token `banana`; `!!`
can overlap inside the upstream grouped punctuation token `!!!!`. The adapter
therefore unions token-derived, postchecked intervals with an exhaustive literal
character-sequence matching using the SAME unmodified upstream
`_find_token_occurrences(chunk, quote)` helper. Python strings satisfy its
`Sequence[str]` contract. This character-granularity invocation is an adapter
choice, not a claimed feature of LangExtract’s default resolver. It is the
authoritative exhaustive candidate path; the token path retains upstream
word-location behavior, but does not by itself guarantee complete coverage. It preserves leading/trailing
whitespace, punctuation overlaps and code-point offsets without normalization.

The upstream monotonic DP is intentionally not copied: memory evidence is not
necessarily emitted in document order, and choosing a deterministic occurrence
would conceal ambiguity between differently typed origins. All candidates are
retained, without an arbitrary cap. Exact identical refs are deduplicated; distinct
positions, roles, sources and revision lineages are not. Neither a repeated quote
nor multiple candidates constitute independent semantic support.

No fuzzy/partial match is promoted to bound evidence. No registry-wide hidden
source search, hidden gap join, rendered marker join, source-hint filtering or
fallback to an unshown raw wrapper is permitted. Each visible span is its own
chunk, even where source-coordinate spans are adjacent. Previous memory remains
`source_kind=memory`, `role=memory_derived` with its parent revision, never public
firsthand evidence. Host-owned source digests and sealed visibility are validated
before alignment; integrity and shape errors remain errors.

## API

`align_evidence(evidence, catalog) -> EvidenceAlignment`

- Input: list of `{quote: str, source?: nonempty str}`. Omitted source is normal.
  A supplied source is only an auditable hint, including a stale/unknown hint;
  it cannot discard other candidates or resolve ambiguity.
- Output `items`: one QuoteAlignment per input, with unchanged quote, source_hint,
  status, reason and all candidate BoundRefs.
- Item statuses: exact_unique, exact_multiple, unbound. Empty quote returns
  unbound/empty_quote; unmatched nonempty quote returns unbound/quote_not_visible.
  Literal whitespace is treated literally, not silently stripped.
- Aggregate: unbound if any item is unbound; otherwise exact_multiple if any item
  is multiple; otherwise exact_unique. Empty evidence is unbound/no_evidence.
- `bound_refs` is the union of all successful per-quote candidates EVEN WHEN the
  aggregate is unbound. It is not an all-evidence-success flag. Consumers must
  retain item/aggregate status and must not promote a partially aligned record
  into a fully bound assertion.

Exact alignment establishes where text occurs in the model-visible snapshots.
It does not establish the model's intended source or that a claim follows from
that text. Source association, semantic truth, provisional memory policy and
runtime decision authority are separate concerns.

## Offline checks

`python -m unittest discover -s tests -p '*alignment*.py' -v`

With the parent directory and installed requirements on Python's import path,
16 test methods pass, including malformed shapes/source-integrity rejection,
empty/partial outcomes, multiple typed origins, hints, Unicode, whitespace,
subtoken/punctuation overlaps, visible boundaries, derived memory, no candidate
cap, actual upstream helper execution and the adapted upstream fixtures.
No model calls or online effectiveness experiment were run.

Local cost check (CPython 3.12, 2026-10-25; one invocation per case, not a
statistical benchmark): a 95,780-character synthetic structured log with literal
quotes of 32 / 512 / 4096 characters took 0.118 / 0.128 / 0.161 seconds, each with
one candidate. An adversarial 10,000-character all-`a` source and 512-character
quote produced all 9,489 overlapping candidates in 0.037 seconds. The inherited
candidate helper is worst-case O(source_length × quote_length) with a first-item
filter; this is not a claim of linear worst-case complexity. No arbitrary match
cap is applied to hide its output or cost.

The reproducible cost probe is `tests/benchmark_gap_evidence_alignment.py`;
`LOCAL_COST_CHECK.json` stores the latest local measurements. It also exercises
10k/100k repeated-punctuation sources with 2/512-character quotes, preserving all
overlapping candidates. This deliberately tests the grouped-punctuation fallback.
