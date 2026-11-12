# Limited observations

| Task | Run ID | Actor steps | Manager wakes/responses | Native tests | Reward | Final bank items | Delivered reminders |
|---|---|---:|---:|---:|---:|---:|---:|
| kv-store-grpc | `pma-1d3ce2b96af14eab` | 14 | 2/4 | 5/7 | 0 | 2 | 0 |
| reshard-c4-data | `pma-58e79e94b969400a` | 20 | 3/9 | 1/1 | 1 | 3 | 0 |
| rstan-to-pystan | `pma-9a98cb669b4c456c` | 26 | 4/9 | 6/6 | 1 | 4 | 0 |
| largest-eigenval | `pma-56f5cf260ef04f0d` | 37 | 5/14 | 3/3 | 1 | 5 | 0 |
| filter-js-from-html | `pma-b35ae7985d2d404b` | 6 | 1/2 | 0/2 | 0 | 1 | 0 |

All episodes ended and owned-resource cleanup was confirmed. The manager saved 15 items through successful `memory_add` receipts. `memory_read` succeeded once in reshard and twice in eigenval. The model also attempted unavailable `execute_command`/`code_run` in reshard and placeholder-named tools in eigenval; these returned errors rather than being executed. There were no actual reminder deliveries, so these runs cannot show that a reminder changed Task behavior.

The prompt did elicit public future-use language in several wakes. Yet the saved content was not consistently limited to information first needed after four turns: initial banks restated immediate task requirements, while later banks often summarized current progress or just-observed failures. For example, kv-store saved the immediate gRPC contract and then the protoc-generated filenames; rstan saved task constraints, R-script sampling settings, a dimension-mismatch diagnosis, then the PyStan array-axis result. The reshard bank includes a broad final accomplishment statement that should not be treated as independently verified beyond the visible receipts. The eigenval bank preserves multiple successive failed-approach summaries, overlapping rather than replacing them. Filter ended after six actor steps, so its initial wake had only a short later-use observation window. The wake index records exactly how many later steps were visible; it does not label semantic use.

Compared with the preceding `4b5d8642d9f1070921cea122363473de3092d871` five-run archive, reward changed from 1/0/1/1/0 to 0/1/1/1/0 in task order. Both sets have one run per task and different Task trajectories; this is descriptive, not a prompt-effect estimate. The preceding archive is at commit `2e7d1370b849f2a7e633a5ede425f1a3d92c668e` under `pma_evidence_review/info_forecast_five_20261111/`.

The ZIP contains the full visible sequence needed to audit claims against contemporaneous inputs, tool receipts, and subsequent actor steps. No private reasoning was extracted or reconstructed. Native failures are represented by counts and public traces, not hidden test bodies. Task-reported tokens are available; manager token usage, full dollar cost, and physical provider attempt counts are unknown.
