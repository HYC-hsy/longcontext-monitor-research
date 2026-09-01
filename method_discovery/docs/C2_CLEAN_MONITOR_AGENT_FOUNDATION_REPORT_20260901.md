# C2 Clean Monitor Agent Foundation Report

Date: 2026-09-01  
Status: implementation complete; deterministic acceptance passed; no Task Agent integration or real-task run

## Goal

Implement the C1 clean foundation as an independent Monitor Agent using only neutral GenericAgent runtime
primitives. This stage establishes identity, tools, history continuity, filesystem isolation, and a
semantic-free asynchronous controller. It does not claim research-method effectiveness.

## Delivered components

### MonitorWorkspace

- exposes `task/...` as authoritative read-only evidence and `monitor/...` as private writable cognition;
- rejects traversal, absolute paths, task writes, and writes into the runtime-owned analysis view;
- provides bounded reads with SHA-256 receipts, private replace/append/prepend, and exact-span patching;
- creates a disposable `.task_view/` copy before analysis execution, without following symlinks, so analysis
  programs cannot mutate the supervised workspace.

### MonitorHandler and MonitorAgent

- derives from `BaseHandler`, not `GenericAgentHandler`, so executor-only tools and production write authority
  are absent;
- exposes exactly seven tools: `file_read`, `file_write`, `file_patch`, `code_run`, `wait`, `intervene`, and
  completion-boundary-only `allow_complete`;
- reuses GA's low-level streamed `code_run` process runner and `agent_runner_loop`;
- keeps one provider client/session across wakes and records before/after history size, hash, duration, and
  terminal action in a private JSONL audit;
- uses natural-language semantic reasoning and only types the three controller actions;
- rejects `allow_complete` outside an explicit root-completion review and rejects reviews that end without a
  control action.

### MonitorController

- runs reviews on a background worker so publishing a task cursor does not wait for the monitor;
- contains cursor/lifecycle scheduling only and constructs no semantic packet or correctness classification;
- honors model-selected `wait(after_turns)` distances;
- enters close watch after intervention and wakes on the next public cursor until the monitor waits;
- preserves cursors and root-completion proposals that arrive while a review is in flight;
- records monitor failures separately instead of fabricating a silent result.

This controller is the C2 shell. Production process isolation, synopsis/raw-log wiring, real cancellation,
same-session correction delivery, and crash restoration remain C3 integration work.

## Verification

Commands:

```text
D:\python\envs\ga_bench\python.exe -m py_compile monitor_agent.py monitor_agent_workspace.py monitor_controller.py
D:\python\envs\ga_bench\python.exe -m pytest tests -q
```

Results:

- syntax compilation passed;
- 319 repository tests passed in 20.90 seconds;
- 22 new foundation tests cover path confinement, exact patch semantics, disposable analysis views,
  persistent multi-wake history, completion gating, controller nonblocking behavior, autonomous wait
  distance, close watch, in-flight cursor catch-up, in-flight completion preservation, failure recording,
  and composed controller-to-MonitorAgent execution.

No API call, Docker task, native verifier, or hidden checker was used.

## Acceptance against C1

- [x] independent monitor role rather than unchanged GA executor;
- [x] minimal general tool surface with hard task-write isolation;
- [x] one persistent provider session and auditable history measurements;
- [x] natural-language reasoning without legacy stage/schema vocabulary;
- [x] semantic-free, nonblocking controller shell;
- [x] model-selected patrol distance and post-intervention close watch;
- [x] root completion remains a distinct boundary;
- [x] monitor failure does not block or masquerade as silence;
- [x] no online checker/verifier dependency;
- [x] full deterministic repository regression passes.

## Known limits and C3 gate

1. The analysis view is a safe disposable copy, not yet an OS/container read-only live mount. Large task
   workspaces may make refresh expensive; C3 must measure this before choosing the production adapter.
2. The worker is a background thread in C2. C3 must establish the specified independent process/session host
   so provider hangs and crashes are isolated beyond ordinary nonblocking scheduling.
3. C2 action receipts do not yet invoke Task Agent abort or inject corrections. C3 must measure cancellation
   during provider streaming and tool execution, then prove same-session delivery at the next inference.
4. C2 uses GA linear provider history as the declared baseline. It records transformations indirectly through
   history before/after measurements but does not introduce the paper's future memory mechanism.
5. C2 has deterministic engineering evidence only. No claim is made that monitor quality, latency, or task
   success has improved until cumulative integration receives an explicitly approved real-task run.
