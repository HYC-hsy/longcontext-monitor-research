# Method Discovery: M0-to-Final Evolutionary Roadmap

Date: 2026-08-24  
Status: user-confirmed execution authority after M0-v1 freeze  
Scope: replaces the post-M0 component-screening order in earlier R1--R7 plans; it does not change the paper problem, innovations A--D, no-checker boundary, frozen data split, or final-holdout policy.

Behavioral target: `method_discovery/docs/FINAL_METHOD_OPERATIONAL_NORTH_STAR_20260824.md`. The roadmap is complete only insofar as its accepted versions implement and validate that lifecycle; component existence alone is not completion.

## 1. Development decision

Method discovery now uses one continuous method lineage:

```text
M0-v1
  -> add one coherent mechanism toward the target architecture
  -> run complete real tasks
  -> measure intended gain and regression of existing M0 capabilities
  -> keep and version the increment, or revert to the last accepted version
  -> repeat
  -> freeze the minimum effective final method
```

M0-v1 is not one candidate among many. It is the runnable teacher policy, capability baseline, and rollback point from which every later method version descends. Offline packets, unit tests, static schemas, and LLM judges may diagnose or validate engineering behavior but cannot promote an increment. An increment is accepted only by complete real-task evidence.

The Git identity of the starting point is:

- commit `3fda924`;
- tag `m0-v1`;
- manifest `M0_V1_FREEZE_MANIFEST.md`.

## 2. Target method

The intended final artifact is a no-checker runtime control layer attached to a task Agent. It consists of:

1. one persistent, capable monitor Agent;
2. an external task--reasoning--evidence state that preserves the root contract, current intent, hypotheses, actions, public observations, repair episodes, and their relations;
3. evidence-carrying, versioned state revision that preserves provenance, reopens claims when their support becomes stale or contested, and avoids evidence washing;
4. decision-centered epistemic control that selects a small, reversible, decision-changing observation instead of attempting to eliminate every UNKNOWN;
5. evidence-gated boundaries for high-risk intent, test-oracle formation, evidence promotion, repair release, and root completion;
6. a persistent challenge--response--action--evidence--residual--release loop with typed recovery actions;
7. an optional budgeted active-view layer that removes redundant observation and context without sacrificing the accepted capability envelope.

This target guides the order of implementation but does not guarantee that every component survives. The final paper method is the last real-task-supported minimal version, not the most feature-complete version.

## 3. Frozen M0 capability envelope

Every successor must preserve, unless real-task evidence and user approval explicitly revise it:

- a single persistent monitor identity;
- online access only to the public task, Agent trajectory/actions, public tools/environment, workspace, and prior monitor state;
- synchronous pause and read-only investigation;
- sparse intervention with continuous visibility;
- intent-level correction when a public faulty inference is about to drive a material action;
- tests treated as executable task interpretations rather than independent truth;
- Agent-authored reports, tests, and verifiers treated as provisional evidence;
- HOLD followed by continuous uptake and residual tracking;
- root task, local subtask, and repair episode kept distinct;
- verbal acknowledgement not counted as repair;
- UNKNOWN preserved without automatically causing HOLD;
- a fresh root audit at completion and release without claiming hidden correctness.

## 4. Real-task acceptance protocol for every increment

Each mechanism stage uses the previously accepted method version as its control. The treatment changes only the current increment plus unavoidable instrumentation.

Before implementation, each stage freezes a small real-task panel containing at least:

1. **target task**: a full task exhibiting the failure the increment is intended to repair;
2. **capability-regression task**: a task on which the previous version displayed valuable monitoring behavior or succeeded;
3. **cross-source task**: a full task from a different benchmark lineage or task type.

Where runtime cost permits, use paired repetitions. Historical M0 traces may select or explain tasks but cannot replace the new treatment run. Reusing FBR, SymPy, or install-windows is allowed for behavioral regression, but at least one rotating `method_dev` task not used to tune the exact increment must be included before acceptance. `final_holdout` remains forbidden until method freeze.

Every run records:

- native post-run outcome;
- representation omission and unsupported closure events;
- intervention, uptake, residual, release, and false-intervention episodes;
- scope expansion, repeated investigation, and unresolved material evidence debt;
- Agent and monitor calls, tokens, latency, wall time, and available dollar cost;
- complete public trajectory, state revisions, prompts/views, workspace result, and post-run verifier.

