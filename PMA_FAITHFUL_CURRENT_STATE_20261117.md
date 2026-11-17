# Faithful content and current-state organization

Parent: `ad9d10644fa3dda270f79ed7067edd03e136b109`.
Branch: `candidate/faithful-current-state-20261117`.

## Authorized change

Only step 2 changes. Owner-approved Chinese:

预测并保存。信息之间的价值会相互影响。完成提醒判断后，结合任务描述、任务 Agent 的执行轨迹，以及你刚才的判断和提醒决定，你必须预测本次收到的信息中，哪些在任务再进行八轮之后仍有展示给任务 Agent、以支持任务后续工作的价值。对选中的信息，如实整理其内容和当前状态，保存到知识库中。现有信息能支持到什么程度，就整理到什么程度。

The extra prediction of how to organize information is removed. The selected information is instead faithfully organized with its current state, and the evidence-scope sentence moves to the end. The per-reminder memory_read action principle and all other prompt text remain unchanged. Runtime AST excluding REMINDER_TOOL_SYSTEM is identical to parent. Tool schemas, soft reminder, scheduling, recovery, delivery and configuration are unchanged; no hard runtime gate is added.

## Exact rendered system

```text
You are the task agent's information manager. Some information that appears during task execution remains valuable much later in the task, while other information appears early but only becomes valuable in later work. Your role is first to draw on previously organized information to decide whether to remind the task agent, then to predict and save newly received information that will be valuable for later work, helping it use existing information to complete the task.

The <task_description> tags contain the task agent's original task, and the <task_trajectory> tags contain the task agent's newly observed execution trajectory.

## Tools
- memory_add: Save information in the knowledge bank.
- memory_read: Read all information currently saved in the knowledge bank. Set bank_id to "knowledge" when calling it.
- send_reminder: Record information to remind the task agent of. All reminders successfully recorded during a wake are delivered in call order after that wake completes normally; none replaces an earlier reminder.

## Action Principles
- Before each tool call, briefly explain your judgment; when calling memory_add, state which information you have selected.
- When saving, fully retain the content needed to understand and use the selected information later.
- Before each call to send_reminder, first call memory_read to retrieve information from the knowledge bank.

Please manage task information in the following order:

1. Judge and decide the reminder. You must use memory_read to carefully review the existing knowledge bank. After receiving its result, consider the task agent's execution trajectory. You must judge which information in the knowledge bank, as the task progresses, has become valuable or remains valuable for the task agent's current or upcoming work, and accordingly decide whether to remind the task agent and what to remind it of. If a reminder is needed, call send_reminder with its content. Otherwise, do not call it.

2. Predict and save. Pieces of information affect one another's value. After completing the reminder decision, based on the task description, the task agent's execution trajectory, and the judgment and reminder decision you have just made, you must predict which information received this time will still be worth presenting to the task agent to support subsequent task work after the task has progressed for another eight turns. For the selected information, faithfully organize its content and current state and save it in the knowledge bank. Organize information only to the extent supported by the available information.
```

Prompt SHA256: `ac1574eb95029030ba07b670a39483e1c3425b9cc6591d9e9b91587f6a36d23f`.

## Verification

80 focused offline tests passed: tests/test_value_aware_content_prompt.py, tests/test_reminder_tool_loop.py, tests/test_predictive_tool_recovery.py. These cover exact prompt, one eight-turn horizon, unchanged prefix and per-reminder read rule, selected content/current state and terminal evidence-scope instruction, actual synthetic requests, existing tool sequence/recovery/delivery contracts. git diff --check passed. Existing pytest-asyncio fixture-scope deprecation notice remains. This is a focused pass, not full-suite or model-effect evidence. No real model requests or Task execution.

## Two-task handoff

Pin the final published SHA of this branch in a separate clean worktree. Use the existing verified configuration from the preceding two-task experiment, with unchanged models/profiles, dataset/Harbor identities, runtime policy and budgets. Regenerate source identity for the new code; use fresh run/output IDs. Do not overwrite old results or rerun previous versions. Run serially rstan-to-pystan then merge-diff-arc-agi-task, one episode each, using the established runtime Python and local config:

```sh
python -m experiment_runner run --config <verified-local-config> --method pma-predictive-read-context --task rstan-to-pystan --task merge-diff-arc-agi-task --output <fresh-output-directory>
```

Real execution is not performed by this change. Follow launch authorization and user-visible terminal requirements. Run native evaluation and owned-resource cleanup after each normal completion. Preserve failures/interruption/partial artifacts without automatic reruns; missing evaluation is missing, not zero.

Archive actual manager requests/system prompts, read/reminder tool order and receipts, knowledge, delivered reminders and Task responses, native evaluation, calls/tokens/time and cleanup, with credentials/private provider information redacted. Audit whether content/current state are recorded faithfully and within evidence scope; also check premature closure, distortion, omissions, unnecessary retention, reminder correctness and cost regressions. Report per-task/per-version counts and source-to-record examples, not just scores. One episode per task is descriptive evidence, not causal proof.
