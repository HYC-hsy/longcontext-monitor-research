# DCEC pre-dev-set mechanism design: observation-boundary adequacy

Date: 2026-09-23

Status: design only; no implementation or new run
Frozen basis: DCEC-v1 `746a695adac4325d6440941d384d543d1364fef9`; Fyne v1 real run and Sphinx R2 replacement `8d88dce8ebbc73b1b2ce5dc75a279904ef797b9b`

## 1. Evidence and attribution boundary

The Fyne v1 run provides positive, targeted evidence for decision-conditioned evidential transition control: the Supervisor tracked local recovery, returned to whole-task assessment after a blocker was repaired, investigated additional alternatives, and the native verifier passed 7/7. One run does not establish a causal effect or cross-task reliability. Its trajectory also retained some broad early completion statements, so the final score does not certify every intermediate ground.

Sphinx R2 is an equally valid scientific record. The first completion proposal lacked an executed check; the Supervisor intervened and obtained one. The Task Agent then ran five direct `PythonDomain.find_obj()` checks, and the Supervisor used those completed results to allow completion. The official verifier applied the patch but failed `tests/test_domain_py.py::test_info_field_list` (PASS_TO_PASS 32/32). There was no transport failure. The positive local intervention and state revision therefore coexist with an unsupported whole-issue transition.

Attribution has three distinct parts:

| Layer | What the record supports | Limit |
| --- | --- | --- |
| Task specification | The original issue explicitly contrasts implicit `:type:` / `:rtype:` references with explicit xref roles, describes `currentmodule` behavior, and asks for correct targets without ambiguity warnings. | It does not dictate one internal implementation. |
| Native verifier | Its failing test checks, among other things, `py:module` on a generated `pending_xref`. | That internal attribute is a white-box commitment of this benchmark. The Supervisor was not required to anticipate this hidden assertion, and another implementation might satisfy the stated behavior. |
| Supervisor control | The accepted standalone checks supplied constructed context directly to `find_obj()`. They did not observe whether implicit info-field references acquire and propagate that context before lookup, nor the resulting target and warning behavior. | The failure is an inadequate observation boundary for the public issue, independently of the hidden assertion's exact form. |

The public issue and the frozen observation are archived in `r2_replacement/monitor/task_evidence/original_task.txt`, `monitor/audit/dialogue.jsonl`, and `monitor/working.md`; the native result is in `verifier/report.json`. The [R2 factual summary](DCEC_V1_CLAW_SWE_GENERALIZATION_R2_FACT_SUMMARY_20260922.md) identifies the same archive. Hidden verifier details are research-side evaluation, never prospective Supervisor input.

## 2. One control invariant

**Decision-relevant observation-boundary adequacy** is an added qualification of DCEC-v1's existing evidential transition control, not a new component:

> Before a completed observation licenses `resolved`, release from recovery, or `allow_complete`, the same Supervisor must relate the current decision-relevant behavioral distinction to the boundary actually measured. The observation must cover enough of the path that produces, propagates, or exposes that distinction for its possible results to separate states requiring different control actions. Otherwise it remains qualified partial evidence and cannot alone license the broader transition.

The three existing questions are one test of adequacy: **what decision and scope?** (scope), **which alternative outcomes change the action?** (discrimination), and **does this observation traverse or otherwise establish the boundary that makes those outcomes differ?** (placement). A check can be completed and accurate at its own level yet fail the third question. The Supervisor judges this in its normal reasoning and tool loop; the runtime does not classify semantic adequacy.

This invariant applies during local recovery as well as root completion. It does not demand an end-to-end test for every decision. A direct source read, a targeted execution, a diff, or a task-visible result may establish the relevant path if it actually bears on the distinction. The minimum useful boundary depends on the current decision.

## 3. Minimal semantics in the existing state

### Behavioral distinction and measurement boundary