Cost awareness begins with M1, not M6. At every stage, prefer the simpler and cheaper implementation when real-task capability is equivalent, and stop for review when an apparent gain is explained only by additional compute or introduces an abnormal cost increase. This is continuous cost accounting and local parsimony, not premature optimization: an unproven capability must not be removed merely to make an early version cheap.

An increment is accepted only when:

- it produces the intended behavioral improvement on at least one complete target task;
- the improvement is attributable to the new mechanism rather than hidden verifier access or an unrelated model/budget change;
- it does not materially regress the frozen M0 capability envelope on the regression panel;
- cross-source behavior does not reveal a severe new failure such as false blocking, objective shift, evidence pollution, or unbounded verification;
- its complexity is justified by the observed gain.

If a run reveals an implementation defect, repair the defect and rerun. If it reveals a mechanism failure, perform a bounded postmortem and make another evidence-motivated attempt within the same mechanism purpose. Research iteration is not capped at one redesign: state format, update rule, trigger, view, or control details may require multiple attempts. Each attempt must be logged, exercised on complete real tasks, and followed by task rotation so that one case does not become the de facto specification. The stage stops for user review when results are interpretable, the preregistered task/API budget is exhausted, a major design choice appears, or evidence supports reverting the mechanism. Failed attempts remain part of the record.

Every accepted version receives a Git commit and annotated tag (`m1`, `m2`, ...). Reports must state the parent tag and exact code/config delta. A tag means the version passed its stage gate; intermediate engineering commits do not.

## 5. Evolution stages

The stages below define **capability gaps to close**, not predetermined implementations. Lists of state content, relations, decision factors, boundaries, or actions are behavioral requirements and diagnostic dimensions. They do not preselect a fixed graph schema, storage engine, prompt, scoring formula, trigger algorithm, or intervention template. Those details are discovered iteratively from complete real-task evidence inside the stage.

### M0-F: freeze and infrastructure correctness

**Purpose:** create the immutable starting point and remove experimental faults that can invalidate later comparisons.

**Current state:** completed on 2026-08-24 and prepared as M0-v1.1. M0-v1 was frozen and the infrastructure work was limited to:

- correct Harbor's outer 3,600-second timeout so it matches the approved 7,200-second adapter/task limit;
- establish that historical decision archives were valid UTF-8 JSON and correct the encoding-dependent audit diagnosis;
- make complete JSON-object writes atomic and verify timeout/archive behavior without changing M0 judgment policy;
- optionally rerun install-windows only as an M0 confirmation/engineering run.

The patch is tagged `m0-v1.1`; it does not alter M0 behavior. Its first M1 long run must still confirm the two-hour limit end to end.

### M1: persistent task--reasoning--evidence workspace

**Purpose:** give M0's existing intelligence a reliable external cognitive substrate without constraining its open semantic judgment.

Starting from M0-v1, add the smallest state that preserves:

- immutable references to original root obligations;
- current local intent and causal hypothesis;
- public evidence and provenance linked to the claim it bears on;
- open questions and UNKNOWNs;
- current repair episode, prior intervention, Agent response, and observed uptake;
- the relation of local work to the root task.

M1 also implements the lifecycle's boot/orientation and continuous semantic compilation behavior: the initial root model may be incomplete, new obligations or relations may be discovered later, and the monitor can rebuild detail from raw history rather than treating the compiled state as authority.

Natural-language content remains allowed. The initial implementation may use JSON/Markdown objects and explicit relations; a graph database is not required. The monitor retains direct access to raw trajectory and workspace and may reconstruct details instead of trusting the compiled state.

**Targeted failures:** monitor obligation loss, local-task tunnel vision, repeated reconstruction, and failure to reconnect the current repair to the root task.

**Regression focus:** preserve M0's flexible task understanding, sparse silence, and task-specific investigation. Reject the increment if the structure makes the monitor more rigid or causes it to follow fields instead of evidence.

### M2: evidence-carrying versioned revision

**Purpose:** make task state revision reliable under code, test, artifact, environment, and interpretation changes.

Starting from accepted M1, add:

