# Host-aligned evidence and explicitly unbound memory

## Scope and research boundary

This revision reduces mechanical source-selection burden without adding a model role, tool, review loop, task-completion veto, or benchmark change. The existing `pma-gap-evidence` entry continues to use the original maintenance -> selection schedule. Ordinary PMA and `pma-gap` remain unchanged. The previous strict classes remain available for historical regression; production construction selects the new aligned subclasses and records the alignment policy in telemetry. Source commit and policy must distinguish old and new experiments.

Literal grounding is NOT semantic verification. A successful file-write receipt cannot by itself establish implementation correctness. This revision intentionally does not implement a semantic judge.

## Model and host responsibilities

The five existing tools remain. Writers accept natural-language `content`, optional `evidence` items containing `quote`, optional `source` hints, and the existing optional target `memory_id` for an in-place revision. Missing/empty evidence is a legitimate unbound proposal, not an invented reference. Delete still requires the actual target ID. XML uses the same parsed arguments; no additional model round is introduced.

The host searches only typed original-text spans actually included in the current Phase 1 request. System instructions, formatting labels, examples, diagnostic messages and `[hidden gap]` are not original evidence. Hidden portions, future events, other episodes and unselected old memories are outside the search universe. Known JSON bodies are decoded by the established projection before both rendering and lookup.

A source hint does not restrict the search or establish authority. Wrong or unknown hints do not invalidate a quote found elsewhere in the eligible view. Record the supplied hint and the actual located candidates separately. A target memory ID is not a hint: nonexistent targets and category mismatches remain operation errors.

## Alignment contract

For each quoted text:

- `exact_unique`: one distinct literal occurrence in eligible spans.
- `exact_multiple`: multiple literal occurrences; retain all candidate positions and their distinct source roles. Do not claim a unique intended occurrence or independent corroboration.
- `unbound`: no literal occurrence, or no evidence was supplied. Preserve the model conclusion with an explicit unbound label and reason.

Each bound candidate retains the existing source identity, source type/role, event order, character interval, text/snippet hashes, visible-request binding and derived-memory ancestry. Duplicate entries for the identical source interval are deduplicated; identical text in different sources is not collapsed across roles.

The aggregate is unbound if any supplied quote is unbound. Matched candidates are still retained as diagnostic context; partially matched proposals are not advertised as completely grounded. Near/fuzzy matching is deliberately not enabled in this first revision. It may later be a locator aid, but must not silently become an exact quote.

## Actual upstream reuse

Pinned LangExtract commit: `3a68580f0aede0e96a2e1e03daa2a5f4011e4fcd`.

The implementation vendors actual tokenizer/character-offset code and `_find_token_occurrences` from LangExtract, with license, upstream hashes and line-level provenance. It uses those to enumerate candidates, then checks the original source slice literally. The adapter supplies the multi-source visible-span loop and existing BoundRef conversion. Literal edge cases not representable by whole-token boundaries require an explicit supplemental path and tests; these adaptations must not be presented as unchanged upstream code.

LangExtract's global monotonic DP is not used to guess provenance: memory operations may be ordered by topic or importance rather than source order. Its lowercased token MATCH_EXACT, lesser-match and fuzzy policies are not equivalent to literal equality. All occurrences are retained instead of choosing a document-order optimum that lacks the needed premise.

OpenWiki informs the host-owned source/version separation; its repository-path resolver and whole-page batch transaction are not imported. Graphiti informs host mapping of displayed source identity; its empty/invalid-index fallback to all episodes is not imported. No graph database or additional extraction-model dependency is introduced.

## Storage and lifecycle

New unbound knowledge, experience or gap content can be retained in the existing category lists. It carries immutable per-revision grounding metadata and must be visibly marked unbound in both maintenance and selection views. A located quote to an unbound derived memory does not turn the conclusion into independently observed evidence.

An unbound revision to an existing grounded entry must not erase that entry. It becomes an explicitly pending revision linked to the target. At most one active pending proposal per target is kept; later proposals replace the active pending proposal while immutable history remains. Existing save/delete tools address proposals; no extra tool is added. A later grounded target update or target deletion retires its pending revision. Revising an already unbound native entry may occur in place.

Unbound status proposals likewise cannot silently overwrite grounded canonical status. They remain visible to both stages as proposed status, not established progress. These labels describe binding only; even a grounded canonical status is still a model conclusion, not certified truth.

Malformed tool arguments, unknown targets, invalid snapshots, broken persistence/lineage and unsupported operations remain explicit failures. They are not converted into unbound conclusions. Independent per-operation atomic publication remains: one operation failure does not undo successful siblings.

## Consumption and reporting

Phase 2 retains its original selection policy and reminder parser. Its input presentation includes grounding labels, pending proposals and appropriately identified quote context; this is not a new semantic-audit stage. Derived assertions and source roles remain distinct. An unbound proposal reaches Phase 2 but is not forced into a Task reminder.

Telemetry must separate mechanically committed grounded writes, retained unbound proposals, and rejected operations. `success` means a storage operation succeeded, not that a conclusion is true. No-op is not a write. Persisted reload must preserve labels, candidates, pending targets and history rather than lose them on restart.

## Required offline evidence

- Upstream duplicate-text/token-position examples plus exact character postcheck, Unicode, punctuation and whitespace boundaries.
- Wrong/missing source hint with a real quote; duplicate occurrence in one source and across different source roles.
- Hidden marker, hidden text and wrong-cycle exclusions; unmatched content remains explicitly unbound.
- Real structured and XML maintenance inputs: no mandatory source ID or unique-occurrence instruction remains.
- All memory categories including status and all gap scenarios; pending revision protects old grounded content; later resolution/deletion and round-trip persistence.
- Actual Phase 2 input contains new unbound conclusions and pending proposals with labels; unchanged reminder/no-intervention protocol and no new model calls.
- Existing strict regression, ordinary PMA/gap regression and actual host construction with the same bank object.
- Historical visible-quote replay with unchanged quote/hint, no model calls, no claim of counterfactual task-score improvement.

Old runs, scores, certificates and archives stay immutable. Cloud offline tests are not Windows/Docker certification, and no new real run is authorized by this implementation.

## Final presentation and validation details

Phase 1 shows each memory's binding/disposition and compact provenance summary,
not its old stored quote strings or hints as pseudo-sources. Its searchable
corpus remains selected current memory content plus actually rendered current
public source spans. It does not add historical-event retrieval. Phase 2, which
has no write tools, sees stored source excerpts and clearly labelled unmatched
model-attempted quotations. A prior quote outside Phase 1's current eligible view
is not silently searched merely because its receipt is persisted.

All matched positions remain persisted. Model-facing location summaries group
by role/event/field and show occurrence count and first/last positions, explicitly
as a summary, rather than printing every internal hash or every repeated offset.
The summary does not claim uniqueness across omitted text. Editable memory IDs
remain distinct from internal provenance identities, which are not requested
from the model.

A synchronous ContextVar-scoped cache reuses validation of exact immutable source
snapshots during an aligned transaction or persistence validation. Every reference
still checks its interval, snippet hash, source metadata and sealed visibility.
There is no cross-request cache; strict paths outside a scope retain their previous
checks. Frozen equality keys prevent trusting a source ID after content changes.
