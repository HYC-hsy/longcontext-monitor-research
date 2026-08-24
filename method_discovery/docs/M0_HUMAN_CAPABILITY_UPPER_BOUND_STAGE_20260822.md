# M0 Human-Capability Upper-Bound Stage

Date: 2026-08-22  
Status: user-confirmed current method-discovery stage

## 1. Why this stage exists

The next stage does not begin by optimizing a schema, trigger, reminder, or token
budget.  It first asks whether a persistent online monitor can reproduce the useful
parts of a human control loop on complete, real GenericAgent tasks.

M0 is therefore a **capability upper bound and teacher policy**, not the final
paper method and not the causal baseline.  B0 (unmodified GenericAgent) remains
the experimental baseline.  Later stages will formalize, ablate, and reduce M0
only after its useful behavior is demonstrated.

This revision changes method-discovery execution order, but does not change the
fixed paper problem or innovations A--D.  M0 is intended to expose which parts of
Evidence-Carrying State, Versioned Revision, Completion Boundaries, and Typed
Recovery are actually necessary.

## 2. Deployment boundary

M0 may use only information available to an ordinary online collaborator:

- the original public task;
- the task Agent's public responses, actions, tool calls, and tool results;
- the public task workspace, including diffs, tests, logs, and artifacts;
- M0's own persistent notes and prior interventions.

M0 must not see the native verifier, hidden tests, gold answers, post-termination
annotations, or future trajectory.  Native verification is run only after the
task Agent terminates.

Cost, token count, and call count are recorded but are not selection constraints
in this stage.  M0 may inspect frequently and reason deeply.

“Frequently” does not mean a fixed interval or maximal deliberation on every
turn. Historical human traces show nonuniform observation windows: ordinary
exploration may be scanned without intervention, whereas creation or weakening
of tests, contradictory execution evidence, phase transitions, risky changes,
and completion proposals receive concentrated inspection. After opening a
repair episode, the monitor follows the subsequent response/action sequence
until task interpretation and evidence policy are observably repaired.

## 3. Required online control semantics

M0 is not a post-hoc log judge and not a one-shot prompt injector.  At every
eligible public turn boundary the orchestrator must give M0 control before the
task Agent receives its next prompt.

M0 can:

1. inspect the newly produced trace delta and selected public workspace state;
2. update persistent natural-language working notes;
3. remain silent and release the task Agent;
4. pause the task Agent and issue a concrete challenge or requested check;
5. observe the Agent's response and subsequent actions;
6. continue the same repair episode with another correction;
7. release only when public behavioral evidence resolves the contested issue;
8. preserve UNKNOWN or abstain when public evidence is insufficient.

The control loop is:

```text
observe -> hypothesize -> inspect -> SILENT or HOLD
HOLD -> challenge -> Agent response/action -> re-observe
re-observe -> residual resolved ? RELEASE : re-correct/inspect/UNKNOWN
```

The same persistent monitor implements two attention modes:

- `SHADOW`: consume every new public delta, maintain situational awareness, and
  normally remain silent without reopening unchanged artifacts;
- `DELIBERATE`: inspect a concrete high-information event or discrepancy and,
  once a repair episode is open, review each subsequent boundary until release.

These are attention modes, not separate models or memories. Trigger signals are
prompts to exercise judgment rather than hard gates: the monitor may escalate on
an unlisted semantic conflict and remain silent on a harmless nominal trigger.
Completion proposals are always monitorable public boundaries and cannot bypass
the repair loop.

Verbal acknowledgement is never sufficient release evidence.  The monitor must
remain able to catch local repair followed by global-task collapse, weakened or
co-adapted tests, and unsupported completion.

## 4. Minimal M0 interface

M0's internal reasoning remains open-form.  Only its control interface is typed:

- `SILENT`: no intervention; allow the next task-Agent turn;
- `HOLD`: inject a message and keep the repair episode open;
- `RELEASE`: close the current repair episode after citing new public evidence;
- `INSPECT`: request an additional public workspace view before deciding;
- `ABSTAIN`: retain UNKNOWN without manufacturing completion evidence.

Every non-silent decision records the public anchors inspected, the discrepancy
hypothesis, requested Agent behavior, and the observable exit condition.  These
records are telemetry and future distillation material, not a restrictive task
ontology.

## 5. Stage steps

### M0.1 Human-policy reconstruction

- audit raw human-monitor traces rather than compressed event packets;
- segment observation/decision/intervention/re-observation/release episodes;
- remove future context, verifier outcomes, and post-hoc annotations;
- preserve positive interventions, correct silence, and human failure cases;
- write the M0 behavior playbook and leakage manifest.

### M0.2 Control-loop implementation

- reuse GenericAgent's turn-end observation and `_intervene` delivery paths;
- add an experiment-side synchronous monitor controller;
- ensure the task Agent cannot advance past a monitored boundary before the
  monitor decision is committed;
- support persistent repair episodes and repeated correction;
- preserve the unmodified B0 path behind a configuration switch;
- emit auditable OTel-compatible research events without duplicating telemetry.

### M0.3 Engineering reproduction

- use seen historical tasks only to test wiring and reproduce characteristic
  human decisions;
- verify SILENT, HOLD, repeated HOLD, RELEASE, INSPECT, and ABSTAIN paths;
- verify SHADOW-to-DELIBERATE escalation, continuous repair tracking, and a
  monitored completion proposal that can be held and resumed;
- verify that no hidden/post-hoc information enters the monitor prompt;
- do not use these tasks as causal improvement evidence.

### M0.4 First unseen real-task comparison

- run paired B0 and M0 conditions on complete `method_dev` tasks from lineages
  not used as demonstrations;
- retain identical task-Agent model, turn cap, environment, and post-run verifier;
- save full trace, monitor views/decisions, workspace artifacts, cost, and result;
- stop after the first interpretable batch, whether positive or negative.

## 6. Completion gate

This stage is complete only if:

- M0 demonstrably controls the task Agent during execution rather than after it;
- at least one full multi-turn repair episode is preserved end to end;
- correct silence is exercised on a no-intervention case;
- the first unseen real-task B0/M0 results and native verifier outcomes exist;
- every intervention can be reconstructed from deployment-visible evidence;
- failures, false interventions, and monitor-induced drift are reported.

M0 need not be cheap.  If it does not improve any unseen real task, the result is
a stage failure requiring diagnosis before formalization.  If it succeeds, its
successful and failed trajectories become the empirical source for subsequent
mechanism stages.

## 7. Later stages (not yet authorized)

After M0 results, later stages proceed failure-first:

1. formalize only the state/memory needed to preserve M0 capability;
2. formalize evidence and challenge revision where M0 makes unsupported claims;
3. formalize repair/release and completion boundaries where one-shot control fails;
4. reduce observation frequency, visible context, model calls, and state size;
5. freeze the minimum effective combination and then enter Stage 7.

The earlier R1--R7 documents remain historical and theoretical references.  Any
mechanism ordering that conflicts with this M0-first empirical stage is deferred
until M0 results identify the actual failure being repaired.
