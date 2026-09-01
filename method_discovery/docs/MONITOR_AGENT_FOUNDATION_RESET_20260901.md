# Monitor Agent foundation reset (2026-09-01)

## Decision

The next monitor remains an independently designed research agent. GenericAgent is a source of
reusable execution primitives, not the paper method and not an application that is launched unchanged.
The existing M0--M3 monitor is retained in Git as behavioral evidence and a regression oracle, but its
accumulated protocol and tool architecture will not be the implementation parent of the clean monitor.

The clean monitor may reuse GenericAgent's provider sessions, streaming/tool loop, generic code
execution, history handling, logging, failure recovery, and abort primitive. It must independently define
the monitor role, observation policy, long-horizon cognition, evidence revision, intervention behavior,
and later memory innovations.

## Behaviors worth carrying forward from the existing monitor

- turn-zero task understanding before ordinary patrol;
- one persistent monitor identity across wakes;
- autonomous observation cadence rather than synchronous per-boundary approval;
- concurrent failure isolation: a blocked monitor never freezes the task Agent;
- tests and Agent intent as high-information public evidence;
- user-like correction followed by continued observation until understanding and action recover;
- root-task awareness after a local repair is released;
- externally auditable state, decisions, observations, and provider telemetry;
- no online checker, hidden test result, or verifier dependency.

These are behavioral requirements, not a requirement to retain the current JSON fields, repair ids,
specialized inspection operations, packet shapes, or compatibility paths.

## Findings from the discarded forced-continuation prototype

An uncommitted prototype established the following engineering facts with deterministic integration tests:

1. GenericAgent already exposes the correct low-level stop primitive through `GenericAgent.abort()`;
   frontends use the same primitive for their Stop action.
2. Monitor correction and user Stop require different lifecycle meanings. User Stop terminates; monitor
   correction interrupts the active generation and then supplies a same-session user-like continuation.
3. The same provider client can be retained across the interrupted and corrective segments; task turn
   numbering can also remain monotonic.
4. Ordinary monitor silence must never enter the task Agent's synchronous path.
5. A monitor correction cannot merely remain in the old next-turn injection queue if immediate intent-level
   interruption is required.

The prototype modified `agentmain.py`, `agent_loop.py`, and `async_monitor_runtime.py`, and added a focused
test. It passed the full suite (299 tests), but it is deliberately discarded before the foundation reset:
it attached the new lifecycle to the accumulated monitor runtime before deciding the clean Monitor Agent
substrate, history, compression, and tool architecture.

## Existing monitor history audit

The old monitor is a custom model session, not a GenericAgent instance. It manually carries a linear
`self.history`, writes that history to its checkpoint after provider calls, and restores it for a matching
task. Its current compaction behavior is:

- default soft threshold: 128,000 serialized characters;
- no compaction while attention is focused or a repair episode is open;
- exact pre-compaction history is archived;
- foreground becomes the stable prefix, a model-authored continuation note, an acknowledgement, and the
  latest eight messages;
- individual very large retained messages are replaced with a short preview and an archive pointer;
- exact older history remains available through a retrieval operation.

Two material limitations were found. `history_target_characters` is configured but is not used by the
compaction algorithm, and a long focused/repair period can grow without a bound. This mechanism is evidence
for later design; it is not accepted as the new Monitor Agent memory solution.

## Clean implementation sequence

1. Freeze a capability map: reuse from GenericAgent, preserve as monitor behavior, or remove as historical
   burden.
2. Build an independent Monitor Agent kernel on reusable GenericAgent primitives.
3. Add the concurrent wake/observe/interrupt/continue lifecycle without introducing method innovations.
4. Establish deterministic engineering evidence before any real-task launch.
5. Only then investigate nonlinear semantic memory, evidence-carrying revision, active reconstruction,
   and capability-preserving cost reduction.
