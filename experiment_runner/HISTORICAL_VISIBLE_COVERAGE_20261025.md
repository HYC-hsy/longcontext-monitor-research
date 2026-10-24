# Historical real-run visible-trajectory audit (2026-10-25)

The per-run source of truth is [HISTORICAL_VISIBLE_COVERAGE_20261025.json](HISTORICAL_VISIBLE_COVERAGE_20261025.json). It lists run ID, task, actual method and candidate, executing source SHA, archive commit, batch, terminal/evaluation/reward, source presence, public package, five separate evidence statuses, and the consequence of each known gap. The public files are redacted, re-encoded projections, **not** raw HTTP bytes. Private originals were not changed. No model, Task, or verifier was called for this backfill.

## Scope and result

A bounded search of existing run indices, reports, selected local run roots, and prior public archives identified **100 distinct ended real Task episodes**: 27 GA-only, 24 original PMA, 28 two-stage PMA-gap, 7 PoS, 4 evidence-bound PMA-gap, 6 stateful memory, 3 PoS+PMA shared-view, and 1 PoS+PMA complement. Fourteen separate real **auxiliary-only diagnostic probes** were excluded from the Task-episode denominator. Synthetic/full-fake fixtures are not counted. The active two-task run was explicitly excluded and neither read for this inventory nor interrupted.

The search is not an assertion that these are every experiment ever performed. The JSON records the root prefixes and directories examined. Earlier or moved private roots outside those bounds, runs without a recognizable `live_result.json`, and unpublished research formats remain unenumerated.

Statuses are per evidence category, not a single `complete` flag: A = visible content publicly auditable; B = private source exists but linkage/projection awaits verification; C = not captured or source lost; D = source exists but cannot safely be published; E = mechanism/stage not applicable; F = not established. Aggregate counts among the 100 episodes:

| Category | A | B | C | D | E | F |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Task request, public response, actions and receipts | 72 | 0 | 21 | 0 | 5 | 2 |
| Auxiliary phase requests and public responses | 73 | 0 | 0 | 0 | 27 | 0 |
| Memory/gap changes | 56 | 0 | 0 | 0 | 27 | 17 |
| Reminder delivery and follow-up | 46 | 0 | 10 | 0 | 27 | 17 |
| Native evaluation public status/result | 100 | 0 | 0 | 0 | 0 | 0 |

An A for the evaluation category may mean an explicitly **unavailable** reward, not that testing occurred or produced a score. The per-run fields distinguish those cases. An A for a source stream is not proof that a model made a sound inference. A reminder decision without a matching complete later Task request is not counted as delivered.

## Newly supplied visible content

- [GA-only successful SQLite](ga_only_sqlite_visible_20261025/README.md), run `pma-1792c5ce7df34858`: condition A/U, source `66705fbba0771788f336884b433c9cb7dfe2372f`; original `live_result`, research-events and terminal hashes matched the contemporaneous summary. The package has 17 actual Task requests and public responses, 16 tool calls with later Task-visible receipts, the native evaluation summary and a line-by-line original-to-public hash map. Inspect turns 1-4 for source acquisition, 5-13 for toolchain/build, 14 for PATH, 15 for gcov, and 17 for the completion claim. One shell's PATH check is not evidence of all future process environments.
- [Earlier denied GA-only SQLite](ga_only_sqlite_denied_visible_20261025/README.md), run `pma-a927e53b0aef4e8e`: one attempted Task HTTP call ended in 403, with no complete public model response or action. Its historical reward record must not be used as evidence of task-solving failure.
- [Twelve other real GA-only A-arm runs](ga_only_historical_visible_20261025/README.md) from the 2026-10-15 A/B batch. Each has the visible Task turn/action/receipt stream, terminal/evaluation projection and per-line provenance. The `pma-` ID prefix does not make an A-arm run a PMA run.
- [Thirty-three other ended real runs](historical_visible_sources_20261025/README.md) across original PMA, PoS, mixed variants, stateful memory and evidence-bound PMA-gap. These include their retained Task and auxiliary visible streams, memory/trajectory files when present, terminal status and original/public hashes. Sixteen PMA-style packages additionally have exact-text/timestamp reminder-to-request links; 412 of 413 generated reminders matched a later complete Task request with visible response. The unmatched one is reported, not promoted to delivery. Other variants' reminder linkage is left B/F/C where independently unverified.

