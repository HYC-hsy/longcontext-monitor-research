# Independent C Online Fyne R5 Audit (2026-09-19)

## Scope

This audit covers the serial Fyne comparison requested after the optional online
Independent C integration.  Both runs used the same task, model, isolation
profile, monitor baseline, budgets, and post-termination native verifier.  The
intended treatment difference was only `GA_MONITOR_INDEPENDENT_C=0/1`.

The runs were:

- `independent-c-fyne-2.2.0-roadmap-c_off-r5`
- `independent-c-fyne-2.2.0-roadmap-c_on-r5`

No native verifier result was exposed during execution.

## Pre-run wiring defect and repair

The preceding R4 pair was not a valid C comparison.  Although its manifest set
the Independent C variables, the benchmark manifest allow-list and the Harbor
container adapter did not forward them.  Inspection of the actual C-on monitor
`review_context` confirmed that `independent_check` was absent.

Commit `98f718e` adds these variables to both boundaries and adds regression
coverage:

- `GA_MONITOR_INDEPENDENT_C`
- `GA_MONITOR_INDEPENDENT_C_TOTAL_REQUESTS`
- `GA_MONITOR_INDEPENDENT_C_MAX_REQUESTS`

The focused benchmark tests passed: `51 passed`.

R5 then confirmed that `independent_check` was present in every C-on review's
actual tool schema and absent from C-off.  Thus R5 repaired tool availability.

## Native results

| condition | phases passed | reward | passed phases |
|---|---:|---:|---|
| C-off | 2 / 7 | 0.272727 | JSON Theme, Toolbar |
| C-on | 5 / 7 | 0.727273 | App Metadata, JSON Theme, Menu, Toolbar, Widget/Container |

Both trials completed without Harbor trial errors.  C-off ran from 10:20:41 to
10:35:31; C-on ran from 10:36:01 to 10:52:25 (Asia/Shanghai timestamps in the
outer results).

## Decisive treatment-integrity finding

The C-on parent Supervisor made **zero actual `independent_check` tool calls**.

Evidence:

- the tool appeared in 14 `review_context` tool schemas;
- parsed `tool_call` events contained file reads, private note operations,
  local analysis, wait, intervene, and allow-complete, but no
  `independent_check`;
- there were zero `independent_probe_finished` events;
- no child-probe budget or child result entered the parent decision path.

Therefore the score difference is not evidence that Independent C improved the
task.  Enabling an unused tool can still perturb sampling through a changed tool
schema, and the Task Agent and Monitor trajectories were visibly different, but
the proposed causal chain did not execute.

## What actually happened

C-off issued three ordinary monitor corrections, concerning App Metadata,
remaining App implementations, and concrete Toolbar constructor return types.
It later allowed completion, but the native verifier passed only phases 2 and 5.

C-on used ordinary direct investigation.  It issued one mid-run correction for
the incorrect `NewAllStrings` semantics and one completion-boundary correction
for the requested file path, then allowed the second completion.  This explains
the phase-6 improvement, but both corrections were produced by the parent
Supervisor's existing file-reading path, not by C.  Other phase differences are
also confounded by different Task Agent trajectories.

Both conditions had one review exceed the existing 20-turn control-action
limit.  The runtime recorded the failures and continued; this is not a transport
failure and did not create a C result.

## Monitor cost (recorded visible token fields)

| condition | completed monitor requests | input | cache read | cache creation | output | aggregate recorded fields |
|---|---:|---:|---:|---:|---:|---:|
| C-off | 79 | 4,503 | 2,075,540 | 1,982,171 | 19,382 | 4,081,596 |
| C-on | 68 | 3,876 | 885,369 | 1,973,566 | 9,230 | 2,872,041 |

These fields are provider token accounting, not a dollar estimate.  C-on has no
child-verifier cost because it never invoked the child.  The lower C-on total is
another trajectory difference, not evidence of C efficiency.

## Research conclusion and stop decision

R5 establishes the engineering fact that optional Independent C can be exposed
inside the real isolated online Supervisor.  It does **not** test whether C
improves decisions, because the parent never selected it.

The immediate bottleneck is now treatment consumption / question selection:
the parent can investigate directly and does not spontaneously delegate, even
at a later incorrect root approval.  This is consistent with the earlier expert
warning that local verification competence and autonomous selection are
separate questions.

Do not claim C effective from the 5/7 score and do not repeat the same pair
unchanged.  Before another real task run, choose a minimal, non-domain-specific
way to make the delegation decision observable and usable while preserving the
parent Supervisor's freedom to decide that no child check is worthwhile.  That
choice changes the tested mechanism and should be discussed before
implementation; no prompt, memory, model, budget, or scheduling change is made
in this audit.

