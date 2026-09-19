# Decision-question diagnostic: accounting repair and exact-state gate

## Scope

This patch keeps the existing three-way diagnostic unchanged: ordinary
investigation, shared-question plus parent-direct investigation, and the same
question plus isolated C. It does not change prompts, models, memory,
compression, concurrency, the six-call ceiling, or the research stages.

## Small repairs

- `complete_calls` counts high-level provider `complete()` invocations at
  entry, including invocations that later fail. Transport retry attempts and
  successful responses remain separate counters.
- Every branch reports its own `status`, conclusion, calls, budget calls and
  usage. An exception or budget exit cannot overwrite a completed sibling.
- A checkpoint with a missing, non-integer, non-contiguous or post-cutoff
  cursor is rejected before any model call. The visible event file must be
  the exact prefix ending at the declared cursor.

The 13 deterministic tests now cover these cases, including failed provider
accounting and the missing-cursor rejection. The three-case R4 outcomes are
preserved as historical engineering results; they are not rerun or re-ranked
by this patch.

## Exact-state gate for the next three-way comparison

The next comparison must use a live Supervisor boundary, not a reconstructed
post-hoc fixture. At one existing pause or root-handoff boundary, capture in
one immutable checkpoint directory:

1. the provider's complete History immediately before the boundary request;
2. the exact system prompt and dynamic input sent for that request;
3. the current working state and evidence files as visible then;
4. the public-event cutoff cursor and the event-prefix hash;
5. the workspace/version manifest and hashes for every model-readable file;
6. task/run identity and capture timestamp.

The capture must be written by the live runtime at that boundary. A later
`provider_history.json`, final workspace, or researcher-side deletion of
later records is not a faithful replacement. If a complete live snapshot is
not available, the comparison remains blocked and the artifact is labelled
`constructed_offline`; it must not be renamed as an R5 replay.

Once such a checkpoint exists, the same three-way runner can consume it with
the existing material and hash validation. Cases with sufficient evidence may
finish directly; C is optional and is evaluated only for incremental evidence
after the parent has stated a decision-changing unresolved premise.

## Implementation mapping and offline acceptance

- `decision_question_diagnostic.py`: strict per-line cursor validation and
  all-parent branch aggregation.
- `run_decision_question_diagnostic.py`: one shared preflight path for dry-run
  and execution; dry-run materializes temporary views and never loads a
  provider.
- `monitor_agent_core/provider.py`: an optional request-assembly callback
  fires once, after compaction and dynamic context insertion but before
  transport; retries do not create another checkpoint.
- `monitor_agent_core/runtime.py`: the callback is enabled only for a root
  handoff, writes request/system/tools/parameters, the event prefix, private
  state, workspace snapshot and hashes, and writes `complete.json` last.
- `monitor_agent_core/agent.py`: each review resets the one-capture guard and
  associates the provider request with the review id.

The production-path regression set has 20 passing tests. It covers malformed
cursor records, branch isolation, failed-call accounting, no-question without
C creation, and one-time request assembly containing dynamic context. A real
checkpoint is still required before the three-way API comparison; no
constructed empty-History fixture is promoted to that role.
