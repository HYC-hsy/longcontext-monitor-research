# Non-tool reminder: action-principles system prompt

Base: a7b6fa250ef2a30a86fa76440d792987bade4852.
This independent variant replaces only REMIND_FIRST_SYSTEM with the cd3bd608d755db338ab80543bd094313931bf1ca prompt and the subsequently approved combined action principle:

> Before each tool call, briefly explain your judgment; when calling memory_add, state which information you have selected.

The complete-save principle remains. There is no separate explanation-before-reminder-decision rule. Consequently, a no-tool no-intervention decision need not have an explanation under this instruction.

The original tag-based reminder decision, mandatory read gate, reminder/organize stage boundaries, dynamic prompts, storage schemas, Claude bounded request retry, attempt audit, Task-readable knowledge file and appended path notice are unchanged. No send_reminder tool or free-loop implementation is included.

Verification: 212 targeted tests passed, 1 unrelated historical candidate-source test deselected, 3 dependency warnings. Source bytes outside REMIND_FIRST_SYSTEM match the base exactly. This is not a whole-repository test pass. No real model, Task, evaluation, or Docker execution occurred; effectiveness remains untested.
