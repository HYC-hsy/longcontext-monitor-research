# DCEC-v1 Minimal Mechanism Design

Date: 2026-09-21

Status: design only; not implemented or experimentally evaluated

Basis: frozen DCEC-v0 implementation and the independently accepted `DCEC_V0_FYNE_R2_MECHANISM_DIAGNOSIS_20260921.md`

## 1. The only v0 → v1 change

DCEC-v1 retains one persistent Supervisor, its existing tool loop, persistent History, and the single bounded `monitor/working.md` active view. It adds no call, agent, checker, selector, or state store.

The sole change is to the semantics by which the Supervisor **revises and consumes its current working state**:

> A concern or task may be closed only when a completed observation is adequate for the current decision scope and distinguishes states that require different supervisory actions. Investigation strength rises when decision scope or consequence rises and relaxes after adequate evidence is obtained. An unfinished decision-critical observation remains a current control dependency, not positive evidence.

This is **decision-conditioned evidential transition control**. It changes the transition policy inside DCEC, not the number or kinds of components.

## 2. Exact bounded state semantics

`monitor/working.md` remains the only model-owned current cognitive state. It holds at most four functional items; their wording and layout may remain natural language.

### 2.1 Current decision anchor

The consequential action presently being decided, together with its scope. Examples of scope are a local implementation instance, a target-level quantified requirement, a recovery episode, or whole-task completion.

It is not a task plan. When the consequential decision changes, this anchor is replaced rather than accumulated.

### 2.2 One focal uncertainty / unresolved premise

One proposition whose materially different answers would cause different next actions. It must be stated at the same scope as the current decision.

For example, after repairing one implementation of an interface, the local uncertainty may be closed while the broader premise “the quantified implementation set is covered” remains unresolved. DCEC-v1 does not enumerate every requirement or retain a concern list.

### 2.3 Current grounds with scope and limitation

Only the observations presently used for the decision are retained, each with enough boundary to avoid unsupported inference:

- source/receipt identity and relevant version;
- what was actually observed;
- the scope it supports;
- what it does not establish for the current decision.

Claims and summaries may be retained as claims and summaries, but do not silently become direct observations. A ground is not a numeric confidence score or an automatic truth label.

### 2.4 At most one decision-critical observation status

When the focal uncertainty is being investigated, the state may retain one current observation dependency:

```text
observation identity and intended distinction
status: requested | running | interrupted | completed
receipt/result reference, only when one exists
```

This is not a workflow history. Once the observation is completed and consumed, superseded, or no longer relevant to the current decision, the slot is cleared or replaced.

The runtime may supply deterministic metadata such as tool identity, receipt presence, range, hash, truncation, cancellation, or exit status. The Supervisor remains responsible for semantic adequacy.

## 3. Transition semantics

### 3.1 `open/recovering → resolved`

Resolution is allowed only when all of the following hold:

1. the concern and the decision have an explicit current scope;
2. the supporting observation is `completed`, with a real result rather than a request, intention, or interrupted execution;
3. the observation's supported scope covers the scope being resolved;
4. the possible observation outcomes were capable of distinguishing a state that permits release from a state that requires continued investigation or intervention;
5. no still-relevant decision-critical observation remains requested, running, or interrupted.

An intervention changes `open` to `recovering`; it does not establish resolution. A direct observation that one repaired instance is correct may resolve that local instance. It cannot resolve a universal or whole-target claim unless the observation also covers that broader quantification.

Resolution removes the concern from the active frontier. If its completed ground remains relevant to a later decision, only the bounded ground and its scope are retained—not the full episode.

### 3.2 Grounds are revised by replacement, not evidence accumulation

New material does not become another supporting bullet merely because it is new text.

- A newer observation of the same object, version, claim, and scope replaces the current ground when it supersedes it.
- A conflicting observation revises or reopens the focal uncertainty.
- A narrower observation replaces only the narrower part it actually covers; it cannot inherit the old broader conclusion.
- A version change is recorded deterministically. Whether it invalidates the ground semantically remains a Supervisor judgment.
- Superseded material remains in History/audit, but leaves the bounded current grounds unless still needed for the current decision.

This prevents claim → summary → note repetition from looking like multiple independent reasons while avoiding a new evidence ledger.

