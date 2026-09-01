# C3 Pre-Real-Task Engineering Audit

Date: 2026-09-01  
Scope: material launch blockers, Monitor-role adaptation, and unintended GenericAgent coupling

## Verdict

The clean Monitor path is ready for a separately approved real-task connectivity run after the fixes in this
audit. No native checker or verifier enters the online path. The audit deliberately excludes stylistic and
hypothetical issues.

## Material findings and fixes

### 1. Whole-GA import leaked executor dependencies into Monitor

Before: `monitor_agent.py` imported `code_run` from `ga.py`. Importing that module also loads the task
executor, browser support, memory helpers, web utilities, and other unrelated GA machinery.

After: a neutral `process_runner.py` supplies the Monitor's analysis runner. The Task Agent retains its
existing runner unchanged, avoiding a behavioral regression. Import probes confirm that importing
`monitor_agent` and `clean_monitor_runtime` does not load `ga`, `agentmain`, `simphtml`, `TMWebDriver`,
`reflect`, `launch`, or `mykey`.

### 2. GA executor protocol was silently appended to the Monitor system prompt

Before: both text and native tool clients added GA's `<summary>`/long-term-working-memory protocol and the
instruction that unfinished user work must call tools. The text client also removed `content` from the
`file_write` schema, which was incompatible with the Monitor handler.

After: tool clients expose a role. The clean worker selects `monitor`, which retains only the tool-call wire
format and the Monitor's own system prompt. Executor summary, forced-tool, and special file-write conventions
remain confined to the Task Agent.

### 3. Monitor core loaded configuration through `mykey.py`

Before: the isolated worker called `resolve_client(config_name)`, making the Monitor runtime itself load
GA's key/config module.

After: `CleanMonitorRuntime` receives a plain model configuration and the worker uses
`client_from_config`. `mykey.py` remains only in the GA adapter that selects credentials for both agents; it
is not a Monitor capability or runtime dependency. A future non-GA harness can inject an equivalent config
or client without copying `mykey.py`.

### 4. Process isolation used platform-default context

Before: Windows happened to use spawn, but the implementation did not state the isolation contract and
other platforms could fork inherited state.

After: the clean runtime explicitly uses a `spawn` multiprocessing context, matching the intended clean
model session and avoiding inherited GUI/provider/thread state.

### 5. Monitor role prompt was correct but underspecified

The stable prompt now explicitly covers turn-zero task understanding, synopsis-as-navigation rather than
proof, decision-relevant active retrieval, tests as executable interpretations, concrete evidence-based
minimal correction, post-intervention understanding/intent/action/result follow-up, local release versus
root completion, autonomous silence through `wait`, and avoidance of exhaustive UNKNOWN verification.
These are high-level role principles rather than task-specific rules or a rigid schema.

## Dependency audit

### Intentionally retained

- `agent_loop.BaseHandler`, `StepOutcome`, and `agent_runner_loop`: neutral tool/reason loop;
- `llmcore` provider sessions and tool clients: provider transport, history, retry, telemetry;
- explicit model configuration supplied by the GA adapter;
- Task Agent's existing `agentmain.py` only at the integration boundary;
- model-authored Task Agent `<summary>` as Layer-1 navigation when available, with fallback to bounded public
  response content.

### Not inherited by Monitor

- `GenericAgent` or `GenericAgentHandler`;
- GA global memory, working checkpoint, self-evolution/reflect, planner, scheduler, browser, web tools, user
  question tool, task completion behavior, or executor reminders;
- `launch.pyw`, Streamlit, pywebview, or other GUI lifecycle;
- `mykey.py` inside the isolated Monitor process;
- old M0/M1/M2/M3 flags, semantic packet, fixed obligation IDs, or HOLD/SILENT/RELEASE protocol.

## Remaining measured boundaries, not launch blockers

- real relay SSE cancellation latency still requires the first live run;
- already-running short synchronous non-code tools may finish before an asynchronous correction arrives;
- analysis `code_run` refreshes a disposable workspace snapshot, whose cost must be measured on a real task;
- process crash is isolated and recorded, but automatic Monitor history restoration is not yet claimed;
- the first run establishes connectivity and behavior, not paper-level effectiveness.
