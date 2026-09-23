# DCEC-vNext design V2: one persistent observation-control slot

Status: design only. `79713f0` targeted acceptance remains FAIL / NO-GO for
pre-dev freeze. This revises the underspecified control affordance in
`DCEC_VNEXT_PERSISTENT_OBSERVATION_DEPENDENCY_DESIGN_20260924.md`; it does not
change that document's scientific attribution or authorize implementation.

## 1. Why the present contract loses a dependency

In the production candidate, `MonitorAgent.__init__` appends
`DCEC_SYSTEM_PROMPT`; `_active_working_context` calls
`dcec_working_context`, which reads `monitor/working.md` and injects only its
first 4000 characters. In `_dispatch`, `file_write` and `file_patch` mutate
that natural-language file before `dcec_state_mutation` is logged. A normal
rewrite can therefore delete the sentence naming an unfinished observation.
`_prepare_continuation` can overwrite the file via `_atomic_private_text`
without the ordinary tool path. `code_run` can also reach the private path.
Finally `_dispatch("allow_complete")` checks that the root proposal is
current, not whether the Supervisor's own unresolved dependency remains.

Thus R2 could tighten once, observe that behavioral verification was
unavailable, rewrite `working.md` around weaker code inspection, and approve.
A stronger sentence in the system prompt would not close these write and
control paths.

## 2. Smallest procedural affordance

Keep `monitor/working.md` as the **only model-owned semantic state**. Reserve
its first line for one machine-readable control slot; all other text remains
unstructured natural language. The slot is an assertion and lifecycle
instruction authored by the same Supervisor, not a runtime judgment:

```text
<!-- DCEC-CONTROL/1 {"op":"retain","id":"obs-7","status":"interrupted","receipts":["tool:R17"]} -->
Current decision: ...
Focal uncertainty: ...
Grounds and limits: ...
```

Canonical JSON, a single first line (for example at most 512 UTF-8 bytes),
strict keys, and bounded opaque IDs make parsing unambiguous. `id` is stable while retained; status is one of
`requested`, `running`, `interrupted`, `unavailable`, `completed`. The last is
**still active** until explicit discharge. The `receipts` array is bounded
(e.g. at most four opaque existing tool/session/public-event IDs); runtime
checks that references are syntactically well formed and, where present in its
archive, exist. It does not infer what the receipt proves. The normal prose
states the observation, decision scope, boundary, and reasoning.

One first-line `none` slot is also required:

```text
<!-- DCEC-CONTROL/1 {"op":"discharge","from":"obs-7","id":null,"status":"none","receipts":["tool:R21"]} -->
```

Its prose must include an explicit model-authored discharge basis. The
validator checks its presence, not its correctness. At initialization with no
dependency, `op:"none"`, `id:null`, `status:"none"` is legal. `create`
starts a new ID; `retain` keeps the ID while status/receipts may change;
`replace` names both `from` and a distinct successor `id`; `discharge` names
`from` and clears `id`. The slot is a current control state, not a ledger: an
accepted transition overwrites the prior line. Historical transitions remain
in the existing audit/progress stream.

This is the smallest useful structure because only the existence and
identity of one model-declared decision-critical observation need mechanical
persistence. Decision anchor, focal uncertainty, grounds, scope, and boundary
adequacy stay natural language. There is no requirement table, second file,
truth score, or semantic classifier. An unchanged slot line is idempotent on
subsequent prose-only edits; the `op` describes the last declared transition,
not an instruction to replay it. A missing `working.md` at initial startup is
treated as implicit `none` only until the first state write. Once an accepted
slot exists, a missing file/line is an integrity failure, never implicit
discharge.

## 3. Transition semantics

