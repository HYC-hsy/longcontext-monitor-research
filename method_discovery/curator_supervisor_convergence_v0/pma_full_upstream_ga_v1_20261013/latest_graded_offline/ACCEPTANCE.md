# Bounded offline acceptance

## Final runtime identity

Published runtime code commit: `132256231b7dba708d055c27cf2bfd450de77f49`.
Local runtime commit: `e37c92b3f773e5be55363eaa29b36f494da70a73`.
Publication rebases only the authorized file snapshots onto latest known archive `a3ba4c0d869c0149ba10ca6a698deecbb16dd0e9`, preserving remote archives and Windows LF rules. Final archive commit is given in the delivery message; documentation follows the runtime commit.

## Environment and results

Cloud CPython 3.12.14 in the existing isolated PMA environment; pinned PMA and its external Harbor imported before globally installed packages. Existing regex 2026.9.29 and rpds-py dependencies were reused. The developer should use the already working local interpreter, not replace it to match this cloud version.

- `test_gap*.py` plus `experiment_runner`: **324 passed, 240 subtests passed**, no failures or skips. Captured final output: logs/gap_runner.txt.
- Four affected GA files (upstream bridge, capture boundary, upstream parity, Task complete response): **42 passed, 38 subtests passed**, no failures or skips. logs/ga_affected.txt.
- The aggregates include the new component tests and actual pinned-host fake-response tests; do not add their subcounts as independent coverage.
- One actual-host three-cycle fixture verifies maintenance→selection exactly three times, same memory ID, bound→malformed-evidence/latest update, immediate Phase2 visibility, next Phase1 visibility, serialization/reload, and zero actor calls. This is not Docker/Harbor certification or a Task result.
- git diff --check passed. Independent source review found no remaining reproduced blocker after the corrections below. Review was not a separate execution of every test.
- Real model, real Task episode, official evaluation: **0**. Docker executable is unavailable in this cloud workspace; final-source Harbor A/B and unified fake run remain reception work, not claimed completed.

## Intermediate failures and fixes

An aggregate invocation during concurrent development observed the not-yet-fixed pristine-bank constructor errors and an incorrect test assumption about displayed escaping. The finalized initialization accepts only the exact empty upstream serialization; actual C8 character code points settle the escaping distinction. A later host assertion expected the old label and was updated to `binding_status`. One pytest collection omitted experiment_runner from PYTHONPATH; rerun used the proper import paths. A new host persistence assertion compared JSON arrays to in-memory tuples; comparison now uses the full JSON round-trip representation, not a reduced subset. None of these intermediate failures is counted as passing.

Review also corrected metadata validation bypasses, malformed-evidence masking of a corrupt catalog, and the XML evidence parser path. Current regression includes those negative boundaries.

## Reuse and replay

Upstream LangExtract LCS helpers are copied at fixed commit with attribution and source correspondence, not a newly invented similarity algorithm. See GRADED_REUSE.md. The two real C8 quotes normalize to their original source range in the hash-verified single-source fixture; all three hidden-gap composites remain unbound. The original 49 submissions had 44 literal associations. Restricted public-source replay is not a comparable new success rate: four redacted blobs differ from their original hashes and unselected/unmatched source snapshots are absent. No original hash was rewritten to pass replay.

Generated replay_results.json is a deterministic offline diagnostic output plus local timing samples; it is not a model experiment. Quotation correctness, full-catalog recall/precision and task effectiveness remain unproven.
