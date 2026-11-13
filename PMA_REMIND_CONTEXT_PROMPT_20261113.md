# Context-and-bank reminder prompt

Base: `71fd847571b7e6732c355ed23dea38e2ddedfc41`.

## Authorized change

Only one sentence in `REMIND_FIRST_SYSTEM` changes:

> After receiving its result, consider both the conversation context and the knowledge bank to decide whether to remind the task agent, and what to remind it of, based on its current and upcoming work.

Chinese review wording:

> 收到结果后，结合上下文和知识库，根据任务 Agent 当前和即将进行的工作，判断是否需要提醒它，以及提醒什么。

The bank is still read before the decision, but reminder content is not restricted to information in the bank alone. Original task, available manager conversation history and newly observed Task trajectory are already supplied by the existing implementation. No new context source or new model is introduced.

Initialization still uses the unified remind-first lifecycle, including reading an empty fresh bank and letting the model choose whether to remind. No special initialization branch is added. The eight-turn presentation-value criterion, tools, read-result-before-decision enforcement, frozen reminder, same-session organization, GA-style no-tool organization completion, history handling and faithful code-block transport are unchanged.

## Verification

`test_remind_context_prompt.py` reverses only this exact sentence and checks the whole source SHA256 against the fixed parent, protecting all unrelated production code and prompt wording. A synthetic initialization test checks actual system requests use the new sentence and retain read -> decision -> organization on an empty bank.

- Focused prompt, lifecycle and code-preservation tests: **65 passed** (Linux/Python 3.12).
- Full root tests: **394 passed, 6 failed, 4 subtests passed**. All six failures were independently reproduced on the tree-identical parent (45 passed / 6 failed in the affected files): four old compression-telemetry cases, one old source-file-set assertion, and one obsolete six-turn prompt assertion. An additional candidate-only pinned AST failure was corrected by updating its expected digest for the authorized sentence; its runtime-mutation negative test remains. No production behavior was changed to hide failures.
- Existing pytest/Pydantic warnings remain. No green full-suite or CI claim is made.
- No real Task, PMA model call or native evaluation was run. Windows is not claimed tested.

## Two-task trial scope

Use the existing unified `experiment_runner`, tasks in order `rstan-to-pystan` and `merge-diff-arc-agi-task`, one complete run each, same model/profile/effective parameters as the preceding two-task run. Retain task initialization and four-turn wakes, uncapped Task limits, isolated fresh bank and continuous manager history per task. Do not silently substitute another driver, model or method.

Prioritize observing whether the model naturally follows the two steps: read results before reminder decision; no early writes; no attempt to overwrite the frozen decision; normal organization tool use and no-tool completion; first-wake behavior; protocol/tool/provider errors or forced recovery. Preserve complete visible requests, replies, tool calls/receipts, actual Task reminder delivery, native evaluation and cleanup. Public artifacts may be redacted only at archival export, not during runtime. Upload diagnostic ZIP and per-file index to GitHub, not as chat attachments. No reruns to replace failures. Engineering tests do not establish behavioral effectiveness.

## Exact production system prompt

```text
You are the task's information organizer. Some information that appears during task execution remains valuable much later in the task, while other information only becomes valuable then. Your role is to predict and save this information, and remind the task agent when it is relevant to its current or upcoming work, helping it use existing information to complete the task.

The <task_description> tags contain the task agent's original task, and the <task_trajectory> tags contain the task agent's newly observed execution trajectory.

Carry out these steps in this same conversation:

1. Recall and decide the reminder. Use memory_read to read the existing knowledge bank. After receiving its result, consider both the conversation context and the knowledge bank to decide whether to remind the task agent, and what to remind it of, based on its current and upcoming work. Do not save information yet. End this step with exactly one of:
<context_for_action>
Information to remind the task agent of.
</context_for_action>
<no_intervention/>

2. Predict and save. When the program advances to this step, you must predict which information received this time will still be worth presenting to the task agent to support subsequent task work after the task has progressed for another eight turns, and organize and save that information in the knowledge bank. Before saving, briefly state which information you have selected. The reminder decision has already been recorded and is not changed in this step. Use tools as needed; when finished, reply in ordinary text without a tool call. No completion tag is required. If nothing needs saving, say so in ordinary text.

## Tools
- memory_add: Save information in the knowledge bank; available during step 2.
- memory_read: Read all information currently saved in the knowledge bank. Set bank_id to "knowledge" when calling it.
```
