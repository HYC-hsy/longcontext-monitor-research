# Four-model batch, stopped after GPT identity failure

Execution code: `98b166aa747da9f5b7e9f0f9d677c25d77d3611a`  
Dataset: `2fd12b88aafdd04a52c298e3940bcb189f9766d6`  
Harbor: `459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc`  
Method: `pma-predictive-read-context`; serial; `agent_timeout=uncapped`, `task_turns=uncapped`, `verifier_timeout=official`.

The revised order put all 15 Claude slots first, then the five `gpt-6-sol` slots. Each slot had a fresh run ID and environment. This archive covers the 17 slots actually attempted; it does not silently fill the three unstarted GPT slots.

| Task | Opus 4.8 | Opus 5 | Fable 5 | GPT 6 Sol |
|---|---:|---:|---:|---:|
| kv-store-grpc | 1 | 1 | 1 | 1 |
| reshard-c4-data | 1 | 0 | 1 | no evaluation; P1 engineering failure |
| rstan-to-pystan | 0 | 1 | 0 | not started |
| largest-eigenval | 0 | 1 | 0 | not started |
| filter-js-from-html | 0 | 0 | 0 | not started |

The 15 Claude slots completed native evaluation and owned-resource cleanup: Opus 4.8 `2/5`, Opus 5 `3/5`, Fable 5 `2/5`. The first GPT slot completed native evaluation (`reward=1`). The next GPT slot, run `pma-ff5f357adb6f4cc9`, reached eight Task steps, then P1 raised `RuntimeError: PMA provider returned a different model identity`. No native evaluation occurred. Its remaining owned Docker volume was removed after confirming no containers remained. The batch stopped; GPT slots 10, 13, and 20 did not start. Neither the failed slot nor unstarted slots are scored as zero.

These are one-run development observations, not a stable model ranking. The failed GPT slot's partially accepted Task/PMA calls and terminal records are retained in the ZIP. The raw local originals remain private. The ZIP is a selected complete *visible* projection of Task and P1/P2 records, runtime/evaluation summaries, errors, and cleanup records; it is not raw HTTP bytes or a restorable execution directory. Private thinking/signatures, credentials, private endpoints, profiles, hidden verifier content, source bundles, and unrelated files are excluded. The external index maps each included public member to its original and projected SHA-256 and lists missing material.

The previous order's slot 1 completed but was discarded at the user's request when restarting; its run outputs were cleaned and are not represented as part of this batch.
