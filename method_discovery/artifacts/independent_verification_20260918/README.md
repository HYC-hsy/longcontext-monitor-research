# Provisional independent-verification calibration panel (2026-09-18)

This is a provisional local calibration fixture for the minimum independent-verifier prototype. It is not wired into the live monitor. Pilot model calls are stored separately; full comparison is on hold.

## Fixed comparison

Every case uses the same Fyne 2.2.0 roadmap task and the turn-60 root-completion checkpoint. The four groups differ only in how the local question is handled:

- **A**: the existing judgment, with no added verifier budget;
- **B**: a same-context review, capped at six provider requests/eight turns;
- **C**: a fresh direct verifier session, with only the permitted requirement/evidence paths;
- **D**: a fresh expectation-first session. The expectation phase sees no implementation/evidence paths; the evidence phase then compares against that committed expectation. The same total six-request budget applies to D.

`scoring.expected_label` and its rationale are evaluator-only. A runner must construct model input from the case question, task source, event prefix, workspace evidence, and group context without copying the scoring block.

The eleven local questions share one reconstructed root-completion checkpoint and span seven targets. They are not eleven independent temporal checkpoints; the final panel still needs additional distinct checkpoints and a resolved toolbar label. No method comparison should be reported from this provisional set alone.

The archived verifier output is used only as offline scoring evidence. It is not copied into model-readable material. The first draft incorrectly listed verifier output among some evidence paths; that leakage has been removed before any model comparison.
