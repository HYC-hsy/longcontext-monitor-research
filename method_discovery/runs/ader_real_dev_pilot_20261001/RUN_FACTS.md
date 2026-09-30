# ADER-v1 real development pilot: objective execution index

This file records execution facts, not an ADER effect verdict. The two archived M1 references were not rerun. The preregistration and zero-model identity gates are in `method_discovery/diagnostics/ader_real_dev_pilot_20261001/`; both gates report `PASS` with no unexplained condition mismatch. The immutable ADER source is `16ddee55ead5f48ef955e5b76bbfae0f7e7698a5`; its Git archive SHA-256 is `61f2606b6769b8cecbebacdc1c3a837dd3fb799ecf55ff1a9765e982088b396a`. The runtime GA source SHA-256 in both proof manifests is `d543634ca51106eb931f8e17acdb492eab28f8f9237170516ce8d6c7e7bfd340`. Task and Monitor profile hashes are `ed09a811b654b83097bee77942704eae2539d67291bf55aa34476692081ff02e` and `cc5f784b069034f44bc4527d15acd70191b1f7fc5810556c087b7b35e0ae00f1`.

| Record, fixed order | Agent outcome and final control | Native post-termination result | UTC start–finish | Task requests/attempts | Parent requests/attempts | Working mutations | File reads / code runs / continuation |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| `r1` Fyne, `ader-real-dev-pilot-20261001-01` | `agent_phase_completed`; `allow_complete` for `completion-3` | 1/7, reward 0.0909091; only phase 5 passed | 2026-09-30 17:05:08–17:36:10 | 64/64 | 49/49 | 10 | 34 / 7 / 0 |
| `r2` Kitex, `ader-real-dev-pilot-20261001-02` | `agent_phase_completed`; `allow_complete` for `completion-3` | 2/6, reward 0.4; phases 1 and 4 passed | 2026-09-30 17:41:46–18:06:40 | 43/43 | 60/60 | 13 | 30 / 11 / 0 |

Fyne phase 1–4 and 6–7 failed in the verifier output. Kitex phase 2–3 and 5–6 failed. These are post-termination facts, not online evidence. Both records used one formal start and one native verifier invocation; all captured provider attempt ordinals were 1. Each record had three completion proposals. Fyne had two completion-boundary interventions; Kitex had three interventions (one before any proposal, two at completion handoffs). The original delivery text and receipts are in `r*/agent/monitor/monitor_private/delivery_feedback.jsonl`. Each proof manifest reports `archive_status=finished`, correct model and source identity, `valid=true`, and no validation errors. The GA subprocess return code 143 appears inside the otherwise completed wrapper/proof; it is not recoded here as an infrastructure failure.

Usage buckets below are direct sums of `agent/research_events.jsonl` Task `provider_usage` payloads and parent `monitor_private/audit/provider_usage.jsonl`. They are token counts, not a price estimate. No missing amount was filled with zero.

| Record / role | Input | Cache creation | Cache read | Output | Usage entries |
| --- | ---: | ---: | ---: | ---: | ---: |
| r1 Task | 87541 | 112033 | 1161416 | 28072 | 64 |
| r1 parent | 20453 | 1796871 | 353087 | 17841 | 49 |
| r2 Task | 56151 | 103989 | 759193 | 37462 | 43 |
| r2 parent | 26649 | 2105641 | 578310 | 39391 | 60 |

There was no independent child verifier request in either record. The native verifier was run only after each Task ended. The original model/provider and tool receipts are in the raw archive, not reconstructed from these totals.

## Consequential transitions and raw anchors

`EVENT_INDEX.json` mechanically enumerates all 14 reviews, their exact `review_id`, dialogue/progress line ranges, tool IDs and calls, checkpoint identities, working-state mutation SHA-256, error results, runtime updates and exact repeated-read locations. It is an index, not an assessment of decision quality. `r*/checkpoint_metadata/checkpoint-*/request.json` contains the captured provider-ready root request with `root_handoff`, system, messages, seven-tool schema and model parameters. The final `provider_history.json` and all dialogue `model_input`/`model_output`/tool-result events remain raw.

