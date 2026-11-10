# Public-explanation P1: five completed real runs

This is a public visible projection, not raw HTTP bytes. The private originals remain on the development machine. The ZIP and external index cover all five completed episodes, including visible Task events, P1/P2 requests and responses, tool calls and receipts, memory, native-evaluation status, and resource cleanup. The index maps each original file hash to its projected file hash.

- Fixed execution code: `4964b7dc88135ba2ab527d4aa9bb521cd7a2cb8a` (unchanged and clean during execution).
- Data: `2fd12b88aafdd04a52c298e3940bcb189f9766d6`; Harbor: `459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc`.
- Method: `pma-predictive-read-context` / `pma_predictive_read_context_v1`; Task model profile SHA-256 `ed09a811b654b83097bee77942704eae2539d67291bf55aa34476692081ff02e`; PMA profile SHA-256 `c568aac2b3042f852537a7302bae48e756bbaea74f732ff7e985298d7b2a98e6`.
- Runtime: Task agent total time and turns uncapped; outer total deadline uncapped. Each task retained its official verifier limit. The non-sensitive runtime receipts are in each run's `archive/runtime_policy_effective.json`.

| Task | Run ID | Actor steps | P1 / P2 responses | P1 public explanation nonempty / empty | Native reward | Cleanup |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| kv-store-grpc | `pma-c2b040d952954074` | 14 | 2 / 2 | 1 / 1 | 1 | clean |
| reshard-c4-data | `pma-13aedb1731c64e6b` | 21 | 7 / 3 | 2 / 5 | 0 | clean |
| rstan-to-pystan | `pma-54e82c7f1aae415e` | 25 | 7 / 4 | 2 / 5 | 0 | clean |
| largest-eigenval | `pma-d2efc09181d048a0` | 16 | 6 / 2 | 2 / 4 | 1 | clean |
| filter-js-from-html | `pma-2584a2fdf6404f25` | 2 | 1 / 1 | 1 / 0 | 0 | clean |

All five Task episodes recorded an original native evaluation. Each runner slot exited successfully and its resource-clearance flag is true. The visible event receipts did not confirm a reminder in any later GA request (`returned_not_confirmed_in_ga_request`); this is **zero confirmed deliveries**, not proof that reminders were useful or unnecessary. The public explanation count measures nonempty ordinary `content` in P1 responses, not hidden reasoning or explanation quality. No model output was repaired or a low-reward task rerun.

The first `kv-store-grpc` launch encountered missing fixed-commit package material in the sparse checkout before any model call. A second pre-Task launch exposed a PowerShell native-stderr handling issue; both failed claims and original logs remain local. Restoring the omitted package from the same commit, correcting stderr capture, and preparing a fresh first-slot output allowed the final unchanged-code serial run. The ZIP contains the final batch log and a preparation record describing these failures; the superseded local pre-Task artifacts are not presented as completed episodes.

Public projection excludes private profiles, credentials, private endpoints, provider private thinking/signatures, source bundles and hidden verifier content. It keeps the ordinary visible content, ordering, errors, status and hashes. No semantic effect conclusion is drawn from five single runs; the historical Opus 5 group is contextual, not a controlled contemporaneous comparison.
