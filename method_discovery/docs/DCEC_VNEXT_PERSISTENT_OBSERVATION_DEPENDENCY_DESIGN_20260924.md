# DCEC-vNext design: persistent decision-critical observation/control dependency

Status: design-only, following the `79713f0` targeted acceptance (`f9d2ab4`).
No code, model call, dev-set run, or new benchmark is authorized by this
document.

## 1. What the current production path actually does

The candidate already reaches production through `MonitorAgent`:

- `agent.py` appends the DCEC contract to the persistent Supervisor system
  prompt and injects a bounded view of `monitor/working.md` before normal
  requests (`_active_working_context`).
- The same file is writable through the existing `file_write`/`file_patch`
  tools; there is no runtime semantic state for a focal observation.
- `DCEC_CONTINUATION_PROMPT` preserves one focal premise and one observation
  status, but continuation is still a model-authored rewrite.
- `runtime.py` and the completion bridge expose completion/interruption and
  tool receipts, while `allow_complete` validates only that a current root
  handoff is pending. It does not inspect or semantically validate
  `working.md`.

This explains the R2 loss. The contract can cause a tightening action, but an
unavailable test is represented only in model-authored prose and ordinary
receipts. A later model response can replace that dependency with code-level
grounds, rewrite the note as resolved, and call `allow_complete`; no existing
transition requires an explicit replacement or discharge of the dependency.
The same gap explains Fyne's interrupted `go test` being left as “tests
running” and later disappearing before completion.

## 2. Minimal unified invariant

**Persistent decision-critical observation/control dependency:** once the
Supervisor has identified an observation as necessary for the current decision
anchor, its unfinished status remains a live control constraint until exactly
one of these model-owned transitions is recorded in the same bounded state:

1. **Replace measurement.** A completed observation is chosen that covers the
   same decision-relevant distinction and boundary, with a stronger or
   equivalent measurement placement.
2. **Explicitly discharge.** Completed existing grounds are reconsidered at
   the same decision scope, and the Supervisor explains why the original
   observation is no longer necessary and what evidence now supports the
   decision.
3. **Retain unresolved.** If neither is justified, the dependency remains
   requested, running, interrupted, or unavailable and prevents broader
   resolution/approval.

The invariant is about the relation between state and the next investigation
or control action. It is not a semantic verdict produced by the runtime.

## 3. Exact bounded state semantics

The sole state carrier remains `monitor/working.md`, with at most:

- the current decision anchor and scope;
- one focal unresolved premise;
- current grounds, their support scope and boundary limitation;
- at most one decision-critical observation dependency with status
  `requested`, `running`, `interrupted`, `unavailable`, or `completed`.

The dependency is not a history ledger. Replacing or discharging it removes it
from the current state; historical receipts remain in the existing audit.
`completed` alone is not sufficient: the Supervisor still judges scope,
discrimination, and boundary adequacy.

An intervention, a claim, a code read, or a partial/internal check cannot
silently clear an unfinished dependency. A changed decision may make it
irrelevant, but that must be an explicit model-owned discharge at the current
anchor, not an accidental omission during a rewrite.

## 4. Minimal production-path delta (design, not implementation)

Relative to `79713f0`, the candidate would change only the existing DCEC
contract and its handoff/continuation plumbing:

1. `agent.py`: extend the DCEC and continuation contracts so every transition
   away from an unfinished decision-critical observation must be one of
   replace, explicit discharge, or retain. At a root handoff the same anchor is
   re-evaluated after either replacement or discharge. The contract must state
   that weaker substitute grounds cannot broaden scope while the dependency is
   retained.
2. `working_context.py`: keep the bounded view stable and ensure the current
   dependency and its limitation are not dropped by truncation or duplicate
   injection. This is view plumbing, not a new state store.
3. `runtime.py` / existing receipt bridge: preserve deterministic facts about
   observation start, completion, interruption, unavailability, exit status,
   source/range/hash/version, and delivery. These facts are made available to
   the next ordinary Supervisor request; runtime does not decide whether a
   dependency is semantically adequate or discharged.
