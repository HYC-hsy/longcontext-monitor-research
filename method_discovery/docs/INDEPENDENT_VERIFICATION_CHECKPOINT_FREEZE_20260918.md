# Independent verification checkpoint materialization — 2026-09-18

## Scope

The minimum verifier prototype is now paired with a fixed eleven-case panel in
`method_discovery/artifacts/independent_verification_20260918/`.

This step materialized a provisional evaluation fixture. It does not alter the
live monitor or claim an effect result. Subsequent pilots and their issues are
recorded in `INDEPENDENT_VERIFICATION_PILOT_AUDIT_20260918.md`.

## What is fixed

- one Fyne 2.2.0 roadmap task and its SHA-256;
- one archived simple parent run, task source, and public-event source;
- eleven concrete questions at the same root-completion checkpoint, covering
  correct, incorrect, and evidence-insufficient claims across all seven targets;
- one turn-60 event cutoff, permitted source/evidence paths, and evaluator-only
  labels;
- equal six-request/eight-turn caps for B/C/D. A four-request pilot was
  protocol-limited, so it is excluded from final comparison.

The first draft named early event prefixes without corresponding parent-state
snapshots and mistakenly included posthoc verifier output as readable evidence.
Before any model calls, the panel was revised to one accurately reconstructable
turn-60 checkpoint. `materialize_independent_probe.py` replays successful
public file writes/patches over the clean task repository and fails closed on
unmodeled mutations. Native verifier output remains evaluator-only. A build-only
question provides the evidence-insufficient calibration case; the root
completion claim is instead contradicted by public code. Eleven local questions
at one checkpoint do not yet meet the requested panel of distinct reproducible
checkpoints; further fixture diversification is required.

## Isolation and scoring boundary

The scoring label and rationale are outside model input. Direct mode receives
the question plus permitted requirement/evidence paths in a fresh session.
Expectation-first receives only requirement/background paths before committing
an expectation; evidence paths are opened only in its second phase. Both modes
share the same total request budget.

## Offline checks

`tests/test_independent_probe_checkpoints.py` checks eleven unique cases, all three
labels, equal C/D budgets, non-empty scoped paths, and the evaluator-input
boundary. Together with provider/core regressions, 63 tests passed offline in
the prior revision; the final eleven-case panel is checked again separately.
