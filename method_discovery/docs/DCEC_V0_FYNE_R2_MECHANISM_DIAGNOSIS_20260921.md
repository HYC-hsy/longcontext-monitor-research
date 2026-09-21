# DCEC-v0 Fyne R2 Mechanism Diagnosis

Date: 2026-09-21

Evidence baseline: public commit `063c5463b3fc73aca76274ee51a40600f6d1dab2`

Scope: mechanism diagnosis only; no implementation or new experiment

## 1. Fyne R2 scientific facts

R2 is a valid scientific observation from one complete `fyn-2.2.0-roadmap` run with frozen DCEC-v0. The archive records 12 Supervisor reviews, 76 successful provider requests out of 76 attempts, and no transport failure. The Supervisor ultimately called `allow_complete`; the native verifier passed 2 of 7 phases and reported reward `0.2727272727272727`.

The infrastructure-invalid R1 batch is not part of this diagnosis. The principal evidence here is:

- `monitor/audit/dialogue.jsonl`: Supervisor requests, tool calls, state mutations, interventions, and final control;
- `monitor/task_evidence/public_events.jsonl`: Task Agent actions and receipts;
- `monitor/working.md`: final persistent working state;
- `verifier/test-stdout.txt`: native phase results;
- `trial/result.json`: run identity and final score.

The verifier found, among other failures, that `dummyApp` and `themedApp` did not implement the newly enlarged `fyne.App` interface, and that the new `desktop.App` interface imposed an unintended `Driver` requirement on the minimal mock. These are post-run evaluation facts; they were not available to the online Supervisor.

## 2. What DCEC-v0 demonstrably solved

DCEC-v0 was not inert. The trajectory shows a functioning local feedback loop:

- `monitor/working.md` was repeatedly revised instead of remaining a static initial plan.
- The Supervisor read the universal Target 1 requirement, directly inspected an implementation, found the missing `testApp.Metadata()`, and intervened. It also detected incorrect theme variant references.
- It detected later task drift, restored the relevant requirements, and followed subsequent behavior.
- It identified that the first `NewAllStrings` implementation was the wrong kind of feature and caused a corrective intervention.
- After repair observations, it removed prior local concerns and moved attention to later targets.

Therefore R2 does not support “persistent state had no effect” or “the model could not revise beliefs.” It supports the narrower conclusion that local revision and recovery worked in several episodes, while the criteria governing **how far a successful observation may close a concern** did not.

## 3. Exact failure chain

### 3.1 Local repair was promoted to universal satisfaction

The original Target 1 requirement said that **all existing concrete implementations** had to satisfy the new `App.Metadata()` method. The Supervisor correctly found one omitted instance, `testApp`, and obtained evidence that this instance was repaired. It later summarized Target 1 as complete and finally stated that all App implementations had been updated.

That transition exceeded the evidence scope. A direct observation about `testApp` established a local repair; it did not establish that the set of existing concrete implementations had been exhaustively identified and updated. The native verifier later exposed `dummyApp` and `themedApp` as counterexamples.

The failure is therefore:

```text
local instance repaired
→ concern marked resolved at target scope
→ target resolution reused at whole-task scope
```

The missing step was not another generic reminder. It was a check that the observation supporting the state transition matched the quantified scope of the claim being closed.

### 3.2 Closure measurements did not distinguish decision-relevant states

At the root handoff, the Supervisor ran a “comprehensive final verification” consisting mainly of `grep` checks for files, symbols, and method names, followed by `go build ./...`. It then wrote that all 29 requirements were checked and confirmed.

Those observations supported existence and compilation, but not every semantic or interface-shape claim used by the completion decision. Target 7 is the clearest example: the task required a `desktop.App` interface with two system-tray methods, but the implementation embedded the entire `fyne.App`. Checking that the interface and the two named methods existed could not distinguish:

```text
the intended minimal interface
from
an over-constrained interface that also contains the two methods
```

The verifier's minimal mock failed because of the additional `Driver` obligation. More observations would not necessarily help if they were more observations of the same non-discriminating kind. The failure was the measurement scheme used for closure, not simply observation quantity.

### 3.3 A requested validation was converted into epistemic progress without completing

At Task Agent turn 55, the public trajectory contains a real `go test ./... -v` action. Its receipt is `Stopped` with exit code `-9` after monitor correction, and the next action is marked cancelled. No test result was obtained. The Supervisor nevertheless revised `working.md` to “build successful, tests running,” with no active concern. The full test was not subsequently completed or rerun before the final state became “All 29 specific requirements checked and confirmed present” and `allow_complete` was issued.

This exposes three distinct states that R2 collapsed:

```text
task state:                 what the implementation currently is
epistemic state:            what available evidence supports
supervisory workflow state: which decision-critical observation is requested,
                            running, interrupted, or completed
```

“Validation requested,” “validation running,” “validation interrupted,” and “validation completed successfully” are not interchangeable. An interrupted observation supplies no positive result. Here, workflow loss removed the only visible reminder that the expected measurement had never arrived.

### 3.4 Unified causal chain

```text
useful local concern and investigation
→ genuine local repair evidence
→ evidence scope not matched to the claim scope
→ concern resolved too broadly
→ root handoff raises the decision scope to whole-task completion
→ closure reuses local resolutions and weak proxy measurements
→ a decision-critical validation is interrupted but not retained as pending
→ working state reaches Active Concerns: None
→ allow_complete despite unresolved decision-relevant alternatives
```

This is not primarily stale-concern persistence. It is **premature epistemic resolution plus loss of an unfinished supervisory observation**.

## 4. Control-theoretic interpretation

