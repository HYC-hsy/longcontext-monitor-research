# Controlled Transition Experiment Harness v0

Offline research orchestration for a verified checkpoint, one explicit content
transition and the **existing frozen WTV sampler**. This module does not run a
Supervisor, Task Agent, verifier or provider. It does not restore E_t or resume
a conversation. An operator may supply a reference to a separately prepared
Supervisor continuation environment; this version archives the reference but
does not use it.

## Interface and ordering

`run_offline_experiment(checkpoint_dir=..., transition_source=...,
transition_id=..., expected_source_sha256=..., expected_checkpoint_id=...,
experiment_id=..., output_root=..., supervisor_session_ref=...)`

1. Validate checkpoint and save its binding/workspace identity reference.
2. Invoke the existing fixture on an independent X_t copy. Its new optional
   `before_apply` observer receives that verified copy *before* the first
   mutation. With no observer, the fixture behaves as before.
3. Take a WTV baseline on that copied workspace, then let the fixture apply
   the preregistered content bundle. Sampling only after the transition would
   lose the very delta being measured.
4. Sample the same workspace with the same WTV sampler after application.
   Store both views and raw audit events, including sample completeness and
   `added`/`modified`/`deleted` paths. Controlled file edits do not advance
   the Task public cursor; equal before/after cursors are reported explicitly.
5. Archive references and status. A failed fixture leaves its own failure
   artifact and the harness reports failure; if a baseline exists, a later
   sample of a partial workspace is labeled `after_failure`, never success.

The WTV implementation is loaded directly from this frozen worktree's
`GenericAgent-main/monitor_agent_core/runtime.py`, without starting its
runtime process. Its source-file SHA-256 is included in the result. The WTV
view is **archived only** and is not inserted into model input. A future live
continuation requires separate, explicitly authorized state restoration and
session wiring; `supervisor_session_ref` alone does not provide that.

## Artifact

```text
experiment-id/
  metadata.json                  # complete/failed; continuation = not_run
  checkpoint_ref.json            # binding and X_t identities
  supervisor_session_ref.json    # operator reference or unavailable
  wtv_before.json                # same-workspace baseline, if reached
  wtv_result.json                # after sample, or labeled after_failure
  transition_ref.json            # fixture artifact identity, if reached
  transitions/transition-id/     # unmodified fixture output layout
```

`synthetic_experiments.json` defines three offline vectors: one endpoint-path
modification, one validation-path modification and one empty transition. The
definitions are test data, not Task or Supervisor input. Their names are not
written into runtime WTV output or used for semantic classification.

There is no replay engine, Task/Monitor resume, semantic transport, path
relevance rule, Carry/Reopen verdict, new tool or model-visible metadata.
The fixture and WTV simply record reproducible mechanical facts.
