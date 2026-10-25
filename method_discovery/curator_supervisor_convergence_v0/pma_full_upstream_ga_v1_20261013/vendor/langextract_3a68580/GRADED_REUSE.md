# Graded association extension (legacy literal API unchanged)

Upstream remains Google LangExtract commit
`3a68580f0aede0e96a2e1e03daa2a5f4011e4fcd`, Apache-2.0.
`fuzzy.py` copies `LcsSpan`, `_best_lcs_spans`, `_accept_lcs_match` verbatim
from the pinned `langextract/resolver.py`, retaining copyright/license header.
Only imports/default constants are reduced to this subset. It does NOT copy
`_normalize_token`: no casefold or stemming is performed by the graded adapter.
The source SHA and pinned repository identity remain those in UPSTREAM.json.

`graded_evidence_alignment.align_graded_evidence` first calls the unchanged
legacy literal API. All exact candidates remain exhaustive and unchanged. Only
quotes with zero exact candidates try controlled ASCII whitespace and actual
backslash-newline continuation normalization. Literal backslash-n/backslash-t
sequences are NOT decoded, including in paths or C strings. Unicode composition,
case, punctuation, negation, numbers and identifiers are not normalized.
Each normalized character maps to its original start/end character indices;
BoundRef hashes the actual source slice, while the model quote stays separate.
Normalization is formatting association, not semantic equivalence: whitespace
and continuations can matter in programming languages.

Only if normalization finds no candidate does the adapter execute the upstream
LCS helpers on raw RegexTokenizer tokens per original visible chunk. Its default
coverage >= .75 and density >= 1/3 are unchanged. It takes the highest accepted
match-count span in each chunk. Upstream's best-span-per-count selection discards
duplicates. Consequently fuzzy output is ALWAYS `fuzzy_candidate`, explicitly
non-exhaustive, never unique/exact/proof. All located candidates retain source
identity and original character offsets. A source hint never filters or ranks.
The quote and approximate source excerpts must not contain omission markers;
separate visible spans never join, including adjacent spans.

LCS costs O(n*m²) time and O(m²) memory. A deterministic 2,000,000-cell budget is
shared across all quotes in one invocation. Each chunk is searched whole only
if its estimated `n*m*m` fits the remaining budget. No partial/window search is
silently substituted. Skipped chunks are explicitly `not_searched`/`partial`;
unbound with skips means `approximate_work_limit_not_searched`, not proven miss.
The limit never fails the surrounding task or the legacy exact path.

The new dataclasses preserve the legacy fields with item-level metadata added.
Status precedence: unbound, fuzzy_candidate, normalized_multiple,
normalized_unique, exact_multiple, exact_unique. Candidate refs are associations,
not a statement that a stored claim is proven. Metadata contains actual source
excerpts, normalization/difference details or LCS coverage/density; no model call
or new semantic judge exists. `candidate_grade_valid` and `quote_metadata_valid`
validate grades and diagnostic details from retained original excerpts; they
cannot reprove original catalog completeness when unmatched sources were not
retained. Search counts remain bounded diagnostics, not evidence of uniqueness.

Offline tests include negation/number/path changes remaining fuzzy-only,
Unicode+CRLF offset/hash preservation, exhaustive normalized duplicates,
upstream helper execution, fuzzy duplicate non-uniqueness, work-limit reporting,
omission/hidden-boundary refusal, and metadata tamper rejection. These are
engineering checks, not online efficacy or semantic reliability evidence.
