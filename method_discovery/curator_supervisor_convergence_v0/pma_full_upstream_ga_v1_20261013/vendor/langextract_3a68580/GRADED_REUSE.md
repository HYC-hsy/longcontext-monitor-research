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
LCS helpers on raw RegexTokenizer tokens in ranked windows within each original visible span. Its default
coverage >= .75 and density >= 1/3 are unchanged. It takes the highest accepted
match-count span in each chunk. Upstream's best-span-per-count selection discards
duplicates. Consequently fuzzy output is ALWAYS `fuzzy_candidate`, explicitly
non-exhaustive, never unique/exact/proof. All located candidates retain source
identity and original character offsets. A source hint never filters or ranks.
The quote and approximate source excerpts must not contain omission markers;
separate visible spans never join, including adjacent spans.

The first version copied the LCS helpers without the upstream pipeline's known,
bounded-source premise. Upstream annotation.py:398-431 pairs each model result
with its text_chunk, then resolver.py:1062-1099 aligns within that chunk. Its
extraction.py default max_char_buffer is 1000, not an across-source LCS budget.
PMA model output covers multiple sources, so cross-source candidate selection is
an explicit local adaptation, not an upstream feature.

The window adapter now directly reuses `create_token_interval` from upstream
chunking.py:143-166 and `get_char_interval`:216-243 (only CharInterval import
changes). `iter_fragment_intervals` adapts ChunkIterator.__next__:441-484's
newline/token splitting and indivisible-long-token rule. It omits prose sentence
grouping, Document/framework dependencies, and all model calls. Base fragments
use 1000 characters; each expands by 3*m-1 tokens on either side, where m is the
quote token count. Expansion stays inside one original visible span. An accepted
LCS span has at most 3*m tokens under the unchanged density >=1/3 rule, protecting
matches across base-fragment boundaries; a very long window can still be skipped
by the computational budget. No fixed 1000-character limit is imposed on quotes.

Local candidate selection first computes multiset token overlap, a cheap upper
bound on LCS matches. Windows below ceil(.75*m) cannot pass the unchanged upstream
coverage rule and are pruned. Others are ranked by overlap/quote length, then
overlap/window length, with source ID and original offsets as deterministic tie
breaks. No top-k candidates are silently discarded. Source hints do not rank.

LCS still costs O(n*m²) time and O(m²) memory. The existing deterministic
2,000,000-cell budget remains shared across quotes in one invocation; it is not
an upstream parameter or model token limit. Budget-skipped windows are explicitly
`not_searched`/`partial`. `candidate_selection` records generated and safely
lexically pruned windows; the old `searched_chunks`/`skipped_chunks` names count
candidate windows on this path. Counts must sum consistently. `complete` means
all generated viable windows were searched, NOT exhaustive possible alignments;
upstream returns only its preferred span per match count. Old metadata remains
readable. Earlier quotes can still consume the shared budget; this change does
not promise exhaustive cross-quote recall or semantic correctness.

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
