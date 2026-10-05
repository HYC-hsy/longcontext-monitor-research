# RSH-v0 four-slot raw archive

Execution was authorized after the frozen implementation
`0f02c15c0c849bf255fad4cfcc768c58e2c4ad60` and historical non-executing
plan `ff64d9303956b35795460e6fde6d308374f33a50`. The plan's original
`execution_authorized=false` is unchanged; the separate
`EXECUTION_AUTHORIZATION.json` and four `AUTH_*.json` files govern this batch.
`PLAN.json` and `RUNNER_MANIFEST.json` preserve the exact execution identities.

The four fresh slots ran once in `PLAN.json` order. Host progress and original
per-slot entry logs are under `host_execution/`. Each `records/<ordinal>_<id>/`
contains copied trial/runner/Task/Monitor/bridge/native-evaluator originals,
`RAW_FILE_MANIFEST.json`, and mechanical indexes. The full provider-visible RSH
horizon is in `monitor/audit/dialogue.jsonl` both as the first root DCM tool
receipt's `release_support_horizon` and the matching `rsh_horizon_emitted` audit
event. `RSH_MECHANICAL_INDEX.json` points to exact dialogue lines. DCM and CFS
indexes are adjacent; originals remain authoritative.

Large scoring-boundary `/app` tar artifacts are retained locally at the exact
paths, sizes and SHA-256 recorded in each `RAW_FILE_MANIFEST.json`; they are not
duplicated into Git. `ARCHIVE_INTEGRITY.json` verifies copied bytes, local tar
bytes, and absence of configured private gateway header values in uploaded
archive material. It does not interpret task semantics or model behavior.

`BLOCK_MECHANICAL_SUMMARY.json` is a derived count/index only. Native evaluation
appears separately in each original trial result and verifier directory. No
record was rerun and no extra scientific slot was started.
