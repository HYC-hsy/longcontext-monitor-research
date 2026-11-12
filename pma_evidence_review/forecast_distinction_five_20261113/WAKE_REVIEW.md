# All manager wakes — mechanical navigation

W1 is the initialization wake before the first Task step. R/A count requested `memory_read`/`memory_add` calls; all A calls below have successful receipts. `C` is accepted `context_for_action`, `N` accepted `no_intervention`. Delivered means the reminder was present in a subsequent actual provider request, not that Task adopted it. Write IDs refer to WRITE_AUDIT.md and the full chronological write timeline in the ZIP.

| Task | Wake | Responses | R/A | Other tool | Decision | Delivered | Write IDs |
|---|---:|---:|---:|---|---|---|---|
| kv-store-grpc | 1 | 13 | 12/0 | — | N | no | — |
| kv-store-grpc | 4 | 3 | 1/1 | — | N | no | 1 |
| kv-store-grpc | 8 | 2 | 1/0 | — | N | no | — |
| kv-store-grpc | 12 | 2 | 1/0 | — | N | no | — |
| kv-store-grpc | 16 | 2 | 1/0 | — | N | no | — |
| reshard-c4-data | 1 | 4 | 2/0 | $BROWSER | N | no | — |
| reshard-c4-data | 4 | 2 | 0/1 | — | N | no | 2 |
| reshard-c4-data | 8 | 2 | 1/0 | — | C | yes | — |
| reshard-c4-data | 12 | 2 | 1/0 | — | N | no | — |
| reshard-c4-data | 16 | 2 | 1/0 | — | C | yes | — |
| reshard-c4-data | 20 | 2 | 1/0 | — | C | yes | — |
| reshard-c4-data | 24 | 3 | 1/1 | — | N | no | 3 |
| reshard-c4-data | 28 | 4 | 2/1 | — | C | yes | 4 |
| reshard-c4-data | 32 | 2 | 1/0 | — | C | yes | — |
| rstan-to-pystan | 1 | 11 | 10/0 | — | N | no | — |
| rstan-to-pystan | 4 | 3 | 1/1 | — | N | no | 5 |
| rstan-to-pystan | 8 | 4 | 2/1 | — | C | yes | 6 |
| rstan-to-pystan | 12 | 6 | 3/2 | — | C | yes | 7, 8 |
| rstan-to-pystan | 16 | 4 | 1/1 | file_read | N | no | 9 |
| rstan-to-pystan | 20 | 5 | 3/1 | — | C | yes | 10 |
| rstan-to-pystan | 24 | 4 | 2/1 | — | C | yes | 11 |
| rstan-to-pystan | 28 | 3 | 1/1 | — | N | no | 12 |
| rstan-to-pystan | 32 | 4 | 2/1 | — | C | yes | 13 |
| rstan-to-pystan | 36 | 3 | 1/1 | — | N | no | 14 |
| largest-eigenval | 1 | 3 | 1/0 | $ACTION_read_file, $ACTION_read_file | N | no | — |
| largest-eigenval | 4 | 2 | 0/1 | — | C | yes | 15 |
| largest-eigenval | 8 | 2 | 0/1 | — | C | yes | 16 |
| largest-eigenval | 12 | 3 | 1/1 | — | N | no | 17 |
| largest-eigenval | 16 | 4 | 2/1 | — | C | yes | 18 |
| largest-eigenval | 20 | 2 | 1/0 | — | C | yes | — |
| largest-eigenval | 24 | 3 | 1/1 | — | C | yes | 19 |
| largest-eigenval | 28 | 5 | 2/2 | — | C | yes | 20, 21 |
| largest-eigenval | 32 | 5 | 3/1 | — | N | no | 22 |
| largest-eigenval | 36 | 4 | 2/1 | — | C | yes | 23 |
| filter-js-from-html | 1 | 13 | 11/1 | — | N | no | 24 |

The full visible requests, public responses, tool receipts, bank and subsequent Task requests remain in the ZIP. This table makes no semantic correctness claim. A prompt requiring a read does not ensure a read occurred; see W4 of reshard and W4/W8 of eigen. The task-ended tail was not given an extra wake.
