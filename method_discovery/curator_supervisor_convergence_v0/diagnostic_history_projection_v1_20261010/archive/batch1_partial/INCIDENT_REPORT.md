# C02 H/R static diagnostic batch — partial mechanical report

Status: stopped after four started slots; eight planned slots were not started. No slot was rerun or replaced.

## Frozen identity and offline gate

- Research source commit: `c92a7b76f67b40341461124af1f0076eda510943`.
- Source request: 96 messages; canonical SHA-256 `31635aae9700c23c7357ecbc4cc4ebf8d4cdb8d4b8a1d55c47f19dccb876c72a`.
- H request: same canonical SHA-256. R request: 9 messages; canonical SHA-256 `c4d5366bdaaeaa5f05a41cd760eefe411bfedbace9bbba3a2aad05bd243f2158`.
- Projection: 182 retained and 50 removed early blocks; 52 historical tool-use/result pairs. Native messages 88–95 remain unchanged. The inverse check parsed the actual R request text.
- Run identity file SHA-256: `66f94661163c2952acd27bb4d1bc0d6946a4d82fe73f128962bd409ae4271558`.
- Targeted zero-model regression: `python -m unittest method_discovery.curator_supervisor_convergence_v0.diagnostic_history_projection_v1_20261010.test_projection method_discovery.curator_supervisor_convergence_v0.diagnostic_history_projection_v1_20261010.test_runtime method_discovery.curator_supervisor_convergence_v0.diagnostic_static_adapter_v1_20261009.test_protocol method_discovery.curator_supervisor_convergence_v0.diagnostic_static_adapter_v1_20261009.test_docker_tool -q`; 29 tests passed in 395.943 seconds. This used fake provider transport and the actual isolated Docker tool path, with no live model calls.

## Started slots

| Slot | Terminal | Provider requests | Accepted responses | Proposed tool calls | Ordinary tool port calls | Polls |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| C02-P1-H | release_proposal | 6 | 6 | 9 | 8 | 4 |
| C02-P1-R | intervention_proposal | 2 | 2 | 5 | 4 | 0 |
| C02-P2-R | release_proposal | 13 | 13 | 18 | 17 | 10 |
| C02-P2-H | protocol_or_infrastructure_failure | 6 | 5 | 10 | 10 | 4 |

No parameter rejections, not-executed calls, or transport retries were recorded in these slots. Sixteen recorded `code_run` script-byte checks matched the submitted UTF-8 bytes.

## Stop trigger

In `C02-P2-H/audit/events.jsonl`, line 71 is `provider_incomplete_or_failed` for request 6, with `error_type=SSLError` and `raw_stream_exists=false`. Line 73 records `failed_terminal` with `error_type=RetryableProviderError`. `request_06.json` exists; `stream_06.sse` does not. The first five requests have response streams and accepted responses. The adapter made no ambiguous transport retry, and the parent stopped the batch. This is a transport failure, not a semantic judgment about H or R.

Planned but unstarted: C02-P3-H, C02-P3-R, C02-P4-R, C02-P4-H, C02-P5-H, C02-P5-R, C02-P6-R, C02-P6-H.

## Archive integrity and boundaries

`RAW_TRACE_INDEX.json` indexes 234 raw/frozen files. Their SHA-256 values match the ZIP members; ZIP CRC verification found no error. The ZIP has one additional member, the index itself. The original raw run root remains at `E:\static_diagnostic_C02_HR_20261010_batch1`.

Task Agent, native evaluator, training, and scoring-model calls: 0. Production changes: 0. The first three terminal proposals are retained without developer-side quality scoring. H/R outcomes are not pooled with earlier B/F batches or interpreted as Task success.
