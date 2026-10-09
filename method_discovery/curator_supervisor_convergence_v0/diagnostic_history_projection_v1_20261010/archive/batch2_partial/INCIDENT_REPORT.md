# C02 H/R replacement batch — second transport stop

This is a separate, complete restart of the planned H/R order using unchanged model-visible requests and unchanged implementation code hashes. The freeze source commit differs from batch 1 only because the first partial archive was committed. Seven slots started; five planned slots did not start. No slot was selectively rerun.

## Mechanical slots

| Slot | Terminal | Provider requests | Accepted responses | Proposed tools | Ordinary tool port calls |
| --- | --- | ---: | ---: | ---: | ---: |
| C02-P1-H | release_proposal | 15 | 15 | 21 | 16 |
| C02-P1-R | release_proposal | 11 | 11 | 17 | 15 |
| C02-P2-R | intervention_proposal | 6 | 6 | 18 | 17 |
| C02-P2-H | intervention_proposal | 16 | 16 | 23 | 22 |
| C02-P3-H | release_proposal | 14 | 14 | 15 | 14 |
| C02-P3-R | intervention_proposal | 6 | 6 | 7 | 6 |
| C02-P4-R | protocol_or_infrastructure_failure | 1 | 0 | 0 | 0 |

At `C02-P4-R/audit/events.jsonl` line 5, the actual first pre-send request has the frozen R canonical SHA-256 `c4d5366bdaaeaa5f05a41cd760eefe411bfedbace9bbba3a2aad05bd243f2158`. Line 6 records `ProxyError` before response headers or an SSE file existed. Line 8 records the failed terminal. The adapter did not retry the ambiguous request and stopped further slots. This is transport failure, not a diagnostic-quality classification.

The five unstarted slots are C02-P4-H, C02-P5-H, C02-P5-R, C02-P6-R, C02-P6-H. Thirty-eight `code_run` script-byte receipts were exact. The archive indexes 485 files; all indexed SHA-256 values match ZIP contents and ZIP CRC validation passes.

## Transport diagnosis, not an experimental result

The configured Windows Requests environment discovers a system HTTPS proxy even though no proxy environment variable or explicit profile proxy is set. Requests' default environment trust therefore permits the proxy route. A no-model, credential-free direct TLS handshake verified the endpoint certificate; a no-model direct HTTP HEAD reached the same configured endpoint with status 200. These checks establish that a direct route was available at diagnosis time. They do not prove the exact cause of either batch's failure, nor do they authorize mixing batch versions or replaying a failed slot.

Task Agent, native evaluator, training, scoring-model and production-code changes: 0. No quality comparison of H and R is made here.