| Transition | Model owns | Runtime validates / receipt | Semantic judgment? |
| --- | --- | --- | --- |
| none → create D1 | declares why D1 matters to current decision | new opaque ID; one slot; `dcec_dependency_transition_accepted` | none |
| D1 requested → running | associates actual attempt | same ID; legal status; optional request/session receipt | none |
| D1 running → interrupted | interprets whether attempt remains decision-critical | same ID; tool/process interruption receipt is recorded separately | none |
| D1 interrupted → retain D1 | keeps current measurement obligation | same ID; no silent removal | none |
| D1 interrupted/unavailable → replace D2 | chooses an alternative intended to cover the same distinction | `from=D1`, new `id=D2`, atomic old→new; receipt references checked | runtime does **not** judge equivalence |
| D1 any active status → discharge | explains why D1 is no longer necessary at this decision/scope | `from=D1`, `id=null`, explicit basis present; transition logged | runtime does **not** judge adequacy |
| D1 completed → retain D1 | judges result not yet sufficient or not yet consumed | completed status remains active; no auto-discharge | none |
| D1 completed → discharge | judges completed grounds adequate and re-evaluates anchor | same explicit discharge validation | runtime does **not** judge result |
| active D1 → allow_complete | attempts control without lifecycle closure | reject tool result; log `dcec_completion_guard_rejected`; proposal remains current | none |
| no active dependency → allow_complete | makes whole-task judgment | existing current-handoff check applies | runtime does **not** certify task |

`unavailable` is **model-owned status**, not automatically derived from a
failed command. Runtime can record a missing executable, process exit,
timeout, interrupted session, absent receipt, or transport failure. The
Supervisor decides whether that makes its intended observation unavailable,
whether replacement is appropriate, and whether other completed evidence
discharges the dependency. Requested/running/interrupted/unavailable are not
positive evidence. Completed is a workflow fact/status, not proof of
adequacy. A claimed completion cannot silently clear an active ID.

The model can discharge an ID poorly or fail to create one. This design does
not make semantic success automatic; those remain falsifiable model failures.

## 4. Single validation and write boundary

Add a small deterministic slot parser/transition validator (possibly a
`dcec_control_slot.py` helper; it is **code, not a state file**). Its input is
the prior accepted first line, proposed complete `working.md`, operation
source, and existing receipt IDs. It returns an accepted transition or a
typed refusal. It never inspects prose for domain keywords or grades evidence.

All DCEC mutations of `monitor/working.md` must reach this one validator:

1. `MonitorAgent._dispatch` intercepts `file_write` (replace **and append**)
   and `file_patch` before `MonitorWorkspace.write_text/patch_text` commits.
   It computes the proposed complete text, validates old→new, then performs
   one atomic commit with an old-content hash precondition. A rejected write
   leaves the old file intact and returns an ordinary tool error; no free
   model call is added. Other private files keep the old path.
2. `_prepare_continuation` validates the proposed continuation note with
   exactly the same function before `_atomic_private_text("working.md", note)`.
   On missing/malformed/deleted active slot, continuation is rejected; prior
   `working.md` remains intact and the existing bounded continuation-failure
   behavior applies. The model must not gain an unbounded repair loop.
3. Because `code_run` can write the path outside those APIs, the last accepted
   slot identity/hash is kept as **transient control bookkeeping** and in the
   existing deterministic transition audit, not a second semantic state.
   Before every normal provider request and before `allow_complete`, compare
   the on-disk first line with the last accepted slot. An out-of-band change
   is logged as `dcec_dependency_integrity_failure`, and the Supervisor must
   see a failure rather than silently consuming or approving a dropped slot.
   A restarted process reconstructs the accepted identity from the existing
   audit receipt, compares it with the file, and fails closed on mismatch.
   This does not claim to OS-sandbox `code_run`; it closes the decision path
   against an undetected rewrite. Legitimate model changes use the validated
   ordinary tools.

Mutation validation and the `allow_complete` guard use the same accepted
slot, so a just-written discharge can be followed by another normal tool
call in the **same review**. No independent maintenance stage or fixed extra
LLM call is necessary. The model may still need an ordinary next request to
consume a tool receipt; that cost remains in the existing review loop.

## 5. Exact production mapping

- `agent.py` — in `MonitorAgent._dispatch`, route only DCEC writes to
  `monitor/working.md` through the pre-commit validator. In
  `_prepare_continuation`, validate before `_atomic_private_text` replaces the
  same file. At `_dispatch("allow_complete")`, after the existing current
  proposal check and before returning a `MonitorAction`, reject an active slot
  or integrity mismatch. Extend the DCEC/continuation contract only enough
  to explain the slot and replace/discharge/retain semantics. Do not change
  ordinary tool schemas.