4. Existing completion handoff text: remind the same Supervisor that
   `allow_complete` is available only after it has reconciled the current
   dependency at the current root anchor. No new tool or model stage is added.

This is not merely a longer cautionary paragraph: the state update contract
changes which subsequent transitions are valid, and the handoff plumbing keeps
the deterministic unfinished fact available for that transition. The model
still owns semantic judgment and the single state file.

## 5. Tightening and relaxation

Tightening means changing measurement placement, abstraction level, or the
observation itself so it can cover the same decision-relevant distinction. It
does not mean automatically adding calls or requiring an integration test.

Relaxation is required after completed evidence actually covers the current
scope and relevant boundary, with no unfinished dependency and no currently
recognizable blocking alternative. The Supervisor replaces/prunes the old
grounds, clears the dependency, and returns to ordinary patrol or the scoped
control action. Thus the invariant is not a permanent conservative barrier.

## 6. Deterministic/runtime boundary

Runtime may record: request/receipt identity, tool and source metadata, range,
hash/version, start/completion/interruption/unavailability, exit status and
truncation. It may expose these facts and reject malformed state writes.

Runtime must not label evidence adequate, supported, resolved, stale in the
semantic sense, truthful, or task-satisfied; it must not infer that a
replacement covers the same distinction. Those remain judgments of the one
persistent Supervisor.

No new state file, tool schema, selector, checker, graph, confidence score,
semantic classifier, or LLM stage is required.

## 7. Cross-task explanation

- **Fyne:** the interrupted global test remains a live dependency. Later local
  repair or build evidence cannot silently replace it. The Supervisor must
  obtain a valid replacement, explicitly discharge it with sufficient grounds,
  or retain unresolved status at root closure.
- **Sphinx:** unavailable behavioral verification remains live. Resolver/code
  inspection may be a partial ground, but cannot silently substitute for the
  measurement needed to distinguish the issue's external behavior. The same
  replace/discharge/retain transition applies without mentioning any API,
  hidden assertion, or fixed test type.

## 8. Falsifiability and discrimination

### Mechanism success

A trajectory must show: dependency creation; deterministic unfinished or
unavailable observation; preservation in the next bounded state; weaker
evidence treated as partial; then an explicit replacement or discharge, or a
correct retained block. If replacement/discharge yields adequate evidence,
the Supervisor must later relax and make the appropriate control decision.

### Mechanism failure

The dependency disappears during a state rewrite, weaker evidence is promoted
to broader resolution, or `allow_complete` occurs without replacement or
explicit discharge. Permanent refusal after completed adequate evidence is
also failure.

### Low-discrimination

No decision-critical observation becomes unfinished, no root closure is
reached, or the task independently resolves before the invariant is exercised.
Such a run cannot support or falsify the mechanism.

Official PASS/FAIL alone is insufficient: PASS can occur without exercising
dependency preservation, and FAIL can result from task-side implementation or
infrastructure failure. The state/observation/control chain must be audited.

## 9. Scope, cost, and regression boundary

Expected difference: zero additional model calls, zero additional tools, one
existing `monitor/working.md`, and no new runtime semantic logic. The ordinary
DCEC-off path must be byte/behaviorally unchanged; existing receipts,
continuation, active-view bounds, and historical-candidate fail-fast behavior
remain covered by their current tests. New offline tests would cover only
dependency retention/replacement/discharge plumbing and would not be evidence
of task effectiveness.

The next gate, after independent design and code audits, is one final targeted
acceptance. If the trajectory still loses the dependency or closes on weaker
grounds, Sphinx-driven mechanism patching stops rather than adding another
rule. Fyne and Sphinx remain discovery/development cases, not held-out paper
results.

## 10. Non-adoption boundary

This is a procedural strengthening of DCEC, borrowing measurement adequacy,
finite-resource control, revision, and sanctioned-inference ideas. It does not
claim a new general KR/control formalism and does not implement TMS/ATMS,
optimal control, a causal graph, a checklist, or a second memory system.
