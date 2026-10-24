# Bounded local acceptance

Runtime source was frozen by local implementation commit `5e59a55d9b13863ad4d988d54d1a24f7346e752f`, published with identical Git tree as `ba151204d5f1b09019e429e4254890f4511f516c`. Later replay and documentation commits do not change the four runtime files; their actual SHA-256 values are in runtime_source_hashes.json.

## Final checks

- Cloud Python 3.12.14, isolated venv; pinned PMA/Harbor source imports. No claim of Windows Python 3.13 execution here.
- `pytest test_gap*.py experiment_runner`: **230 passed, 183 subtests passed**, no skips or failures. `logs/gap_runner.txt` preserves final console output. This includes existing ordinary gap, new evidence behavior, host fake seams, replay and frontend tests; subtests are separately reported, not added to the test count.
- Four affected GA files (upstream bridge, capture boundary, upstream parity, complete response): **42 passed, 38 subtests passed**, final output in logs/ga_affected.txt.
- Actual-log development replay: **4 tests, 32 subtests**, included in the 230, not additional tests. Pinned old binder yields 29 absent/3 ambiguous; explicit decoded-field selection yields 26 matching/3 absent/3 ambiguous. No new model output was generated.
- Independent code review found nested XML could be interpreted as an independent action inside a malformed outer call in an intermediate per-operation parser. Fixed before the runtime commit; closed and unclosed nested regions and malformed-name cases have regressions. Review also checked stable-ID repeated updates, pre-cycle evidence, copy-on-write and persistence validation.
- Every implementation step is below 600 added+removed code/test lines: identity 52; decoded projection 252; stable update 136; per-tool execution/regressions 472; replay code/tests 284. Mechanically extracted fixture JSON and generated result JSON are evidence data, not hidden code.

## Setup and intermediate failures, not silently counted as passes

The fresh cloud checkout initially lacked dependencies and sparse-checkout support modules. A LiteLLM import attempted its model-price metadata fetch and encountered a missing SOCKS dependency; tests subsequently used its existing `LITELLM_LOCAL_MODEL_COST_MAP=True` option, with no model request. Missing tenacity/toml and required small local test dependencies were installed into the isolated venv. Harbor metadata came from the pinned vendor checkout; no provider credentials were loaded.

An initial test command named nonexistent test_gap_agent.py and collected no tests. Correct test discovery uses test_gap*.py. Earlier frontend/collection attempts failed on sparse-excluded long_context_bench and historical fixture support imports; the exact tracked source files were restored, not stubbed and no assertion weakened. The existing upstream parity reference path was populated with the four official PMA files at commit 89e5c0d6aadfe531a1aee42fd290d48be89973dd, not rewritten to force equality. Final results above supersede setup failures but do not erase them.

Old tests encoding whole-batch rollback and two visible memory IDs were updated to the explicitly authorized new contract: retain successful independent operations, reject invalid operations, atomic in-place replacement, one displayed ID. Quote/visibility/provenance checks were not disabled.

Git CLI push lacked a login in this cloud environment. Publication used the already connected GitHub API, on a new branch only, with exact local/remote Git tree comparison for each commit. Local and remote commit metadata/SHAs differ; no force push or history rewrite was used.

## Not performed

No real model generation, real Task, official SQLite/HTML evaluator, Docker/Harbor full-fake certification or Windows local acceptance was performed here. Docker executable is unavailable in this cloud environment. Existing certificates bind older source; developer must perform final merged-source fake acceptance on the already working local environment. This patch does not authorize real episodes.

## Known semantic and reporting limits

Exact quotes do not prove interpretations. Sequential independent commits can still contain semantic contradictions. Phase 2 may still miss visible errors; its policy/parser were deliberately unchanged. The replay selects new field IDs explicitly and does not demonstrate real model compliance. The same historical data were used to diagnose and test the repair, so no held-out improvement claim is made.

A mixed cycle reports accepted=false plus partial_success=true and per-operation outcomes. Consumers must inspect those fields rather than treating the whole bank as rolled back. An accepted empty operation list is a no-op, not a successful write. Public fixture excerpts are redacted projections with separate provenance, not private HTTP bytes.
