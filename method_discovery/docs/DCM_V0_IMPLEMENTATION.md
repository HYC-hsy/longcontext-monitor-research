# DCM-v0 — zero-model implementation note

DCM-v0 is an opt-in, review-local release boundary atop the frozen CFS-v0
mechanics. It is enabled by `monitor_decision_conditioned_measurement=true` and
requires CFS, continuous manual verification, and EIS off. It changes neither
the system prompt nor the seven tool definitions, Task input, wake cadence,
budgets, or completion freshness checks.

After the existing legality checks, the first valid `wait(mode="patrol")` or
root `allow_complete(result="resolve")` returns a normal tool result saying
that release has **not** executed. The review continues in the same History.
The result asks the Supervisor to decide whether the available measurement
distinguishes states that would warrant different control. A matching release
in a later model response of the same review executes the original control
action; no intervening observation is required. Two release tool calls in one
model response cannot bypass the boundary, because the model has not yet
received the first result. A different reason is allowed.

`wait(follow)`, `intervene`, and `allow_complete(defer)` retain their original
control paths and abandon an armed boundary. After an intervention, a later
patrol attempt in the same review is a fresh relaxation attempt. Review end,
including model-turn exhaustion or error, discards the boundary without
executing release. A new review starts unarmed. Stale handoffs, invalid
arguments, and root-frame identity remain subject to existing checks before
DCM can issue a boundary.

Private `monitor/audit/dialogue.jsonl` gains mechanical events:
`dcm_release_attempted`, `dcm_boundary_issued`, `dcm_post_boundary_tool`,
`dcm_release_confirmed`, `dcm_release_abandoned`, and
`dcm_review_ended_with_boundary_pending`. They record the review, frame,
challenge ID, proposed arguments/reason, model/tool sequence, observed tool
names and safe locators, and disposition. They do not classify evidence,
measurement quality, or requirement coverage. Ordinary `tool_call` receipts
remain the authority for full tool arguments; DCM does not copy command text
into progress metadata.

Example private audit row, with synthetic identities:

```json
{"review_id":"<review>","event":"dcm_boundary_issued","challenge_id":"<opaque>","frame":"root","release_kind":"allow_complete","proposed_reason":"Current public observations support completion.","issued_at_model_turn":4,"issued_at_tool_sequence":7,"observed_tools":[]}
```

Provider-visible synthetic boundary example (ordinary tool result, not system
guidance; only the challenge ID is substituted):

```json
{
  "status": "release_not_executed",
  "challenge_id": "<opaque>",
  "scope": "whole_task_completion",
  "proposed_action": "allow_complete(result=resolve)",
  "proposed_reason": "Current public observations support completion.",
  "control_state": "The current handoff remains pending; completion was not allowed.",
  "message": "This release has not executed. For this proposed control action, rather than a general check: if a material state remains compatible with your current grounds but would call for different control, use the existing tools to obtain an observation that distinguishes those states. If your current grounds already distinguish the decision-relevant states, repeat the release action to execute it. You may change measurement placement or abstraction when the current proxy would look the same in different states. Do not reopen unrelated work whose support remains adequate. You may instead follow or intervene when that better fits the public evidence."
}
```

This is a decision boundary, not a verifier. Immediate repetition is a valid
outcome and may reveal no change in decision. A first release at the final
review turn consumes the remaining turn and does not silently execute. The
boundary does not guarantee that the Supervisor finds a discriminating
observation. All real scientific execution remains unauthorized by this note.

Targeted zero-network check:

`$env:PYTHONPATH='GenericAgent-main'; python -m pytest GenericAgent-main/tests/test_dcm_v0.py GenericAgent-main/tests/test_cfs_v0.py GenericAgent-main/tests/test_verification_loop_v0.py GenericAgent-main/tests/test_root_scope_v1.py -q`

Result: 48 passed. Pytest also emitted an unrelated Windows `atexit`
permission warning while resolving an older temporary pytest directory;
the process exit code was zero. No Task Agent, Supervisor service, native
verifier, or independent probe was called.
