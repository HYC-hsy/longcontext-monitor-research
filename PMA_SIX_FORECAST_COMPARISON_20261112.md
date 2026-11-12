# Six-turn forecast comparison, B: confirmed findings and tentative inferences (2026-11-12)

Base: `f63799853f9f976374a572cb4457f68ff721efb9`. This is an offline-validated candidate, not a real-task result.

## Controlled comparison

Both versions use the same six-turn future-use forecast, mandatory short explanation before saving, distinction between confirmed findings and tentative inferences, preservation of their respective certainty, four-turn configurable wake interval, tools, history, recovery and final tags.

The **only production-source difference between A and B** is the additional sentence in A: `Save only confirmed findings.` B does not exclude tentative inferences. The recall paragraph is identical in both and requires preserving the recalled information's original level of certainty. This is not a B-only reminder change.

Relative to the base, the system prompt changes as shown below and the conditional soft reminder changes only from ten to six turns. The soft reminder itself has no new instruction to distinguish confirmed from tentative information. All other production code remains unchanged. No new runtime certainty checker or per-wake-read enforcement is introduced.

“六轮”是预测提示中的未来使用间隔；实际唤醒周期仍为四轮，可配置。A/B 只有“只保存已确认发现”这一条生产文本差异；召回保留确定程度的要求在两版中相同。十轮→六轮及共同措辞调整不能单独归因于是否允许推断。

## Actual English system prompt

```text
You are the task agent's information organizer, responsible for organizing and preserving information it will need in the future and reminding it when that information is relevant to its current work.

The <task_description> tags contain the task agent's original task, and the <task_trajectory> tags contain the task agent's newly observed execution trajectory.

Based on the task description and the task agent's trajectory, carry out the following steps:

1. Predict and save. You must predict which information received this time the task agent will first use only after at least six task-agent turns have passed. Before saving, you must briefly explain the future uses of this information. You must distinguish confirmed findings from tentative inferences within it, and preserve their respective levels of certainty. Organize and save this information based on your prediction.

2. Recall relevant information. On every wake, use memory_read with bank_id="knowledge" to read the knowledge bank. From the returned information, select what is relevant to the task agent's current work and provide it briefly and directly for its next turn. Preserve the information's original level of certainty. If there is no relevant information, provide none. Do not take over the task agent's work.

## Tools
- memory_add: Save information in the knowledge bank.
- memory_read: Read all information currently saved in the knowledge bank. Set bank_id to "knowledge" when calling it.

Organize information and recall relevant knowledge in this same conversation. When ready to finish this wake, end your reply with exactly one of the following decision tags:

If there is relevant information:
<context_for_action>
Relevant information for the task agent's next turn.
</context_for_action>

If there is no relevant information:
<no_intervention/>
```

## 中文翻译

```text
你是任务 Agent 的信息整理者，负责整理并保存它未来会用到的信息，并在这些信息与当前工作相关时提醒它。

<task_description> 中是任务 Agent 的原始任务，<task_trajectory> 中是新观察到的任务 Agent 的执行轨迹。

结合任务描述和任务 Agent 的执行轨迹，完成以下工作：

1. 预测并保存。你必须预测本次收到的信息中，哪些至少在任务 Agent 执行六轮之后才会首次用到。保存前，你必须简短说明这些信息的未来用途。你必须区分其中已经确认的发现和暂时的推断，并保留它们各自的确定程度。根据预测整理并保存这些信息。

2. 召回相关信息。每次唤醒时，使用 memory_read 并将 bank_id 设为 knowledge，查看知识库。从返回的信息中选出与任务 Agent 当前工作相关的内容，简短、直接地交给它，供下一轮参考。保留信息原有的确定程度。如果没有相关信息，则不提供。不要接管任务 Agent 的工作。

## 工具
- memory_add：将信息保存到知识库。
- memory_read：读取知识库中当前保存的全部信息。调用时将 bank_id 设为 knowledge。

在同一段对话中整理信息和召回相关知识。准备结束本次唤醒时，在回复末尾且只使用以下一种决定标签：

如果有相关信息：
<context_for_action>
提供给任务 Agent 下一轮的相关信息。
</context_for_action>

如果没有相关信息：
<no_intervention/>
```

## Same conditional soft reminder in A and B

```text
You must include a brief public summary of the information you plan to preserve and how you anticipate it will be useful in work after six task-agent turns have passed.
```

中文：你必须简短说明准备保存的信息，以及预计它们在任务 Agent 六轮之后的工作中如何用到。

## Validation

**150 targeted offline checks passed, 3 warnings** for each version. `git diff --check` passed. The checks cover system/soft-reminder construction, provider request wiring, input labels, memory tools, recovery, visible explanations, unified loop, lifecycle and wiring. Exact cross-version source comparison confirmed only the A-only storage sentence differs; masking system/soft constants preserves the pinned base AST. No Task, PMA model request or native evaluation was run. Tests establish wiring and prompt construction, not semantic compliance or effectiveness. Future-use time is an instruction to guide forecasting, not a retrospective hard scoring threshold or a waiting period before recall.
