# M1 Persistent Task--Reasoning--Evidence Workspace: Experiment Contract

Date: 2026-08-24
Status: M1.0 frozen contract; implementation and paid runs require later stage gates
Parent: `m0-v1.1` (`1a753a4`)

## 1. Research increment

M1 tests one increment to the accepted M0 monitor: an external, persistent,
auditable task--reasoning--evidence workspace. The workspace is intended to
preserve the root contract, current local intent and causal hypothesis, public
evidence with provenance, open questions, repair history, and the relation of
local work to the root task.

The causal contrast is:

```text
control   = m0-v1.1
treatment = m0-v1.1 + independently switchable M1 workspace
```

The task-Agent model, monitor model, reasoning effort, turn limit, time limit,
environment, tools, and post-run native evaluation must otherwise remain the
same. M1 must not add online checker, hidden-test, gold-answer, future-trajectory,
or post-run evaluator information.

## 2. Mechanism boundary

M1 may add:

- immutable references to original public task clauses;
- open-semantic objects for root obligation, local intent, causal hypothesis,
  public evidence, UNKNOWN/open question, and repair episode;
- explicit relations connecting local work, evidence, and the root task;
- persistent update, lookup, and reconstruction from raw public history;
- telemetry for state updates, retrieval, reconstruction, calls, tokens, time,
  and cost.

Natural-language payloads remain first class. The implementation must not force
task semantics into a closed domain ontology, treat the compiled workspace as
authority, or cause a state update to become an automatic intervention.

M1 does not yet add M2's full version/invalidation semantics, M3's
decision-value controller, M4's formal boundary/recovery policy, or M6's active
view optimization. Minimal identity and provenance needed to avoid ambiguous
records are permitted; they must not be claimed as validation of later stages.

## 3. Frozen real-task panel

The machine-readable panel is `method_discovery/m1_real_tasks/panel.json`.
It uses four `method_dev/dev_pilot` tasks from three sources, satisfying the R0
first-increment protocol.

| Role | Task | Why it is in M1 |
|---|---|---|
| target and untuned rotation | `roadmapbench:pyg-2.3.0-roadmap` | Natural Agent promoted imports to completion of 12 targets but passed 2/12 phases. Tests root/local preservation and proxy-evidence scope. |
| M0 regression | `roadmapbench:fbr-2.43.0-roadmap` | M0 previously demonstrated sparse, flexible multi-turn correction and 7/7 completion. Tests whether structure damages that capability. |
| cross-source reasoning stress | `claw_swe:sympy__sympy-13091` | M0 solved it but widened scope and later lost a corrected constraint. Tests persistent intent/hypothesis/constraint memory. |
| cross-domain long horizon | `tb2:install-windows-3.11` | Accumulated many true proxies without root satisfaction. Also confirms M0-F's 7,200-second outer timeout in a real run. |

`clawbench:T071_video_mme_coauthor_papers` remains a valuable representation-
omission reserve, but its native evaluation adapter is not ready enough to own
the first M1 gate. No `stage_validation` or `final_holdout` task is used.

## 4. Frozen runtime and comparison policy

- Task Agent: `claude-opus-4-6`.
- Monitor: `gpt-5.6-sol`, `high` reasoning effort.
- Maximum Agent turns: 500.
- Agent/outer time limit: 7,200 seconds.
- Online native checker: disabled.
- Native evaluation: once, after deployment termination.
- Each task receives one control and one treatment branch in the first
  exploratory batch.
- Condition order alternates across tasks to reduce a simple temporal/provider
  order confound.
- Provider APIs do not expose a dependable seed, so one pair is not treated as
  a deterministic sample or statistical effect estimate.

Before each pair, preflight must verify model/API identity, image/environment,
disk, public tools, evaluator adapter, trace sink, and absence of online evaluator
feedback. A model, reasoning-effort, budget, image-semantic, or evaluator change
requires a new user decision rather than silent substitution.

## 5. Outcome and process evidence

### Primary outcome evidence

- post-run native task result and phase/test detail;
- whether the task reaches a normal, timeout, blocked, or failed termination;
- representation omission and unsupported closure episodes identified from
  deployment-visible trace, with post-run labels kept outside the online run.

### M1-target process evidence

- root obligations preserved at meaningful phase changes and completion;
- current local work remains explicitly related to the root task;
- relevant intent, hypothesis, or constraint survives until its next use;
- public evidence retains source and claim scope;
- local repair does not silently close or replace the root task;
- the monitor can reconstruct omitted detail from raw history/workspace;
- repeated reconstruction of unchanged facts decreases rather than increases.

### M0 capability-regression evidence

- correct silence during coherent reversible work;
- task-specific inspection rather than field-following behavior;
- test oracle and evidence-scope auditing;
- intent-level correction where justified;
- multi-turn uptake and residual tracking;
- release with non-material UNKNOWN;
- false HOLD, objective shift, state pollution, and unbounded investigation.

### Cost evidence

Record Agent and monitor calls, input/output/cache tokens, wall time, latency, and
available dollar cost. A treatment gain explained only by additional calls or an
abnormal cost increase is an immediate stopping point, not an accepted method
result.

## 6. Attribution and decision rule

Offline unit tests, schema validation, replay, and LLM judgment may establish
engineering correctness or explain a trajectory. They cannot promote M1.

M1 is accepted only if complete real-task evidence shows:

1. intended behavioral improvement on at least one target task;
2. a plausible causal link to workspace preservation/reconstruction rather than
   model, budget, environment, or verifier differences;
3. no material loss of the frozen M0 capability envelope on the regression task;
4. no severe cross-source false blocking, state pollution, objective shift, or
   unbounded verification;
5. complexity and cost justified by the observed gain.

If the first interpretable result exposes an implementation defect, repair and
rerun the affected pair. If it exposes a mechanism defect with one clear
trajectory-grounded remedy, M1 may make one bounded redesign after user review.
Otherwise revert to `m0-v1.1`. An accepted result receives an annotated `m1`
tag; intermediate implementation commits do not imply acceptance.

## 7. Mandatory stopping points

Stop before expanding the experiment when any of the following occurs:

- the first complete PyG control/treatment pair is interpretable;
- M1 first improves or degrades a target behavior;
- FBR shows loss of a known M0 capability;
- process evidence and native evaluator disagree;
- treatment has an abnormal cost increase;
- install-windows is again cancelled at 3,600 seconds;
- the evidence requires a major representation or architecture decision.

## 8. M1.0 completion gate

- [x] Increment and non-goals are frozen.
- [x] Four `method_dev/dev_pilot` tasks from at least three sources are frozen.
- [x] A target task, M0 regression task, cross-source task, and cross-domain long
  task are represented.
- [x] Every selected task has a historically available post-run evaluator.
- [x] `stage_validation` and `final_holdout` are excluded.
- [x] Runtime identity, budgets, evidence separation, costs, and stopping rules
  are specified.
- [x] M1 acceptance requires complete real-task behavior, not offline scores.

M1.0 does not authorize M1.1 implementation or paid M1.3 runs.
