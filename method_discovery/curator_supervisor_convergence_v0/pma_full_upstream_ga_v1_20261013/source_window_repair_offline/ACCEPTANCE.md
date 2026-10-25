# Source projection and fuzzy-window repair

Published runtime code: `aa760fdd12209a6482752738bc8f8bd270ea1c30`. Parent archive: `4eb7d6e9fe99d9df999920d248d948494e75dab2`. Runtime commits: `daefb885cebc9317dfdcacc83e4f1f8a7cca9bc7` (file_patch), `b10aac21e07ef7c6b4818306365598e6332f2765` (pinned interval/fragment helpers), and the runtime commit above (candidate windows and necessary source-identity wiring). Final archive SHA is supplied in delivery.

## Scope

1. Existing `_project_tool_text` whitelist now includes file_patch old_content/new_content. One JSON decode, separate original coordinates and tool_command identities; no claim that supplied edits actually succeeded. Original wrapper remains retained.
2. Fuzzy fallback now forms source-visible ~1000-character fragments using pinned LangExtract interval helpers and adapted newline/token splitting. Query-length-aware overlap preserves boundary/long-quote opportunities. A multiset token overlap upper bound prunes impossible candidates; deterministic lexical ranking processes plausible windows first. It never joins hidden spans or changes original source text.
3. Existing pinned LCS, coverage/density thresholds and 2,000,000 local DP-cell ceiling remain. The ceiling is not a model token or experiment budget. Search metadata records generated/pruned/budget-skipped windows and `lexical_ranked_visible_windows_v1`. Search remains non-exhaustive; extreme quotes can remain unsearched. The ceiling is shared across evidence items as before.
4. The two new runtime modules are explicitly included in the existing source identity list and unified-entry regression. No new model phase, tool, reminder policy, lifecycle, evaluation protocol, episode or external dependency is added.

Not changed: ellipsis/omission-marker rules, exact and normalized association, semantic trust, five tools, maintenance→selection. Fuzzy associations remain fuzzy_candidate/unbound with no successful binding receipt.

## Upstream reuse

See vendor/langextract_3a68580/GRADED_REUSE.md. create_token_interval is reused, get_char_interval only substitutes the local compatible type import, and the newline/token fragment loop is adapted from pinned ChunkIterator. Cross-source lexical candidate ranking is our necessary PMA adapter, not a feature falsely attributed to LangExtract. Long-quote overlap and raw-token matching are explicit adaptations.

## Verification

Existing cloud Python 3.12.14 environment:
- Final gap + experiment_runner: **339 passed, 250 subtests passed**.
- Affected GA: **42 passed, 38 subtests passed**.
- Independent final targeted review: 28 tests passed (overlap with totals; do not add).
- Tests cover historical C8/C9 projection, identical old/new multiple sources, one decoding pass, ordinary literal escapes, source-order invariance, repeated-token upper bounds, long quotes and boundary coordinates, hidden-span separation, multiple candidates, limited-search metadata, old metadata compatibility and bank serialization/reload.
- file_patch-only intermediate aggregate was 330 passed. Initial targeted pre-fix failures and an initial GA command missing its PYTHONPATH are preserved separately, not counted as passed.
- No real model, Task or evaluation calls. No Docker/Harbor final certification in this cloud workspace. Developer reception must certify the final packaged runtime using the existing local environment before any separately authorized real episode.

## Historical replay limits

The public C8/C9 fixture is included with user authorization. It is a one-tool-source deterministic replay, not full-catalog recall or a live model test.

The actual HTML C12 verification uses a local-only reduced directory: eight preceding public source blocks plus a 299-character real tool-result target, whose original saved SHA-256 is b79cb828e645837308c24a99e395800433a750dd0dc8fcee343a6988e6bbb1b6. Old ordered search used 1,758,348 estimated cells and skipped the target; ranked windows locate a fuzzy candidate in the original line-numbered target using 279,936 cells. This is not reconstruction of the entire original source catalog. The synthetic unit regression is separately published. The real C12 input payload is not republished by this patch.

Public trajectory redaction and unretained sources prevent claiming complete full-catalog recall/precision. Successful textual association does not establish that a remembered conclusion is supported.
