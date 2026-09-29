# Fyne M1/DCEC-v1 reproduction — one formal record

- Run ID: `m1-746a695-fyne-repro-20260930-r1`
- Task: `roadmapbench:fyn-2.2.0-roadmap`
- Task and Supervisor tracked source: detached checkout `E:\longcontext-m1-746a695`, commit `746a695adac4325d6440941d384d543d1364fef9`
- Runtime GenericAgent tree SHA-256: `762e7ae7b73a9b19fe1af458745407f76287b53a2529dfaba546008e0c3cb656` (includes locally supplied, untracked runtime configuration; **not** the historical run's `cdd78ef4...` runtime-tree fingerprint). This is a reproduction from the specified tracked commit, not a claim of byte-identical historical bundle contents.
- Original task tree, source revision, image, and Harbor base commit matched the historical Fyne preflight. Effective adapter arguments included `max_turns=500`, `timeout_sec=10000`, `monitor_enabled=true`, `monitor_config=claude_monitor_opus48`, and native DCEC with a 4000-character working view. No P/R policy was installed.
- Result: native verifier `1/7` phases, reward `0.09090909090909091`; `agent_phase_completed`, no trial exception, proof validation errors `[]`. The Agent phase ran from `2026-09-29T17:55:47.382257Z` to `18:36:36.795290Z`.
- The first launcher attempt failed **before Task container startup and before model requests** because the detached checkout lacked the ignored OTel collector config. Its isolated bundle remains under the local output root as `prelaunch_failed_bundle_zero_calls`. The config was copied from the existing runtime; the same record ID then had its sole model-bearing run. There was no model-bearing record restart or additional task.

This Git archive contains the original proof, trial, Task output/logs, Supervisor audit/history/usage/working state, public task evidence, three checkpoint request/identity/manifest extracts, OTel trace, and native verifier output. Files were copied without editing. The private credential files and isolated gateway configuration are not published; an exact-value credential scan of these copied files found no match.

The full workspace checkpoint tarballs remain in the local immutable output and are **not** included in Git because each exceeds 100 MiB. The remote archive therefore does not contain the full final workspace snapshot. Local source paths and hashes:

| Original local file (under `.../agent/monitor/monitor_private/audit/live_checkpoints/`) | Bytes | SHA-256 |
|---|---:|---|
| `checkpoint-0001.tar` | 116162560 | `d07048ad4ab012398e82a708cd718568fe8eefcee220243dbecf01400af70641` |
| `checkpoint-0002.tar` | 116572160 | `c0304c5d973eb83aeefccbc24cd1b2314d935b7ee179165828ebfc68c226985e` |
| `checkpoint-0003.tar` | 116756480 | `18f2c40336f41d83f9298ff803755f8545f48e76427d60309887013cf55798b0` |

Local full-output root: `E:\LongContext\long_context_bench\output\m1_746a695_fyne_repro_20260930`. This run does not overwrite the historical 7/7 run or the later 4/7 record.
