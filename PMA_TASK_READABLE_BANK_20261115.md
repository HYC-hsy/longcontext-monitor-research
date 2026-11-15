# Task-readable knowledge file

Parent: `73b60e00aecf1dda0105331a1c0952a5b1eb17a0`.

For `pma_predictive_read_context_v1`, the worker publishes an initially empty,
per-run knowledge projection at its existing `control/spool/responses/knowledge/memory.json`.
The existing read-only **directory** mount exposes this file to Task at
`/run/pma-bridge/responses/knowledge/memory.json`. No new mount, model call, tool, prompt,
context policy, or scheduling policy is introduced.

After each accepted `save_knowledge`, the projection is atomically replaced with
the cumulative ordered knowledge entries (original IDs, full content and entry
metadata). This is an incremental update of the existing bank, not another model
summary. Unchanged publication does not rewrite the file; repeated reads/events
must not append duplicate records. Distinct successful model writes remain
separate even when the text repeats. Only knowledge is exposed, not private
profiles, prompts, manager history, status or procedural memory.

A real nonempty reminder returned by `before_actor_call` keeps its original text
and appends:

> The knowledge bank is available at /run/pma-bridge/responses/knowledge/memory.json. You may consult it alongside your current task and judge the information yourself.

Silent decisions add no input. The reminder is still frozen before organizing;
the actual delivery remains after that wake's organization completes. Therefore
the file available with the delivered reminder contains the cumulative knowledge
**including this wake's successful additions**, not a frozen pre-decision bank.
It contains no future Task observations. File publication does not alter the
frozen reminder or turn a silent decision into an intervention.

Publication uses UTF-8, fsync, atomic replace and directory mode 0755 and file mode 0644 so a different Task UID
can read it through the read-only mount. On publication failure, the host write
may already exist, but the tool/event cannot report success: a fatal publication
error crosses normal model/tool recovery, the dispatcher writes an error receipt,
and finalization retains both the private bank and the actually exposed snapshot.
Further writes through the failed publisher are stopped rather than retried.

Finalization archives the exact exposed bytes as `task_visible_memory.json`;
the existing ordered archive exporter includes a normal redacted projection as
`task_visible_memory_public.json`. The original private memory/trajectory outputs
remain unchanged. The snapshot lives in a subdirectory, separate from event receipt filenames.
Each run uses its own existing responses directory; a stale
file at initialization is rejected, not silently reused or overwritten.

Validation: 171 targeted offline tests passed (14 new publication tests plus
existing prompt, lifecycle, tool, reminder-code, bank-content and GA bridge tests).
Coverage includes a separate-process reader through simulated mount mapping,
file permissions, exact Unicode/code content, incremental order, unchanged/replayed
writes, isolation, failed add, failed atomic publication, dispatcher error receipt,
finalization, no-reminder silence, and actual synthetic PMA episode timing.
No Docker executable is available in this cloud environment, so actual Docker
bind-mount behavior / the Windows host mount has not been end-to-end exercised.
Two wider legacy test modules could not collect due a missing historical module
and relative-import setup; no real Task, model call or native evaluation was run.
