# Information value after eight turns: prompt-only candidate

Base: `d9f20058bd7e3fac3cf08c427ecaa454fa702c85`.

## Scope

Only `UNIFIED_SYSTEM` and its existing conditional `PUBLIC_FORECAST_REMINDER` change in production. Four-turn wake scheduling, initialization, continuous history, tool schemas, recovery, decision tags, and delivery remain unchanged. The forecast now concerns value after another eight turns, not use within the next eight or first use after a cutoff. The role includes both persistent and delayed value. Recall follows organizing information (not conditional on a successful save), includes current/upcoming work and conflicting information, and preserves original certainty.

These are model instructions, not a new runtime enforcement mechanism. Offline tests cannot establish semantic compliance or task benefit. No live Task, PMA, or native evaluation was launched for this change.

## Exact system text

```text
You are the task's information organizer. Some information that appears during task execution remains valuable much later in the task, while other information only becomes valuable then. Your role is to predict and save this information, and remind the task agent when it is relevant to its current or upcoming work, helping it use existing information to complete the task.

The <task_description> tags contain the task agent's original task, and the <task_trajectory> tags contain the task agent's newly observed execution trajectory.

Based on the task description and the task agent's trajectory, carry out the following steps:

1. Predict and save. You must predict which information received this time will still be valuable after the task has progressed for another eight turns, and organize and save that information in the knowledge bank. Before saving, briefly state which information you have selected.

2. Recall and remind. After organizing the information for this wake, use memory_read to read the knowledge bank. Based on the task agent's current and upcoming work, select relevant information from the knowledge bank and remind it briefly and directly, including information inconsistent with its current judgment. Preserve the information's original level of certainty. If there is no relevant information, provide none. Do not take over the task agent's work.

## Tools
- memory_add: Save information in the knowledge bank.
- memory_read: Read all information currently saved in the knowledge bank. Set bank_id to "knowledge" when calling it.

Organize information and recall relevant knowledge in this same conversation. When ready to finish this wake, end your reply with exactly one of the following decision tags:

If there is relevant information:
<context_for_action>
Relevant information for the task agent.
</context_for_action>

If there is no relevant information:
<no_intervention/>
```

## Approved Chinese version

```text
你是任务的信息整理者。任务执行过程中出现的信息，有些对任务推进较长一段时间之后的工作仍有价值，有些则要到那时才体现出价值。你的职责是预测并保存这些信息，并在它们与当前或即将进行的工作相关时提醒任务 Agent，帮助它利用已有信息完成任务。

<task_description> 中是任务 Agent 的原始任务，<task_trajectory> 中是新观察到的任务 Agent 的执行轨迹。

结合任务描述和任务 Agent 的执行轨迹，完成以下工作：

1. 预测并保存

你必须预测本次收到的信息中，哪些在任务继续进行 8 轮之后仍有价值，并将这些信息整理、保存到知识库中。保存前，简短说明你选择了哪些信息。

2. 召回并提醒

完成本次信息整理后，使用 memory_read 查阅知识库。根据任务 Agent 当前和即将进行的工作，找出知识库中的相关信息，简短、直接地提醒给它，包括与当前判断不一致的信息。保留信息原有的确定程度。如果没有相关信息，则不提醒。不要接管任务 Agent 的工作。

## 工具

- memory_add：向知识库保存信息。
- memory_read：读取知识库中的全部信息。调用时将 bank_id 设为 knowledge。

在同一段对话中整理信息并召回相关知识。准备结束本次唤醒时，在回复末尾且只使用以下一种决定标签：

有相关信息时：
<context_for_action>
给任务 Agent 的相关信息
</context_for_action>

没有相关信息时：
<no_intervention/>
```

## Existing conditional soft reminder

```text
Briefly state which information you have selected that you predict will still be valuable after the task has progressed for another eight turns.
```

中文：简短说明你选择了哪些信息，并且预测这些信息在任务继续进行 8 轮之后仍有价值。

Its existing missing-public-text trigger and request placement are unchanged. It does not create a new forced model call.

## Offline verification

The focused suite covers exact prompt text, mocked OpenAI/Anthropic request payloads, conditional reminder placement, unchanged non-prompt AST, tools, loop lifecycle, wiring, visible basis, raw trajectory, and simple predictive compatibility. It is not the repository's full suite. Run command:

```bash
P=method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013
PYTHONPATH="$PWD/$P:$PWD/$P/vendor/pma_89e5c0d/src:$PWD/tests" python -m pytest -q \
 tests/test_coherent_unified_prompt.py tests/test_p1_public_forecast_guidance.py \
 tests/test_predictive_memory_read.py tests/test_predictive_memory_read_integration.py \
 tests/test_predictive_tool_recovery.py tests/test_predictive_unified.py \
 tests/test_predictive_unified_lifecycle.py tests/test_predictive_unified_loop.py \
 tests/test_predictive_unified_wiring.py tests/test_predictive_visible_basis.py \
 tests/test_raw_task_trajectory.py tests/test_simple_predictive_prompts.py
```

Result on 2026-11-13: **214 passed**, 3 Pydantic dependency warnings, in 59.08 s; pytest also emitted its existing unset asyncio loop-scope deprecation notice at startup. `git diff --check` passed. A pre-test attempt with the bare Python interpreter lacked pytest; the established local test environment was used without installing or changing dependencies.
