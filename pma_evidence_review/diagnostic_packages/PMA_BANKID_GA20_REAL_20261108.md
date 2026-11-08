# Fixed GA20 task panel: read-context PMA run

This is a redacted visible projection of one serial, 20-slot run. The execution checkout remained `b17151b8d57c61cfb4e058ad1601225f9fa2ea15` (`pma-predictive-read-context`, condition B, candidate `pma_predictive_read_context_v1`). The dataset was `2fd12b88aafdd04a52c298e3940bcb189f9766d6` and native Harbor was `459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc`. Each task had one new run ID and an independent workspace and knowledge bank. Effective agent time and task turns were uncapped; each official verifier limit was retained.

The frozen GA20 comparison source is `experiment_runner/ga20_evidence/GA20_FINAL_SUMMARY_20261030.json` at commit `918bcb99d28a70997e73450168a6c00cb20e1c12`. All 20 current runs have a native reward: PMA 8/20 reward 1, 12/20 reward 0; historical GA 9/20 reward 1, 11/20 reward 0. Task 11 (`circuit-fibsqrt`) had a `PROVIDER_FAILURE` Task terminal, even though its native evaluation ran and recorded reward 0. Do not interpret it as normal Task completion.

| # | Task | Historical GA | This PMA |
|---:|---|---:|---:|
| 01 | git-leak-recovery | 1 | 1 |
| 02 | git-multibranch | 1 | 0 |
| 03 | feal-linear-cryptanalysis | 0 | 0 |
| 04 | query-optimize | 0 | 0 |
| 05 | mcmc-sampling-stan | 1 | 1 |
| 06 | fix-ocaml-gc | 1 | 1 |
| 07 | rstan-to-pystan | 0 | 1 |
| 08 | merge-diff-arc-agi-task | 0 | 1 |
| 09 | break-filter-js-from-html | 0 | 0 |
| 10 | nginx-request-logging | 1 | 1 |
| 11 | circuit-fibsqrt | 0 | 0 |
| 12 | multi-source-data-merger | 1 | 1 |
| 13 | filter-js-from-html | 0 | 0 |
| 14 | largest-eigenval | 1 | 1 |
| 15 | make-mips-interpreter | 0 | 0 |
| 16 | kv-store-grpc | 1 | 0 |
| 17 | sanitize-git-repo | 0 | 0 |
| 18 | build-pov-ray | 0 | 0 |
| 19 | reshard-c4-data | 1 | 0 |
| 20 | db-wal-recovery | 0 | 0 |

New successes relative to the historical GA run were `rstan-to-pystan` and `merge-diff-arc-agi-task`; new failures were `git-multibranch`, `kv-store-grpc`, and `reshard-c4-data`. This is a cross-batch, one-attempt-per-task exploratory comparison, not a controlled causal estimate. The public GA20 record does not independently establish all original image/verifier identities or temperature/top_p; these remain unknown. Neither a score change nor adjacent Task actions alone establish the effect of a memory or reminder.

The current run recorded 817 Task model calls, 286 P1 logical calls, 112 P2 logical calls, 211 successful `memory_add` operations and 32 successful `memory_read` operations. Thirteen reads returned a nonempty bank, all in tasks 03 and 15; none of the five score-changed tasks had a successful nonempty read. Fifty-two reminders were appended and matched to subsequent provider request attempts, so they were actually sent; this does not show that they caused any later action. Task-side usage fields summed to 1,104,145 input, 429,229 output, 1,358,357 cache-creation input and 13,006,418 cache-read input tokens. Complete PMA token usage, physical provider attempt count and total cost were not reliably available and are `unknown`, not estimated. Agent duration summed to approximately 23,530 seconds across serial tasks; this is not a benchmark time-budget result.

The ZIP contains the per-slot run IDs, full redacted visible Task/PMA records, tool calls and receipts, memory and reminder records, official evaluation summaries, effective policy, cleanup evidence, `GA20_COMPARISON.json` and `BEHAVIOR_AUDIT.json`. The adjacent external `.index.json` lists every member's size and SHA-256; `SOURCE_MAP.json` inside maps retained private originals to each public projection by hash. Private originals stay local. The projection excludes credentials, complete profiles, private endpoints, provider-private thinking/signatures, hidden test bodies and task workspaces; it is not raw HTTP byte-for-byte evidence. Hidden-test names, assertions and stdout are intentionally not present. All 20 slot cleanup checks passed; no automatic repeat or second-round experiment was performed.
