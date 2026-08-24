# Final Method Operational North Star

Date: 2026-08-24  
Status: user-confirmed behavioral target for M0 evolutionary method discovery  
Purpose: define what the intended best-paper-level system actually is and how it behaves throughout a complete task. This is a behavioral/product specification, not a commitment to one fixed schema, graph implementation, prompt, mathematical estimator, or model architecture.

## 1. One-sentence artifact definition

The final method is a **no-checker, persistent deliberative control layer** attached to a long-running task Agent. It continuously compiles public task execution into a revisable task--reasoning--evidence model, remains silent during coherent progress, activates deep investigation only when a consequential decision is at risk, intervenes with the smallest evidence-grounded recovery action, follows the resulting repair until observable uptake or escalation, and releases or terminates without pretending to know hidden correctness.

It is not merely:

- another task Agent;
- a static knowledge graph;
- a summary or RAG memory bank;
- a completion checker;
- a fixed workflow or rule engine;
- a second model that comments after every turn.

It is one monitor Agent plus an external auditable cognitive substrate and a runtime control loop.

## 2. System boundary

```text
ORIGINAL PUBLIC TASK
        |
        v
  TASK AGENT <---- recovery message / release ---- PERSISTENT MONITOR
        |                                          |       ^
        | actions, intent, tool results, artifacts |       | active reconstruction
        v                                          v       |
  PUBLIC ENVIRONMENT ---------------------- EVENT ARCHIVE + REVISABLE
                                             TASK--REASONING--EVIDENCE STATE
```

The task Agent owns ordinary task execution. The monitor owns sustained task understanding, evidence discipline, selective investigation, and sparse course correction. The environment and native verifier do not provide a hidden online oracle.

The same monitor identity is used throughout the task. Deterministic code may archive events, compute deltas, maintain indexes, and enforce pause/resume mechanics. It may not make hidden semantic judgments on behalf of the monitor.

## 3. Persistent cognitive substrate

The logical representation is a dynamic task--reasoning--evidence graph, regardless of whether the implementation uses JSON, Markdown, relational tables, an event-sourced projection, or an actual graph store.

### 3.1 Stable semantic objects

The minimum object families are:

- **Root contract:** original objective, explicit obligations, prohibitions, termination conditions, and immutable source references.
- **Task state:** open, active, provisional, supported, contested, unknown, superseded, or otherwise empirically justified obligation state.
- **Process state:** current local goal, Agent intent, plan, hypothesis, attempted action, observation, and repair episode.
- **Evidence:** public claim, action, tool result, test, diff, environment observation, or artifact with provenance and scope.
- **Relations:** supports, contests, operationalizes, depends-on, invalidates, supersedes, motivates, affects, and contributes-to-root.
- **Control state:** current attention mode, open decision, intervention, uptake, residual, reopen condition, and release basis.

Natural-language payloads are allowed inside these objects. Structure supplies stable roles and relations; it must not force all task semantics into a closed ontology.

### 3.2 Required invariants

The final method must preserve these behavioral invariants:

1. The original public task remains immutable authority and is always recoverable.
2. A local subtask or repair episode cannot silently replace or close the root task.
3. Agent statements create claims, not supported completion by themselves.
4. Agent-authored tests and verifiers are evidence whose oracle and scope must be audited, not independent authority.
5. Evidence is linked to the claim, object version, and observation that it actually supports.
6. Relevant public change may invalidate current support without deleting historical evidence.
7. Conflicting evidence remains contested until resolved; new positive evidence cannot silently wash it away.
8. “Not observed” is not “did not occur.” UNKNOWN is a legitimate persistent state.
9. Monitor judgments and interventions are themselves revisable when later public evidence or Agent pushback shows them to be wrong.
10. The monitor can reconstruct detail from raw history and workspace instead of treating its compiled state as infallible.

## 4. Complete online lifecycle

### Phase 0: boot and contract orientation

At task start, the monitor receives the full original public task exactly once and establishes a provisional root model.

It should:

- preserve immutable task clauses and their source spans;
- identify clearly explicit obligations, prohibitions, and completion conditions;
- leave ambiguous acceptance semantics as UNKNOWN rather than inventing a checker;
- record task type and likely high-information boundaries only as hypotheses;
- initialize an empty event archive and no open repair episode.

It should not:

- demand a complete formal specification before the Agent starts;
- generate an exhaustive test plan that becomes a new user requirement;
- intervene merely because the initial task model is incomplete.

**Normal action:** allow the task Agent to begin.

### Phase 1: continuous silent shadowing

For every new public Agent delta, deterministic infrastructure archives the raw event and updates cheap indexes. The monitor maintains situational awareness without deep-reading the entire history or messaging the Agent.

In normal coherent progress it should:

- update current intent, local goal, public actions, observations, and affected objects;
- notice new or changed tests, diffs, failures, phase transitions, and claims;
- keep unresolved concerns as watch items;
- allow ordinary failed commands and natural self-repair;
- remain silent while the Agent is gathering information that can resolve the concern;
- avoid rereading unchanged artifacts.

