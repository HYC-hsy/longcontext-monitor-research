# Evidence scope in each tool judgment

Parent: `dbb02f219552f4017286012a2fc8f7849e1213e5`.
Branch: `candidate/tool-judgment-scope-20261117`.

## Approved change

The action principle now reads: 每次调用工具前，简短说明你的判断，以及现有信息能支持到什么程度；调用 memory_add 时，说明你选择了哪些信息。

The former terminal step-2 sentence (现有信息能支持到什么程度，就整理到什么程度) is removed. Everything else remains unchanged, including faithful content/current-state organization, the eight-turn horizon, and reading knowledge before every reminder. No hard gate, tool schema, recovery, scheduling, delivery or configuration changes. Temperature remains 1 in the execution handoff, not a new source/profile modification.

## Exact rendered system

```text
You are the task agent's information manager. Some information that appears during task execution remains valuable much later in the task, while other information appears early but only becomes valuable in later work. Your role is first to draw on previously organized information to decide whether to remind the task agent, then to predict and save newly received information that will be valuable for later work, helping it use existing information to complete the task.

The <task_description> tags contain the task agent's original task, and the <task_trajectory> tags contain the task agent's newly observed execution trajectory.

## Tools
- memory_add: Save information in the knowledge bank.
- memory_read: Read all information currently saved in the knowledge bank. Set bank_id to "knowledge" when calling it.
- send_reminder: Record information to remind the task agent of. All reminders successfully recorded during a wake are delivered in call order after that wake completes normally; none replaces an earlier reminder.

## Action Principles
- Before each tool call, briefly explain your judgment and the extent to which the available information supports it; when calling memory_add, state which information you have selected.
- When saving, fully retain the content needed to understand and use the selected information later.
- Before each call to send_reminder, first call memory_read to retrieve information from the knowledge bank.

Please manage task information in the following order:

1. Judge and decide the reminder. You must use memory_read to carefully review the existing knowledge bank. After receiving its result, consider the task agent's execution trajectory. You must judge which information in the knowledge bank, as the task progresses, has become valuable or remains valuable for the task agent's current or upcoming work, and accordingly decide whether to remind the task agent and what to remind it of. If a reminder is needed, call send_reminder with its content. Otherwise, do not call it.

2. Predict and save. Pieces of information affect one another's value. After completing the reminder decision, based on the task description, the task agent's execution trajectory, and the judgment and reminder decision you have just made, you must predict which information received this time will still be worth presenting to the task agent to support subsequent task work after the task has progressed for another eight turns. For the selected information, faithfully organize its content and current state and save it in the knowledge bank.
```

Prompt UTF-8 SHA256: `d9d47c8ea9b59229eaabec14d5a609395dd290666f7a7f600759a4cf9624a3f7`.

## Verification

80 focused offline tests passed: tests/test_value_aware_content_prompt.py, tests/test_reminder_tool_loop.py, tests/test_predictive_tool_recovery.py. Exact wording, unchanged residual prefix/step, single eight-turn horizon, actual synthetic requests, unchanged soft reminder/read-before-reminder rule and tool/recovery/delivery contracts are covered. Runtime AST excluding REMINDER_TOOL_SYSTEM equals parent. git diff --check passed. Existing pytest-asyncio deprecation warning remains. This is not a full-suite result or evidence of model compliance/effectiveness. No real model requests or Task execution.

## Two-task handoff (instructions only)

Pin the final published commit on this branch in a separate clean worktree. Reuse the preceding verified two-task model/profile/dataset/Harbor/runtime configuration, keep temperature 1, and change only code/source identity plus fresh run/output IDs. Confirm the actual temperature/configuration before launch rather than silently replacing profiles. Do not rerun old versions, expand the task list, change limits or automatically retry a started episode.

Run serially rstan-to-pystan then merge-diff-arc-agi-task, each once, using the established local runtime:

```sh
python -m experiment_runner run --config <verified-local-config> --method pma-predictive-read-context --task rstan-to-pystan --task merge-diff-arc-agi-task --output <fresh-output-directory>
```

Respect launch authorization and user-visible terminal requirements. Native evaluation and owned-resource cleanup follow each normal completion. Preserve failures/interruption and partial artifacts; missing evaluation is missing, not zero. Upload redacted actual prompts/requests, read/reminder order and receipts, knowledge, delivered reminders, Task trajectory, evaluation, calls/tokens/time and cleanup.

Audit whether pre-tool explanations correctly represent available support, rather than merely adding a phrase; inspect reminder correctness, knowledge fidelity and current state, premature closure, omissions, redundant retention and cost/regression. Report per-task/per-version counts plus source-to-record examples. Two tasks once each are descriptive evidence, not causal proof.
