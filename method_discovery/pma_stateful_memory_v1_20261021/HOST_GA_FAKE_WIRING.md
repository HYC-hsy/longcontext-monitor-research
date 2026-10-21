# Stateful proactive memory v1: minimal GA fake-only wiring

`single_run prepare-stateful-fake --output DIR --fake-only` writes an unarmed
`pma-stateful-ga-fake-plan-v1`. `run-stateful-fake --output DIR --fake-only`
consumes it once and enters the actual `agent_runner_loop` / `NativeToolClient`
path with a finite local SSE server. Both commands reject omission of
`--fake-only`; neither creates live authorization or a Harbor manifest.

The opt-in host setting is `GA_STATEFUL_MEMORY_ENABLED=1`, with
`GA_STATEFUL_MEMORY_MODE=fake-only`. The adapter requires a new SQLite store,
a finite role script, synthetic run/task IDs, Task complete-response, a fixed
Task deadline, a loopback HTTP Task endpoint, and the literal synthetic key.
It is exclusive of prior PMA/PoS/monitor modes. Unknown role/script state
fails rather than falling back to a provider. No live candidate route exists.

At fresh Task initialization, the original user content is stored as a user
source at event sequence zero. Each completed GA action batch supplies paired
`executed_action` and `tool_result` leaves from actual dispatch. A host batch
has one stable event/trigger ID; each tool has a unique batch-scoped leaf
identity while retaining the GA tool-use ID in the batch payload. The core
`CycleEngine` runs once per complete batch. An incomplete batch is journaled
as a diagnostic and cannot advance the event frontier. Terminal agent reports
already received are retained as pending events; `finish` does not run a new
maintenance, audit, or selection cycle.

The next Task request uses the core `attach_once` binding and native request
assembly. A reminder is confirmed only after the finite local HTTP response
has passed Task complete-response acceptance. The reminder is not newly
inserted again, although ordinary GA history retains its prior text. An
unknown transport result leaves a delivery attempt in the journal and is not
resent. State update failure retains the core's old snapshot and pending
event; an exhausted fake role script is fatal to this bounded fixture.

Verification levels are separate: the direct GA fake chain exercises native
SSE request/response, real GA tool dispatch and the new core store. It is
**not** a Harbor/native-SHARED certification. Native context guard, live
transport failure taxonomy, full packaged-source certification, and real
provider compatibility remain unverified. Real model, real benchmark Task,
and official evaluator calls in this stage: zero. The local fake Task sends
three HTTP POSTs and the finite method script makes nine fake role calls.

`single_run.py` is in the older source-bound A/B certification file list.
Consequently its historical fixture's execution identity no longer matches
the current source after this entry change; that is an expected refusal, not
evidence of a newly certified Harbor path. The old evidence is unchanged.
