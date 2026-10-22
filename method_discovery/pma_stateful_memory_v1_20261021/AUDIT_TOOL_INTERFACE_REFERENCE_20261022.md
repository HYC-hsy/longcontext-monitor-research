# Offline reference acceptance, 2026-10-22

Base: 55560439a4b15afdc4573f2c6334f1ef91aa86f7. Only additive reference files.

- Targeted new tests: 53 passed, 0 failures/errors. Raw stdout/stderr is committed in evidence/tool_interface_reference_20261022/unittest_targeted.txt.
- Complete stateful package discovery: 182 tests passed, 0 failures/errors. This includes the 53 targeted tests; counts must not be added together.
- Python compileall passed. Real model, Task and evaluator calls: zero.
- Original 41 Python files were verified against base Git blob IDs and remain unchanged.
- Native-shaped object pipeline tests exercise the compilers and existing validators, not HTTP/SSE or Harbor.

The complete package console output is ~463 KB because existing fixtures print extensive telemetry; it remains local, with its exact hash in manifest.json. It is NOT presented as committed raw evidence. The 53-test new component raw log is committed and replayable.

Environment preparation: initial broad collection failed due missing tiktoken/historical fixtures in the partial checkout; subsequent preparation exposed an extra trailing newline introduced by the file-copy mechanism, failing pinned hashes. Exact fetched bytes were restored (41 Git blob IDs verified), existing local tiktoken/o200k data loaded and committed historical fixtures fetched. No validators or expected hashes were changed to pass. These preparation failures are not method-run results and their original console files were not committed.

Independent review found and fixed: shared schema incompatibility with emitted anyOf/empty schemas; malformed Python-shaped input exception leaks; and over-rejection of valid archived-only historical references. Regression tests cover each. Existing domain checks remain mandatory.

Descriptor-only size measured with local o200k_base (not provider usage, not per-cycle total): maintenance 13 tools / 18,726 UTF-8 bytes / 4,554 proxy tokens; audit 1 tool / 4,558 bytes / 1,114 proxy tokens; selection 1 tool / 1,456 bytes / 361 proxy tokens. This does not establish cost reduction; the final prompt and schemas must be counted together after integration.

NOT completed: auxiliary native request/response plumbing, revised tool-mode prompts, actual SSE completeness verification, integrated repair-credit/error handoff, schema-inclusive runtime accounting, source-bound Harbor certificate, real model validation, or general short-handle registry. See TOOL_INTERFACE_REFERENCE_20261022.md for the exact handoff. Existing production runtime is unchanged and this commit does not authorize a new experiment.
