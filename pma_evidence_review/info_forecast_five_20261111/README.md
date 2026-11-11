# Information-use forecast: five real Tasks (2026-11-11)

Execution commit: `4b5d8642d9f1070921cea122363473de3092d871`, not the earlier `6b06a27` wording. Dataset: `2fd12b88aafdd04a52c298e3940bcb189f9766d6`; Harbor: `459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc`. Five new, independent slots ran serially once through `experiment_runner`, with Task profile `claude-opus-4-8`, unified memory-manager profile `claude-opus-5`, eight-step periodic wakes, uncapped Task turns and total Agent time, and per-task official verifier limits. There is no separate P2.

The actual `memory_payload.jsonl` requests in all five runs used only the approved base system (SHA-256 `3823014c2297648a46226c0aec5df3b297b3d17683d3f82240f5a009d6a7d99c`) and that same base plus the conditional public-summary soft reminder (SHA-256 `56bceed8b6b7c094af60cb11a881babcd04d773886af73a2d1470280a2be05ac`). The latter is exactly base, two newlines, then `PUBLIC_FORECAST_REMINDER`. The base includes “anticipate which of the information received this time the task agent will use in its next 10 turns of work.” The ten turns are a selection horizon, not a memory TTL.

| Task | Run ID | Native tests | Reward | Actor steps | Wakes / manager responses | Successful add / read | Actually sent reminders | Cleanup |
|---|---|---:|---:|---:|---:|---:|---:|---|
| kv-store-grpc | `pma-9ac94a4f2080481c` | 7/7 | 1 | 16 | 2 / 5 | 2 / 1 | 1, actor request 1 | confirmed |
| reshard-c4-data | `pma-09a05a15817a49d1` | 0/1 | 0 | 23 | 3 / 13 | 5 / 3 | 0 | confirmed |
| rstan-to-pystan | `pma-ed0213d62e134fe0` | 6/6 | 1 | 50 | 7 / 23 | 7 / 5 | 2, actor requests 25 and 33 | confirmed |
| largest-eigenval | `pma-36cd90c1ba0d4b2e` | 3/3 | 1 | 23 | 3 / 10 | 4 / 2 | 0 | confirmed |
| filter-js-from-html | `pma-08633378b67e4b0a` | 0/2 | 0 | 2 | 1 / 2 | 1 / 0 | 0 | confirmed |

All five Task terminals recorded `CURRENT_TASK_DONE`; all five native evaluations ran and their owned resources were cleared. Each of the three reminder-bearing actor requests has an actual ready request, provider attempt and successful provider response. Generation and host return alone were not counted as delivery. No episode was retried. The manager attempted unavailable tools in reshard, rstan and largest-eigenval; each returned an explicit failure, not an executed action. The manager nevertheless reached normal decisions, so these calls remain part of the observed behavior.

The same-environment focused offline test comparison was candidate 262 passed/2 failed and parent 262 passed/the same 2 failed. One is the installed LiteLLM `AsyncHTTPHandler(transport=...)` fixture mismatch. The other is a hard-coded AST digest that differs under local Python 3.13; replacing the two prompt values with sentinels yields identical candidate and parent AST digests in that environment. No production code or test was altered to conceal these failures.

The ZIP is a redacted visible projection, not original HTTP bytes. It contains Task and manager visible requests/responses, tool calls/receipts, bank changes, native evaluation and cleanup records, runtime identities, and both offline logs. `wake_index.json` links decisions and actual delivery to task requests and marks incomplete next-ten-step observation windows. `facts.json` contains mechanical counters; `OBSERVATIONS.md` gives limited manual observations. The external index lists original and public-projection sizes and hashes for each member. Private originals remain local. Credentials, private profiles/endpoints, native private thinking/signatures, hidden verifier cases and unrelated source bundles are excluded. PMA usage totals, server-effective model settings, total dollar fees and physical HTTP-attempt totals are `unknown` where not independently retained.

These one-off development trajectories can reveal behaviors but cannot establish a stable advantage. The preceding `ef19` batch is historical, not a controlled same-trajectory replay; differences in Task outcomes cannot be assigned solely to the prompt wording.