### 3.3 Scope increase

When the decision changes from local recovery to a broader target or whole-task completion, prior local resolutions are not revoked, but their grounds are **re-qualified against the new scope**. They remain evidence only for what they actually covered.

The broader decision creates one new focal uncertainty: the currently most consequential unsupported premise whose answer could change the broader control action. The same Supervisor then chooses an existing observation action by asking:

```text
What plausible outcomes would lead me to different actions for this decision,
and can this observation distinguish them?
```

This does not prescribe a test. Depending on the premise, a source read, search, execution result, diff, or public behavior may be discriminating. Symbol presence, task claims, or compilation are used only at the scope they actually distinguish.

Supervision tightens at whole-task closure because the action is broader and harder to reverse: a local false negative delays one repair, while a false global completion ends oversight across all remaining obligations. Tightening means demanding a better match between decision scope and observation adequacy—not enumerating every requirement or always spending more calls.

### 3.4 Root re-evaluation transition

Resolving one focal uncertainty does not authorize whole-task completion. While the current decision anchor is whole-task completion, the anchor remains in place across a bounded sequence of focal investigations:

```text
keep the root decision anchor
→ choose the one currently most decision-relevant unresolved alternative
→ obtain and consume a discriminating observation
→ resolve or reopen that focal uncertainty
→ return to the same root decision anchor
→ re-evaluate current grounds and current control dependencies
```

After each focal resolution, the Supervisor asks whether, under its current task representation and grounds, there is still a **plausible completion-blocking alternative** whose answer would change the control action.

- If one is currently identifiable, it replaces the prior focal uncertainty. The resolved item exits the active frontier rather than joining a concern list.
- If an unfinished decision-critical observation remains relevant, it remains the single current control dependency and completion is not yet supported.
- `allow_complete` is available only when current whole-task grounds are adequate for completion and the Supervisor can identify neither a current decision-relevant unresolved alternative nor an unfinished control dependency.

This is a closed-loop re-evaluation, not exhaustive proof. DCEC-v1 does not enumerate every requirement, retain resolved concerns, build a requirement graph, or claim that no unknown defect can exist. The criterion is bounded by the task representation, current grounds, and currently recognizable alternatives. “One focal uncertainty” limits active control state; it does not imply “one uncertainty resolved is enough for the root decision.”

### 3.5 Unfinished observation

`requested`, `running`, and `interrupted` observations provide no positive result. If the intended observation can still change the current decision, it remains the single control dependency:

- `requested`: selected but not started;
- `running`: execution began but no terminal receipt exists;
- `interrupted`: execution ended without the result needed for the intended distinction;
- `completed`: a terminal receipt exists and may now be interpreted.

An interrupted observation may justify choosing a replacement observation or explicitly retaining uncertainty. It cannot be rewritten as success, failure of the implementation, or “verification underway.” If the decision changes and the observation is no longer relevant, the slot is dropped; no workflow manager or historical queue is created.

### 3.6 Reopen

A resolved concern re-enters the active frontier only when a new relevant conflict, version change plus material dependency, or contradictory observation affects the current decision. Historical salience alone is insufficient.

## 4. Adaptive tightening and relaxation

DCEC-v1 regulates **evidential demand**, not a numeric risk score.

### Tighten when

- decision scope increases, especially to whole-task completion;
- current grounds are narrower than the claim being closed;
- available observations would look the same in states requiring different actions;
- the only decision-critical observation is unfinished;
- a new conflict or relevant version change undermines the current ground.

Tightening means keeping the concern open and selecting an observation with more decision-discriminating outcomes. It does not automatically mean more observations, a fixed test suite, or blocking the Task Agent indefinitely.

### Relax when

- a completed observation distinguishes the relevant alternatives;
- its supported scope matches the present decision scope;
- the result has been consumed into current grounds;
- no current control dependency remains unfinished.

Relaxation means resolving the concern, clearing the focal observation, pruning superseded grounds, and returning to ordinary patrol or permitting the scoped control action. Adequately supported work must leave the frontier. The mechanism fails if it merely converts completion into perpetual `unknown`.

## 5. Production-loop mapping

DCEC-v1 fits the existing persistent Supervisor loop:

