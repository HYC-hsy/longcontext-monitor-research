# Bank-ID two-tool PMA: one nginx real Task

This package is a redacted **visible projection**, not raw provider HTTP. Private originals remain on the development machine. The ZIP includes the complete recorded visible Task events, P1/P2 requests and responses, tool calls and receipts, knowledge snapshots, original task, runtime identity, native evaluation summary, and resource-cleanup records. `SOURCE_MAP.json` gives the local original and public-projection size/SHA-256 for every included file; `FIELD_EXCLUSIONS.json` records omitted sensitive fields. Hidden test names, assertions, stdout, provider-private thinking/signatures, complete profiles, credentials, and private endpoints are excluded.

## Fixed identity and preflight

- Execution SHA: `b17151b8d57c61cfb4e058ad1601225f9fa2ea15`; method: `pma-predictive-read-context` (`pma_predictive_read_context_v1`). This commit changes the two-tool read contract to require exactly `{"bank_id":"knowledge"}`. No additional production repair was made for this run.
- Dataset SHA: `2fd12b88aafdd04a52c298e3940bcb189f9766d6`; native Harbor SHA: `459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc`.
- Prior-run profile hashes reused unchanged: Task `ed09a811b654b83097bee77942704eae2539d67291bf55aa34476692081ff02e`; PMA `cc5f784b069034f44bc4527d15acd70191b1f7fc5810556c087b7b35e0ae00f1`.
- Both model IDs: `claude-opus-4-8`. Task: max tokens 64000, temperature 1, max retries 4. PMA: max tokens 8192, temperature 1, max retries 8, Anthropic messages/adaptive thinking, read timeout 300 s.
- Effective Task-agent duration and turns: uncapped; outer Task timeout: none; native verifier: official 900 s. This is a diagnostic agent-limit override, not an official agent-time-budget score.
- Target Windows zero-model selected regression: **259 passed, 3 skipped**. The real Harbor LiteLLM adapter and installed Anthropic request/response transforms were used with synthetic provider replies; this was not a real model call.

## One Task and native result

- Task: `nginx-request-logging`; run_id: `pma-702ab451a8fd4bbd`.
- Task, launcher, Harbor, and PMA worker completed with exit code 0. Native verifier ran once: **8/8 tests passed**, reward **1.0**.
- Actor: 11 model calls, 10 observed steps. P1: 8 logical calls; P2: 2 logical calls. Six `memory_add` operations succeeded; final bank size: six. P2 chose no intervention twice; **zero reminders** entered subsequent Task requests.
- The model made one `memory_read` call with the exact arguments `{"bank_id":"knowledge"}`. The call ID `toolu_jP7lswfdTct0iZdnqW9hle` had a matching success receipt in the same P1 wake. It read the then-empty bank (`<memory_bank>(empty)</memory_bank>`); the model subsequently added information. It did **not** read the later populated bank. No invalid or unopened tool calls were recorded.
- Task-visible provider usage records: input 13,640; output 4,833; cache-creation input 9,060; cache-read input 69,142 tokens. PMA token totals, physical HTTP attempts, and dollar cost are not reliably recorded and are `unknown`.
- Before evaluation, the writer check found zero remaining registered control processes; nginx service processes were intentionally preserved for native verification. Final sidecar, container, and owned-volume cleanup was confirmed clean.

This single episode verifies an actual valid read and receipt in this run. It does not establish that the model will consistently choose to read when useful, that reminders improve behavior, or that this method is statistically better than another version.
