# Reminder-first wake lifecycle (engineering trial)

Base: `84c3fa0bd57d83bcf54dab607b9595347de844f6` (preserves reminder code blocks).
No real Task, PMA model call, native evaluation, or paid experiment was run for this change.

## What is implemented

The existing `pma_predictive_read_context_v1` production wiring now instantiates
`RemindFirstMemoryAgent`. It subclasses the previous manager, which is retained
as a historical comparator. The same model, bank, provider-native continuous
history, tool dispatcher/receipts, original-task anchor, history trimming,
four-turn default wake cadence, and one-time host injection are reused.
No additional model, semantic judge, memory tool, separate conversation, or
`memory_done` tag is added. The transport audit phase name remains
`unified_memory` for compatibility; each loop row now records `stage`,
`bank_read_before_response`, `decision_accepted`, and `organize_completed`.
The host stores `loop_mode=remind_first`, `termination=organize_no_tool`.

## Actual state transitions

1. A wake receives the task anchor and this period's new trajectory. Task waits.
2. `remind` state exposes only `memory_read(bank_id="knowledge")`. The execution
   dispatcher also rejects `memory_add`, even if the model invents a call absent
   from the current schema. Nothing can be written by this manager in this state.
3. A successful read returns the existing bank in the native tool-result history.
   A reminder tag emitted in the **same** response as that read is not accepted:
   the model has not seen the result yet. A later response with no tool call and
   one valid existing decision tag (`context_for_action` or `no_intervention`)
   is accepted. Empty banks follow this same path.
4. The program latches the reminder body/decision, then sends an explicit
   transition message in the **same conversation**. No reminder is injected yet.
5. `organize` state exposes the existing `memory_add` and `memory_read`. Tool
   calls execute, receipts are appended, and the model continues. Adds mutate
   the bank immediately as before, but cannot change the latched reminder.
6. The model's next ordinary, nonempty public reply **without tools** is a
   completion candidate, borrowing GA's tool/no-tool lifecycle. No completion
   keyword is required. If nothing needs saving, an ordinary statement suffices.
   A write and "done" in the same response does not end the wake; its receipt
   is returned for a subsequent response. Reminder tags alone are not an
   organization-completion signal and cannot replace the latched reminder.
7. Only after organization completes does `process()` return the latched
   decision. The existing host enqueues it for the next Task request and
   consumes it once. `no_intervention` simply resumes Task without a reminder.

A typical wake is four model calls: read -> reminder decision -> add -> plain
completion. A no-save wake can use three: read -> decision -> plain completion.
Additional tool rounds remain possible. These are examples, not fixed counts.

## Completion/error boundaries

- Blank/punctuation-only, hidden-only, code-only, malformed/nested hidden spans,
  legacy textual pseudo-tool calls, and reminder tags are not normal
  organization completion. Explicit GA interruption/error/length markers are
  rejected. The native Anthropic/LiteLLM and Responses adapters already raise
  on truncation/incomplete responses; tests exercise that route.
- Existing consecutive tool-error and invalid-no-tool recovery limits are reused.
  They are not total model-call limits: successful tool chains can continue.
- A tool failure cannot complete the wake in that response. Successful earlier
  writes are not replayed or rolled back. A later valid no-tool response can
  finish if the model decides no further action is needed; no semantic judge
  proves all intended work was saved.
- Provider errors, audit errors, and cancellation propagate; they do not return
  a successful no-intervention result. A reminder latched before an organization
  failure is **not** released to the host. Prior successful writes remain recorded.
- Current worker access is serial. There is no new bank snapshot or concurrency
  control. Within this lifecycle, preventing writes during `remind` suffices to
  preserve the pre-write bank for the reminder decision.

## What is reused vs adapted from GA

Reused: continuous history/native tool-result handling, the existing provider
adapters, tool execution and error receipts, host reminder delivery. Adapted:
GA's normal no-tool completion rule is applied to organization, while an explicit
stage variable distinguishes it from the preceding reminder decision. GA's
plan-mode checks and task tools are not imported; they do not apply to this
memory-only worker.

The program guarantees ordering and faithful transport, **not** that the model
notices conflicts, predicts future value correctly, preserves enough detail, or
saves true information. "Organization complete" is a protocol outcome, not
proof of semantic completion or task improvement.

## Prompt scope

The previous eight-turn presentation-value selection criterion is retained.
Only sequencing/tool availability/end behavior is adapted to explain the new
runtime. The new `REMIND_FIRST_SYSTEM` lives beside the old `UNIFIED_SYSTEM`;
production uses only the new one. There is no new correction/verification rule,
no forced conflict checklist, and no change to when a reminder is considered
useful. Prompt wording is a reviewable engineering draft, not an optimized
semantic intervention established by experiment.

## Verification

See `tests/test_remind_first_loop.py` for stage ordering, premature decision,
read/write gating, empty bank, no-save, frozen reminder, native call identity and
history, same-response writes, failure/cancellation, hidden/invalid/truncated
completion, code preservation, actual Anthropic/Responses adapter shapes, host
release/one-time consumption, and multiple wakes. Existing worker and raw Task
batch tests are adapted to the actual additional model calls without weakening
trajectory/content or failure-preservation assertions.

Synthetic provider requests only; no live Task, memory model or native evaluation.

- Root `tests/`: **392 passed, 6 failed, 4 subtests passed**. All six failures
  reproduce against the tree-identical parent: four existing compression telemetry
  cases, one source-file-set assertion, and one old six-turn prompt assertion.
  The parent check of those files is 45 passed / 6 failed. They remain visible,
  not suppressed or presented as a green full suite.
- Focused new lifecycle/raw-trajectory/prompt boundary suite: **86 passed**.
- Staged `test_model4_transport.py`: **9 passed, 11 subtests passed**, including
  six model-profile constructors and synthetic Responses lifecycle/artifact cases.
  Its fixtures now represent read -> decision -> organize -> ordinary completion.
- Commands used the existing Python 3.12 environment with repository, test,
  staged PMA and Harbor paths in `PYTHONPATH`, and
  `LITELLM_LOCAL_MODEL_COST_MAP=True` to avoid an unrelated metadata-network fetch.
- Linux offline verification only. Windows and live-task behavior have not been
  asserted. Existing Pydantic/pytest configuration warnings remain.
