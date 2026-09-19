# Decision-question diagnostic R2 audit (2026-09-19)

## What is uploaded

This directory contains the constructed checkpoint fixture, its manifest and
hashes, and the three-case run produced by the three-way diagnostic. The
fixture is explicitly marked `constructed_offline`; it is not a faithful
provider-history replay.

## Why R1 is excluded

The first materialized run inherited post-hoc wording from an old monitor
History (including references to earlier interventions and repairs). Although
the evaluator-only files were not mounted, those summaries could anchor the
model. R1 is therefore retained only as an engineering failure record and is
not part of any mechanism comparison.

## R2 setup

- Same original task and public event prefix for all cases.
- Per-case model-visible directories contain only the declared requirement and
  workspace files.
- The parent History is the empty clean History `[]`, because no faithful
  checkpoint snapshot was available. This prevents post-hoc leakage but means
  R2 tests the diagnostic workflow, not persistent-supervisor continuity.
- Three branches are run with the same model and budget: ordinary investigation,
  one shared question followed by parent investigation, and the same question
  followed by isolated C verification and parent decision.
- Transport and audit logs are written incrementally.

## Observed outcome

| case | run status | ordinary | parent-direct | isolated C |
|---|---|---|---|---|
| `json_theme_api` | incomplete (budget) | no final decision | no final decision | no final decision |
| `validator_after_correction` | completed | supported | supported | C not called (`worthwhile=false`) |
| `build_only_behavior` | completed | contradicted | unresolved | unresolved |

The results are a calibration record only. They do not establish that C is
better or worse than direct investigation. In particular, the fixture does not
contain the original continuous parent state, and the first case exhausted its
diagnostic budget before a final decision.

## Engineering checks

- The virtual `task/` namespace now maps to the physical evidence root; this
  fixed the first real-run path error.
- The checkpoint validator checks config and artifact hashes, cursor end,
  explicit History source kind, hidden-evidence exclusions, and per-case view
  materialization.
- Ten deterministic regression tests pass.

## Next valid comparison

Do not tune prompts from R2. A valid mechanism comparison requires either an
exact provider History snapshot at a chosen checkpoint, or an explicitly
approved constructed baseline whose research question is stated as such. Keep
the R2 artifacts for expert audit and do not combine them with the old R1/R4
results.
