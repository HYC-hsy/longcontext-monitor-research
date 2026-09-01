# C4 Monitor Agent Source-Independence Migration Report (2026-09-01)

## Goal

Migrate the clean Monitor Agent from runtime isolation with GenericAgent source reuse to a complete,
independently evolvable Agent implementation. GenericAgent retains only a thin adapter for public task
events, resumable interruption, and completion-boundary type conversion.

## Independent core

`GenericAgent-main/monitor_agent_core/` owns:

- the monitor role, tools, deliberation, and control actions;
- Anthropic Messages and OpenAI Responses/Chat provider transport;
- canonical provider history, usage records, and baseline history compaction;
- the private workspace and task-evidence view;
- general analysis execution;
- process isolation, two-layer public archives, patrol scheduling, intervention, and completion review;
- monitor-owned action and tool-result types.

The core package does not import `ga`, `agentmain`, `agent_loop`, `llmcore`, `mykey`,
`research_runtime`, `experiment_conditions`, or GenericAgent GUI, Web, Reflect, and self-evolution code.

## GenericAgent adapter

`GenericAgent-main/ga_monitor_adapter.py` is the only GenericAgent-specific boundary. It creates the
independent runtime, forwards public observations, connects resumable interruption, converts completion
outcomes, and closes the monitor process. GenericAgent resolves model configuration into a plain dictionary;
the core never reads `mykey.py`.

## Removed duplicate implementation

- `monitor_agent.py`
- `monitor_agent_workspace.py`
- `monitor_controller.py`
- `clean_monitor_runtime.py`
- root `process_runner.py`
- `tests/test_monitor_controller.py`

## Verification boundary

- Automated AST checks reject forbidden GenericAgent imports from the core.
- A clean-process import test verifies that importing the core does not load forbidden modules.
- Provider, history, tool loop, workspace, runtime, and adapter behavior have deterministic tests.
- Real-task effectiveness still requires the independent real-run gate and cannot be inferred from
  engineering tests.

## Current decisions

- By user decision, `code_run` remains a local general executor. It starts in the private monitor directory
  and receives `.task_view`, but this version does not claim a hard filesystem sandbox.
- The monitor defaults to `gpt-5.6-sol` with high reasoning. The independent provider passed a minimal live
  connectivity check.
- The provider uses a wide-window engineering compaction baseline. This baseline is not the paper's final
  memory mechanism.

This stage establishes source independence and engineering integration only. It does not freeze M3 or claim
formal experimental evidence.
