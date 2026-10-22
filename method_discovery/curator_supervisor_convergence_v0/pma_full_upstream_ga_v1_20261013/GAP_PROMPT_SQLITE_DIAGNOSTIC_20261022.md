# PMA-gap prompt diagnostic: one real SQLite episode

This is a single-task development diagnostic, not a comparison with ordinary PMA or pure GA. The agent time/turn limits were relaxed, so reward must not be presented as an original 900-second Agent-protocol result.

## Identity and outcome

- Executed source commit: `103cdebaa93d0b7446fffcd8ef7d8af069f9405c`.
- Unified entry: `experiment_runner` plan → prepare → run, one serial `sqlite-with-gcov` slot, `pma-gap` / `B` / `pma_gap_memory_v0`, run `pma-b39bcc4a6c44456a`.
- Models: existing private Task and PMA profiles, both resolved publicly to `claude-opus-4-8`; private profile bytes and endpoints are not exported.
- Fixed task source commit: `2fd12b88aafdd04a52c298e3940bcb189f9766d6`; manifest SHA-256 `cebde35f8549bad39b26efc2e77ed8b060ee1322eb960744724de5345048f036`.
- Effective policy: Agent cumulative time and Task turns uncapped; native verifier time 900 seconds. Evaluation preparation protocol `bootstrap_retry_v1`.
- Task ended normally (`task_end`); Harbor and PMA worker returned 0. Agent execution: 2026-10-22 15:12:40–15:20:09 UTC. Evaluation: 15:20:26–15:21:27 UTC.
- Preparation completed, the real test entry started exactly once, required CTRF report was present and parseable, and native reward was **1.0**. Original test script SHA-256 `4770437ea96c3cc84684b4f99d55fb148fcac09f9ea1e8ef49de487716e6c334`; effective prepared script SHA-256 `574e48fdbcac3c837a07f1589f2dfdc0e168ed431d56fbdeb664e725bc186a21`.

## Observable method path

- 12 Task generation requests returned HTTP 200 with complete responses. The Task selected 11 tools: 9 `code_run`, 2 `file_read`. Task usage records sum to 14,930 input, 4,046 output, 11,647 cache-creation and 97,381 cache-read tokens (provider fields, not cost estimates).
- 12 PMA cycles each recorded exactly `maintenance → selection`: 12 completed calls of each; no gap review, repair or rereview. Auxiliary physical HTTP-attempt and billing totals are not independently established by these role-level records.
- The first maintenance saved two gaps (instrumented build and PATH). A compiler failure was recorded as procedural experience; later maintenance updated the instrumentation gap, removed it after visible checks, then removed the PATH gap after a successful `which sqlite3` / `sqlite3 --version` tool result. Final formal gap view is empty. No cycle recorded a tool-operation or transport error.
- Selection returned 9 `no_intervention` and 3 `context_for_action`. Reminders addressed the missing compiler (cycle 7), instrumentation verification and PATH (cycle 10), and PATH (cycle 11). The three distinct reminder event IDs were bound into actual subsequent Task requests 7, 10 and 11; each of those requests subsequently received a successful provider response. `pma_reminder_appended.input_sent=false` describes append time, not final delivery, so the later request binding is the delivery evidence.
- This trace demonstrates the prompt text was used and the two-stage mechanism operated. The reward and Task actions do not isolate the reminders' causal effect, and an empty final gap view is not itself proof of correct semantic maintenance.

## Cleanup and evidence boundary

The result records `cleanup_confirmed=true`, no remaining run containers, no cleanup errors, stopped PMA worker and clean owned-volume clearance. A direct Docker check found no run-owned container or volume. The run-specific one-use authorization was removed after the terminal result; older runs and unrelated workspace files were untouched.

Private originals remain under `E:\LongContext\gap_prompt_final_real_20261022\01-sqlite-with-gcov-r1\runs\pma-b39bcc4a6c44456a`. This public summary does not copy hidden thought, credentials, private endpoints, full Task messages or hidden test source. SHA-256 below identifies originals, not an alleged byte-identical public transcript:

| Private relative path | SHA-256 |
| --- | --- |
| `archive/live_result.json` | `ecf6a201fc2d79ea64c0663b676e895a0d7cc84a2e18cd9b5606c0113fcde89e` |
| `archive/bootstrap_retry_v1.json` | `189c9454b548990495144e33b9a9756d5b62f4fc84fb00a49053c580a7b1b95c` |
| `archive/native_reports_checked.json` | `989bf2b00e17ffea74a0c35b13e8e4241fe2a4c36dacb6c00b05a2a10708af19` |
| `host_private/archive/gap_cycle.jsonl` | `4eea770e7771d1ea61f31dc2fd0aed8b51707b04624e2c983fbe054cb92adc43` |
| `host_private/archive/gap_visible_transport.jsonl` | `96b19551c6f175c6f281cc8ddf17085c1510001dee9ac1f143177ed4f993e734` |
| `host_private/archive/memory.json` | `b56208fabc13bcd05a3d239b16da5dd1fc17468a27b13cabea4b7b28c7dcc364` |
| `host_private/archive/trajectory_memory.json` | `d6bbda9f481ad2d48699f2df77fbf25602e754a404d68abc8d309062cf6ecf57` |
| `jobs/pma-b39bcc4a6c44456a/public_task__jS5p2xj/agent/research_events.jsonl` | `82c096e08721a52421d9d92e4ac20d00c602d4330045516f63d51e5691267a3a` |

The final-source unified fake chain and separate preparation-boundary tests preceded this run; their synthetic reward is not included in the real outcome. No second real episode or extra evaluation was started.