- `working_context.py` — parse the first-line slot and render it **in full**
  before natural-language prose. The existing 4000-character default becomes
  a total bounded source view: reserve the slot's small fixed maximum, then
  truncate only prose to the remainder. If the slot is malformed or missing,
  show an explicit control-state error, not an invented `none`. Keep stale/
  not-verified-truth warnings for model-owned prose. Telemetry separately
  records slot/prose chars and hashes.
- `provider.py` / existing pre-send callback — invoke the integrity check
  before normal request assembly/send so out-of-band deletion cannot be
  hidden by the next bounded view. Do not trigger a new model request.
- `runtime.py` — existing tool/session/public-event receipts remain the
  deterministic observation source. No new semantic runtime controller or
  automatic dependency creation is planned. If required, only pass stable
  receipt identity/status through the existing wake context.
- Existing progress/audit — add only deterministic events
  `dcec_dependency_transition_accepted`,
  `dcec_dependency_transition_rejected`,
  `dcec_dependency_integrity_failure`, and
  `dcec_completion_guard_rejected`, with old/new IDs, status, operation,
  receipt IDs, hashes, and reason codes; never log a semantic PASS label.

With DCEC off, no slot parsing, pre-commit validation, pre-send integrity
check, or completion guard runs. The ordinary prompt, tools, workspace
mutation, continuation, and approval semantics remain unchanged.

## 6. Closure, relaxation, and scope

An active slot gates `allow_complete` because the Supervisor itself says the
observation is still decision-critical. The runtime is not judging whether
it should have been declared critical. If an attempted measurement cannot
complete, the model either replaces it, discharges it on other completed
grounds, or retains it. After adequate evidence, the model explicitly
discharges, prunes superseded prose grounds, returns to the same root anchor
for re-evaluation, and can approve or resume patrol. No fixed test type or
global end-to-end requirement is imposed, so a locally adequate observation
can resolve a local decision without permanent conservatism.

This covers both known trajectories without embedding their domains: an
interrupted global measurement and an unavailable behavioral measurement
cannot silently turn into completed positive grounds or disappear under a
more convenient narrower check. It does **not** require the model to choose
a particular implementation path or hidden verifier assertion.

## 7. Offline acceptance to implement later

Tests must exercise production dispatch/continuation/request/approval paths:

1. `file_write` replace or append cannot silently delete active D1;
2. `file_patch` cannot silently delete D1;
3. continuation cannot silently delete D1 and preserves prior file on refusal;
4. replace commits D1→D2 atomically, never an intermediate `none`;
5. explicit discharge clears D1 and records a transition;
6. completed receipt/status does not automatically discharge D1;
7. active D1 rejects `allow_complete` with current proposal preserved;
8. accepted discharge restores ordinary `allow_complete` behavior;
9. slot remains fully visible with prose longer than 4000 chars;
10. malformed transition is rejected while a semantically dubious but
    syntactically valid discharge is **not** labeled adequate by runtime;
11. direct `code_run`/out-of-band rewrite is detected before request and
    approval, including after process restart;
12. DCEC-off requests and control behavior remain unchanged;
13. no new Agent, state file, tool schema, or model call is introduced.

These are plumbing tests, not evidence that the Supervisor will make correct
semantic decisions.

## 8. Falsification and research boundary

Mechanism support requires a trajectory with a model-declared dependency,
an unfinished/unavailable receipt, preservation across later state revisions,
and an explicit replace/discharge/retain transition that changes investigation
or control. Adequate completed evidence must permit relaxation. The candidate
fails if it does not create the needed dependency, discharges it on weaker
grounds, fails to change measurement/closure behavior, or remains blocked
after adequate evidence. A run with no such decision boundary is
low-discrimination. Official PASS/FAIL alone never establishes the chain.

The regime remains: design audit → implementation/code audit → one final
targeted acceptance → freeze or stop Sphinx-driven revision. No dev set or
online run starts from this design commit. Fyne and Sphinx remain development
cases, not held-out paper results.
