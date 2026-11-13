# All manager wakes — mechanical navigation

W1 is the initialization wake before the first Task step. R/A count requested `memory_read`/`memory_add` calls; all A calls below have successful receipts. `C` is accepted `context_for_action`, `N` accepted `no_intervention`. Delivered means the reminder was present in a subsequent actual provider request, not that Task adopted it. Write IDs refer to WRITE_AUDIT.md and the full chronological write timeline in the ZIP.

| Task | Arm | Wake | Responses | R/A | Other tool | Decision | Delivered | Write IDs |
|---|:---:|---:|---:|---:|---|---|---|---|
| kv-store-grpc | A | 1 | 21 | 19/1 | — | N | no | 1 |
| kv-store-grpc | A | 4 | 3 | 1/1 | — | N | no | 2 |
| kv-store-grpc | A | 8 | 3 | 1/1 | — | N | no | 3 |
| kv-store-grpc | B | 1 | 4 | 2/1 | — | C | yes | 4 |
| kv-store-grpc | B | 4 | 3 | 1/1 | — | N | no | 5 |
| kv-store-grpc | B | 8 | 3 | 1/1 | — | C | yes | 6 |
| reshard-c4-data | A | 1 | 8 | 6/1 | — | C | yes | 7 |
| reshard-c4-data | A | 4 | 4 | 2/1 | — | C | yes | 8 |
| reshard-c4-data | A | 8 | 2 | 1/0 | — | C | yes | — |
| reshard-c4-data | A | 12 | 3 | 1/1 | — | C | yes | 9 |
| reshard-c4-data | A | 16 | 6 | 4/1 | — | N | no | 10 |
| reshard-c4-data | B | 1 | 3 | 1/1 | — | N | no | 11 |
| reshard-c4-data | B | 4 | 3 | 1/1 | — | N | no | 12 |
| reshard-c4-data | B | 8 | 5 | 3/1 | — | N | no | 13 |
| reshard-c4-data | B | 12 | 4 | 2/1 | — | N | no | 14 |
| reshard-c4-data | B | 16 | 4 | 2/1 | — | N | no | 15 |
| rstan-to-pystan | A | 1 | 12 | 11/0 | — | N | no | — |
| rstan-to-pystan | A | 4 | 3 | 1/1 | — | N | no | 16 |
| rstan-to-pystan | A | 8 | 2 | 1/0 | — | N | no | — |
| rstan-to-pystan | A | 12 | 5 | 2/1 | code_run | C | yes | 17 |
| rstan-to-pystan | A | 16 | 3 | 1/1 | — | C | yes | 18 |
| rstan-to-pystan | A | 20 | 4 | 2/1 | — | C | yes | 19 |
| rstan-to-pystan | A | 24 | 5 | 3/1 | — | N | no | 20 |
| rstan-to-pystan | B | 1 | 3 | 1/1 | — | N | no | 21 |
| rstan-to-pystan | B | 4 | 3 | 1/1 | — | N | no | 22 |
| rstan-to-pystan | B | 8 | 3 | 1/1 | — | N | no | 23 |
| rstan-to-pystan | B | 12 | 4 | 2/1 | — | C | yes | 24 |
| rstan-to-pystan | B | 16 | 3 | 1/1 | — | C | yes | 25 |
| rstan-to-pystan | B | 20 | 10 | 5/4 | — | C | yes | 26, 27, 28, 29 |
| rstan-to-pystan | B | 24 | 4 | 2/1 | — | C | yes | 30 |
| largest-eigenval | A | 1 | 3 | 1/0 | $ACTION_TYPE | N | no | — |
| largest-eigenval | A | 4 | 3 | 1/1 | — | N | no | 31 |
| largest-eigenval | A | 8 | 3 | 1/1 | — | C | yes | 32 |
| largest-eigenval | A | 12 | 3 | 1/1 | — | C | yes | 33 |
| largest-eigenval | A | 16 | 3 | 1/1 | — | N | no | 34 |
| largest-eigenval | B | 1 | 4 | 1/1 | $FUNCTION_NAME | N | no | 35 |
| largest-eigenval | B | 4 | 3 | 1/1 | — | N | no | 36 |
| largest-eigenval | B | 8 | 3 | 1/1 | — | N | no | 37 |
| largest-eigenval | B | 12 | 4 | 2/1 | — | N | no | 38 |
| largest-eigenval | B | 16 | 3 | 1/1 | — | N | no | 39 |
| largest-eigenval | B | 20 | 4 | 2/1 | — | N | no | 40 |
| largest-eigenval | B | 24 | 6 | 3/2 | — | N | no | 41, 42 |
| filter-js-from-html | A | 1 | 3 | 1/1 | — | N | no | 43 |
| filter-js-from-html | A | 4 | 3 | 1/1 | — | N | no | 44 |
| filter-js-from-html | B | 1 | 4 | 1/1 | file_write | N | no | 45 |

The full visible requests, public responses, tool receipts, bank and subsequent Task requests remain in the ZIP. This table makes no semantic correctness claim. A prompt requiring a read does not ensure a read occurred. The task-ended tail was not given an extra wake.
