# Continued judgment and read-before-reminder prompt candidate

Parent: `235711cd2929127e946beeea1b73f279bb6f9295`.

## Authorized scope

Only two prompt changes: add the action principle requiring memory_read before each send_reminder; replace step 2 with the owner-authored wording below (translated to English for the existing runtime). This remains prompt guidance, not a hard runtime gate. Read-before-reminder applies to each reminder, including multiple reminders in one wake.

预测并保存。信息之间的价值会相互影响。现有信息能支持到什么程度，就整理到什么程度。完成提醒判断后，你必须结合任务描述、任务 Agent 的执行轨迹，以及刚才的判断和提醒决定，预测本次收到的信息中，哪些在任务再进行八轮后仍值得展示给任务 Agent，以支持其后续工作；同时预测怎样整理这些信息，最有助于它据此继续判断、推进任务。根据这些预测，整理信息并保存到知识库中。

New action principle: 每次调用 send_reminder 前，先调用 memory_read 获取知识库中的信息。

All other system text, conditional soft reminder, tool schemas, loop/recovery/completion behavior, scheduling, and runtime configuration are unchanged. Runtime AST excluding REMINDER_TOOL_SYSTEM is identical to parent. No real provider request or Task was started for this change.

## Exact rendered system prompt

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

2. Predict and save. Pieces of information affect one another's value. Organize information only to the extent supported by the available information. After completing the reminder decision, you must consider the task description, the task agent's execution trajectory, and the judgment and reminder decision you have just made, and predict which information received this time will still be worth presenting to the task agent after another eight turns to support its subsequent work; at the same time, predict how to organize this information to best help it use the information to continue making judgments and advance the task. Based on these predictions, organize the information and save it in the knowledge bank.
```

Prompt UTF-8 SHA256: `6f86816941c8730e85ff9bd82e799d70f7115a13b683af519b3911f3b70a8ab4`.

## Offline verification

79 targeted tests passed (test_value_aware_content_prompt.py, test_reminder_tool_loop.py, test_predictive_tool_recovery.py). Coverage: exact step-2 wording, exactly one eight-turn horizon, otherwise unchanged prefix, actual synthetic requests and soft reminder, read/remind/read/remind sequence and receipts, existing no-hard-gate/recording/delivery/recovery contracts. These are synthetic model replies, not evidence of actual compliance or effectiveness.

Initial environment attempts failed because pytest/shortuuid and Harbor package metadata were absent, then because the dependency tried to load its online cost map. Tests passed after installing dependencies in an isolated test environment, installing the vendored Harbor package with --no-deps, and setting LITELLM_LOCAL_MODEL_COST_MAP=True. Assertions were not relaxed and no failing tests were deselected. Existing pytest-asyncio fixture-scope deprecation notice remains. Final git diff --check passed. This is a focused check, not a full-suite pass.

## Two-task execution handoff (prepared, not executed here)

Pin the final published commit on candidate/continued-judgment-read-20261117 in a separate clean worktree; preserve old code/results. Reuse the exact local configuration/profile/model/dataset/Harbor and runtime limits of the prior 235711 two-task batch. Dataset 2fd12b88aafdd04a52c298e3940bcb189f9766d6; Harbor 459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc. Regenerate source identity for this candidate; do not copy the old source hash. Change only source revision and fresh output/run IDs. Run serially, rstan-to-pystan then merge-diff-arc-agi-task, once each. Do not rerun prior versions, add tasks, retry a started task automatically, or change limits to force completion.

Using the target machine's established runtime Python and verified local config path (experiment.local.json below is a placeholder):

```sh
python -m experiment_runner run --config experiment.local.json --method pma-predictive-read-context --task rstan-to-pystan --task merge-diff-arc-agi-task --output runs/continued-judgment-read-two-UNIQUE
```

Run only with the owner's launch approval in a user-visible running terminal. After each normal completion run native evaluation and owned-resource cleanup. Missing evaluation is missing, not zero. Preserve failures/interruption and partial artifacts without silently rerunning. Archive actual manager requests/system text, memory_read/send_reminder call order and receipts, knowledge entries, reminders actually delivered to Task, Task trajectory, evaluation, usage/time and cleanup; redact credentials/private provider material when uploading.

Audit both intended improvements and regressions: per-reminder retrieval and actual use of returned information; preservation of evidence scope/unfinished judgments; premature closure and factual distortion; useful information omissions and unnecessary retention; reminder correctness and Task uptake; calls/tokens/time. Retain per-task/per-version counts and concrete source-to-record examples. Two tasks once each are descriptive evidence, not causal proof. As both step-2 wording and read guidance change, do not attribute effects separately without further evidence.
