# Three-way diagnostic acceptance R4 (2026-09-19)

## Scope

This change keeps the existing three-way structure. It does not add a research
mechanism or expand the panel. The run remains an explicitly constructed
offline calibration with an empty parent History, not an R5 replay.

## Four acceptance items

1. **Independent branch records.** Ordinary, question, parent-direct and
   isolated-C branches each write status, conclusion, logical calls and current
   provider usage as soon as the branch ends. A failed or exhausted branch no
   longer discards a completed sibling.
2. **One six-call ceiling.** Ordinary investigation may use all six calls. The
   shared question stage may use three calls, covering requirement read,
   evidence continuation and question submission. B and C charge the shared
   prefix and retain room for investigation and final parent judgment.
3. **Input preflight.** Before loading the provider, every selected case is
   materialized and resolved. Event cursors must be ordered, unique, contiguous,
   end at the declared cutoff, and be an exact prefix of the research archive.
   The legacy path that removed control tool blocks but retained later History
   is disabled; only the explicit empty constructed History is used here.
4. **Realtime audit and usage.** Branch-labelled audit and transport logs are
   flushed during execution. Branch files are written on success, protocol or
   budget exit, and exception. C evidence references are included in the
   isolated result passed to the parent.

All parent branches use the same label contract: `supported_in_scope` requires
affirmative scoped support, `contradicted` requires a concrete conflict, and
non-discriminating evidence is `unresolved`.

## Deterministic verification

Twelve regression tests pass, including:

- requirement read -> evidence read -> question submission at the stage edge;
- question-stage exhaustion preserving an already completed ordinary branch;
- one branch exception not erasing sibling results;
- exact fixture/history provenance and per-case model-view isolation.

## R4 three-case acceptance run

| Case | Ordinary | Parent-direct | Isolated-C parent | Calls A/B/C |
|---|---|---|---|---|
| JSON API | contradicted | contradicted | contradicted | 3 / 4 / 6 |
| Corrected validator | supported | supported | supported; C not called | 2 / 3 / 3 |
| Build-only behavior | unresolved | unresolved | unresolved | 2 / 3 / 5 |

For JSON, the child C itself reached `probe_turn_limit`, while the parent still
formed a contradicted decision from the shared question state and returned
scope. Both facts are preserved separately; the child limit is not reported as
a successful child verification.

These three examples are an engineering acceptance result, not evidence that C
improves the Supervisor. No prompt, model, memory, compression or research
claim should be changed based on their relative outcomes.
