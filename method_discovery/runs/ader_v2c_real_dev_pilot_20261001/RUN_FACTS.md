# ADER-v2c real development pilot — execution facts

This is a two-record development batch, not a candidate-effect judgment. The frozen treatment is `c6f6cc8fac555b638303237b64881552e38d846b`; the archived ADER-v1 records are references, not same-trajectory counterfactuals. The preregistration and both zero-model gates were committed before the first real request as `b9fe91e17bde003637be97659cb8c59770ee4ef5`. Both gates report PASS with no mismatches. Each isolated runtime source differs from the corresponding ADER-v1 source only in `monitor_agent_core/agent.py` and `monitor_agent_core/working_context.py`. The effective source SHA-256 in both trials is `aab4359dfd5dab0584e3eceadaeae724830a8018aeff110f92dcb2b69b685a2e`.

| Record | Task | End | Native result | Task requests / attempts | Parent requests / attempts | Root proposals | `intervene` calls | Working mutations | `file_read` / `code_run` | Final control | Trial wall time |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| r1 | `roadmapbench:fyn-2.2.0-roadmap` | `agent_phase_completed` | 3/7; reward `0.36363636363636365` | 94 / 94 | 60 / 60 | 2 | 3 | 6 | 31 / 29 | `allow_complete` on `completion-2` | 1695.3 s |
| r2 | `roadmapbench:ktx-0.13.0-roadmap` | `agent_phase_completed` | 4/6; reward `0.7` | 179 / 179 | 98 / 98 | 1 | 4 | 19 | 48 / 19 | `allow_complete` on `completion-1` | 2194.7 s |

Both proof manifests say `valid=true`, `archive_status=finished`, `online_checker_feedback=false`, and have empty validation errors. The native verifier ran after Task termination. Provider attempts above are actual logged attempts; no provider retries appear in these records. Parent request purposes are all `review` (no observed continuation request). No child verifier was enabled. The full original verifier outputs, including phases, are under each record's `verifier/` directory; the numeric reward is not the fraction of phases passed.

Observed token buckets, from Task `research_events.jsonl` and parent `provider_usage.jsonl`, respectively:

| Record / role | Input | Cache creation input | Cache read input | Output |
| --- | ---: | ---: | ---: | ---: |
| r1 Task | 133847 | 164744 | 1645310 | 34733 |
| r1 parent | 30682 | 1821268 | 531898 | 22514 |
| r2 Task | 247784 | 327857 | 3263184 | 86662 |
| r2 parent | 50022 | 3604511 | 2491585 | 36420 |

Dollar cost is not derived here. r1 ran from `2026-10-01T04:23:20.754439Z` to `04:51:36.072538Z`; r2 from `04:55:14.701817Z` to `05:31:49.432412Z`.

## Completion and control locations

- r1 `completion-1`, cursor 177: review `6e774b3a1f374baa816678b704ea1915`, `progress.jsonl` `root_checkpoint_created`; `dialogue.jsonl` line 325 is an `intervene` call, whose result is `submitted` to the completion boundary, and the review subsequently accepts `wait`. `delivery_feedback.jsonl` line 3 records the completion boundary handoff. This is not an approved completion.
- r1 `completion-2`, cursor 185: review `ced840ed65d54d23920a2de58b7757a0`, `dialogue.jsonl` line 364 invokes `allow_complete`; the final `control_result` is accepted. `delivery_feedback.jsonl` line 4 records the completion handoff.
- r2 `completion-1`, cursor 357: review `0a50b5573b1e48928db5d31a50006be0`, `dialogue.jsonl` line 576 invokes `allow_complete`; the final `control_result` is accepted. `delivery_feedback.jsonl` line 5 records the completion handoff.
- All three root reviews started with `completion_pending=true` in `progress.jsonl`; no initially ordinary review has a recorded root checkpoint in these two runs. This does not claim an unobserved dynamic-transition capability was exercised.

`MECHANICAL_EVENT_INDEX.json` gives review IDs, raw line numbers, root checkpoints, working-view SHA values, state mutations, tool calls, tool errors, exact repeated reads/scripts, runtime updates, control results and delivery feedback. It is a locator, not a judgment about evidence adequacy. The raw files remain authoritative. r1 has 3 indexed tool-error results and 3 exact repeated-read groups; r2 has 4 and 2. These counts do not classify measurement substitution or information gain.

## Source and retained originals

- `r1/` and `r2/` hold the copied Task public events, Task telemetry, parent dialogue/history/attempts/usage, working state, runtime and delivery receipts, source/proof/trial identity, and native verifier originals. `RAW_FILE_MANIFEST.json` hashes 218 copied raw files. All 218 source bytes matched the copied files and, after the scoped `-text` Git attribute, the staged Git blobs byte-for-byte. `MECHANICAL_EVENT_INDEX.json` and this note are derived research-side navigation files, not model input.
- The following large root checkpoint tar files are retained locally, not copied into Git. Paths are relative to `E:\LongContext\long_context_bench\output\ader_v2c_real_dev_pilot_20261001\jobs\`:

| Record | Checkpoint path beneath the record's trial directory | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| r1 | `fyn-2.2.0-roadmap__PVXnH5A/agent/monitor/monitor_private/audit/live_checkpoints/checkpoint-0001.tar` | 116439040 | `ff4758179b47a123627e6a05ff1402784258a7475c36bcd9441259e6d0542e64` |
| r1 | `fyn-2.2.0-roadmap__PVXnH5A/agent/monitor/monitor_private/audit/live_checkpoints/checkpoint-0002.tar` | 116520960 | `cbb3298c7635cc4736481c056e83c7b8a98475f849639546839d53f0f27b102e` |
| r2 | `ktx-0.13.0-roadmap__FTpEaq6/agent/monitor/monitor_private/audit/live_checkpoints/checkpoint-0001.tar` | 17879040 | `13d41e6184a3effad98914ddbb87e0fba7ab5fc381ed03dbf535668570b5cd29` |

Each tar belongs beneath `jobs/<run_id>/<trial>/` at that output root. The root checkpoints are proposal-time snapshots; no separate full post-verifier workspace export is claimed. Private provider profiles and gateway secrets are not in the public archive. A targeted secret-pattern path scan of the public archive found no matches; this is not a proof that arbitrary task text contains no sensitive string.
