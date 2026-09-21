# DCEC-v1 Fyne long-run R1 factual summary

## Identity and validity

- Run: `clean-monitor-fyn-2.2.0-roadmap-dcec-v1-longrun-20260921-r1`.
- Task: `roadmapbench:fyn-2.2.0-roadmap`.
- Condition: frozen DCEC-v1, no ordinary control, no repeat.
- Mechanism source: `746a695adac4325d6440941d384d543d1364fef9`.
- Task Agent and Supervisor model: `claude-opus-4-8`.
- Started: `2026-09-21T11:49:19.556281Z`.
- Finished: `2026-09-21T12:18:34.073909Z`.
- Harbor trial completed with no exception; proof validation reports `valid=true` and no
  validation errors.

## Native outcome

- Phases passed: 7 of 7.
- Reward: `1.0`.
- Trial outcome: `agent_phase_completed`.
- This score is an outcome fact. It does not by itself establish that the preregistered
  DCEC-v1 mechanism chain operated as intended.

## Recorded execution and cost facts

- Supervisor reviews: 13.
- Successful Supervisor provider responses / attempts: 71 / 71.
- Input tokens: 34,042.
- Output tokens: 28,235.
- Cache-read input tokens: 881,042.
- Cache-creation input tokens: 2,797,234.
- Sum of recorded Supervisor review durations: 1,368.275 seconds.
- DCEC working-state mutations: 11.
- Bounded working-view injections: 71, ranging from 1,057 to 2,651 characters.
- Recorded Supervisor tool operations: 92.
- Continuation events: 0.
- OTel trace: 257 spans; observed model identity only `claude-opus-4-8`.
- No provider-attempt, TLS, gateway, Harbor, or verifier failure occurred.

## Factual trajectory

### Target 7 desktop interface

The Supervisor first observed that `driver/desktop/app.go` did not exist. After the Task
Agent placed the system-tray methods on `desktop.Driver`, the Supervisor directly inspected
the workspace, revised `working.md` from an awaiting state to a confirmed requirement
violation, and intervened. A later review directly read the newly created
`driver/desktop/app.go`, checked that the methods had been removed from `driver.go`, and
revised the state to whole-task completion assessment.

### Hyperlink behavior

While the state said that all seven target requirements were implemented and the build
compiled, the Supervisor inspected `Hyperlink.Tapped`. It observed that `openURL()` was
called even after `OnTapped()`, changed the focal uncertainty to that behavioral conflict,
and intervened. A later review read the repaired implementation and revised the grounds to
record the `if/else` behavior.

### NewAllStrings behavior

At the first root completion handoff, the Supervisor continued investigating instead of
approving. It inspected `data/validation/all.go`, observed `AllValid` with a different
signature and error-aggregation behavior, changed the focal uncertainty, and intervened.
After the Task Agent added `NewAllStrings`, a later review directly read that file, observed
the successful build and test-compilation receipt, revised `working.md`, performed a final
cross-target source check, and then called `allow_complete`.

## Four preserved audit chains

### 1. Scope-bound resolution

- The working state did not treat the Target 7 intervention itself as resolution; it moved
  to a correction-monitoring state and awaited the new file.
- The Hyperlink and NewAllStrings concerns were also followed by later source observations
  before their corresponding grounds were revised.
- The raw trajectory also contains earlier broad statements such as “Targets 1-6 complete”
  and “all 7 target requirements implemented” based on narrower inspections. Whether those
  statements satisfy the v1 scope discipline is left for independent mechanism audit.

### 2. Unfinished observation

- At cursor 115 the state explicitly recorded that the Task Agent was running final build
  and tests. Subsequent receipts reported build success but test-compilation errors, and the
  Supervisor did not approve at that point.
- At cursor 124 the state retained the compilation import cycle as the focal uncertainty.
- Later build and scoped `go test -c` receipts completed successfully. No continuation event
  or unresolved interrupted decision-critical validation was recorded at final approval.
- The state did not consistently use the literal workflow labels
  `requested/running/interrupted/completed`; this is a trace fact, not an effectiveness
  judgment.

### 3. Root re-evaluation

- The run contained two archived root checkpoints.
- The earlier completion path was interrupted by the Target 7 correction.
- At the later root handoff, the Supervisor selected NewAllStrings as a new focal issue,
  intervened, consumed the repair evidence, returned to the whole-task anchor, performed a
  final multi-target source check, and only then approved completion.
- Hyperlink was found and corrected during the intervening whole-task assessment rather
  than being inferred from the final native score.

### 4. Tighten and relax

- Investigation tightened at high-consequence points through direct source reads and
  code/build observations: Target 7 file/interface placement, Hyperlink control flow, and
  NewAllStrings name/signature/first-error behavior.
- After completed repair observations, each focal issue was removed or replaced rather than
  remaining the final active concern.
- The final `working.md` has whole-task scope, no focal uncertainty, three named successful
  corrections, and a successful build receipt. The Supervisor then relaxed to
  `allow_complete`.

## Interpretation boundary

This document reports trace facts and deliberately does not declare DCEC-v1 effective or
attribute the 7/7 result causally to the mechanism. Independent audit must still judge the
adequacy and scope of the observations, the accuracy of broad “verified” statements, and
whether the full preregistered transition chain—not merely the final answer—was satisfied.
