# Latest memory revisions and graded source alignment

## Scope and version

User-approved engineering change, not a new semantic judge. Existing `pma-gap-evidence / pma_gap_evidence_v1` selects `LatestEvidenceGapMemoryAgent` and `LatestEvidenceGapMemory`. Runtime policy: `latest_revision_with_graded_alignment_v1`; persisted alignment schema: 2. Ordinary PMA, ordinary PMA-gap and the pinned PMA vendor are unchanged. Strict and alignment-v2 classes remain available for historical archives and regression tests.

Five tools and maintenance → selection remain. No additional LLM request, review/repair stage, completion veto, task-specific validation rule, or experiment authorization is introduced.

## One current object per stable ID

`save(content, memory_id?, evidence?)` creates or revises one memory. Every valid content update becomes the latest revision, independently of evidence alignment. An update's previous revision records edit history, not proof inheritance. Old revisions remain immutable history. No new pending proposal is created or displayed; saving does not implicitly delete another memory. `memory_delete` explicitly retires the selected entry; `memory_update_status` replaces only status.

Content and binding are logically separate results, published atomically together. A malformed evidence field yields committed content plus binding `error`, not a half-written record or silent `no_evidence`. Invalid content, target/category, tool envelope, source catalog, hashes, manifests or revision integrity still fail the operation. The XML path catches only evidence JSON decoding failure after the original shape validation and reuses the original parser with a sentinel. Other parsing errors are not swallowed.

Operations remain individually atomic. No whole-batch rollback or inferred dependency grouping is added. An actually invalid content update followed by an explicit delete can still delete its target; no dependency was declared. Revising content must use the existing ID, not delete-and-save. The previously observed citation-failure/pending/delete chain disappears because valid new content now becomes latest even when its citation is unbound.

## Citation grades and provenance

1. `exact_unique` / `exact_multiple`: original literal matching, unchanged.
2. `normalized_unique` / `normalized_multiple`: exact search after controlled ASCII whitespace and backslash-newline continuation folding. Original Unicode character-coordinate mapping remains. No general escape decoding, case folding, stemming, punctuation deletion or Unicode normalization is used here.
3. `fuzzy_candidate`: pinned LangExtract LCS span discovery with coverage 0.75 and density 1/3. Raw token strings preserve case and punctuation. This is approximate location, not semantic support and not exhaustive uniqueness. See `../vendor/langextract_3a68580/GRADED_REUSE.md` for exact upstream functions and exclusions.
4. `unbound`: no eligible match, missing evidence, omission marker, or explicitly incomplete approximate search. Reasons remain separate.
5. `error`: malformed evidence input; valid content remains latest.

The source excerpt and its SHA-256 always come from the actual original `source[start:end]`, not the model quote or normalized text. The submitted quote is separately retained. Every matched ref preserves role, event order, field, visibility and parent revision. Visibility spans are never joined across a hidden gap. Approximate association refuses omission-marker composites.

Fuzzy DP has a 2,000,000 estimated-cell work bound per evidence operation because the reused kernel is O(n*m²). Skipped work is explicitly `not_searched`, not a complete negative search or a Task failure. This is a local algorithm cost bound, not a model token, episode time, request-count or research-budget limit. Scores are text matching statistics, not truth probabilities.

All candidate positions persist. Prompt rendering displays at most three original candidate excerpts, explicitly says when others are retained, and never calls a fuzzy result unique. A clean original candidate is not erased merely because another alternative is unbound derived memory; both source kinds remain recorded. Literal association with a derived memory remains derived, not fresh observation. No grade proves the claim is correct.

## Persistence and compatibility

A fresh empty original PMA bank may initialize the new policy. Populated plain banks, alignment-v2 banks and active pending proposals are not silently migrated or adopted. Load historical archives with their original classes. New real episodes start with fresh memory, so developer reception needs no historical migration tool. Certification dispatches to the correct loader by policy; source identity includes all new runtime and upstream helper files.

## Evidence and limitations

See ACCEPTANCE.md and replay_README.md. Actual C8 quotations are offline development cases, not holdout evidence. Their successful normalized association does not imply better Task outcomes. Public-redacted archives cannot support an identical full-original-catalog replay. This patch changes provenance handling only; task-score and semantic-completion problems are outside scope.
