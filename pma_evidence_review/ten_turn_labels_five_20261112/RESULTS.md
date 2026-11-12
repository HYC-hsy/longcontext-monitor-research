# Real-run results and limits

| Task | Run ID | Task steps | Manager wakes / visible responses | Successful add / read | Delivered reminders | Native tests | Reward | Cleanup |
|---|---|---:|---:|---:|---:|---:|---:|---|
| kv-store-grpc | `pma-99acbfec247b4cc4` | 22 | 3 / 7 | 3 / 1 | 1 | 5/7 | 0 | confirmed |
| reshard-c4-data | `pma-2ce23dfffc9e4a53` | 29 | 4 / 9 | 4 / 1 | 0 | 0/1 | 0 | confirmed |
| rstan-to-pystan | `pma-1b6b07b146f443b7` | 36 | 5 / 12 | 5 / 1 | 1 | 6/6 | 1 | confirmed |
| largest-eigenval | `pma-7d759fef862e4c1f` | 32 | 4 / 11 | 4 / 3 | 0 | 3/3 | 1 | confirmed |
| filter-js-from-html | `pma-c6b7e586ad3944c3` | 2 | 1 / 3 | 1 / 1 | 0 | 0/2 | 0 | confirmed |

The batch ran from 2026-11-12 13:37:53 to 14:44:43 Asia/Shanghai. Each Task's verifier used its own official limit (900/3600/1800/900/1800 seconds in task order); the Task total runtime, Task turn count, and outer deadline were uncapped. The effective runtime policy is in each run archive; `uncapped` is a diagnostic condition, not an official Agent time-limit score. Shared evaluation dependencies were used without changing the Task's initial environment. The actual fixed source tree and method binding were recorded separately for each run.

Two `context_for_action` decisions were made. For kv-store, the reminder was assembled into Task provider attempt 17 and that attempt received a successful provider response. For rstan, the same chain is confirmed for attempt 33. Both are genuine delivery evidence, not just generated text. The subsequent Task actions are visible, but adjacent actions alone cannot prove adoption or causal benefit. The other 15 wakes ended in `no_intervention`; none are silently counted as a successful prediction. This version attempted no tool outside the declared `memory_add` and `memory_read`; all 24 tool receipts succeeded (17 adds, 7 reads). Empty public reply bodies and intermediate, not-yet-accepted decisions remain in the trace.

Compared with the preceding four-turn archive at commit `47a046498edb9d802f1aa9da720623d9da3bbc5a`, native rewards in task order changed from `0,1,1,1,0` to `0,0,1,1,0`. The new runs had 22/29/36/32/2 Task steps versus 14/20/26/37/6 before. In the earlier four-turn run, reshard and eigenval included seven calls to unavailable tools; this run had none. That is an observed difference in these trajectories, not an identified effect of the tags: the ten-turn distance, mandatory public wording, and input tags changed together, and each task was run once per version.

The saved banks still often contain requirements needed immediately, results already used while solving the current problem, or current progress. `rstan`'s array-axis observation was saved at wake 32 and applied by the Task at step 33—useful, but not a first use ten turns later. `filter-js` ended after two Task steps, so no ten-turn outcome window exists. The per-wake conservative classification is in `WAKE_REVIEW.md`. We did not find a demonstrated case where a saved fact was **first** used only after ten subsequent Task steps; some facts were reused later, which is not equivalent. Full atom-by-atom use and server-side model identity remain uncertain.