For the one current decision anchor, the single focal uncertainty identifies two plausible task states that would lead to different supervisory actions. An observation boundary is the portion of task behavior or implementation path the selected read, test, trace, or public event actually exposes. The practical counterfactual is:

> Could the task still have the decision-blocking behavior while this observation returns the same favorable result because the distinguishing path was bypassed?

If yes, that observation is not sufficient on its own for the broader transition. This is a bounded, decision-relative question, not a causal graph, exhaustive list of paths, or proof of absence of all defects. An observation need not be literally end-to-end if source or execution evidence establishes the missing propagation and its relevant outcome.

In Sphinx, the distinction is whether an implicit info-field xref under `currentmodule` retains context and resolves to the intended target without a false ambiguity warning. Direct `find_obj()` calls with manually supplied context test resolver behavior under those inputs. They leave open whether `:type:` / `:rtype:` construction supplies the context and what the implicit path produces. Working grounds may retain the direct check as local support, but must state that limit. A task-level observation would need to cover the implicit path or establish its context propagation and externally specified behavior through other direct evidence; this design does not prescribe a particular test or patch.

### Transition and revision

When an observation finishes, the Supervisor revises the current grounds in `monitor/working.md` with what was actually observed, its source/version and scope, the measured boundary, and the current decision it does **not** yet support. This extends the existing grounds limitation in prose; it creates no new field, ledger, or state file. Superseded grounds are replaced rather than stacked.

`open/recovering → resolved` remains scope-bound and requires a completed, decision-discriminating observation. The added condition is that the measured boundary is adequate for the distinction at the scope being closed. If it is not, the local finding can resolve a narrower uncertainty while the same decision anchor retains or replaces its single focal uncertainty. `requested`, `running`, and `interrupted` still provide no positive result. A completed but boundary-inadequate observation is a different case: it provides genuine partial evidence, not permission for a broader closure.

At whole-task handoff, local grounds are re-qualified against the root decision. After one focal uncertainty resolves, the Supervisor returns to the **same** root anchor and asks whether current grounds still expose a plausible completion-blocking alternative. Boundary adequacy is checked again before `allow_complete`; resolving a lower-level component cannot silently become support for the externally specified task behavior.

### Tighten and relax

Tightening changes the **placement or abstraction level** of the next measurement when the current one bypasses the decision-relevant distinction. It may mean inspecting source propagation, exercising a real input path, observing integration behavior, comparing a diff to the requirement, or another existing tool action. It does not mechanically add tests or calls. The focal uncertainty should say which different outcomes would change intervention, continued investigation, release, or completion.

Relaxation is required when completed grounds at the current decision scope do cover that distinction and no relevant unfinished dependency or currently recognizable blocking alternative remains. A local decision may therefore close after an adequate local observation. Inability to run one preferred check permits another suitable observation or an explicit limit; it is not a permanent veto on all completion. The Supervisor remains responsible for choosing under finite calls, time, and task-blocking cost.

## 4. Why this is one cross-task mechanism

Fyne v0's final symbol/grep checks and `go build ./...` were real completed observations. They did not separate an intended minimal `desktop.App` interface from an over-constrained interface that still contained the named methods. A local `testApp.Metadata()` repair likewise did not cover the requirement quantified over all concrete implementations. The measurement point or scope missed the distinction that could change completion control.

Sphinx R2's direct resolver checks were also real completed observations. They separated some `find_obj()` inputs, but bypassed the implicit-xref construction and context propagation where the reported explicit-versus-implicit difference arose. The same transition error followed: evidence valid for the measured component was promoted to the broader task behavior.

The invariant therefore concerns the relation between **decision, behavioral distinction, and measured boundary**. It names neither Fyne nor Sphinx APIs in the future Supervisor contract and requires no fixed reproduction, integration suite, or extra model stage. Fyne v1's successful corrective loops remain evidence that the existing DCEC architecture can act on adequately placed observations; Sphinx shows a remaining case where the placement judgment failed.

