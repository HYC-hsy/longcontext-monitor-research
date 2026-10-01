# Replay feasibility: historical v0c r1/r2

Scope: read-only audit of `dynamic_observer_v0c_adoption_20261001/r1` and `r2`, published at `m2-from-m1c@9c01b60d1357f6110fca478d2c0406ded9590db4`. Their source was v0c `e521078...`, not the later WTV candidate `6c72477...`. No WTV sample event exists in these runs. File paths and raw-byte SHA-256 values are in `ARTIFACT_INVENTORY.md` / `RAW_ARTIFACT_HASHES.json`; per-review and per-mutation calculations are in `HASH_VERIFICATION.json`.

| Component | Status | Evidence and exact boundary |
| --- | --- | --- |
| E_t system and tool contract | available at each review | `dialogue.jsonl` `review_context` carries full `system_prompt`, `wake_context`, and tools; `source_identity/source_identity.json` binds source/profile hashes. No continuation occurred, so continuation behavior is source-identifiable but not historically exercised. Private credentials are intentionally absent. |
| E_t conversation | available at review boundaries | Final `provider_history.json` has 172 (r1) / 223 (r2) items. Every `reviews.jsonl` before/after prefix hash matches: 14/14 and 23/23 reviews. `dialogue.jsonl` preserves model input/output and tool calls/results. This is not an in-flight request checkpoint. |
| E_t working state | reconstructable at recorded mutation/review boundaries, not separately snapshotted | Replay of the recorded `file_write`/`file_patch` parameters reproduced all 12 (r1) / 22 (r2) mutation SHA-256 values and each final `working.md` SHA-256. `progress.jsonl` alone records hashes, not text. The reconstruction assumes the archived successful operations are the complete private-file writers. |
| E_t control state | partial | Review actions, wake contexts, delivery receipts, root proposal identities and public cursors are archived. No single arbitrary-review artifact records every pending barrier, in-flight tool, completion generation, scheduler value and asynchronous delivery state needed for exact live continuation. |
| X_t workspace | missing for ordinary review points | Original image and public tool events exist, but no per-review workspace tree/manifest. `code_run` and concurrent changes preclude exact reverse reconstruction from the final tree. Full snapshots exist only at root handoffs. |
| E_t–X_t binding | missing for ordinary review points | No joint checkpoint ID or consistent capture boundary binds a reconstructed E_t to the workspace bytes actually present then. Root checkpoint is a limited exception. |
| Transition history | partial | `public_events.jsonl` contains `archive_sequence`, `task_turn` and tool records. It is not a complete filesystem change ledger or WTV path sample. A source read's SHA identifies that read, not the whole workspace. |
| Root checkpoint | available only for its handoff | r1 cursors 213/225; r2 cursor 361. Each has request, identity, workspace manifest, local snapshot tar, and a checked public-event prefix. These are not snapshots at an arbitrary earlier ground-formation point. |

## Distinct feasibility claims

**Review-boundary analysis reconstruction:** feasible for much of E_t without another model call. History prefix hashes and working mutation hashes were actually checked, not inferred from final-file presence. The original wake context and public cursor can be located, while within-review concurrent world position remains bounded only by the available events and timestamps.

**Exact continuation replay:** not established. Ordinary review points lack X_t, a joint capture boundary and complete live control state. A root `request.json` can reproduce that root's provider-ready request, but it cannot turn the root snapshot into a pre-transition T2/T5/Hyperlink checkpoint. Neither the historic v0c run nor its archive contains WTV's previous-sample baseline. A restored workspace may also have different metadata timestamps; a future WTV experiment must explicitly bind or establish a new baseline before the controlled change.

The checkpoint itself would be audit input, not an extra prompt, memory system or semantic judgment. This document does not evaluate model adoption or method effect.
