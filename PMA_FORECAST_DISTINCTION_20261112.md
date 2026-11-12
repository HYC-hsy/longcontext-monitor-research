# PMA forecast distinction in the public explanation (2026-11-12)

Base: `76b4181717cdf66c5b54fe74f3d07ca9efb52b7d`.

Only the first numbered paragraph of the production `UNIFIED_SYSTEM` changes. Before saving, the organizer must briefly explain which information it considered and how it will be used, distinguishing confirmed findings from tentative inferences; it saves only confirmed findings. This moves the distinction into the requested public explanation instead of leaving it only as a general selection rule.

Only the corresponding prompt tests are updated. Four-turn configurable wakes, the second recall paragraph, tool schemas, history, tool execution, final tags, recovery, initial wake and no trailing wake remain unchanged. Per-wake reading and the distinction are prompt requirements, not new runtime gates.

## English system prompt

```text
You are the task agent's information organizer, responsible for organizing and preserving information it will need in the future and reminding it when that information is relevant to its current work.

The <task_description> tags contain the task agent's original task, and the <task_trajectory> tags contain the task agent's newly observed execution trajectory.

Based on the task description and the task agent's trajectory, carry out the following steps:

1. Predict and save. You must predict which information received this time the task agent will first use only after at least ten task-agent turns have passed. Before saving, you must briefly explain which information you considered and how it will be used in the future, distinguishing confirmed findings from tentative inferences. Save only confirmed findings.

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

1. 预测并保存。你必须预测本次收到的信息中，哪些至少在任务 Agent 执行十轮之后才会首次用到。保存前，你必须简短说明考虑了哪些信息、它们未来将如何使用，并区分已经确认的发现和暂时的推断。只保存已经确认的发现。

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

## Conditional reminder stays unchanged / 条件软提醒保持原样

```text
You must include a brief public summary of the information you plan to preserve and how you anticipate it will be useful in work after ten task-agent turns have passed.
```

The reminder contains **no new explicit requirement to distinguish confirmed findings from tentative inferences**. That requirement is in the base system prompt. 本次没有同步修改条件软提醒；它仍只要求简述准备保存的信息及未来用途，没有新增区分已确认发现与暂时推断的要求。

## Verification boundary

Targeted offline checks: **148 passed, 3 warnings**; `git diff --check` passed. The test selection covers coherent prompt/request construction, task input labels, memory reading, tool recovery, visible explanations, unified execution, lifecycle and wiring.

No real Task, model request or native evaluation was run. Offline tests cannot prove that the model consistently makes the distinction or improves research outcomes. Ten turns remains the existing forecast instruction, not a retrospective hard scoring threshold or a reminder waiting period.
