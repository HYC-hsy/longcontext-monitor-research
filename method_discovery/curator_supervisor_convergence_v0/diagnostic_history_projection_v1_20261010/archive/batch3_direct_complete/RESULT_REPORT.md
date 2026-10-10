# C02 H/R static diagnostic — complete direct-transport batch

This is the first completed 12-slot H/R batch. The prior `batch1_partial` and `batch2_partial` are retained as separate infrastructure-interrupted attempts and are not pooled with it. No developer-side semantic winner or correctness score is assigned.

## Frozen identities

- Source commit: `b477c0a8909e44ef9b6263e9dd5c8ee56e04db4a`.
- H first-request canonical SHA-256: `31635aae9700c23c7357ecbc4cc4ebf8d4cdb8d4b8a1d55c47f19dccb876c72a`.
- R first-request canonical SHA-256: `c4d5366bdaaeaa5f05a41cd760eefe411bfedbace9bbba3a2aad05bd243f2158`.
- Model: `claude-opus-4-8`; Task image: `sha256:b0da1cb31d367df38d05b81f98e68a94b0f7114efd3c82537633d1d92325efe1`.
- Host limit: 300 new outer model cycles per slot. No added request, tool-call, or diagnostic wall-clock ceiling.
- Transport correction: research-only Requests Session with `trust_env=false`, same HTTPS endpoint and model route, certificate verification enabled, no ambiguous-request retry. This avoids automatically inherited Windows system proxy settings. It does not alter model-visible request payloads.

## Offline gates

- Original projection protocol/path regression: 29 tests passed, including actual isolated Docker tool-path execution with fake provider transport.
- Direct-transport path regression: 10 tests passed, including the child-to-certified-loop Session wiring and no-proxy/TLS-verify settings.
- Projected early history: 182 retained blocks and 50 removed early assistant thinking/free-text blocks; 52 historical tool-use/result pairs. Native messages 88–95 remain unchanged. Reverse validation parsed the actual R request text, not cached source blocks.

## Mechanical run result

All 12 planned slots started and terminated normally; all child exit codes were zero. There were 190 provider requests and 190 accepted responses, 190 outer model cycles, 248 proposed tool calls, 226 ordinary tool-port calls, 137 tool polls, 8 parameter rejections and 2 co-occurring ordinary calls recorded `not_executed`. No transport retries were made. Terminal proposals: 9 release, 3 intervention. These are static diagnostic proposals only; no Task message was delivered and no real completion was executed.

The archived request JSON bytes total 27,196,464 for H and 30,733,566 for R, reflecting different subsequent trajectories rather than equalized input length. Provider usage records (not cost-normalized): H input 42,255, cache-read 1,932,097, cache-create 4,130,907, output 9,903 tokens; R input 43,870, cache-read 3,643,993, cache-create 4,486,176, output 18,759 tokens. Per-slot usage and duration are in `BATCH_RESULT.json` inside the ZIP.

Sixty-seven `code_run` script-byte receipts matched submitted UTF-8 exactly. `RAW_TRACE_INDEX.json` indexes 975 raw/frozen files; every indexed SHA-256 matches the ZIP member, and ZIP CRC verification passes. The ZIP's one additional member is the index itself. Secret-bearing endpoint and key bytes were checked against all selected archive files before ZIP creation.

## Interpretation boundary

R removes separable early assistant thinking and free text, but prior judgments can remain in historical intervention content, command comments, and private-memory writes. The current root tail and Task Book remain intact. Role, length and evidence position changed together. This experiment is repeated static diagnosis of one known checkpoint, not independent opportunity discovery, strict information equivalence, Task success, or a causal estimate of anchoring alone. Evaluation dimensions are frozen in `EVALUATION_RECORD_TEMPLATE.json`; substantive judgments require independent review of raw event locators.

Task Agent, native evaluator, training, and scoring-model calls: 0. Production changes: 0.
