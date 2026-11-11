# Coherent unified memory-manager: five real Tasks (2026-11-11)

Execution commit: `ef19e9ac6194261f1fbd24c5d8eba5a111e6c7ae` (parent `352280922aa2b3746bad857452d471e465a5b4a6`). Dataset: `2fd12b88aafdd04a52c298e3940bcb189f9766d6`; Harbor: `459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc`. The five slots ran serially once each through `experiment_runner`, with Task `claude-opus-4-8`, memory manager `claude-opus-5`, eight-step wake interval, uncapped Task turns and total Agent time, and official per-task verifier limits. No separate P2 was introduced: this candidate uses one unified management loop.

| Task | Run ID | Native tests | Reward | Memory wakes | Manager responses | Tool calls (add/read/other) | Confirmed reminders | Cleanup |
|---|---|---:|---:|---:|---:|---:|---:|---|
| kv-store-grpc | `pma-b31fe8c1e27f47d1` | 5/7 | 0 | 3 | 8 | 3/2/0 | 0 | confirmed |
| reshard-c4-data | `pma-7a65291aa70b4695` | 0/1 | 0 | 3 | 11 | 5/2/1 rejected `code_run` | 0 | confirmed |
| rstan-to-pystan | `pma-2af23a30fd9e444e` | 1/6 | 0 | 2 | 7 | 4/1/0 | 0 | confirmed |
| largest-eigenval | `pma-fbc78feedd38446c` | 3/3 | 1 | 2 | 9 | 5/2/0 | 1, actor request 9 | confirmed |
| filter-js-from-html | `pma-209b6f7840f94e1e` | 0/2 | 0 | 1 | 3 | 1/1/0 | 0 | confirmed |

All five Task terminals were `CURRENT_TASK_DONE`. A memory decision of no intervention is not a quality judgment. The sole intervention was generated in the largest-eigenval run and was present in the actual ready request for actor attempt 9, followed by a provider request attempt and response. The trace contains the exact text and linkage; this table does not claim the reminder caused the native success.

The focused local offline run had 260 passes and two failures. The LiteLLM `AsyncHTTPHandler(transport=...)` test-fixture incompatibility was also seen in the prior same environment. The fixed AST-hash assertion differs under local Python 3.13.14; normalizing the parent and candidate ASTs in that environment yields the same digest. The candidate's requested system prompt and request/continuation behavior passed the remaining focused tests. No production source was changed to address these test-fixture issues.

`PMA_COHERENT_FIVE_REAL_20261111.zip` contains the visible Task and memory-manager records, tool receipts, evaluations, runtime policy, failure and cleanup records. The external index lists every member with original and public-projection hashes and sizes. `facts.json` adds mechanical counters without hidden verifier cases. Originals remain local; the ZIP is a redacted visible projection, not raw HTTP bytes. It excludes credentials, private profiles/endpoints, private thinking/signatures, hidden verifier contents and unrelated source bundles. Test counts are provided, but hidden test names, assertions and stdout are not published.

These are one-off developmental trajectories, not a controlled or statistically powered estimate of prompt benefit. The earlier five-task run used a different two-stage architecture and naturally different Task trajectories; score differences cannot be attributed solely to this system prompt.
