# Two-tool continuous-context PMA: two real Tasks

This archive is a redacted **visible projection**, not raw provider HTTP. Private originals remain on the development machine. The companion ZIP contains full recorded visible Task events, P1/P2 requests and responses, tool receipts, memory snapshots, run identities, native evaluation summaries, and cleanup records. Its `SOURCE_MAP.json` maps each included projection to the local original's size and SHA-256; `FIELD_EXCLUSIONS.json` lists omitted sensitive fields. Hidden test names, assertions, stdout, provider-private thinking/signatures, complete profiles, credentials, and private endpoints are excluded.

## Identity and preflight

- Execution SHA: `cdb32d3c60b7471f2b6dfb00b29049ffb6b55e8c`; method: `pma-predictive-read-context` (`pma_predictive_read_context_v1`).
- Parent method SHA: `4eb35705418a8e3265d17dcf9c9d9b02e1aaea15`. The only new change is a Windows offline-test fixture exception for Python `asyncio`'s local `socketpair`; production method, prompts, models, and runtime policy are unchanged.
- Dataset: `2fd12b88aafdd04a52c298e3940bcb189f9766d6`; native Harbor: `459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc`.
- Same Task/PMA profile hashes as the preceding four-slot run: Task `ed09a811b654b83097bee77942704eae2539d67291bf55aa34476692081ff02e`; PMA `cc5f784b069034f44bc4527d15acd70191b1f7fc5810556c087b7b35e0ae00f1`. Task model: `claude-opus-4-8`, max tokens 64000, temperature 1, max retries 4. PMA model: `claude-opus-4-8`, max tokens 8192, temperature 1, max retries 8, Anthropic messages/adaptive thinking, read timeout 300 s.
- Effective Task agent duration and turns: uncapped; outer timeout: none; native verifier: official 1800 s for rstan, 900 s for nginx. These are diagnostic agent-limit overrides, not official agent-time-budget scores.
- First Windows test attempt: 204 passed, 33 failed, 3 skipped. The socket guard mistakenly blocked local `asyncio` event-loop setup. After the test-only repair: **237 passed, 3 skipped**. No real calls were used in this offline check.

## Results

| Task | run_id | Task end / native reward | Tests | Actor calls / observed steps | P1 / P2 logical calls | Adds / reads | Reminder appended | Cleanup |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rstan-to-pystan | `pma-6211a5505a844fc7` | completed / 1.0 | 6/6 | 28 / 27 | 9 / 4 | 6 successful adds / 0 successful reads | 2 | confirmed |
| nginx-request-logging | `pma-60c35849065b4ba9` | completed / 1.0 | 8/8 | 10 / 9 | 6 / 2 | 4 successful adds / 0 successful reads | 1 | confirmed |

The Task-visible provider usage records report, respectively, input/output/cache-creation/cache-read token counts of `36551/11700/29744/330438` for rstan and `12358/4015/5016/67196` for nginx. PMA token totals, physical HTTP attempts, and dollar cost are not reliably recorded here and are `unknown`, not estimated.

Both real runs attempted `memory_read` with `{"_noargs":"unused"}`. The fixed two-tool contract correctly returned `memory_read takes no arguments; call it with {}`; neither run produced a successful read. Rstan also received the unsupported literal tool name `$FUNCTION_NAME` and returned an explicit error. P1 continued within its bounded recovery rules; neither error was hidden as a successful read. These are observed protocol behaviors, not proof that the model understood the bank.

Both runs exited with launcher/Harbor/worker return code 0 and native evaluation recorded. The writer check found no remaining registered control processes before evaluation. Rstan had no task-owned process preserved; nginx preserved its server processes for verification. Final per-run sidecar, container, and owned-volume cleanup was confirmed clean. No Task was rerun to obtain these results.

The two single-episode results are diagnostic only; they do not establish statistical superiority or prove the no-argument interface will elicit valid model calls.
