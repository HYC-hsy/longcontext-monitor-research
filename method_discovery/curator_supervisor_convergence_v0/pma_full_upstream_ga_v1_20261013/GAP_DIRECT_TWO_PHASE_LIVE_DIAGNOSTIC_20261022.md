# PMA gap direct-two-phase SQLite diagnostic (2026-10-22)

This is one time-relaxed diagnostic, not an official 900-second Agent-protocol score or a comparison against PMA/GA. The previous reviewed-gap runs and their results are unchanged.

## Identity and outcome

- Unified entry: `experiment_runner` plan → prepare → run; one `sqlite-with-gcov` slot, occurrence 1, serial; method `pma-gap`, B / `pma_gap_memory_v0`, `fake_only=false`.
- Run ID: `pma-d1847af4750941c0`. Runtime source commit: `9757a11c4e896c6999f774358e03585d2f313036` (method fix commit `3f84739f46ac340b2766fcad0dc3737d1ea85684`). Frozen manifest SHA-256: `015cefab978d8857c128e24083929bd256e06eaa3ebad046f935352b11ec053d`; single-run plan SHA-256: `fc7742982bc323d7c9ee3d9b46d4d3cf186bcd9aff757f233228e5ff72963a41`.
- Fixed task source commit: `2fd12b88aafdd04a52c298e3940bcb189f9766d6`. Task and PMA model public identity: `claude-opus-4-8`. Task/memory private profiles were reused but are not published.
- Effective Agent cumulative timeout and Task-turn cap: none by the approved diagnostic policy. Native verifier timeout: 900 seconds. The task started, executed tools, and returned `CURRENT_TASK_DONE`; Harbor and memory worker exited with code 0. The single native test script invocation returned code 0, but the expected CTRF report did not exist, so the native evaluator declared `native_reward_missing`. **Reward: unavailable, not 0.** No second evaluation or episode was run.
- The verifier's captured stdout shows a package download failing with HTTP 502, followed by `curl: command not found`, missing `/root/.local/bin/env`, and `uvx: command not found`. This explains the absent report at the observable script level; it does not establish a Task reward. Hidden test sources were not published.

## Observable method and Task behavior

- 54 complete memory cycles: exactly 54 `maintenance` and 54 `selection` visible role responses, all transport rows marked `complete`; no gap review, repair, or rereview role. Auxiliary physical HTTP attempt and billing totals are not separately available in this capture; logical calls must not be presented as those totals.
- First cycle saved four formal gaps. Across the run the gap log records 21 successful saves and 18 successful deletes, with no recorded gap-operation errors; the final formal view contains three gaps. Final items concern PATH persistence/interpretation and a gcov artifact-name mismatch. These are model-maintained observations, not host-certified truth.
- 54 completed Task provider requests/responses and 62 recorded tool calls. Task-visible usage rows total 71,018 input and 27,798 output tokens; auxiliary native usage and monetary charge are unavailable here.
- Phase 2 chose 27 reminders and 27 silent decisions. The 27 reminders were matched by identity and body to subsequent Task request-ready/attempt/response records. A reminder selected in Phase 2 is not counted as delivered merely because it was generated.
- The final Task response claimed successful installation and a gcov workflow, while the final formal gap view still questioned PATH persistence and the gcov filename. This divergence is a diagnostic observation, not an externally verified task-success or method-effect claim.

## Evidence and boundaries

Private originals remain under `E:\LongContext\gap_direct_real_v1\01-sqlite-with-gcov-r1\runs\pma-d1847af4750941c0`. Public, allowlisted, redacted cycle/Task/reminder projections and exact source-row-to-public-row hashes are in `gap_direct_real_visible_20261022/INDEX.json`. The public copies are reserialized, not original bytes. The index records removed/replaced values and never-selected hidden reasoning, private metadata, profiles, raw HTTP headers and verifier content.

Key private source SHA-256: `gap_cycle.jsonl` `51cbe992ccf7d387596de50c27f93749ded05aa517cab7a5aa9ea92dfcc560c0`; `memory_payload.jsonl` `7ebd8afc09efdf5b6b168326f519dea641477cd4ec973fcd0c8d06b9690cd93c`; `archive/live_result.json` `b7e39b69cb8526a7cdb59e19c8419b5b959c990d3de836859f61f30b36f71df0`; verifier stdout `97a42284c46d5af4b7a4e8aa68258afef2ed6c99df3a24750ffe26d05382167b`. Public index SHA-256 at export: `dba89d97502d364fdc4688b7a0dd223d2dd9894943741dcf3030e4bb0165c0a6`.

The one-time authorization was bound to the above manifest, run ID and commit (private authorization SHA-256 `fd2a01549144f27f08a002d0a93895300b318997550ceb981b67f1525cac43ad`) and removed after termination. Owned containers and volume were reported clean, Docker showed no remaining running container, and the worker stopped. The public export code was generalized *after* this run solely to project direct-two-phase evidence; it was not part of the executed runtime commit.

The source-bound Harbor full-fake preflight is separately documented in `GAP_DIRECT_TWO_PHASE_PREFLIGHT_20261022.md`. It is not a real-model result. This single real episode establishes that the direct two-stage method and Task ran through the unified path; because native evaluation yielded no score, it establishes neither SQLite success nor any comparative benefit.
