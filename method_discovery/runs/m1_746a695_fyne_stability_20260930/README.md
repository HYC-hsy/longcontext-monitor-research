# M1 Fyne stability repeats — two pre-registered records

The two run IDs and common configuration were fixed in `preregistered_records.json` at commit `07da4b2` after the earlier `m1-746a695-fyne-repro-20260930-r1` result (1/7) was known, and before either repeat's first model request. These are development repeats, not a retrospectively planned series with the historical 7/7, later 4/7, or preceding 1/7 records. They do not isolate Supervisor variance from Task Agent or environment variance.

Both records used the complete detached checkout `E:\longcontext-m1-746a695` at `746a695adac4325d6440941d384d543d1364fef9` for Task and Supervisor. The runtime GenericAgent source SHA-256 was `762e7ae7b73a9b19fe1af458745407f76287b53a2529dfaba546008e0c3cb656`; task tree SHA-256 was `928e4d98926e9c6038f2538ec960be19fa1fb199bfc11f06e3fe01a7d50259d6`; Fyne image ID was `sha256:b0da1cb31d367df38d05b81f98e68a94b0f7114efd3c82537633d1d92325efe1`. The same private model configuration SHA-256 `ed09a811b654b83097bee77942704eae2539d67291bf55aa34476692081ff02e` was used without publishing credentials. DCEC was enabled with a 4000-character working view; Task max turns was 500 and the integration budget was 10000 seconds. No P/R or later strict-slot mechanism was enabled. This is the same stated running condition as the preceding 1/7 reproduction, not a claim of byte-identical historical 7/7 private environment.

| Record | UTC trial interval | Native result | Passed phases | Terminal/control |
|---|---|---:|---|---|
| `m1-746a695-fyne-stability-20260930-r1` | 03:27:58–03:55:12 | 1/7; reward 0.090909 | 5 | `agent_phase_completed`; allowed `completion-3` at Task turn 67 |
| `m1-746a695-fyne-stability-20260930-r2` | 03:58:07–04:17:15 | 4/7; reward 0.545455 | 1, 3, 4, 5 | `agent_phase_completed`; allowed `completion-1` at Task turn 91 |

Both native evaluations ran once after the respective Agent phase; both proof manifests report `validation_errors=[]`, `round_end_seen=true`, and `archive_status=finished`. There was one formal trial per ID and no trial-level rerun. The second record was started only after the first finished and its host Supervisor archive was readable. The original task, working state, and container were fresh for each record. The two image/model/source identities match. The earlier 1/7 run remains separate and unchanged.

## Short event index (raw records are authoritative)

### r1

- The Monitor intervened on missing `testApp.Metadata()` during Task execution; `monitor/runtime_receipts.jsonl` records delivery.
- Task completion proposals occurred at turns 50, 56, and 67 (`agent/research_events.jsonl`). `completion-1` was continued because `StringToStringWithFormat` was missing. During `completion-2` the Monitor intervened on Toolbar constructor types and the missing desktop icon method; the old proposal was not approved. It eventually allowed `completion-3`.
- At the final handoff the Monitor checked `Container.Add` nil-safety with `code_run` and asserted all seven targets verified. That observation did not measure the other targets. Native verifier output later showed Phase 1, 2, and 4 compile failures; Phase 3 behavior failures; Phase 6 compile/behavior failures; and a Phase 7 interface compile failure. Only Phase 5 passed. These native results were post-termination research evidence, not online Supervisor input.

### r2

- The Monitor intervened on the mistaken password-visibility implementation in place of `Entry.SetMinRowsVisible`, on missing `desktop.App`, and on `NewAllStrings` implemented as substring matching instead of validator composition; delivery appears in `monitor/runtime_receipts.jsonl`.
- There was one completion proposal, at Task turn 91. The final Monitor review re-read `driver/desktop/app.go`, accepted its local interface shape, and allowed `completion-1`. The final working state described all seven targets as verified and reported no pending observation.
- Native verifier output later passed Phases 1, 3, 4, and 5, but Phase 2 had a compile failure, Phase 6 failed the default visible-rows behavior despite passing container/validation subchecks, and Phase 7 had an interface compile failure. The final local re-read did not establish whole-task behavior. These native results were unavailable to the live Supervisor.

The records show real corrections and eventual relaxation, alongside insufficient grounds for both final whole-task approvals. Neither a broad sentence in `working.md` alone nor the native score alone establishes the control error: the relevant chain is in the public task, actual observation/tool results, working-state revisions, control receipts, and final artifact. There was no observed continuation event in either Monitor progress log, so this batch does not test post-continuation behavior. The two scores are an initial variability signal under fixed running conditions, not evidence that Supervisor randomness is the sole cause or that M1's historical positive capability was invalid.

## Usage, archive, and limits

Task provider attempts: r1 67 success; r2 88 success and 3 cancelled. Monitor request attempts: r1 59 success; r2 56 success. Logged usage rows: Task 67/89 and Monitor 59/56 respectively; the two missing Task usage rows in r2 are not imputed as zero. Logged Task input/cache-write/cache-read/output tokens: r1 92,614/170,092/1,260,574/43,429; r2 125,422/222,089/1,657,952/48,405. Logged Monitor input/cache-write/cache-read/output tokens: r1 21,714/2,565,796/300,209/22,756; r2 25,098/2,188,817/556,886/24,628. These are raw usage buckets, not an independently verified dollar total.

This Git archive contains the original proof/preflight/trace, trial configs/results, Task logs and events, Supervisor dialogue/progress/history/attempts/usage/working state, tool command outputs, public task evidence, checkpoint metadata, OTel trace, and native verifier outputs. Copied artifacts are byte-identical to the local output and not edited for the report. Credential-bearing runtime configuration, isolated bundles, and gateway secrets are excluded. The full workspace checkpoint tarballs are over 100 MiB each and remain local rather than in Git:

| Record | Local tar (under that trial's `agent/monitor/monitor_private/audit/live_checkpoints/`) | Bytes | SHA-256 |
|---|---|---:|---|
| r1 | `checkpoint-0001.tar` | 116162560 | `1c236227bcdfa7aafdec18430472942822b4466935047b2ad312c6c3c3124520` |
| r1 | `checkpoint-0002.tar` | 116295680 | `5e121379a961499f9f8df2f24fe172d50a7ac15589f3fcacfcbfbf56edc4c6b9` |
| r1 | `checkpoint-0003.tar` | 116459520 | `a8e312c230240f016dd94b42d552d5beb1f681090ab9e6e6ade585d8b0debb12` |
| r2 | `checkpoint-0001.tar` | 116623360 | `fb2132d4f133e24a3a61c564ea2b6b81ad943bc2355ba6a579813915cfe7ae12` |

The local full-output root is `E:\LongContext\long_context_bench\output\m1_746a695_fyne_stability_20260930`; trial suffixes are `fyn-2.2.0-roadmap__wC4uzXz` (r1) and `fyn-2.2.0-roadmap__F7ChpXL` (r2). The remote Git copy intentionally lacks those four full-workspace tarballs, but includes their checkpoint request/identity/manifest extracts. No model call, verifier rerun, task mutation, or mechanism edit was performed during this post-run archive audit.
