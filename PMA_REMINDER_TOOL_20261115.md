# Native reminder tool variant

Parent: `cd3bd608d755db338ab80543bd094313931bf1ca`. Independent candidate branch; no real model or Task runs.

## Runtime

The existing read-context candidate selects ReminderToolMemoryAgent. The old ordered class remains a historical comparator. The manager reuses the existing native tool-batch parser, ordered execution and individual receipts, provider continuation history, context trimming, memory store and host reminder delivery. GA agent_loop's no-tool completion and normal tool-result continuation informed this change; it is not a copy of GA's Task completion gate.

All three tools are available throughout the wake. Ordering is prompt guidance, not a stage gate. `send_reminder` records exact content, with a receipt explicitly saying `recorded` and `delivered=false`. Multiple successful calls accumulate in call order and are joined with two newlines, without rewriting each body. Normal nonempty no-tool public text completes the wake. Provider error/truncation, empty replies and tool-bearing replies do not count as successful completion. Existing bounded error recovery is retained.

No reminder is exposed to Task until the whole wake returns successfully. A later provider or publication failure does not deliver a partially recorded reminder. Successful knowledge writes remain committed, as before. No successful reminder means no injection and no path notice. After completion, the existing before_actor_call path delivers the reminder and appends the existing knowledge-file notice. The file includes this wake's successful additions, not a pre-judgment snapshot; no later Task trajectory is included. Task-readable path remains `/run/pma-bridge/responses/knowledge/memory.json`, with the same per-run isolation, UTF-8 original content, atomic publication and read-only mount. No mirror or context compression code changes.

The old forecast soft reminder is triggered only when a memory_add operation lacks public selection text, not by a read/reminder-only reply. Worker fake-memory fixture and cycle/source-identity diagnostics are adapted to the native reminder tool, without using old reminder-stage properties.

## System prompt (exact)

```text
You are the task agent's information manager. Some information that appears during task execution remains valuable much later in the task, while other information appears early but only becomes valuable in later work. Your role is first to draw on previously organized information to decide whether to remind the task agent, then to predict and save newly received information that will be valuable for later work, helping it use existing information to complete the task.

The <task_description> tags contain the task agent's original task, and the <task_trajectory> tags contain the task agent's newly observed execution trajectory.

## Tools
- memory_add: Save information in the knowledge bank.
- memory_read: Read all information currently saved in the knowledge bank. Set bank_id to "knowledge" when calling it.
- send_reminder: Record information to remind the task agent of. The program delivers recorded reminders after this wake ends.

## Action Principles
- Before expressing the reminder decision, briefly explain your judgment.
- Before calling memory_add, briefly state which information you have selected.
- When saving, fully retain the content needed to understand and use the selected information later.

Manage task information through the following steps:

1. Judge and decide the reminder. You must use memory_read to carefully review the existing knowledge bank. After receiving its result, consider the task agent's execution trajectory. You must judge which information in the knowledge bank, as the task progresses, has become valuable or remains valuable for the task agent's current or upcoming work, and accordingly decide whether to remind the task agent and what to remind it of. If a reminder is needed, call send_reminder with its content. Otherwise, do not call it.

2. Predict and save. Based on the task description, the task agent's trajectory, and the judgment you have just made, you must predict which information received this time will still be worth presenting to the task agent to support subsequent task work after the task has progressed for another eight turns, and organize and save that information in the knowledge bank.

When finished, reply in ordinary text without calling a tool to end this wake.
```

## 中文对照

你是任务 Agent 的信息管理者。任务执行过程中出现的一些信息，在很久之后仍然有价值；另一些信息很早就出现，但要到后续工作中才体现价值。你的职责是先利用之前整理的信息决定是否提醒任务 Agent，再预测并保存新收到的信息中对后续工作有价值的内容，帮助它利用已有信息完成任务。

`<task_description>` 标签中是任务 Agent 的原始任务，`<task_trajectory>` 标签中是新观察到的任务 Agent 的执行轨迹。

### 工具
- memory_add：向知识库保存信息。
- memory_read：读取知识库中当前保存的全部信息。调用时将 bank_id 设为 knowledge。
- send_reminder：记录要提醒任务 Agent 的信息。程序在本次唤醒结束后送达已记录的提醒。

### 行动原则
- 表达提醒决定前，简短说明你的判断。
- 调用 memory_add 前，简短说明选择了哪些信息。
- 保存时，完整保留后续理解和使用这些信息所需的内容。

请按以下步骤管理任务信息：

1. 判断并决定提醒。你必须使用 memory_read 仔细查阅已有知识库。收到结果后，结合任务 Agent 的执行轨迹，你必须判断知识库中哪些信息随着任务推进，对任务 Agent 当前或即将进行的工作变得有价值，或者仍然有价值，并据此决定是否提醒、提醒什么。如果需要提醒，调用 send_reminder 填入提醒内容；否则不要调用该工具。

2. 预测并保存。结合任务描述、任务 Agent 的执行轨迹以及刚才的判断，你必须预测本次收到的信息中，哪些在任务继续进行八轮之后，仍有展示给任务 Agent、以支持任务后续工作的价值，并将这些信息整理、保存到知识库中。

完成后，用不调用工具的普通文字回复结束本次唤醒。

## New tool schema

```json
{
  "type": "function",
  "function": {
    "name": "send_reminder",
    "description": "Record a reminder for the task agent. Recorded reminders are delivered in order after this wake ends; this call does not deliver them immediately.",
    "parameters": {
      "type": "object",
      "properties": {
        "content": {
          "type": "string",
          "description": "The complete reminder text for the task agent. It may include original text, code, or formulas."
        }
      },
      "required": [
        "content"
      ],
      "additionalProperties": false
    }
  }
}
```

## Verification

206 focused tests passed, 1 explicitly deselected: candidate_registry_source_identity_and_actor_projection imports the unavailable historical causal_reminder_turn30_20261007 module. Before exclusion this check failed for that missing module; it is not a method failure or a full-suite green claim. Existing constructor expectations and source-fingerprint fixtures were updated for the authorized runtime change.

Coverage includes no-tool/no-reminder; mixed add/read/reminder batches; multiple reminders; content/code fidelity; malformed args and per-call error receipts; correction; provider-native Anthropic/OpenAI history and mock wire schemas; provider truncation; stale-reminder reset across wakes; soft-prompt timing; host queue and actual before_actor_call timing; mirror isolation/atomicity/failure; zero-model real worker lifecycle success and failure; source identity and archived loop records. No Docker executable is available, so an actual container mount/user read was not tested. Existing local mount mapping/subprocess and production mount declaration tests passed. No real Task, provider or native evaluation ran.
