# Offline acceptance: host alignment and explicitly unbound memory

## What was actually run

Cloud CPython 3.12.14, existing isolated PMA test environment, pinned PMA and vendor Harbor imports. New regex dependency 2026.9.29 was materialized in `/tmp/pma_alignment_deps`; the final test subprocess included that directory. Developers must install/check evidence_requirements.txt with their actual runtime interpreter rather than assume that scratch path exists.

- Final `tests/test_gap*.py` plus `experiment_runner`: **283 passed, 232 subtests passed**, no failures or skips. `logs/gap_runner.txt` is the captured final console summary.
- Four affected GA bridge/capture/parity/complete-response files: **42 passed, 38 subtests passed**, no failures or skips. `logs/ga_affected.txt`.
- Those aggregates already include alignment, upstream adapted fixtures, actual-host construction, protected pending revisions, persistence, scope-cache and historical replay tests. Do not add their subcounts as independent test totals.
- `git diff --check` passed. Final read-only review found no remaining reproduced functional/integrity blocker; that review was not an independent execution of every test.
- Real model generations, real Task episodes, official evaluation and new Docker/Harbor full-chain certification: **0**. The actual-host tests use the pinned upstream constructor and fake role responses, not a real benchmark result.

## What changed and what stayed fixed

Five tools, original two-stage schedule and selection system/parser remain. Production evidence candidate constructs aligned subclasses; strict old classes remain for historical regression. Ordinary PMA/gap and vendor PMA are untouched. There is no new candidate registration, model judge or semantic repair loop. Policy is `literal_alignment_with_explicit_unbound_v1`, recorded in gap-cycle telemetry; source identity covers the new runtime and vendor files.

Actual LangExtract code reuse, fixed upstream SHA, line references, license and deliberately excluded DP/fuzzy behaviors are documented in `../vendor/langextract_3a68580/REUSE.md`. This is selected tokenizer/candidate-code reuse, not a claim to run its complete pipeline.

## Historical development replay

The 32 original quotations and originally supplied source hints were retained unchanged. Program projection generates a new decoded eligible view for every relevant public header of the same archived Phase 1 prompt, without manually selecting replacement source IDs. Results: **26 exact_unique, 4 exact_multiple, 2 unbound**.

These are literal-location results, not truth labels or model-effect estimates. Six to nine derived-memory headers per prompt are omitted because the public fixture does not contain authentic revision identities. Thus this is a public-source projection replay, not a complete original runtime state replay. The actual historical model never saw these newly rendered requests. The two noncontiguous quotations remain unbound, not fuzzily certified. Full boundaries are in replay_report.md/json. No old run/archive/score was changed.

## Performance and review corrections

All candidate locations persist; the prompt shows source-group counts and first/last positions explicitly as summaries. A request-local synchronous cache reuses only immutable source-snapshot validation; per-reference spans, hashes, provenance and visibility checks remain. No cross-request cache or candidate-count cutoff is introduced.

An isolated host-only synthetic probe with 540,000 source characters and 2,000 matches took about 0.36 seconds for preparation, alignment, atomic publication, serialization and JSON round-trip/load in this environment; Phase 2's synthetic prompt was 1,110 characters. See STORE_BENCHMARK.json. This is not an average live-task cost. Candidate enumeration retains an upstream worst-case O(n*m) bound, storage can grow with the number of occurrences, and the full task input can still be large.

Review caught and corrected: unbound references missing pre-cycle/cycle checks; receiptless legacy laundering; proposal/native ID shadowing; missing proposal target history; missing metadata stripping guards; P1 historical quote text outside its eligible corpus; and redundant whole-source checks for repeated candidates. Tests cover the corrected cases. P1 now omits stored quote strings from metadata rather than pretending they are searchable raw events; P2 labels stored versus model-attempted quotes.

Intermediate test invocations exposed (a) missing experiment_runner or test-helper paths during collection and (b) an outdated exact six-file source identity expectation. Paths were corrected, and the identity test now checks the exact current thirteen-file set and actual bytes rather than weakening equality to a subset. No final failed assertion is concealed as passed. Windows-specific behavior remains for local reception validation.