| Record | Review and start condition | Root transition, action and direct locator |
| --- | --- | --- |
| r1 | `23427730…`, ordinary | Initialization and Task reading; three tool errors, one state mutation, `wait`. `dialogue.jsonl:1–41`, `progress.jsonl:1–73`. |
| r1 | `c105da3c…`, ordinary | Two state mutations, `wait`. `dialogue:42–68`, `progress:74–128`. |
| r1 | `f35a857d…`, ordinary | One state mutation, `wait`. `dialogue:69–99`, `progress:129–183`. |
| r1 | `55c34e2e…`, ordinary | One state mutation, `wait`. `dialogue:100–128`, `progress:184–239`. |
| r1 | `031c500b…`, pending `completion-1` at cursor 105 | Root checkpoint `progress:242`; task/source reads `dialogue:133–162`; `intervene` at 167, runtime invalidation visible at 169, then `wait`; delivery receipt `decision=continue`. |
| r1 | `b7256b28…`, pending `completion-2` at cursor 119 | Root checkpoint `progress:340`; reads and code observation `dialogue:184–218`; `intervene` at 223, invalidation visible at 225, then `wait`; delivery receipt `decision=continue`. |
| r1 | `4b85a162…`, pending `completion-3` at cursor 127 | Root checkpoint `progress:446`; reads and code observations `dialogue:240–274`; `allow_complete` at 279–281; delivery receipt `decision=allow`. |
| r2 | `ed71cf45…`, ordinary | Two missing early public navigation files, two state mutations, `wait`. `dialogue:1–71`, `progress:1–134`. |
| r2 | `c1bf1502…`, ordinary | One state mutation, `wait`. `dialogue:72–98`, `progress:135–195`. |
| r2 | `7f7f5df4…`, ordinary | Two state mutations, `wait`. `dialogue:99–125`, `progress:196–255`. |
| r2 | `19aad1a0…`, ordinary | Task/source observations, `intervene` at `dialogue:164` (delivery receipt `cursor=25`), then `wait`; `dialogue:126–176`, `progress:256–369`. |
| r2 | `d9f0511b…`, ordinary at start | `completion-1` appears within this review: `progress:370` starts with `completion_pending=false`, checkpoint at 393 (cursor 57); next model input at `dialogue:188` carries runtime handoff update. `intervene` at 206, invalidation update at 208, then `wait`; delivery receipt `decision=continue`. |
| r2 | `c0dbc7b4…`, ordinary at start | `completion-2` appears within this review: `progress:469` starts false, checkpoint at 502 (cursor 71); next model input at `dialogue:235` carries handoff update. `intervene` at 283, invalidation update at 285, then `wait`; delivery receipt `decision=continue`. |
| r2 | `54603fee…`, ordinary at start | `completion-3` appears within this review: `progress:628` starts false, checkpoint at 648 (cursor 83); next model input at `dialogue:307` carries handoff update. `allow_complete` at 320–322; delivery receipt `decision=allow`. |

The three r2 mid-review handoffs were not externally forced into new reviews. Their checkpoint `request.json` files retain the exact `root_handoff` identities. The above intervention receipts establish submission/delivery routing; subsequent Task events are in `r*/agent/monitor/task_evidence/public_events.jsonl` and should be read directly rather than inferred from intervention counts.

## Observation availability and repetition locators

Fyne initialization: `dialogue:7–8` and `12–13` show `task/synopsis.jsonl` and `task/public_events.jsonl` not yet created. The later same-review code execution at `dialogue:24–25` returns exit code 1; its command output is preserved under `agent/monitor/monitor_private/audit/commands/`. The next code observation begins at `dialogue:29`. Kitex initialization similarly finds those two navigation files absent at `dialogue:15–16` and `20–21`; subsequent ordinary observations begin at `dialogue:25`. These are raw availability/exit facts; no claim is made that a later observation preserved the same decision distinction. No other parent tool result has `status=error` or a nonzero `exit_code` in the captured dialogue.

Exact repeated `file_read` argument groups appear only in r2: `task/synopsis.jsonl` at `dialogue:15,76`, `task/workspace/transport/keys.go` at `50,142,186,228`, and `task/public_events.jsonl` with `tail=true,count=1` at `191,238,310`. The last group reads a moving tail, not a claim of identical content. The mechanical index found no byte-identical repeated `code_run` script and no exact repeated `file_read` group in r1. Similar-but-not-identical observations were not classified by this index.

## Archive boundaries

The 152 copied raw files are listed with byte sizes and SHA-256 in `RAW_FILE_MANIFEST.json`; the archival copy procedure verifies every copied file against its original host file hash. The archive includes public Task evidence/synopsis, Task telemetry/output, complete parent dialogue, final provider history, request attempts/usage, working file and mutation progress, control/delivery receipts, root checkpoint request/identity/manifest, source/proof identity, and verifier stdout/reward. The original output root remains `E:\LongContext\long_context_bench\output\ader_real_dev_pilot_20261001`; neither record was overwritten. Secret profiles, keys and gateway configuration were excluded; a targeted secret-pattern scan of the copied text found no matches.

The large root checkpoint tar files were not pushed. They remain at the original trial paths under `agent/monitor/monitor_private/audit/live_checkpoints/`:

| Record / checkpoint | Bytes | SHA-256 |
| --- | ---: | --- |
| r1 / 0001 | 116131840 | `797510838add3899c9a36cec058db309066a16c79cece72e48e9382eb85ba3eb` |
| r1 / 0002 | 116254720 | `14614e62a3e2042749584c04757b6d755020168378586fbff440073e2df633b4` |
| r1 / 0003 | 116336640 | `f23a917f35631726db069bea6cfd30b01a9df6803fcc38e493c548495ddf988e` |
| r2 / 0001 | 16199680 | `eda4008271132c0b2fecddb2dd1492ba8dec725a2f8e2ab2c844b268704c9702` |
| r2 / 0002 | 16343040 | `c3616cc4e073a679c21fc0fc825f1eb949818772f903b466cf731ee0f56fde37` |
| r2 / 0003 | 16476160 | `3240bd136982014260af787d4f44037b754f7d4d7878793bc8eb785ff2393978` |

The small checkpoint metadata is pushed. A separate post-approval final workspace export was not present after native container cleanup; the tar files are root-decision snapshots, not mislabeled as a final workspace. Also, the frozen runtime saved exact provider-ready payloads at root checkpoints, but not a separate full payload snapshot for every ordinary request. The final provider history and per-turn dialogue/request/usage events are retained; this per-call payload limitation is not silently filled by reconstruction.