Silence is an active decision to preserve autonomy, not absence of monitoring.

### Phase 2: attention activation

The monitor moves from cheap shadowing to focused deliberation when a public event creates a plausible, material risk to a consequential decision. Triggering deep attention does not automatically justify intervention.

Candidate activation events include:

- a stated causal diagnosis about to drive a material implementation change;
- a new, weakened, deleted, or relied-upon test oracle;
- evidence promoted from a local observation to a broader claim;
- a relevant object changed after earlier support was recorded;
- an explicit task clause, prohibition, or safety constraint contradicted by an action;
- a repair episode response or proposed release;
- local or root completion proposal;
- irreversible, destructive, or evidence-polluting action;
- persistent repetition, rationalization, objective substitution, or abandonment of an obligation;
- a state inconsistency detected during incremental revision.

Activation should depend on semantic materiality and current decision relevance, not only keyword rules or fixed turn intervals.

### Phase 3: decision-conditioned active reconstruction

Once activated, the monitor formulates the current decision under review, then retrieves a minimal sufficient view:

- relevant original contract slice;
- current Agent intent and causal claim;
- affected task/evidence objects and versions;
- supporting, conflicting, stale, and missing public evidence;
- relevant test oracle, production diff, environment state, or trajectory window;
- prior interventions and uptake within the current repair episode;
- connection between the local decision and root-task impact.

It may invoke read-only tools repeatedly when needed. It must be able to revise the query as evidence changes. The active view is not a fixed top-k memory retrieval; it is conditioned on the decision being made.

### Phase 4: epistemic and control judgment

The monitor distinguishes at least:

- confirmed contract conflict;
- unsupported closure or evidence promotion;
- observed failure with unknown cause;
- causal uncertainty between plausible explanations;
- stale or invalidated support;
- representation omission;
- ordinary recoverable friction;
- residual uncertainty that does not justify control.

Before intervening it asks:

1. What concrete next decision or action is at risk?
2. What public contract, safety, or correctness harm could result from silence?
3. Is the Agent already taking a safe action that will resolve the concern?
4. Is the contemplated action reversible?
5. What smallest observation could distinguish plausible alternatives?
6. Would either result change the next action?
7. What finite condition ends this investigation?

No single numerical formula is required in advance. The final implementation must make these factors observable enough for audit and ablation.

### Phase 5A: remain silent

The monitor remains silent when:

- the Agent is making coherent, reversible progress;
- an ordinary error is already being investigated or naturally repaired;
- a concern is only speculative or semantically similar but not causally connected;
- a planned safe experiment will resolve the uncertainty;
- another check would not change the next decision;
- the remaining UNKNOWN is not material to the current boundary.

It may update the external state, create a watch/reopen condition, or schedule a later completion audit without messaging the Agent.

### Phase 5B: inspect without intervention

The monitor may pause long enough to read tests, diffs, logs, history, or environment state, yet still return silence. Inspection is not evidence that a fault exists and must not manufacture a HOLD.

### Phase 5C: intervene with a minimal recovery action

When control is justified, the monitor selects the recovery purpose and expresses it adaptively in natural language. A good intervention contains only what is needed for recovery:

- authoritative task clause or safety basis;
- concrete public discrepancy or unresolved causal assumption;
- why the next intended action or closure is at risk;
- the smallest appropriate recovery action;
- a discriminating observation when causality is uncertain;
- observable conditions for returning autonomy.

Typed purposes may include:

- `RESURFACE` an omitted obligation;
- `DISCRIMINATE` competing causes;
- `REPAIR` a confirmed conflict;
- `REOBSERVE` stale environment evidence;
- `ROLLBACK/CONTAIN` a harmful or evidence-polluting action;
- `HOLD_TRANSITION` a risky state change;
- `HOLD_COMPLETION` unsupported root closure;
- `ABSTAIN/ESCALATE` when safe progress cannot be supported.

The type supports audit and control; it must not force templated wording that suppresses monitor intelligence.

### Phase 6: persistent repair episode

An intervention opens a repair episode. The monitor does not disappear after sending the message.

```text
challenge
 -> Agent interpretation
 -> Agent intended next action
 -> actual action/tool result/artifact change
 -> public behavioral evidence
 -> residual discrepancy
 -> re-correct, remain silently engaged, or release
```

Within the episode:

- every subsequent response/action remains visible under focused attention;
- verbal agreement is not uptake;
- a correct repair step usually receives silence, not repeated instruction;
- a new public misunderstanding is corrected before avoidable propagation;
- the monitor may retract or revise its own challenge when new evidence defeats it;
- only the affected slice is repaired unless evidence connects the issue more broadly;
- one requested discriminating probe is allowed to run before another is demanded;
- local repair is checked against materially affected prior evidence and the root task.

### Phase 7: local release and return to shadowing

