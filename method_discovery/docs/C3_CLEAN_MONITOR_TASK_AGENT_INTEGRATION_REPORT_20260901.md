# C3 Clean Monitor–Task Agent Integration Report

Date: 2026-09-01  
Status: deterministic engineering integration complete; real provider/task validation not started

## Goal

Connect the C2 clean Monitor Agent to GenericAgent using the old monitor's proven public attachment points,
while replacing delayed next-turn queue delivery with resumable cancellation and same-session correction.
The integration must retain asynchronous ordinary execution and exactly two task-observation layers.

## Implemented control path

```text
Task Agent publishes intent before tool execution
  -> append bounded synopsis + original public event
  -> isolated Monitor process autonomously wakes according to its own wait distance
  -> Monitor inspects synopsis, raw events, tests, diff, artifacts, or workspace as needed
  -> intervene(message)
  -> immediately cancel an active provider response and/or running code process
  -> prevent an announced but not-yet-started tool from executing
  -> append correction to the same Task Agent provider history
  -> close-watch every newly published event until Monitor calls wait
```

Root completion remains a distinct controlled boundary. Ordinary turns do not synchronously wait for the
monitor. User Stop still terminates the whole task, whereas monitor interruption cancels only the current
action and resumes the same task.

## Reused versus replaced

Reused from the historical wiring:

- `post_model_pre_tool` and `post_tool_pre_next_llm` public attachment points;
- append-only task-side archiving;
- separate monitor process and failure isolation;
- same Task Agent session as the correction destination;
- independent root-completion callback.

Replaced:

- old `M0DeliberativeMonitor` with the clean `MonitorAgent`;
- semantic review packets with `synopsis.jsonl` plus `public_events.jsonl`/live workspace;
- delayed intervention queue consumption with `ResumableInterruption`;
- cursor-count patrol timing with actual Task Agent turn distance;
- legacy semantic action/schema protocol with natural-language reasoning and three terminal actions.

## Engineering changes

- `task_interruption.py`: ordered, thread-safe resumable correction mailbox.
- `llmcore.py`: active provider responses expose best-effort immediate cancellation; intentional cancellation
  is distinct from transport failure and is never retried.
- `agent_loop.py`: consumes monitor corrections before inference, resumes after cancellation without
  resending the root task, and skips an announced tool when correction arrives before dispatch.
- `agentmain.py`: clean runtime activation, monitor/user interruption separation, external artifact placement,
  and completion-boundary wiring.
- `clean_monitor_runtime.py`: process-isolated monitor host, two-layer archive, autonomous patrol scheduling,
  close-watch delivery, failure receipts, and completion decisions.
- `monitor_agent_workspace.py`: named read-only live-workspace mount in addition to immutable task evidence.

## Verification

```text
D:\python\envs\ga_bench\python.exe -m py_compile agent_loop.py agentmain.py llmcore.py \
  task_interruption.py monitor_agent.py monitor_agent_workspace.py monitor_controller.py \
  clean_monitor_runtime.py
D:\python\envs\ga_bench\python.exe -m pytest tests -q
```

Result: 328 tests passed in 21.81 seconds in the final pre-commit suite.

New deterministic evidence covers:

- archive publication remains nonblocking;
- synopsis and original public event remain separate layers;
- monitor correction is delivered immediately through the resumable mailbox;
- a cancelled provider response is not treated as a retryable failure;
- cancellation outside a provider call does not poison the next corrected inference;
- an announced tool is prevented when correction arrives before dispatch;
- same-loop continuation receives the correction without duplicating the original root task;
- analysis code cannot mutate live task evidence;
- completion uses a separate `allow_complete|continue` boundary;
- artifacts cannot be nested inside the supervised workspace.

## Limits requiring gated validation

1. Cross-thread `response.close()` is the strongest cancellation supported by the current HTTP stack, but a
   relay blocked before a response object exists remains bounded by connect timeout. Real-provider latency
   must be measured before claiming hard real-time cancellation.
2. Generic synchronous tools cannot be preempted safely from another Python thread. The integration prevents
   tools not yet dispatched and actively stops GA `code_run`; quick already-running file operations may finish
   before the correction arrives. This is an observable latency boundary, not hidden synchronous approval.
3. The live workspace is read authoritatively through `file_read`; `code_run` still refreshes a disposable
   snapshot. Large-workspace snapshot cost must be measured and may motivate an OS/container read-only mount.
4. No real API, Docker task, checker, verifier, or outcome claim is part of C3 engineering acceptance. The
   first cumulative real-task run remains separately gated by the user.
