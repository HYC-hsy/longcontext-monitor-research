# Per-wake visible review

This table is a navigation-level reading of the complete wake records in the ZIP. “No reminder” means an accepted model decision, not an assessment that silence was correct. Saved content is quoted or paraphrased from successful tool receipts and the final bank; Task behavior is not assumed to be caused by it. The `wake_index.json` maps each row to complete request/response and subsequent Task events.

| Task | Wake after Task step | Visible save/read and decision | Review boundary |
|---|---:|---|---|
| kv-store-grpc | 0 | Read empty bank; saved port, package versions and proto/RPC details; no reminder. | Initial entry used hyphenated generated-module names, later contradicted by observed underscore names. |
| kv-store-grpc | 8 | Saved observed underscore module naming, server PID/log and missing process tools; no reminder. | Corrected naming in a new entry, leaving the old inconsistent entry present. Only four Task steps followed. |
| reshard-c4-data | 0 | Read empty bank; saved file/directory size limits and script requirements; no reminder. | Requirements are available to Task already; future first use is not established. |
| reshard-c4-data | 8 | Saved sample-data characteristics and implementation layout; no reminder. | Current implementation facts; later-use value cannot be inferred solely from saving. |
| reshard-c4-data | 16 | Multiple reads, saved failed-decompression cleanup and missing metadata state; no reminder. | Prior partial run was explicitly distinguished from a fresh failure. |
| reshard-c4-data | 24 | Read bank, saved round-trip and “Task Completion” assertions; no reminder. | Some checks were sampled and the native verifier later failed; do not treat the bank label as verified whole-task completion. |
| rstan-to-pystan | 0 | Read empty bank, saved PyStan/CSV requirements; no reminder. | Useful original constraints but not necessarily first needed ten turns later. |
| rstan-to-pystan | 8 | Saved Stan model and R sampling details; no reminder. | Task had already read the R script; later reuse differs from later first use. |
| rstan-to-pystan | 16 | Read bank, saved PyStan API parameter-name observations, generated one reminder. | The reminder entered actual Task attempt 17; Task had already identified the parameter-name issue, so incremental value is unproven. |
| rstan-to-pystan | 24 | Multiple reads; saved timeout interpretation and adjusted sample count; no reminder. | “Maintains equivalence” is a stronger conclusion than the mere completion of a shortened run. |
| rstan-to-pystan | 32 | Read bank, saved vector-output shape bug diagnosis; no reminder. | Only five further Task steps observed, an incomplete ten-step window. |
| largest-eigenval | 0 | Read empty bank; two unavailable `file_read` attempts got error receipts, then no reminder. | Tool misuse is an observed protocol issue, not a successful read. |
| largest-eigenval | 8 | Saved baseline timing, correctness and failed approach; read bank; no reminder. | Mostly recent results/current plan. |
| largest-eigenval | 16 | Read bank and saved performance progression; no reminder. | Task already had the timings; native verifier later passed, but reminder contribution is zero. |
| filter-js-from-html | 0 | Two reads, saved original HTML/XSS requirements; no reminder. | Two-step Task provides no ten-step future window and no delivered reminder. |

Current known Task evaluation is `0,0,0,1,0` in the order above; per-test public counts are in `RESULTS.md`. No hidden verifier body is used for these interpretations. More granular first-use and causal claims remain uncertain where a requirement was already in the Task context or there is no explicit Task uptake statement.
