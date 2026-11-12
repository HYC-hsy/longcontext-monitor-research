# PMA confirmed findings and per-wake recall (2026-11-12)

Base: `5dc85672dd747af2ff26495462a7432583154084`.

## Changes / 改动

- Default predictive-PMA wake interval: 8 → 4 Task turns. `pma_batch_rounds` / `--pma-batch-rounds` remains a positive configurable integer; an explicit 8 remains supported. Initial wake and no trailing completion wake remain unchanged.
- Prompt: require distinguishing confirmed findings from tentative inferences and saving only confirmed findings. Ten-turn future-use prediction remains unchanged.
- Prompt: read `knowledge` on every wake and return relevant information for the Task Agent's next turn, rather than separately deciding whether a reminder is needed.
- Tool schemas, conditional public-summary reminder, continuous history, tag parsing, tool execution and recovery logic remain unchanged. Reading on every wake is a **prompt requirement**, not a new runtime enforcement gate.

默认唤醒周期改为四轮，仍可显式配置其他正整数周期。首次唤醒、任务结束不补尾部唤醒的行为不变。保存阶段只记录已确认的发现；召回阶段每次唤醒查库，将当前相关信息交给 Task Agent 下一轮。没有新增工具、验证器或强制查库门禁。四轮是唤醒周期，十轮是预测提示，两者独立。

## Verification / 验证

Combined offline suite: **226 passed, 3 warnings**. Targeted final-prompt suite: **130 passed** (overlapping coverage, not additive). `git diff --check` passed.

Two historical eight-turn test fixtures were changed to explicitly request eight turns, preserving their original meaning with the new default. Sparse-checkout support files were restored from the base commit to run tests; these restorations are not content changes in this commit.

No real Task, PMA API request or native evaluation was run for this release. Offline passing does not establish research effectiveness, accurate memory selection, mandatory tool usage, or successful reminder uptake. This candidate changes three things together; a single later comparison cannot isolate their causal contributions.

## Actual English system prompt

```text
You are the task agent's information organizer, responsible for organizing and preserving information it will need in the future and reminding it when that information is relevant to its current work.

The <task_description> tags contain the task agent's original task, and the <task_trajectory> tags contain the task agent's newly observed execution trajectory.

Based on the task description and the task agent's trajectory, carry out the following steps:

1. Predict and save. You must predict which information received this time the task agent will first use only after at least ten task-agent turns have passed, and organize and save that information. You must distinguish confirmed findings from tentative inferences, and save only confirmed findings. Before using memory tools, you must briefly state which information you plan to preserve and how you anticipate it will be useful in work after ten task-agent turns have passed.

2. Recall relevant information. On every wake, use memory_read with bank_id="knowledge" to read the knowledge bank. From the returned information, select what is relevant to the task agent's current work and provide it briefly and directly for its next turn. If there is no relevant information, provide none. Do not take over the task agent's work.

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

1. 预测并保存。你必须预测本次收到的信息中，哪些至少在任务 Agent 执行十轮之后才会首次用到，并整理保存这些信息。你必须区分已经确认的发现和暂时的推断，并且只能保存已经确认的发现。使用记忆工具前，你必须简短说明准备保存哪些信息，以及预计它们在任务 Agent 十轮之后的工作中如何用到。

2. 召回相关信息。每次唤醒时，使用 memory_read 并将 bank_id 设为 knowledge，查看知识库。从返回的信息中选出与任务 Agent 当前工作相关的内容，简短、直接地交给它，供下一轮参考。如果没有相关信息，则不提供。不要接管任务 Agent 的工作。

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

## Unchanged conditional public-summary reminder / 保持不变的条件软提醒

```text
You must include a brief public summary of the information you plan to preserve and how you anticipate it will be useful in work after ten task-agent turns have passed.
```

中文：你必须简短说明准备保存的信息，以及预计它们在任务 Agent 十轮之后的工作中如何用到。
