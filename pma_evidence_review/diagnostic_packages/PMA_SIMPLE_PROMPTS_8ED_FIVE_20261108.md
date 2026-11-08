# 8ed simple-prompts five-task run

Execution code: `8ed3a7f8958db8c3f5807bd7276b9413d1d5f934`. Dataset: `2fd12b88aafdd04a52c298e3940bcb189f9766d6`. Harbor: `459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc`. Method: `pma-predictive-read-context`, condition B, future-ten-turn selection guidance, eight-new-step wake interval. Five tasks were launched serially once each with `agent_timeout=uncapped`, `task_turns=uncapped`, and official per-task verifier timeouts. The local originals remain separate from this public, redacted visible projection.

| Order | Task | Run ID | Native reward | Tests | Cleanup |
|---|---|---|---:|---|---|
| 1 | kv-store-grpc | `pma-2b17a59b88dd40c0` | 1 | 7 passed / 0 failed | confirmed |
| 2 | reshard-c4-data | `pma-cf8b7f5b6f1b404e` | 0 | 0 passed / 1 failed | confirmed |
| 3 | rstan-to-pystan | `pma-018b0dbd5c8044a2` | missing | report not produced | confirmed |
| 4 | largest-eigenval | `pma-2561048037114ebd` | 1 | 3 passed / 0 failed | confirmed |
| 5 | filter-js-from-html | `pma-6f0da49b970e47d2` | missing | report not produced | confirmed |

The two missing native reports followed `uv 0.9.5` download HTTP 504 errors inside the official verifier; `uvx` was then unavailable. They are **not** zero rewards or model-semantic failures. The runner's safe `on_slot_failure=continue` path launched the remaining independent slots only after each slot's cleanup was confirmed. There were no automatic Task retries. The available evaluated mean is 2/3; coverage is 3/5, not a complete five-task score.

The ZIP contains per-slot visible Task and PMA records, request/response and tool traces, runtime identity and policy, native evaluation status, cleanup records, preflight logs, source-to-projection hash mapping, and an internal file index. Hidden test bodies, provider private thinking/signatures, credentials, complete private profiles, endpoints, and task workspaces are excluded. This is a redacted visible projection, not original HTTP bytes.

The eight-to-three-step wake-frequency condition has **not** started. The verifier dependency failure should be resolved or explicitly accepted as an unresolved comparability limitation before that condition's real runs.
