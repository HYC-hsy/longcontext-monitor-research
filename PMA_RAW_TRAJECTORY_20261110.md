# Configurable raw public trajectories and continuous observer history

Base: `ac57a1e4d840abddcc7f75b9976a705e94e8d566`.
Scope: offline-verified engineering only. No real model, benchmark run, merge,
deployment, prompt change, model change, or new end-of-task inference.

## Configuration

`pma_batch_rounds` is a positive JSON integer, default **8**. The experiment
frontend also accepts `--pma-batch-rounds 3`. Booleans, zero, negatives,
fractions, and numeric strings in JSON are rejected. The value is bound into
the plan, manifest, run identity, worker arguments and worker-ready receipt,
then forwarded as `GA_PMA_BATCH_ROUNDS` to the task container. The task-start
handshake must agree with the worker. P1 and P2 consume the same complete
batch, including with values 1, 3, 8 and 11.

The existing startup wake is unchanged. Only the originally counted normal
and parse-error rounds advance the periodic trigger. Public input/output from
an intervening cancelled attempt remains in the next batch; cancellation does
not become an extra counted round. A completed or interrupted final attempt is
archived without forcing a final wake. A short tail is not silently processed.
The existing uncapped task/time policy is unchanged.

## Reusable boundary, with GA as the first adapter

`GenericAgent-main/task_trajectory.py` is a dependency-free protocol module.
It does not import GA, PMA, a provider SDK, or a tool executor. Another host can
use `PublicTrajectory(round_number).record(event_id, kind, payload)` and send
its `snapshot()` through the existing event bridge. The host loader
`public_trajectory.py` loads that same file, rather than maintaining a second
implementation. `ga_trajectory.py` contains the GA-specific conversion.

The outer transport continues to provide task/run identity, an event ID, and
ordered sequence numbers. Each round has ordered public events and stable
occurrence IDs. Re-delivery of the same ID and identical typed JSON is ignored;
reuse of an ID with different content is an error. Identical text or identical
tool arguments with different occurrence IDs are retained. A repeated native
provider tool ID does not collapse two actual executions: occurrence IDs are
separate, and the original native ID is preserved as data.

GA captures the actual newly assembled native input, accepted public output,
each tool result immediately when it returns, and the next framework input.
The capture happens before terminal breaks and before a post-tool display yield
can be cancelled. Calls that never ran and calls whose outcome is unknown are
labelled explicitly. No successful receipt is invented. A tool's result text
uses exactly GA's ordinary `json_default`/`str` serialization; this also handles
Python values such as sets or tuples without changing task execution.

Typed public text fragments from an interrupted provider response are retained
as unaccepted output. Completed but unaccepted public blocks are also retained.
They are never converted into executable observer tools. Accepted output uses
one complete message for the same response occurrence, without duplicating its
stream fragments. Private thinking/reasoning is not captured through this
public channel. GA supports public text/tool-use blocks and preserves their
public extra fields, such as citations. This is not a claim of general
multimodal support; unsupported accepted block types fail explicitly.

There is no task-side summary, character limit, relevance filter, semantic
deduplication, or tag removal. Structured event envelopes are serialized as
text evidence for PMA. JSON key ordering is canonicalized; original string
values and event order are preserved. Source text resembling `memory_add`,
provider output items, host status, or task-description markers is still data,
not an instruction to the runtime.

## Observer history and provider continuation

P1 and P2 keep separate histories across wakes. The original task and the whole
active batch/wake remain protected. Existing GA tag compression is reused for
eligible older text. Old context is removed in complete interaction groups,
not by leaving orphaned native tool results. Signed/redacted thinking and
OpenAI opaque output items are treated as provider protocol state, not as
editable text. This state remains private to the observer's provider path.

The minimal OpenAI reasoning-only repair prevents a synthetic `.` assistant
message from being introduced when the actual previous output contains only
opaque reasoning. Model settings and provider requests are otherwise unchanged.
P1/P2 system prompts and the memory tools are unchanged.

## Failure evidence

`received_events.jsonl` durably records each complete received public event
before any P1/P2 inference. `events.jsonl` records completed event receipts.
A failed wake therefore retains its exact input without claiming a successful
decision, replaying a memory write, or silently producing no-intervention.
Final metadata records both the existing counted tail and the full pending
public-attempt list. New tasks clear the previous task's active batch.

## Verification

New test suites:

- `tests/test_raw_task_trajectory.py`: real local HTTP Task mock, native GA
  session and loop, file spool, separate worker process, and both PMA phases;
  N=1/3/8/11, two full batches plus tail, long Unicode/tag-containing input,
  exact input and result assertions, duplicate occurrences, cancellations,
  provider/tool errors, closing during model text or after a known tool result,
  and durable input on P1/P2 failure.
- `tests/test_pma_batch_configuration.py`: actual frontend/prepare/launch
  functions, configuration identity, worker arguments/receipts, Harbor
  forwarding, rejection of invalid values, and unchanged uncapped policy.
- `tests/test_observer_history_retention.py`: complete native tool groups,
  signed/opaque state, reasoning-only continuation, protected >90k-character
  current input, P1/P2 isolation, real OpenAI SDK and Claude provider-handler
  HTTP serialization with mocked HTTP responses.

All model responses in these tests are offline fixtures. The subprocess worker
uses `--fake-memory`; the Task HTTP server binds only to loopback. These tests
establish transport, capture and lifecycle behavior, not real-model usefulness.

The verification report accompanying the branch distinguishes new focused
checks from older baseline failures and tests blocked by unavailable unrelated
fixture dependencies. It must not be read as a claim that every historical
candidate test or real benchmark has passed.
