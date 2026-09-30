# RISC real development pilot: execution facts

This is an objective index for the two preregistered RISC records. It is not a scientific comparison or a candidate verdict. The M1 reference records were archived earlier and were not rerun. The zero-model identity gates are `method_discovery/diagnostics/risc_real_dev_pilot_20260930/IDENTITY_GATE_01.json` and `IDENTITY_GATE_02.json` (both `PASS`); the preregistration and launcher are in that same directory. The RISC source is commit `0239ee0a61ddb51556d11ce04c058229a9a4b8a9`, built as Git archive SHA-256 `67edbd089e4ab256ff4e901ad452f2d1e31d9b443477369b2af639d4166886b1`. Both trials report runtime GA source SHA-256 `d3efc3cdb9daa930d423f3efe255d6a1d08b7ae838e2610a1d5a664402e4f5e4`. The Task and Monitor profile hashes are `ed09a811b654b83097bee77942704eae2539d67291bf55aa34476692081ff02e` and `cc5f784b069034f44bc4527d15acd70191b1f7fc5810556c087b7b35e0ae00f1`.

| Record | Native result | Trial outcome | UTC start–finish | Task requests/attempts | Parent attempts | Child requests | Proposals | Parent interventions | Final control |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `r1` Fyne, `risc-real-dev-pilot-20260930-01` | 4/7, reward 0.5454545 | `agent_phase_completed` | 2026-09-30 14:41:01–15:03:40 | 78/78 | 56 | 0 | 1 | 1 | `allow_complete` on `completion-1` |
| `r2` Kitex, `risc-real-dev-pilot-20260930-02` | 3/6, reward 0.6 | `agent_phase_completed` | 2026-09-30 15:06:15–15:43:57 | 119/119 | 94 | 0 | 2 | 4 | `allow_complete` on `completion-2` |

Each trial ran once, in the registered order, with one post-termination native verifier invocation. `trial/result.json`, `proof/manifest.json`, `verifier/reward.json`, and `verifier/test-stdout.txt` contain the original outcomes. Native scores were not provided to either online agent. Task `provider_request_ready` and `provider_request_attempt` event counts match; every parent `request_attempts.jsonl` entry has `attempt=1`. There was no child verifier call or child provider usage in either record. No unknown child usage has been imputed as a measured zero-cost request.

Provider usage buckets, summed from original `agent/research_events.jsonl` (Task) and `agent/monitor/monitor_private/audit/provider_usage.jsonl` (parent), are as follows. These are token counts, not dollar estimates; each bucket is reported separately rather than merged into an assumed billable total.

| Record / role | Input | Cache creation | Cache read | Output | Usage entries |
| --- | ---: | ---: | ---: | ---: | ---: |
| r1 Task | 109328 | 137384 | 1485315 | 30583 | 78 |
| r1 parent | 25613 | 1744137 | 570841 | 17005 | 56 |
| r2 Task | 166778 | 220165 | 2076453 | 50133 | 119 |
| r2 parent | 64271 | 4184890 | 1468179 | 29292 | 94 |

The 155 copied raw files are listed with byte counts and SHA-256 in `RAW_FILE_MANIFEST.json`. This includes the original public Task events/synopsis, Task telemetry, complete parent dialogue and provider history/attempts/usage, working-state file and audit, control/delivery receipts, checkpoint request/identity/manifest, trial/proof/source identity, and native verifier files. The copied files were compared byte-for-byte by SHA-256 with the host originals. Original run roots remain at `E:\LongContext\long_context_bench\output\risc_real_dev_pilot_20260930\jobs\risc-real-dev-pilot-20260930-01` and `...-02`; no raw record was overwritten. The large immutable root-checkpoint tar files remain local, not in Git:

| Record / checkpoint | Local file under `agent/monitor/monitor_private/audit/live_checkpoints/` | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| r1 / 0001 | `checkpoint-0001.tar` | 116449280 | `4d922ec6c6f50932408f92f4ced4af5b7d4f7ef21065c06fcf58ba4626981a02` |
| r2 / 0001 | `checkpoint-0001.tar` | 16967680 | `9206162d78f98a281c993a3194dd7b07a2e9de60107eeb9c28c64884129845be` |
| r2 / 0002 | `checkpoint-0002.tar` | 17172480 | `d57b4a88f80a3ca2d4ba96af65b64874bba21803e2bbb238ef191a1a73916b21` |

The corresponding small checkpoint `request.json`, `identity.json`, `manifest.json` and `complete.json` are included in Git under each record's `checkpoint_metadata/`. The local tar files capture those root decision snapshots; a separate post-approval final workspace export was not present in the trial artifacts. Do not infer unseen final-state details from that absence. Private profiles, keys and gateway configuration were not copied into the public archive. A targeted secret-pattern scan of the copied raw files found no matches.

## Root-review event index

`independent_check` adoption requires a parent `tool_call` followed by an isolated child request. None of the three checkpointed root reviews contains such a `tool_call`. Question, paths, child history, child outcome, evidence refs and post-child parent consumption are therefore not applicable, not inferred. The checkpoint `request.json` files preserve the actual captured provider-ready requests and tool schemas.

| Record / proposal | Review ID; checkpoint identity | Root treatment in captured request | Parent action and raw anchors |
| --- | --- | --- | --- |
| r1 `completion-1`, cursor 155 | `c673c50e97ab45b791461c8fd5291f0c`; `r1/checkpoint_metadata/checkpoint-0001/identity.json` | RISC root paragraph once; `independent_check` once | No child call; `allow_complete` at `r1/agent/monitor/monitor_private/audit/dialogue.jsonl:303-306`; root event at `progress.jsonl:501`; completion receipt in `r1/agent/monitor/monitor_private/delivery_feedback.jsonl`. |
| r2 `completion-1`, cursor 205 | `f0f4a2364c5144329fda670fa5da40b1`; `r2/checkpoint_metadata/checkpoint-0001/identity.json` | RISC root paragraph once; `independent_check` once | No child call; parent `intervene` at `r2/agent/monitor/monitor_private/audit/dialogue.jsonl:469-470`, then `wait` at line 476; root event at `progress.jsonl:789`; delivery feedback records `decision=continue` for `completion-1`. Later public Task events and `completion-2` are preserved. |
| r2 `completion-2`, cursor 237 | `d3e9290ce8a948d7b92a597c6e594fa7`; `r2/checkpoint_metadata/checkpoint-0002/identity.json` | RISC root paragraph absent; `independent_check` absent | The review began with `completion_pending=false` (`progress.jsonl:928`), then checkpointed `completion-2` (`progress.jsonl:949`); no child call; `allow_complete` at `dialogue.jsonl:523-526`; delivery feedback records `decision=allow`. This is a captured treatment-exposure limitation for this proposal, not a retroactive fix or rerun. |

`r2/agent/monitor/monitor_private/delivery_feedback.jsonl` preserves four intervention receipts, including the completion-1 correction; the subsequent public Task events and second proposal are in `r2/agent/monitor/task_evidence/public_events.jsonl`. The exact intervention wording and subsequent Task behavior should be read from those originals. No claim about question quality, evidence consumption, semantic correctness, or RISC effect is made here.
