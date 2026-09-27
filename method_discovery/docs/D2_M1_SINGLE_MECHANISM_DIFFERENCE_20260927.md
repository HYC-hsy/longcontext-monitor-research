# D2 / M1 single mechanism-difference note

Status: design and source audit only. No implementation, model call, test, or
new experiment is authorized.

## Anchor

M1 is DCEC-v1 at
`746a695adac4325d6440941d384d543d1364fef9`. D1-R1 remains closed as invalid
for primary causal comparison / low discrimination; its raw records are not
changed.

## What M1 already provides

The frozen production path already has one persistent Supervisor, one bounded
model-owned `monitor/working.md`, ordinary evidence tools, a normal dispatch
path, deterministic progress/tool receipts, and the next review request built
from persistent history plus refreshed working context. In the M1 source these
connections are visible at:

* `MonitorAgent._active_working_context()` and
  `dcec_working_context()` for the current bounded state;
* `MonitorAgent._dispatch()` for ordinary tool execution and deterministic
  result/audit recording;
* `MonitorAgent.review()` / `run_review(... before_model=...)` for the next
  normal request and refreshed context.

This is already an action → receipt/history → next-reasoning loop. The current
source does not prove that every semantic decision premise is optimally linked
to every observation, but it does show that “direct association” is not absent
as a basic plumbing capability.

## D2 diagnostic boundary (not an approved new mechanism)

No new mechanism difference is approved in this note. The only diagnostic
contrast under consideration is controlled availability of one complete
preferred measurement event. The Supervisor, model, tools, semantic state,
history, request construction, and budget remain M1. When the preferred event
is unavailable, the Supervisor may select an ordinary replacement observation;
the runtime does not create a dependency, classify adequacy, or attach a new
semantic label.

The contrast is therefore:

`M1 + preferred measurement available`

versus:

`M1 + the same preferred measurement event deterministically unavailable,
with ordinary tools still available for replacement`.

This is a measurement-availability diagnostic, not a new “decision-context and
receipt-link” module. If source/request inspection shows M1 already exposes the
same relevant context and feedback in both cases, there is no substantive
mechanism difference to implement.

## Observed facts, inference, and open hypothesis

Observed facts: M1 stores/revises `working.md`; tools execute through
`_dispatch`; deterministic tool outcomes are recorded; normal subsequent
requests include persistent history and the bounded working view.

Inference: these afford a model-level opportunity to connect a decision premise
to an action and its result, but they do not establish that the Supervisor will
choose a decision-discriminating measurement.

Open hypothesis: under an unavailable preferred event, the same Supervisor may
either replace it with an adequate ordinary observation, substitute a weaker
observation, or leave the decision unresolved. That is the D2 question; it is
not evidence that M1 lacks a missing runtime layer.

## Semantic/runtime boundary

The Supervisor owns premise selection, measurement design, interpretation,
scope, and release. Runtime may record tool identity, arguments, receipt,
source/path/range, output, status, interruption, and version/hash facts. It
must not infer adequacy, truth, completion, or decision-criticality and must
not automatically create a semantic dependency for each tool call.

## FBR evidence relation

The public FBR package is
`method_discovery/evidence/fbr_cors_public_20260927/`. It supports a bounded
local CORS distinction and preserves the seven-target original task context;
it does not license whole-task completion. One historical R1 branch repaired
the CORS phase after an indexed public conflict, while the failure-analysis
document cited by earlier D2 drafts is missing from this checkout. No hidden
verifier or fabricated receipt is used.

## What would support or reject the candidate

Support requires the unavailable-event condition to cause a reproducible change
in the first useful observation or subsequent control, with the replacement
still testing the public decision-relevant distinction. A mere extra natural-
language reminder is not a mechanism effect.

Reject if M1 already exposes equivalent information/action/feedback and the
paired measurement intervention produces no substantive control distinction;
also reject if any apparent gain depends on research labels, hidden evaluation,
fixed domain commands, or an added schema/agent/checker.

No implementation or execution follows from this note. Main-thread audit is
required before any future materialization.