The monitor releases focused control when:

- the Agent's interpretation is again compatible with the public contract;
- the next actions demonstrate behavioral uptake;
- the concrete discrepancy is repaired or honestly preserved as unresolved;
- material affected evidence has been revalidated to the degree justified by the decision;
- no additional bounded check has positive expected decision value.

Release returns autonomy and switches back to shadowing. It does not certify hidden correctness, erase UNKNOWN, or close the root task. Reopen conditions remain in the state.

### Phase 8: root completion proposal

When the task Agent proposes completion, the monitor reconstructs a fresh root view from:

- immutable original obligations;
- current versions of relevant artifacts/environment;
- support, conflicts, invalidations, and unresolved repair episodes;
- whether public tests/observations actually discriminate required behavior;
- whether local evidence has been overgeneralized;
- whether residual UNKNOWN is material evidence debt or merely residual uncertainty.

The monitor then chooses:

- `RELEASE_COMPLETE`: no known repairable material public discrepancy remains;
- `HOLD_COMPLETION`: one or more explicit material obligations are being closed without normally expected public support and a bounded check/action exists;
- `REOPEN`: relevant change or conflict invalidates prior closure;
- `ABSTAIN/ESCALATE`: public evidence cannot support either safe completion or a feasible autonomous repair.

The monitor never claims that hidden tests would pass. It judges only whether completion is justified by the best safely obtainable public evidence.

### Phase 9: non-success terminal conditions

The system must terminate coherently when:

- budget or time is exhausted;
- the environment is irrecoverably unavailable;
- required authority, credential, or user decision is missing;
- repeated repair produces no new decision-changing evidence;
- the Agent process fails;
- continuing would be destructive or unsafe.

At such a boundary it preserves the root state, achieved work, unresolved obligations, evidence, attempted repairs, and the exact reason for abstention/escalation. It does not convert resource exhaustion into task completion.

### Phase 10: post-run archival and evaluation separation

After online termination:

- finalize append-only events, state versions, decisions, prompts/views, interventions, uptake, and costs;
- run native verifier or hidden evaluation only in the post-run evaluation path;
- never feed that result back into the completed deployment trajectory;
- record enough identity and hashing information to reproduce the run.

## 5. What “matching the intended final method” means

The final implementation need not use one exact prompt or data structure. It matches the target only if it passes four forms of evidence.

### 5.1 Lifecycle conformance

For every phase above, the system has an implemented, auditable transition and can exercise it in integration tests or real runs. No phase exists only in prose.

### 5.2 Behavioral conformance on complete real tasks

It must demonstrate across task sources:

- correct silence during coherent progress;
- activation on material decision risk;
- autonomous evidence reconstruction;
- at least one intent-level correction;
- test/evidence-scope auditing where relevant;
- a multi-turn repair episode with behavioral uptake;
- local release without root-task loss;
- completion hold/reopen where justified;
- release with non-material UNKNOWN;
- abstention or escalation when safe public resolution is unavailable.

No single task must exhibit every behavior, but the stage-validation portfolio must cover the lifecycle.

### 5.3 Problem-level effectiveness

Relative to B0, strong memory/reminder baselines, and M0-v1 where appropriate, the final method must improve real outcomes or materially reduce representation omission and unsupported closure without unacceptable false blocking or monitor-induced drift.

### 5.4 Reliability--cost evidence

All costs are reported. Equal-budget and Pareto comparisons determine whether cost control is a core contribution. The reliability method may survive even if cost reduction fails, but an advantage that disappears under reasonable matched-compute controls cannot be presented as an algorithmic gain.

## 6. Failure criteria

The implementation is not the intended method if it degenerates into any of the following:

- a schema-filling Agent that follows fields instead of understanding the task;
- a reminder system that injects remembered clauses without auditing evidence;
- a completion checker that depends on hidden or reliable online verification;
- a monitor that speaks at every trigger instead of separating attention from intervention;
- a graph that stores entities but cannot revise support or govern decisions;
- an exhaustive UNKNOWN-elimination loop;
- a one-shot critic that does not follow repair uptake;
- an unbounded strong-model resampling system whose gain is only extra compute;
- a workflow that cannot preserve M0's flexible response to unseen domains.

## 7. Discovery uncertainty

This specification fixes the desired behavior, not the implementation path. It is expected that state formats, update rules, trigger estimators, active-view construction, boundary logic, and recovery representations will require repeated real-task-driven attempts.

Iteration is permitted when:

- each attempt is a concrete hypothesis derived from observed trajectory evidence;
- the mechanism purpose and parent version stay fixed within the stage;
- changes, tasks, budgets, and outcomes are logged;
- task rotation and untouched validation tasks prevent single-case overfitting;
- failed attempts remain recorded rather than silently rewritten;
- major architecture, model, benchmark, budget, or contribution changes return to the user for decision.

The roadmap controls direction and evidence quality; it does not pretend that research implementation is deterministic.
