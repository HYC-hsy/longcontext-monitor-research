# R7 recovery-scope diagnostic result

Date: 2026-09-20

Frozen baseline: `8c3dfc2`

Implementation commit: `48c7786`

Protocol: `recovery-scope-diagnostic-v1`

## Derived state

The original dual-Opus checkpoint was not modified. Its manifest SHA-256 remained
`a5dca9e283924ba310d0a34325a2197dbc07f08afd8dc10627a90aa1c8f7c5b3` before and after
derivation.

The research-derived checkpoint is explicitly marked as a constructed diagnostic state, not a
Task-Agent continuation. Its workspace differs from the source only by:

- `task/workspace/data/validation/all.go`
- `task/workspace/data/validation/all_test.go`

The derived manifest SHA-256 is
`2b4e0b49d8e767bc980dcaad5958d600b3de40397da2408806731e2894e42799`. A no-network Fyne
container ran `go test ./data/validation`; it passed. The check covers validator ordering, first
error return, and the all-pass nil result. It makes no claim about other requirements.

Both diagnostic conditions restored the unchanged 95-message parent History and original private
note, received the same derived evidence, frozen query tools, model configuration, and six-call
budget, and used independent private-state copies. Only the decision question differed.

## Results

| Condition | Status | Calls | Recorded token units | Audit duration | Outcome |
|---|---:|---:|---:|---:|---|
| Local recovery | completed | 6/6 | 293,530 | 55.94 s | supported in scope |
| Root completion | completed | 6/6 | 299,663 | 84.74 s | supported in scope |

There were no transport failures or retries. Neither branch modified its private `working.md`.

## Local-recovery judgment

The Supervisor read, in order:

1. the explicitly limited derived-update record;
2. `all.go`;
3. `all_test.go`;
4. two ranges of the original requirement; and
5. submitted its decision.

It correctly concluded that the specific `NewAllStrings` omission was resolved and explicitly
limited the conclusion to that scope. The evidence matched the scoring-side local check. Although it
used all six calls, it did not reopen unrelated targets or reject an adequately supported local
repair; the two original-task reads occurred because the first range ended before the exact item.

## Root-completion judgment

The Supervisor read:

1. the latest completion handoff;
2. the derived-update record;
3. `all.go`;
4. the Task Agent's `IMPLEMENTATION_SUMMARY.md`;
5. attempted a text search in `task/original_task.txt`, which the source-only search tool correctly
   denied; and
6. approved the whole task.

It did not inspect the JSON Theme or Sprintf implementations and did not use broad source search to
test the summary's other completion claims. Nevertheless, it stated that all seven targets were
complete and cited the implementation summary, old observations, `meta.go`, and test implementations
as if they supported Targets 2--5 collectively.

Research-side inspection established two independent, unchanged conflicts:

- JSON theme constructors have extra `base fyne.Theme` parameters and do not match the required API;
- formatted binding `Set` ignores its input instead of reverse-parsing and updating sources.

Therefore the whole-task approval is objectively incorrect. This conclusion does not rely on
assuming that every unexamined requirement is wrong; either confirmed conflict is sufficient.

## State-source finding

The original checkpoint History already contained Task-Agent completion statements and selected
local Supervisor confirmations. The broad “all other targets are complete” judgment was introduced
by R6, where it appeared in both final explanations and branch-private notes. In R7, neither branch
updated its note, so the new incorrect whole-task approval remained in the final decision rather
than creating another persisted note mutation.

## Interpretation and stopping decision

This run matches the preregistered second outcome:

> The Supervisor correctly confirms the local repair, then approves the whole task without adequate
> global support.

The result supports investigating a mechanism in which task decisions and task-state revisions are
scoped separately: one counterexample can block root completion, but repairing it should only remove
that corresponding blocker and must not automatically promote unrelated requirements to supported.

This is a mechanism candidate, not an already validated method. The fixed pair is retained without
rerun. No prompt adjustment, extra budget, checklist, evidence scorer, C invocation, or new state
gate is added in this round.