## 5. Architecture and theory limits

The architecture remains one persistent Supervisor, one bounded `monitor/working.md`, one current decision anchor, one focal uncertainty, bounded current grounds, at most one decision-critical observation dependency, grounds replacement, scope-bound resolution, root re-evaluation, and adaptive tightening/relaxation. Existing History, receipts, tools, continuation, and normal model calls remain the operating substrate. No per-wake rewrite is required. This design adds no checker, selector, second memory, requirement table, causal-graph store, numeric confidence, semantic runtime classifier, or fixed test policy.

The control-theoretic mapping is limited to a question about measurement schemes: whether the placement and outcomes of an observation reveal the task-state distinction needed for a control action under finite resources. More measurements at the same bypassed boundary need not help. This is a design analogy, not an application of linear observability, Kalman, LQG, or optimal-control theorems. No independent textual claim about *Engineering Cybernetics (Revised Edition)* is made here; its primary-text verification remains with the research main thread.

Davis, Shrobe, and Szolovits describe a knowledge representation as making ontological commitments and shaping sanctioned and recommended inferences in [*What Is a Knowledge Representation?*](https://groups.csail.mit.edu/medg/ftp/psz/k-rep.html), especially Roles II and III. In this project, a bare ground saying “internal component verified” makes “externally specified behavior satisfied” too easy to infer. Retaining the measured boundary and its limit in the *existing* grounds narrows what a `resolved` state licenses and directs the next investigation toward the missing distinction. This borrows their account of representational consequences; it does not import a formal KR system, prove an inference sound, or establish DCEC's novelty.

## 6. Falsifiability and next evaluation sequence

This design fails at the mechanism level if the Supervisor again accepts an internally successful check as whole-issue support while the public task's distinguishing path remains unmeasured, or if it substitutes endless caution for a decision despite adequate completed evidence. A more elaborate working note without a changed tool choice or control action is not support.

After independent design audit: implement only this candidate pre-dev-set contract in the existing v1 path; run offline contract/regression tests and independent code audit; then run **one** Sphinx targeted acceptance with the R2 task, image, dataset, native verifier, budgets, Task Agent `claude-opus-4-6`, and Supervisor `claude-opus-4-8`. The sole scientific change is the DCEC candidate. The earlier R2 record remains frozen; stochastic run variation limits causal attribution from one new record.

Pre-registered interpretation of that acceptance:

| Outcome | Interpretation |
| --- | --- |
| Root anchor is established; direct `find_obj()` evidence stays internal/local; the Supervisor identifies the implicit-xref distinction, chooses an observation that covers its path, revises grounds/control, relaxes when warranted, and the official verifier passes. | Strong targeted support for the mechanism chain and task outcome. |
| It rejects the narrow evidence and investigates the relevant implicit path, but the Task Agent still fails to repair the task and the verifier fails. | Mechanism behavior improved; task outcome failed. Preserve both facts. |
| The Task Agent repairs the issue before the Supervisor has occasion to use the new transition rule, and the verifier passes. | Low-discrimination run for the Supervisor mechanism. |
| Internal checks are again promoted to whole-issue support and completion is allowed without boundary adequacy, or adequate evidence can never release the concern. | Candidate fails this targeted mechanism test. |

The official verifier score is not substituted for process evidence, and its `py:module` assertion is not made a prospective requirement for the Supervisor. No online gold, hidden-test content, or research-side defect location enters model input.

Only after design audit, code audit, and targeted acceptance demonstrate an actual improvement at the original failure boundary may the candidate become the frozen pre-dev-set method. Fyne and Sphinx then remain discovery/development cases. A stratified dev set is to be preregistered separately. Once entered, the method stays frozen for the entire dev set: aggregate failures first; permit at most a later unified revision only when multiple cases support the same recurring control gap. After freeze criteria, proceed to held-out validation and final paper test; final-test results do not feed back into mechanism changes. No dev-set split is chosen in this document.
