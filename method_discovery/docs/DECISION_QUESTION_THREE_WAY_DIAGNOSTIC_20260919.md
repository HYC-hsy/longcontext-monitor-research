# Decision-question three-way diagnostic

## Purpose

This diagnostic separates three possible sources of improvement without
changing the online Supervisor:

1. ordinary continued investigation;
2. the parent Supervisor first stating a decision-changing unresolved premise,
   then investigating it directly;
3. the same generated premise being investigated by an isolated C verifier,
   with the scoped result returned to the parent for the final decision.

The question-generation exchange is executed once and cloned into branches 2
and 3. Thus question quality is not confounded with verifier choice. Its
logical calls are charged to both branches. A model may explicitly say that
no worthwhile question exists; the runner does not manufacture a defect.

## Input boundary

Researcher archives and model-visible material are separate. A checkpoint
manifest must declare:

- the exact event prefix visible to the model;
- the exact parent History visible at that prefix;
- the full event archive used only by evaluators;
- workspace and bank hashes for the same prefix;
- control actions that must be absent at that checkpoint.

When an archived monitor dialogue is available, `extract_model_history_at_cursor`
selects the complete provider `model_input` recorded at or before the declared
public cursor. It does not reconstruct history by keyword filtering, and does
not append later `model_output`/approval records.

The validator in `decision_question_diagnostic.py` deliberately does not
require a historical `allow_complete`. The legacy turn-60 fixture is not a
valid input to this diagnostic because its parent history contains later
approval and post-hoc summaries.

## Budget and outputs

The default ceiling is six logical `complete()` calls per branch. Branches 2
and 3 reserve a final parent decision after the shared question and
investigation. Transport retries are recorded separately by the provider.
Each case stores the selected question, branch status, final decision, C's
scoped conclusion and evidence references, plus the audit stream. No scoring
labels, native verifier output, or post-hoc rationale enters a model-visible
mount.

## Current status

The runner and deterministic tests are complete. Real execution is blocked
until three checkpoint fixtures are rebuilt with exact historical prefixes;
the previous materialized fixture must not be reused by changing only its
line count or directory name.