Source boundary: this section uses only the research thread's supplied, already-verified concepts and mappings from engineering cybernetics. This document does **not** claim an independent rereading or textual verification of *Engineering Cybernetics (Revised Edition)*, and it does not transfer Kalman, LQG, linear-observability, or optimal-control guarantees to an LLM Supervisor.

The useful mapping is limited but precise:

- **State:** task state alone is insufficient; the controller also needs the epistemic support for its present decision and the execution status of decision-critical observations.
- **Observation/measurement scheme:** an observation is useful for control when its possible outcomes distinguish task states that require different supervisory actions. Symbol existence and compilation did not distinguish the Target 7 states above.
- **Feedback:** observation should revise the current state, and the revised state should alter the next action. R2's local repair loops achieved this; closure failed when evidence was promoted beyond its scope and an interrupted measurement disappeared from control state.
- **Constraints and conflicting performance objectives:** investigation, latency, task interruption, and false blocking are finite costs. The answer cannot be unlimited verification. Investigation intensity should depend on the consequence and scope of the current decision: ordinary patrol may accept bounded local evidence, while irreversible whole-task closure requires observations capable of separating plausible completion-blocking alternatives.

Thus “run more tests” is not the mechanism. A test is only one possible measurement. The mechanism-level question is why the current decision requires an observation with particular discriminating power, and whether the chosen observation actually supplies it.

## 5. Knowledge-representation interpretation

This section relies on the full public text of Davis, Shrobe, and Szolovits, *What Is a Knowledge Representation?* (`https://groups.csail.mit.edu/medg/ftp/psz/k-rep.html`). The relevant claim is not merely that representation stores facts: a representation also embodies sanctioned inferences and helps recommend which inferences are made efficiently.

`monitor/working.md` could represent `open`, `recovering`, and `resolved`, and R2 demonstrated real revision. But `resolved` lacked an explicit inferential boundary tying it to:

- the decision/claim scope being closed;
- the observation actually obtained and its scope;
- the still-live alternative that the observation was supposed to distinguish;
- the execution status of a decision-critical observation.

Consequently, writing `resolved` made “stop investigating this concern” and later “reuse this as completion support” easy recommended inferences, even when the supporting observation was local or interrupted. The representation could express resolution, but did not constrain what that resolution licensed.

This does not justify a full requirement graph, truth-maintenance system, or second knowledge base. R2 points to a narrower representational/control defect at consequential state transitions, not a demonstrated inability to retain the whole task.

## 6. Minimum missing capability

The minimum unified missing capability is:

> **Decision-conditioned evidential transition control:** the existing Supervisor may move a concern out of the active frontier, or close the whole task, only by relating the current decision scope to an actually completed observation whose scope and possible outcomes are adequate to distinguish the states that would require different control actions; any decision-critical observation that is requested, running, or interrupted remains an unresolved control dependency.

This is one capability, not a bundle of new agents or stores. Its minimum semantics are:

1. **Before `open/recovering → resolved`:** retain which claim at which scope is being closed, what completed observation supports that transition, and what relevant alternative that observation excludes. A local instance repair can resolve the local concern without resolving a universal target.
2. **At a scope change:** root completion is a new whole-task decision, not the automatic aggregation of the latest local recovery. The same Supervisor adapts its observation policy to the higher consequence and broader scope.
3. **When evidence is inadequate:** keep one bounded focal uncertainty such as “current evidence covers instance X but not the quantified target.” This is not a list of every requirement.
4. **When validation is unfinished:** retain only the minimal workflow fact needed for control—requested/running/interrupted/completed plus its observation identity. This is not a workflow manager; it prevents absence of a result from becoming positive evidence.
5. **During ordinary low-risk patrol:** no exhaustive re-verification is required. Investigation intensifies only when the current action is consequential and the present grounds do not discriminate the alternatives relevant to it.

The capability belongs in the existing DCEC feedback loop and existing `monitor/working.md`; it must change state transitions and subsequent tool choice, not add a final checker or merely produce more cautious prose.

## 7. What must NOT be added

R2 does not justify adding:

- a checker Agent, root verifier, selector Agent, or extra LLM stage;
- RACC or a separate closure-budget mechanism;
- numeric confidence;
- a requirement graph, fixed 29-item checklist, TMS/ATMS, or second memory system;
- Fyne-specific rules such as always checking `dummyApp`, `themedApp`, or always running `go test`;
- another general caution prompt;
- a rule that any unknown blocks completion or that every repaired concern must be rechecked indefinitely.

These additions would confound the diagnosis, increase cost, or turn a scope-sensitive control problem into blanket conservatism.

## 8. One falsifiable next mechanism hypothesis

**Hypothesis.** If the existing persistent Supervisor applies decision-conditioned evidential transition control inside its normal loop—without extra model calls, agents, checklists, or memory—then its behavior will change at the two R2 failure boundaries:

1. after a local repair, it will retire the local concern but will not treat the broader target as supported unless the obtained observation matches that broader scope; and
2. at root completion, it will preserve any interrupted decision-critical observation as unresolved and select at least one observation whose possible outcomes could change the completion action, rather than relying only on symbol existence, claims, or build success.

The hypothesis is supported only if the resulting state revision changes subsequent investigation/control, a latent defect is rejected or corrected using a genuinely discriminating observation, and a correct control state is not materially over-blocked.

It is falsified if the Supervisor merely writes richer scope language while repeating the same proxy checks, forgets an interrupted observation, becomes uniformly conservative, or cannot release a correctly repaired/local or fully correct state. A correct final label without the observation → revision → changed-control chain does not count as support.