These 47 new packages were checked against the **currently present private source bytes** and their final public file/line hashes. Sensitive fields and hidden reasoning were removed or masked with per-package redaction records. Some streams retained only truncated Task-visible tool output; no missing stdout was reconstructed. The existing exporters, rather than a model-generated narrative, preserve the recorded commands, public responses and receipts.

## Previously public packages and irrecoverable gaps

The existing [20-task PMA-gap batch](../method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/evidence/pma_gap_batch20_20261023/) and [five-task repeat batch](../method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/evidence/pma_gap_repeat5_20261025/) already contained visible packages; their 505 and 154 indexed public files respectively were rechecked, not uploaded again. Three singleton PMA-gap visible packages also remain at their existing paths in the matrix.

Twenty-five older A/B arms remain in existing redacted archives: [six-task batch](../method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/six_task_live_batch_20261014_r1/raw/arms/), [retry batch](../method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/live_batch_retry_20261014/raw/arms/), and [two-task batch](../method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/two_task_live_20261015/REAL_BATCH_ARCHIVE_V3/raw/arms/). Published archive member bytes match their existing public indexes (998, 408 and 222 members). Their external private roots are no longer present here, so the **private originals could not be rehashed**. The 21 October-14 arms recorded Task request hashes rather than full final payload and did not capture the public response content. Their console/tool traces cannot reconstruct what the model actually saw or said (C). The four October-15 arms have captured visible Task content in the published archive.

Five stateful-memory attempts stopped during initialization before a Task request (E); one later stateful episode has Task-visible material but its reminder linkage is not independently certified here. Two PoS runs have native evaluation records but no retained Task event source at the inspected paths (F). One original PMA run has a generated reminder without exact text in a later complete Task request; it is not counted as delivered. For nine PoS/mixed runs, auxiliary and Task streams exist but reminder-to-request association has not been independently reconstructed (F); unlike a B, there is no identified unpublished private reminder-link file waiting to be copied. Where the matrix says F for memory transitions, do not infer that no memory existed: the available source does not establish the requested transition history.

Consequently, the successful GA-only SQLite run was **not the only GA-only public-trajectory gap**: thirteen local GA-only packages were backfilled here (the success, the denied attempt, and twelve A-arm runs), while eleven older GA-only October-14 arms retain an unrecoverable full Task prompt/response gap. Full stepwise causal comparison across those October-14 A/B arms is not supported by the surviving hashes and summaries. The 100 public evaluation outcomes can be tabulated, but they cannot all support stepwise behavioral or reminder-effect claims. A reward, source hash, or later memory entry cannot replace absent contemporaneous model-visible content.

## Verification and limits

Run the local, read-only verifiers `experiment_runner/verify_ga_visible_audit.py`, `verify_historical_visible_sources.py`, and `verify_legacy_visible_archive.py`; the batch20/repeat5 packages retain their own validators. Each new package's `INDEX.json` records the original byte SHA-256 separately from the redacted public byte/line SHA-256 and the source-line mapping. The original-byte hash cannot be recreated from the redacted copy. For existing legacy archives the local check only verifies **published archive bytes**, never the absent private roots.

This audit does not retroactively change any task result, rerun or rescore any episode, recover an unrecorded model response, inspect hidden tests, or establish method superiority. Future real-run reports should link the publicly safe visible trajectory and explicitly state any unavailable intervals, not equate a summary or hashes with a complete trajectory.
