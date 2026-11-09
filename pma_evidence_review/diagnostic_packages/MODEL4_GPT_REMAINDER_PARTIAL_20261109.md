# GPT remainder: new model-ID recording, two attempted slots

Execution source: `deacf72b8512c7fcdf774d93633c8a5ca6fc0181`.
Dataset: `2fd12b88aafdd04a52c298e3940bcb189f9766d6`.
Harbor: `459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc`.
Method: `pma-predictive-read-context`; requested P1/P2 model `gpt-6-sol`; agent time and turns uncapped; official per-task verifier timeout.

This is a new-code continuation of the earlier partial batch archived at `172f7c235c09c2873bd471fdab80baba20de6a6f`. The old completed slots and the old interrupted reshard run were not overwritten or counted as these new results. The only production changes from `98b166aa747da9f5b7e9f0f9d677c25d77d3611a` remove exact response-model equality as an acceptance gate and log requested/returned model ID, response ID, and status separately. Prompt, memory protocol, tool handling, scheduler, and native evaluation were not changed. The targeted zero-model transport suite passed 11/11.

| Slot | Task | New run ID | Task / native status | Reward | Owned cleanup |
|---|---|---|---|---:|---|
| 07 | reshard-c4-data | `pma-efbd97b8c2a04ecb` | completed; native evaluation recorded | 1 | confirmed |
| 10 | rstan-to-pystan | `pma-d3cccc6cdb8b489b` | first P1 failed; native evaluation not run | missing | runner recorded incomplete; remaining owned volume removed after process/container check |
| 13 | largest-eigenval | — | not started | missing | — |
| 20 | filter-js-from-html | — | not started | missing | — |

The rstan P1 response contained an unrequested `web_search_call`. The adapter rejected that unsupported output item; this is a different failure from model-ID mismatch. Its sole PMA logical call is recorded with request and returned model metadata. No unsupported tool call was replayed or treated as ordinary text. This is an engineering/protocol stop, not a semantic failure or reward 0. The batch intentionally stopped before slots 13 and 20; no task was automatically restarted.

The ZIP is a public *visible projection*, not raw HTTP bytes or a restorable runtime. It includes actual visible Task and P1/P2 records, effective GPT requests, logs, identities, native evaluation summaries, failure and cleanup records for the two attempted slots. Private thinking/signatures, credentials, private endpoints/profiles, hidden verifier content, source bundles, and unrelated files are excluded. Local private originals are retained. The index maps included source-file hashes to public-member hashes and lists missing slots.
