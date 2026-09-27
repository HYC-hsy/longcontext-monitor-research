# R/P panel draft (not frozen)

This is an experiment-design artifact only. All four cases below are proposed
synthetic or replay-derived situations; none is a completed scientific run.
M1, R, and P would be run independently on the same initial snapshot. R and P
are never stacked.

| case | initial decision context | visible evidence | feedback/event | control question |
|---|---|---|---|---|
| local-insufficient | a local repair is proposed, but its scope is unclear | source diff plus the original local requirement | a direct source observation can confirm or disconfirm the local premise | continue for a discriminating local observation or make a qualified local decision |
| preferred-unavailable | the preferred behavioral observation is requested but its executable dependency is unavailable | task source, tool receipt/error, and the stated observation purpose | an ordinary replacement observation may be available; otherwise the dependency remains unresolved | replace the measurement, explicitly explain why it is no longer needed, or remain bounded-unresolved |
| correct-release | direct evidence already covers the current decision scope | source/result receipt and no currently visible blocker | a further wait may add no decision value | relax and approve, rather than investigate indefinitely |
| repair-then-root | a local repair has completed while whole-task completion remains pending | repair receipt plus original task and public event update | a new public event may reveal a material blocker, or may confirm none | return to the same whole-task decision and select the next useful action |

For each case, the future harness must specify the exact original task text,
initial working prose, allowed evidence paths, tool receipts, and follow-up
event. `wait` means defer/observe the next public event; `intervene` means a
concrete correction is delivered and the next model turn can observe its
feedback; `allow_complete` applies only to the current proposal. A static
snapshot without the stated feedback is not a closed-loop record.

## Proposed common resource budget

These are reviewable suggestions, not authorization: 12 logical Supervisor
calls per review, at most 2 reviews per record, up to 2 provider retries per
logical request, 1,200 output tokens per completion, 120 seconds per tool
operation, and 1,800 seconds per record. Wait/intervention latency is recorded
separately. With M1, R, and P across four cases and two repeats, the proposed
panel has 24 records, at most 576 logical calls, and at most 1,728 provider
attempts including two retries per logical call. Truncation, budget exhaustion,
tool failure, transport failure, and semantic/control failure remain distinct
outcomes. No grid, extra repeat, or hidden verifier is implied.
