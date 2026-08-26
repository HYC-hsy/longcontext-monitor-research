# M1 stage close and M2 entry decision

Date: 2026-08-26  
Status: user-confirmed method-discovery transition

## Decision

Stop further M1 redesign and enter M2 from the first usable active-reconstruction cost-reduction version.

- Frozen code parent: commit `6128acc` (`Fix transient monitor upstream retries`), which includes commit `ac74ce8` (`M1-C: add monitor-directed active reconstruction`).
- New development line: `m2-from-m1c`.
- One behavior-neutral test correction is carried on top: the M1 treatment contract enables both the persistent workspace and active reconstruction.
- Rejected history remains preserved on branch `m1-restart-from-m1c`, including commit `29279b1` for the sparse/bounded candidate.

The transition is a deliberate research-budget decision. It does not reinterpret incomplete or interrupted M1 runs as valid terminal success evidence.

## What M1 contributes to the M2 parent

1. A single persistent monitor identity backed by an external task--reasoning--evidence workspace.
2. Durable public task, event, decision, workspace, repair, and telemetry archives.
3. A minimal passive wake-up view plus monitor-directed active reconstruction rather than repeatedly injecting the complete history and state.
4. Public-evidence-only monitoring with no online native checker or hidden verifier.
5. Independently switchable workspace and active-reconstruction paths for later rollback ablation.

## What is explicitly not inherited

- `MinimalSparseWake` batching introduced after `6128acc`;
- bounded-UNKNOWN local release introduced in the rejected R2 candidate;
- dense root-audit/repair loops from the archived M1-D line;
- any online checker, verifier result, hidden test, or gold state;
- claims that M1 cost is already optimal or that M1 has passed final holdout validation.

## Why the last CORS finding does not block this transition

The CORS miss occurred in the later sparse-wake candidate, where turns 14--18 were deferred and the turn-19 wake view did not surface their cumulative semantic delta. That batching mechanism is absent from the `6128acc` parent. The partial run remains a valid negative result for the rejected candidate, not evidence that the rollback parent contains the same routing defect.

## M2 objective

M2 serves innovation B: **Challenge-Guided Versioned State Revision**.

Starting from the frozen M1 workspace, M2 must make task state genuinely evidence-carrying and revisable:

- state claims retain provenance and the evidence scope that currently supports them;
- public changes and contradictions create a new version rather than silently overwriting history;
- old evidence remains auditable and cannot be reused to wash a changed claim in the same version;
- affected claims can be reopened as `contested` or `unknown` without falsely reverting unrelated established state;
- “not observed” remains distinct from “did not occur”;
- revision is independently switchable and must not import completion gating, decision-value stopping, or typed repair/release mechanisms assigned to M3--M4.

## M2 execution gate

Before the first paid real run:

1. audit the exact existing M1 workspace/state interfaces and the retained Stage 6C revision substrate;
2. define the smallest revision increment and its off-switch;
3. implement it in steps below 600 changed lines;
4. pass deterministic provenance/version/conflict-reopen tests and existing regression suites;
5. prepare a real-task comparison against the frozen M1 parent, with identical model, public inputs, budgets, and telemetry;
6. stop for user confirmation before launching the paid task.

Offline tests may establish engineering correctness but cannot accept M2. M2 acceptance still requires complete real-task evidence and later rotating-task confirmation.