- append-only evidence/provenance history;
- object or claim versions;
- explicit `claimed`, `observed`, `supported`, `contested`, `unknown`, and `superseded` distinctions;
- change-driven invalidation or reopening of affected support;
- preservation of conflicting evidence without same-version washing;
- selective, relation-based revalidation rather than global reset.

Revision is bidirectional: later evidence or justified Agent pushback can also contest and revise the monitor's own hypothesis, intervention, or state update. The monitor must not become an unchallengeable second source of truth.

**Targeted failures:** proxy evidence promoted to completion, stale tests supporting changed behavior, old success surviving a relevant modification, and new success erasing a prior unresolved conflict.

**Regression focus:** avoid reopening unrelated obligations or turning every edit into full-task verification.

### M3: attention activation and decision-centered epistemic control

**Purpose:** implement the transition from cheap silent shadowing to deep deliberation, then teach the evolving monitor to choose what is worth investigating now and when to stop.

Starting from accepted M2, introduce a transient decision view containing only what is needed to judge the current consequential choice:

- current proposed decision/action;
- plausible competing explanations;
- public supporting and conflicting evidence;
- causal/material connection to a root obligation;
- reversibility and cost of acting or waiting;
- one candidate decision-changing observation;
- an explicit finite stopping condition.

M3 must separately expose: event ingestion, attention activation, active reconstruction, and intervention judgment. A trigger may increase attention without producing a HOLD. Fixed keywords or intervals may support deterministic indexing but cannot be the complete semantic activation policy.

The mechanism must distinguish semantic similarity from decision relevance. UNKNOWN is investigated only when a plausible result would materially change the next action, release decision, or completion claim.

**Targeted failures:** SymPy-style scope inflation, Windows-style accumulation of unresolved hypotheses, repeated checking of auxiliary artifacts, and delaying safe reversible work until an imagined inventory is complete.

**Regression focus:** do not suppress M0's ability to discover an unanticipated but material conflict. Decision control guides attention; it is not a closed list of allowed concerns.

### M4: evidence-gated boundaries and typed persistent recovery

**Purpose:** formalize the successful M0 control loop without replacing adaptive natural-language collaboration with rigid workflow rules.

Starting from accepted M3, make the following boundaries independently observable and switchable:

- material faulty intent before it becomes a test or production change;
- test-oracle creation or weakening;
- promotion of local evidence to a broader claim;
- release of a repair episode;
- root completion;
- irreversible or evidence-polluting action.

Represent the recovery purpose separately from its natural-language message, for example:

- `RESURFACE` an omitted obligation;
- `DISCRIMINATE` competing causes;
- `REPAIR` a confirmed conflict;
- `REOBSERVE` stale environmental evidence;
- `CONTINUE` safe natural work;
- `HOLD_COMPLETION` unsupported closure;
- `RELEASE` a repaired local episode;
- `ABSTAIN/ESCALATE` when public evidence cannot support action.

The persistent loop remains:

```text
challenge -> Agent interpretation -> intended action -> actual action
          -> public evidence -> residual -> re-correct or release
```

M4 must also implement lifecycle-complete intervention delivery, local release, root completion, and non-success terminal semantics. Timeout, missing authority, environment failure, or exhausted investigation must preserve unresolved state and produce abstention/escalation rather than accidental completion.

**Targeted failures:** one-shot reminders, verbal acceptance treated as repair, premature release, local success treated as global completion, and repeated HOLD while the Agent is already carrying out the requested probe.

**Regression focus:** preserve correct silence and autonomy during coherent repair and ordinary recoverable failures.

### M5: integrated reliability stabilization

**Purpose:** stabilize the single cumulative method produced by M1--M4 and remove any increment whose value disappears in combination.

This is not a new component tournament. Begin with the latest accepted version and run:

- full-version repetitions;
- one-at-a-time rollback to its accepted parent behavior;
- only the few interaction tests motivated by an observed regression;
- cross-source and rotating method-development tasks.

M5 includes a lifecycle coverage audit against `FINAL_METHOD_OPERATIONAL_NORTH_STAR_20260824.md`. Every required phase and invariant must point to implementation, trace evidence, or an explicit unresolved gap. Passing component tests without lifecycle coverage cannot complete M5.

If two mechanisms duplicate each other after integration, retain the simpler one. If an earlier mechanism helps alone but harms the cumulative method, revert or simplify it. The output is the reliability-first candidate, not yet the cheapest candidate.

