# PMA simple prompts: wake every 3 steps, five tasks

This is a public, redacted visible projection, not raw HTTP bytes. Private originals remain local. The ZIP contains the serial run log, selection and per-run identity/policy records, visible Task and PMA traces, native-evaluation summaries, and cleanup records. `SOURCE_MAP.json` maps each public file to the local original's size and SHA-256; `FIELD_EXCLUSIONS.json` records redacted fields. Hidden thinking/signatures, credentials, private endpoints/profiles, hidden test bodies, and task workspaces are excluded.

Execution commit: `e5a7a10d5a8d17c8c831ad23fd46db2e40142028` (the simple-prompt candidate with wake interval changed from 8 to 3 and evaluation-cache integration). Dataset: `2fd12b88aafdd04a52c298e3940bcb189f9766d6`; Harbor: `459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc`. Method: `pma-predictive-read-context`, condition B, candidate `pma_predictive_read_context_v1`. Task agent total time and turns were uncapped; verifier used each task's official limit. Single-request and environment-setup limits remained.

| Task | Run ID | Reward | Native tests | Cleanup |
| --- | --- | ---: | ---: | --- |
| kv-store-grpc | `pma-a18c529b4be34e74` | 1 | 7/7 | confirmed |
| reshard-c4-data | `pma-ce79deff81974f14` | 1 | 1/1 | confirmed |
| rstan-to-pystan | `pma-ed02e35aa3df4a88` | 1 | 6/6 | confirmed |
| largest-eigenval | `pma-ef432451d7de4896` | 1 | 3/3 | confirmed |
| filter-js-from-html | `pma-b02da28ed34b4456` | 0 | 0/2 | confirmed |

All five tasks were attempted once in the frozen order. All five produced native reports; all owned run resources passed cleanup. Evaluation dependency protocol was the original path for kv-store-grpc, reshard-c4-data, and largest-eigenval, and `prepared_dependency_bundle_v1` for rstan-to-pystan and filter-js-from-html. The latter restores prechecked evaluator dependencies only after the Task agent finishes; it does not guarantee that task execution or model transport is offline. This is a cross-batch, exploratory comparison with the wake-8 results, not a strict same-environment or causal estimate.

The adjacent `.index.json` gives ZIP byte count, SHA-256, and per-member sizes and hashes. ZIP CRC and member hashes were checked locally and should be checked again after remote download.
