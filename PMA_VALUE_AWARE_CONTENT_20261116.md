# Value-aware content organization prompt candidate

Parent: `381f0658ddeab49c824d276953cb254cf7f1eb37`.
Status: implemented and offline-tested; no real model, Task, Docker, or native evaluation run.

## Authorized scope

Only step 2 of the native reminder-tool manager system prompt changes:

1. Add the relationship between judgments/organization and the subsequent value of this and other information.
2. Ask the manager to predict what content to produce when organizing selected information for greatest subsequent task value.

The eight-turn selection horizon, original-task context, reminder-first order, public tool-call explanations, full content retention requirement, conditional forecast soft reminder, tool schemas, retries, wake-completion logic, Task-readable knowledge file, models, and runtime configuration are unchanged. No additional confirmation checklist or hard gate was introduced.

Approved Chinese step 2:

> 预测并保存。对信息的判断和整理，可能影响它以及其他信息在后续工作中的价值。完成提醒判断后，结合任务描述、任务 Agent 的执行轨迹，以及你刚才的判断和提醒决定，你必须预测本次收到的信息中，哪些在任务再进行八轮之后仍有展示给任务 Agent、以支持任务后续工作的价值，并预测将这些信息整理成什么内容对任务后续工作最有价值，再保存到知识库中。

## Exact rendered English system prompt

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

Please manage task information in the following order:

1. Judge and decide the reminder. You must use memory_read to carefully review the existing knowledge bank. After receiving its result, consider the task agent's execution trajectory. You must judge which information in the knowledge bank, as the task progresses, has become valuable or remains valuable for the task agent's current or upcoming work, and accordingly decide whether to remind the task agent and what to remind it of. If a reminder is needed, call send_reminder with its content. Otherwise, do not call it.

2. Predict and save. Judging and organizing information may affect its value and the value of other information for subsequent work. After completing the reminder decision, based on the task description, the task agent's trajectory, and the judgment and reminder decision you have just made, you must predict which information received this time will still be worth presenting to the task agent to support subsequent task work after the task has progressed for another eight turns, and predict what content to produce when organizing that information to make it most valuable for subsequent task work, then save it in the knowledge bank.
```

UTF-8 SHA256 (includes final newline): `ee0c666852482e02f4da4e5cecd83e7b0b9209a45e1304ec03c0f6ecd87884fa`.

Conditional soft reminder remains:

```text
Briefly state which information you have selected that you predict will still be worth presenting to the task agent to support subsequent task work after the task has progressed for another eight turns.
```

## Offline verification

- 78 tests passed: `tests/test_value_aware_content_prompt.py`, `tests/test_reminder_tool_loop.py`, `tests/test_predictive_tool_recovery.py`.
- New tests check the unchanged prefix against the exact parent SHA, exact step 2 text, one eight-turn horizon, actual mock-request system text, unchanged soft reminder, and normal wake completion.
- The runtime module AST excluding only `REMINDER_TOOL_SYSTEM` is identical to the parent: no tool, loop, retry, or completion change.
- `git diff --check` passed.
- Tests used Python 3.12 on Linux, existing network-blocking fixtures and synthetic provider replies. `LITELLM_LOCAL_MODEL_COST_MAP=True` prevents LiteLLM's import-time price-map fetch.
- Initial environment attempts failed for missing test/provider dependencies and Harbor package metadata. After installing dependencies and the vendored Harbor package into a temporary test directory, the import-time price-map fetch was blocked by the existing test guard; the local-map setting resolved it. No production code or test assertion was relaxed for these environment failures.
- The new snapshot test initially expected one extra trailing newline; its expectation was corrected to match the parent's preserved single final newline, without changing the runtime newline.

## Real-run handoff scope

Run only the new candidate, sequentially, once each: `rstan-to-pystan`, then `merge-diff-arc-agi-task`, with the same unified runner, dataset/task identities, Task and manager model configuration, images and effective runtime settings as the parent two-task run. Reuse parent results instead of rerunning the old condition. Archive actual complete prompt requests and public trajectories, tools/receipts, knowledge records, native evaluation and cleanup evidence. Do not auto-retry a failed task or count missing evaluation as zero.

Later independent audit should examine both regression and intended gains: preservation of useful facts, constraints, tentative ideas and timely reminders; prediction of what content is useful to preserve; unsupported completion/root-cause/generalization, record distortion, omissions and unnecessary retention. Report per-task/version knowledge-record totals and overlapping issue categories. Single runs cannot establish causal gains, and public explanation changes alone are not proof of improved judgment.