### M6: capability-preserving cost reduction

**Purpose:** use the cost evidence accumulated since M1 to systematically remove wasted computation after the reliable method exists and run the strict matched-budget comparisons that earlier capability stages cannot settle.

Starting from accepted M5, progressively test:

- deterministic event archival and delta computation;
- simple event-triggered deep deliberation;
- query/decision-conditioned active views;
- suppression of unchanged-history rereads;
- bounded inspection depth and reuse of validated state;
- optional lower-cost maintenance only as an ablation, never a core cross-model dependency.

Compare each cost reduction against the complete M5 method on the same real-task protocol. Report task quality and cost as a Pareto frontier. Cost control enters the core paper method only if it is non-inferior within a preregistered tolerance or improves the frontier. Otherwise retain the full reliability method and report cost as a limitation or follow-up direction.

Required comparisons include full ledger/history, static truncation, always-visible state, PMA-style reminder, equal-frequency random views, and query/use-site-conditioned active view under matched visible tokens/calls/cost.

### M7: unseen validation and final method freeze

**Purpose:** stop development and decide the paper method.

Use `stage_validation` tasks not used to tune the increments, multiple task sources, repetitions, and where feasible more than one task-Agent model. Run matched-budget comparisons and disable each surviving mechanism independently. Do not tune on `final_holdout`.

Freeze the smallest cumulative version that:

- improves real task outcomes or prevents material long-horizon failures;
- jointly addresses representation omission and unsupported closure;
- preserves the required M0 capabilities;
- avoids severe false blocking and unbounded verification;
- has a defensible reliability--cost position;
- retains no component solely for narrative completeness.

Create the final Git tag and migrate stable constraints from the temporary AGENTS.md section into the formal paper/method specification. Only after user confirmation may the temporary section be removed and Stage 7 formal experiments begin.

## 6. Stage reporting and stopping

Every evolution stage stops after its first interpretable complete real-task batch or any major decision point. The report must identify:

- parent and treatment Git identities;
- exact mechanism delta;
- real tasks and why they were selected;
- intended gain;
- observed gain, failures, and M0 capability regressions;
- native outcomes and process evidence;
- calls, tokens, time, and cost;
- whether the increment is accepted, requires one bounded redesign, or should be reverted.

The next stage cannot start until the user confirms the result and the accepted version is tagged.

## 7. North-star coverage audit

The revised roadmap covers the final lifecycle at the following capability level:

| Required final behavior | Primary evolution stage |
|---|---|
| boot from the public task without inventing a perfect specification | M1 |
| preserve root task, local intent, evidence, and repair history across a long run | M1 |
| revise state, evidence, and the monitor's own mistaken judgments | M2 |
| remain silently aware during coherent work | M1 and M3 |
| activate attention on a consequential semantic event | M3 |
| actively reconstruct the evidence needed for the current decision | M1 and M3 |
| decide whether to observe, stay silent, or intervene without eliminating every UNKNOWN | M3 |
| deliver a minimal adaptive intervention | M4 |
| follow multi-turn uptake, residuals, and re-correction | M4 |
| release local control without losing the root task | M4 |
| audit root completion and distinguish residual uncertainty from evidence debt | M2--M4 |
| terminate honestly on timeout, missing authority, environment failure, or irreducible uncertainty | M4 |
| demonstrate the whole lifecycle without hidden checker information | M5 |
| reduce redundant observation/context while preserving capability | M6 |
| establish unseen-task, matched-budget, and ablation evidence | M7 |

No lifecycle aspect is intentionally left without a stage after this revision. What remains intentionally unresolved is **how** each aspect should be implemented and which implementation survives real-task testing.

## 8. Anti-drift summary

- M0-v1 is the only starting method lineage.
- Every later method is an incremental modification of the last accepted version.
- Complete real tasks decide whether an increment survives.
- Every increment is tested for both intended gain and regression of existing capability.
- Offline tests validate engineering only.
- No online checker, hidden verifier, gold answer, or future trajectory is introduced.
- Reliability is optimized before cost; cost remains measured from the beginning.
- Cost is considered in every increment; M6 is the dedicated optimization and causal validation stage rather than the first time cost appears.
- The ideal architecture guides development, but real evidence determines the final minimal method.
