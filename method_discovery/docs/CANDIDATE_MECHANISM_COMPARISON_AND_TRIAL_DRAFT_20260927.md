# Candidate mechanism comparison and trial draft

Status: design only. M1/DCEC-v1 at `746a695adac4325d6440941d384d543d1364fef9`
remains the provisional anchor. No candidate is implemented, combined, frozen,
or executed here.

## Common audit baseline

M1 already provides one persistent Supervisor, bounded model-owned
`monitor/working.md`, ordinary evidence tools, deterministic tool results and
history, and refreshed context in the next normal request. In the current
source this is the path through `_active_working_context()` /
`dcec_working_context()`, `_dispatch()`, and `review()` / `run_review()`.

The `code_run` contract already exposes Python (and Bash on Unix), session IDs,
incremental reads, cancellation, wait limits, timeout, exit status and archived
output. `AnalysisSessions` runs in its configured monitor working directory.
This is a static capability check, not proof that every real-task container or
path mapping is faithful. E must not claim a mechanism gain for fixing a
platform or contract defect shared by all branches.

Research labels, expected outcomes, candidate names and scoring are never
model-visible. All candidates use the same M1 model/profile, tools, semantic
contract, history, task evidence and budget unless a future manifest states one
single treatment difference.

## R — conditional grounds

**Causal hypothesis.** Broad `verified`/`resolved` prose can license an
inference beyond the observation's scope. Replacing it with a concise statement
of what an observation supports, under which conditions, and which premise the
current decision still depends on may reduce unsupported closure.

**Single major change relative to M1.** A controlled change to the natural-
language grounds guidance/state wording in the existing `working.md` loop; no
new file, field, lifecycle, tool or model stage.

**Production locations to inspect if ever authorized.** The existing DCEC
system/active-view guidance and the Supervisor's normal working-state update
path. The next request remains the existing `review()` path; runtime records
facts only and does not classify adequacy.

**Illustrative difference.** Before: “Target verified.” After: “Observed X in
source Y at version V; supports local condition Z; does not establish W; the
current decision still depends on premise Q.” The wording is an example of
qualification, not a new schema.

**Overlap and reuse.** R overlaps the old boundary-adequacy wording and the
M1 grounds contract. If the audit finds only paraphrase, R must merge into M1
or be rejected; it must not create a new version by vocabulary alone.

**Expected behavior/cost.** Better scope qualification and fewer unsupported
local-to-root promotions, at possible prose/context cost. A result that merely
changes wording without changing observation or control is not mechanism
evidence.

**Falsification.** Repeated unsupported closure with the same measured scope,
or no difference from M1 after equal evidence and budget, weakens the claim.
Correct control under both conditions is compatible with M1 already being
adequate.

## P — bounded observation-plan comparison

**Causal hypothesis.** When several executable observations are available, a
single Supervisor may improve finite-budget control by briefly comparing their
possible decision consequences and costs before directly choosing one.

**Single major change relative to M1.** Add one bounded planning operation in
the same Supervisor turn, represented in ordinary reasoning rather than a
selector tool/agent or extra model stage. It must be optional and disappear
when one observation is already clearly sufficient.

**Production locations to inspect if ever authorized.** The normal prompt and
tool loop around `run_review()` and `_dispatch()`, with no new runtime semantic
state. The action still goes through ordinary `file_read`, `file_patch`,
`code_run`, `wait`, `intervene`, or `allow_complete`.

**Illustrative difference.** M1 asks which outcome would change the action and
then acts. P adds a short comparison such as “A can distinguish states S1/S2
but costs a run; B is cheaper but cannot distinguish them; choose A,” followed
by the same ordinary tool call. This is a proposed reasoning control, not a
fixed checklist.

**Overlap and reuse.** P overlaps R11/R12 selector attempts and M1's existing
decision-discrimination question. It is admissible only if it does not recreate
their protocol friction, selector semantics, extra calls, or `file_list` used as
a semantic test.

**Expected behavior/cost.** Fewer weak first observations under comparable
budget, at a possible planning-token/latency cost. It must still relax after
sufficient evidence and must not overblock correct controls.

**Falsification.** No improvement in first useful observation, or a cost
increase that consumes the investigation budget, rejects the added operation.
Repeated protocol/format failures or fixed extra calls are a design failure,
not evidence for P.

## E — faithful real-task observation execution

**Causal hypothesis.** Some apparent observation/planning failures may instead
be caused by an analysis tool that cannot execute in the real task context,
cannot preserve versions/paths, or returns a platform-distorted result.

**Single major change relative to M1.** None is approved yet. First audit
whether existing `AnalysisSessions` plus the task adapter already provide the
required working directory, interpreter/shell, session continuation,
timeout/cancel, isolation, source version and output fidelity. Only a verified
missing capability could motivate a narrow common execution repair.

**Production locations to inspect if ever authorized.**
`monitor_agent_core/process_runner.py`, `agent.py`'s `code_run` dispatch, and
the task adapter/container path. Runtime would record command type, cwd/object
version, session, exit/timeout/cancel, output and hashes. It would not decide
semantic adequacy or embed task tests.

**Illustrative difference.** Current: a `code_run` receipt reports a session,
status, output and exit facts. Possible E repair only if missing: the same
receipt comes from the frozen task workspace with a documented path mapping and
the same semantics for both branches. This is substrate validation, not a
candidate benefit.

**Overlap and reuse.** E is a common infrastructure precondition for R/P and
must not be packaged as a new mechanism. Existing code already supplies many
requested semantics, so a duplicate runner or wrapper is presumptively
rejected.

**Expected behavior/cost.** Interpretable observations and fewer tool/platform
errors, not improved epistemic judgment. If current support is equivalent, E is
closed with no implementation.

**Falsification.** If the existing path is faithful and failures persist, E is
not the explanation. If a proposed repair changes only infrastructure and all
branches benefit equally, it cannot support E as a mechanism.

## Static versus experimental claims

Static review can identify duplicate wording, existing M1 capabilities,
unisolated combinations, unavailable source material, and tool-contract gaps.
It cannot establish causal improvement. Experimental evidence must separately
record observation choice, actual result, grounds revision, control action,
premature approval, unnecessary blocking, bounded unresolved outcomes, true
provider/tool cost, and task-blocking/wait latency. Native score, tool use, or a
complete-looking `working.md` is never sufficient alone.

## Same-panel comparison proposal (not frozen)

Use one small common panel with locally resolvable evidence:

1. local evidence insufficient but a direct source observation can settle the
   local premise;
2. preferred observation unavailable but an ordinary replacement is possible;
3. sufficient evidence on a correct control where continued investigation is
   unnecessary;
4. a local repair followed by return to whole-task judgment.

Compare M1 with each surviving single branch R or P independently. E is a
shared readiness gate, not a third mechanism arm unless static audit finds a
real missing capability. A conservative proposal is four cases × two repeats
per arm, with the same Supervisor/model profile and a per-record budget no
higher than the frozen M1 budget; exact calls and wall limits remain for a
future manifest. Do not reuse D1 records, rename D2 into execution, use held-
out tasks, or use hidden verifier details.

The panel stops without rerun after the fixed records. A systemic
infrastructure failure is archived and adjudicated; valid model mistakes,
unresolved decisions, wrong releases, and unnecessary blocks are retained as
scientific outcomes. No candidate is combined with another before independent
comparison.

## Current decision

R and P remain hypotheses requiring a static non-duplication audit; E is first
a substrate-fidelity question and may be closed if M1 already supports it.
No implementation, request materialization, authorization, model call or
experiment is authorized by this draft.
