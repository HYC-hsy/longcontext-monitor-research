# R3 audit: requirement-first comparison did not establish supported completion

## Scope and result

Read-only audit of implementation 09169e7, run `clean-monitor-fyn-2.2.0-roadmap-pma-two-phase-20260913-r3`, trial `fyn-2.2.0-roadmap__2whCiCg`. No model calls, hidden tests supplied online, production edits, or new runs in this audit.

Artifact root P: `long_context_bench/output/clean_monitor_real_tasks/fyn-2.2.0-roadmap/jobs/clean-monitor-fyn-2.2.0-roadmap-pma-two-phase-20260913-r3/fyn-2.2.0-roadmap__2whCiCg/`.
Below D denotes `P/agent/monitor/monitor_private/audit/dialogue.jsonl`; T denotes `P/agent/monitor/task_evidence/public_events.jsonl`.

- Agent execution 13:28:44.158–13:39:39.905 UTC: 655.747 seconds; 72 task turns.
- Native post-run result 2/7, reward 0.272727; phases 3 and 5 pass. R2 also 2/7, but passed phases 1 and 4. Equal aggregate score is not equal behavior or preserved capabilities.
- Metadata omissions in dummyApp/themedApp block phases 1/2/4 and part of 6. Entry minimum-row behavior fails independently; desktop.App lacks SetSystemTrayIcon and unnecessarily embeds fyne.App (phase 7).
- Wrapper archived successfully, no trial exception. However initial PMA maintenance FAILED; previous status statement that there was no runtime anomaly was too broad. GA process 143 alone is not proof of an abnormal termination: completion receipt exists, wrapper 0 and round_end_seen true.

## Evidence chain

1. D L1: first maintenance returns three `file_search` calls, not allowed bank tools. Adapter rejects with `Unexpected PMA phase tool call`, rolls back the bank, records failure. Subsequent review retries successfully. This is NOT a normal no_intervention or an API connectivity failure.
2. D L17: PMA comparison recommends file-search tools for repository exploration. Its snapshot still concerns initial turns; this two-phase call costs 159.35 seconds. It is not timely evidence about later implementation. It also quotes system guidelines not located in the audited local monitor source; their origin is unproven.
3. Main review `29b88...`: actual grep checks identify missing testApp.Metadata; D L95 records diagnosis, L101 sends correction. Task turn 50 adds it. This is a real, useful local correction.
4. D L110: next PMA update distinguishes the check at 13:35:30 from the later successful patch at 13:36:13. It does not infer that this write failed. This is positive evidence for use of timing metadata, not a general causal proof.
5. The same comparison says `go build ./...` is the definitive check for missed App implementations. This is wrong for implementations confined to `_test.go`; ordinary package building does not establish test-package compatibility. It also cannot prove behavior.
6. D L128, main review `a75a...` turn 3, working.md: “If compilation succeeds, all requirements are met”. This is the explicit decision rule failure, before final approval.
7. D L140, turn 5: compilation is marked VERIFIED separately under all seven targets. It claims desktop.App contains SetSystemTrayIcon although task turn 53 actually writes SystemTray and SetSystemTrayMenu plus embedded fyne.App. The bank still correctly names SetSystemTrayIcon. Thus retained correct requirement did not prevent unsupported closure; it is not merely lost memory.
8. D L152 allows completion. No main-monitor behavioral test execution or assertion-content inspection occurs in this final review. Reading task trajectory previews is not equivalent to inspecting the implementation or test assertions.

## What actually reached the monitor

- Final review tool sequence: file_read first 30 lines of test/testapp.go; review_context; write notes; review_context; write completion notes; review_context; allow_complete.
- D final review turn 2 returns events 91–122 with heavily clipped action/result previews. The desktop interface body is not visible in full there. Main monitor does not open driver/desktop/app.go or retrieve full corresponding raw event.
- Task's build command is `go build ./... 2>&1 | head -50`. Pipeline exit 0 is not independently the compiler exit status. Empty captured output does not prove runtime behavior; do not assert an actual build failure from this caveat alone.
- Earlier search for App structs returns a noisy large output with 5,268,482 unread bytes. A separate test-file search uses `head -10` and returns a non-exhaustive list. Neither supports “no other implementations”. Tools expose truncation/continuation; model did not establish exhaustive coverage.

## Mechanism and integration assessment

- Requirement-first subclass is active: archived prompts show changed order/instructions. Author process still executes both phases; successful cycles are not merely file availability.
- Four PMA attempts: one failed maintenance, three successful cycles (one no_intervention, two reminders). Seven phase calls plus 24 main-monitor calls = 31 total.
- PMA update runs once at `agent.py:review` entry. `_refresh_completion` can announce a completion within the same ongoing review, but does not re-run PMA. In the final review its comparison was based on task progress around turn 50; the task finishes at 72. Therefore the new comparison was NOT directly exercised on the final completion evidence. This is a scope/trigger mismatch, not proof the process was accidentally removed.
- follow control preserved: wait from turn 1 to 2 and 50 to 52, both follow; one ordinary correction, final allow. No evidence of the old repeated-build-cancellation loop. Initial failed review/re-wake did cancel early exploration; not a fully anomaly-free start.
- Current method does not yet bind revised grounds to the actual decision. Correct bank facts coexist with unsupported main working notes. PMA's own inaccurate advice contributed a plausible but overbroad verification rule. Simply making a reminder always visible is insufficient evidence of decision quality.
- Timing improvement has a concrete positive example. Overall effectiveness is not established; R2/R3 differ in trajectories and successful phases. Shorter time cannot be claimed as capability-preserving cost improvement.

## Costs recorded, not estimated dollars

| Stream | Calls | Input | Output | Cache read | Cache creation |
|---|---:|---:|---:|---:|---:|
| PMA maintenance | 4 | 24678 | 3856 | 204 | 3808 |
| PMA comparison | 3 | 21670 | 3295 | 198 | 2556 |
| Main monitor | 24 | 38212 | 12329 | 197255 | 620062 |

Source: provider_usage.jsonl, grouped by monitor_phase (unmarked = main). Raw Anthropic fields kept separate. PMA durations total about 283.17 seconds including failure; concurrent wall-time impact cannot be obtained by directly summing them. Billing dollars not established. Task-side tokens not aggregated in this audit.

## Comparison with actual human supervision

Read `PHASE1_MANUAL_FYNE_REFERENCE_AND_CONTINUITY_CHANGE_20260907.md` and original manual intervention 014 under the manual 20260907-r1/Fk7n6ZM archive. That correction points out that pointer/count assertions pass even with empty Refresh, asks for observation of actual SetMainMenu routing, and explicitly stops adding tests after that narrow requirement is supported. The important distinction is checking whether evidence distinguishes the required behavior, not requiring exhaustive testing or more interruptions. Human outcome remains a diagnostic reference, not an equal-budget baseline.

## Next decision, not implemented

First address the demonstrated decision mismatch: when moving from a local repair to root completion, reassess the relevant grounds against CURRENT evidence, not an old PMA lead plus green working notes. This may reuse the existing comparison at that boundary, but must first specify its input and avoid blindly adding another expensive call. Re-running the same inaccurate “compilation is definitive” judgment alone is not a solution.

Independently investigate invalid phase tool output using retained request/response evidence before choosing protocol recovery. Do not enable unrelated tools inside bank maintenance or claim the cause is definitely upstream. Preserve the timing and follow changes; neither requires a new controller to audit.

No production correction or new real run authorized by this report. Next change requires a small coherent design, not more unrelated prompt rules or a fixed per-task test checklist.
