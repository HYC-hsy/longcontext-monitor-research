# Independent-verification measurement repair — 2026-09-18

This repair changes measurement and fixture validation, not the online
Supervisor or the C/D verification mechanism. Earlier pilot `correct` fields
were produced by the old scorer and must not be pooled with new results.

## Terminal state before correctness

`ProbeResult.status` is now `completed`, `probe_budget_exhausted`, or
`probe_turn_limit`; provider exceptions become `execution_error` in the panel.
Only an explicit `finish_probe` with a valid outcome and substantive conclusion
is completed and score-eligible. Otherwise `outcome=null`, `correct=null`, and
the failure remains in the results. A finished, reasoned `unresolved` can be
correct for an evidence-insufficient case; budget exhaustion cannot. The six
request cap counts logical `client.complete()` calls, **not** transport retry
attempts. Both counts, actual tokens, and wall time are recorded separately.

## Comparability

- A is an archived root approval, not a per-question answer. It now has no
  local outcome or correctness score and is only historical reference.
- C/D are the primary same-evidence comparison. B is supplementary: it restores
  the full parent History and can contain other evidence and prior conclusions.
  B is incompatible with the build-only scoped question and is not run there.
- The default panel selects C/D and excludes unconfirmed labels. Explicitly
  selecting an unconfirmed case fails before a model call.
- Eleven questions at one checkpoint remain local calibration, not eleven
  independent checkpoints. No C/D winner is claimed.

## Label audit from original requirement and reconstructed code

**Toolbar:** Target 5.1 requires `ToolbarAction.SetIcon` to update `Icon` and
refresh the toolbar object. The turn-60 method only assigns `t.Icon = icon`.
`ToolbarObject()` creates a button, and `toolbarRenderer.Refresh()` rebuilds
the item objects; neither is called from `SetIcon`. This is concrete evidence
of a task-contract gap. Native phase-5 tests pass but check field/concrete
constructor types, not displayed-toolbar refresh. The case remains excluded
pending independent label review rather than being called a D win.

**Desktop:** The original Target 7 lists exactly two tray methods. The
reconstructed `desktop.App` embeds `fyne.App`, adding inherited methods. The
native compile error says the test's `mockDesktopApp` does not implement
`desktop.App` because **the mock lacks `Driver`**. The previous rationale
incorrectly claimed the interface was missing a Driver relationship. The
correct concern is possible *overconstraint* relative to the specified
two-method API. This case is provisional and excluded until the task's
intended interface boundary is reviewed.

## Fixture freeze

`materialized_r4/materialization.json` now records SHA-256 for the exact
configuration, original task, public event prefix, build observation, ten
reconstructed workspace files, PMA state, and parent provider History.
The runner checks inventory and each byte hash before loading the parent
History or a model profile. Altering a workspace file is rejected in an
offline regression. The manifest contains hashes, not private file contents.

The earlier r3 fixture and all old pilot outputs are historical diagnostic
material. R4 is the new comparison fixture; new runs must use fresh output
directories and preserve their exact configuration revision.