```text
normal wake / root handoff
→ inject the same bounded view of monitor/working.md
→ Supervisor identifies the current decision and, if needed, one focal uncertainty
→ Supervisor uses an existing investigation/control tool in the same response loop
→ runtime records deterministic receipt/status metadata
→ Supervisor interprets the completed or unfinished observation
→ Supervisor revises the same working.md by replacement
→ at root scope, return to the unchanged root anchor and re-evaluate
→ observe | investigate | intervene | track recovery | wait | allow completion
```

No per-wake state rewrite is required. The note changes only when future control should change. No hidden call evaluates adequacy, and the runtime does not infer semantic correctness. Existing History and audit retain provenance; the active view retains only what controls the present decision.

At an intervention, the current concern becomes recovering. At post-repair observation, it may resolve only at the observation's supported scope. At a root handoff, the decision anchor changes to whole-task completion and current grounds are re-qualified. Resolving a focal uncertainty returns control to that same root anchor; the Supervisor either replaces it with the next currently recognizable completion-blocking alternative or allows completion only when the whole-task grounds are adequate and no current unresolved alternative or unfinished dependency remains.

## 6. Theory boundary

The control-theoretic borrowing is limited to the problem structure of observability/measurement adequacy, constrained control, and conflicting performance objectives. DCEC-v1 asks whether the selected observation distinguishes states that require different actions under finite resources. It inherits no theorem or guarantee from linear systems, Kalman filtering, LQG, or optimal control.

The KR borrowing follows Davis, Shrobe, and Szolovits, *What Is a Knowledge Representation?*: a representation makes ontological commitments and shapes sanctioned and recommended inference. In DCEC-v1, a bare `resolved` state previously made overly broad closure easy; scope-bound grounds and unfinished-observation status narrow what that state licenses. This does not establish that the DCEC name or the general idea of revisable evidence-aware state is novel.

## 7. Likely degenerations

The design can fail by becoming:

- a prose checklist that enumerates requirements;
- a closure checker applied only at root handoff;
- a selector stage disguised as a “focal uncertainty” form;
- a second memory or evidence matrix inside `working.md`;
- a confidence score expressed with qualitative adjectives;
- a fixed “always run tests” policy;
- a conservative barrier that never relaxes;
- state ceremony whose text changes but whose next tool/control action does not;
- scope laundering, where the Supervisor merely labels local evidence “global.”

Any implementation that requires another LLM call, separate semantic state, automatic adequacy classifier, or multiple active concerns is outside DCEC-v1.

## 8. One minimal falsifiable next evaluation

After DCEC-v1 is frozen and independently audited, the next scientific evaluation is one complete real `fyn-2.2.0-roadmap` DCEC-v1 run. It is not a new domain-neutral synthetic pair, and it does not add an ordinary-control run, repeat, checker, or online gold feedback. The purpose is to test the mechanism against the real R2 failure boundaries under the existing long-running Supervisor architecture.

The evaluation inspects one pre-registered behavioral chain:

```text
local repair observation
→ scope-bound local resolution
→ whole-task decision anchor
→ one focal uncertainty and discriminating observation
→ grounds revision
→ root re-evaluation
→ replace the focal uncertainty or relax to an appropriate control action
```

Support requires all of the following observable behavior, not merely a correct final score:

- a repaired local instance is not silently promoted to universal satisfaction;
- a requested, running, or interrupted decision-critical observation never becomes positive evidence and remains visible while it can change the decision;
- at root closure, the selected observation can distinguish states that require different completion actions, rather than only confirming claim, symbol, inventory, or build proxies;
- resolving one focal uncertainty leads back to root re-evaluation, and another currently recognizable completion-blocking alternative replaces it when one remains;
- completed adequate evidence allows the Supervisor to resolve, prune, and relax rather than permanently block progress;
- state revision changes the subsequent investigation or control action without adding an LLM stage.

The upgrade is directly falsified if it merely writes richer scope/status prose, promotes local evidence to universal closure, loses an interrupted dependency, stops after resolving one root-level uncertainty despite another currently recognizable blocking alternative, repeats non-discriminating checks, or becomes a permanent conservative barrier. A correct final decision without the observation → revision → root re-evaluation → changed-control chain is not a pass.
