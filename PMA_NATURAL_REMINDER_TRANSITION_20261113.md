# Natural reminder transition repair

Base: `06cd553c2ff0474072a284f085f9fb8e57e1f7a8`.

## Scope

- Accept a single unambiguous public reminder decision anywhere in the reply, not only at its end. Original PMA uses an unanchored `re.search` for its decision tag; this repair adopts that location flexibility, not its ambiguous-tag precedence or default no-op behavior.
- After a successful knowledge-bank read, the continuation asks for the reminder decision rather than asking the model to read again. Failed reminder-stage calls receive reminder-stage recovery guidance, not generic memory-management instructions.
- Keep the initial read requirement, read-before-decision order, no writes during the reminder stage, and explicit organize completion. A decision in the same response as the first read is not accepted before the read result is observed. Prose after a valid decision does not itself perform saving or finish the next stage.
- Keep hidden-block/code-example filtering, rejection of incomplete or conflicting decisions, and verbatim extraction of the reminder payload including fenced code.
- No change to the main system prompt, wake period, model profile, task runner, or initialization policy.

## Regression evidence

`tests/fixtures/reminder_stage_regressions.json` contains only public response text from archive `22871bd40ea4fb1cf789cb1cee96bbf1267b7ba3`, with source call and SHA-256: RStan wake 12 / call 15 and ARC wake 24 / call 28. Both now accept the original valid nonterminal decision. ARC's original no-intervention stays no-intervention; the replay does not substitute its later revised reminder. Scripted read/decision/add/done tests verify the actual stage transition and unchanged payload.

Linux / Python 3.12 offline validation:

- Focused regression suite: **114 passed**.
- Independent review and independently rerun natural-transition, code-preservation, remind-first tests: **77 passed**.
- Full root `tests`: candidate **407 passed, 6 failed**, baseline **394 passed, the same 6 failed**; each also reports 4 subtests passed. Not a claim of all-green acceptance. The identical failures are four compression-telemetry cases, one legacy source-file identity-list assertion, and one legacy six-turn prompt assertion. No new failure in this comparison.
- Existing `scripts/replay_reminder_transport.py` against the historical presentation archive: all **13 reminder payloads** match, including both code-containing reminders. This verifies transport preservation, not task outcome or model behavior.

The existing runtime-source guard was updated for this authorized change. The old prompt-only whole-file hash assertion was replaced with an exact hash of the approved main system prompt, which remains unchanged. Parser tests no longer assert that trailing prose is invalid. New tests cover stale prompts, failed reads, same-call reads, early writes, malformed/conflicting/hidden/fenced tags, and the two actual incident responses.

No real Task, PMA model call, native evaluation, or Windows validation was run. Offline replay does not prove that live models will avoid all repeated reads or misunderstandings. Existing compression failures were not silently suppressed or fixed as part of this scope.
