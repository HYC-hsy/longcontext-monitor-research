# Results and limitations

| Task | Run ID | Task steps | Manager wakes / responses | Successful read / add | Actual reminder deliveries | Native tests | Reward | Cleanup |
|---|---|---:|---:|---:|---:|---:|---:|---|
| kv-store-grpc | `pma-0a690298e9624945` | 15 | 4 / 11 | 3 / 4 | 1 | 7/7 | 1 | confirmed |
| reshard-c4-data | `pma-c08e486836d5410d` | 25 | 7 / 24 | 11 / 6 | 2 | 1/1 | 1 | confirmed |
| rstan-to-pystan | `pma-cf7b19552b5841c1` | 26 | 7 / 23 | 9 / 7 | 4 | 6/6 | 1 | confirmed |
| largest-eigenval | `pma-c398fcb0730d4651` | 35 | 9 / 37 | 17 / 10 | 2 | 3/3 | 1 | confirmed |
| filter-js-from-html | `pma-0f564497efc843f9` | 2 | 1 / 3 | 1 / 1 | 0 | 0/2 | 0 | confirmed |

All five slot dispositions are `completed`; all native evaluations ran. There were 28 wakes, 98 manager responses, 41 successful `memory_read` receipts, 28 successful `memory_add` receipts, and nine reminders verified in subsequent Task requests. These counts are from the original logged events; a decision or queued reminder was not counted as delivery. One extra `$ACTION_CALL` attempt in largest-eigenval was rejected by the manager tool boundary and is not counted as a successful memory operation. For the HTML task, two Task steps ended before any later four-step wake; the saved initial requirement was not a remedy for the failed native tests.

Compared with the earlier `5dc85672...` archive, the reward vector here is `1,1,1,1,0` versus `0,0,0,1,0`. This run changed the save criterion, recall wording, and wake frequency together. Different single trajectories and model stochasticity prevent attribution to any one change or a stable improvement claim. In particular, a delivered reminder is not proof that Task adopted it, and reward is not proof that every saved statement was correct.

The Task usage records contain provider-reported token fields in the ZIP. Manager responses had no usable per-response usage records or return model IDs, so manager tokens and total cost are `unknown`. Physical HTTP attempts are likewise `unknown`; do not infer them from logical response counts. The Task profile and manager profile hashes in the run configuration establish configuration identity, not service-side defaults.
