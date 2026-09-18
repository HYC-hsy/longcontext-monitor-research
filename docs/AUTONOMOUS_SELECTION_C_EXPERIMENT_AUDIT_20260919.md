# Autonomous selection + independent C: r3 audit (2026-09-19)

## Scope

This run evaluates the second-step hypothesis: a parent Supervisor chooses one
decision-relevant local question, an isolated C verifier investigates that
question, and the parent makes the final scoped decision. It is not a full
long-task result and does not compare D. The four fixed checkpoints were run
with the same task, event prefix, workspace material and six logical-call
budget. The build-only checkpoint was restricted to the build observation for
both direct C and autonomous C, correcting the invalid scope in r2.

Run directory: `autonomous_selection_c_20260919_r3b`.

## Results

| checkpoint | direct C | autonomous selection + C |
|---|---|---|
| app metadata defaults | supported (eligible, correct) | incomplete during selection after 2 calls |
| JSON theme API | contradicted (eligible, correct) | incomplete during selection after 2 calls |
| build-only behavior | unresolved (eligible, correct) | completed: selected metadata question, C returned unresolved, parent returned unresolved (eligible, correct) |
| validator after correction | supported (eligible, correct) | incomplete during selection after 2 calls |

The three incomplete autonomous cases are excluded from accuracy. They are not
correct UNKNOWN answers: no local question was selected, no C verifier was
started, and no final decision was made. The one completed autonomous case used
all six calls and preserved the correct evidence boundary: a successful build
did not support runtime behavior.

## What this establishes

1. The end-to-end wiring works when the parent selects a question: selection,
   isolated C, structured child result, and parent finalization are connected.
2. Under the frozen six-call budget, the parent often spends both selection
   calls rereading the long original task and does not reach
   `select_local_question`. This is a real selection/indirection bottleneck,
   not evidence that C cannot answer a local question.
3. The single completed case is insufficient to claim autonomous selection is
   useful. Direct C has four eligible results; autonomous C has one. No method
   win or loss should be reported from this panel.
4. The result does not justify increasing the budget or adding D. Before a new
   comparison, the next experiment must isolate whether the bottleneck is the
   parent’s task-reading/selection phase or the allocation of the shared budget,
   while keeping C and the evidence boundary fixed.

## Integrity checks

- `result.json` distinguishes incomplete/transport/protocol failures from
  scored verdicts; incomplete runs have `correct: null` and
  `score_eligible: false`.
- Per-case material manifests and hashes were checked before the run.
- Parent and C received the same allowed paths for each checkpoint; the
  build-only override contains only the original task and build observation.
- Transport JSONL and redacted transport configuration are retained per group.
- r2 remains an engineering diagnostic and is not pooled with r3b.

## Decision

Keep direct C as the working baseline. Treat autonomous selection as an
unresolved candidate requiring a targeted selection-budget diagnosis; do not
claim a mechanism improvement or proceed to a larger panel yet.
