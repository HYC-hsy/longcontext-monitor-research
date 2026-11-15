# Exact cd3 system prompt on the retry-enabled tag-based manager

Parent: 6b59bcc4586b857aaf1c95496f1a1913ab3a4cdb.

REMIND_FIRST_SYSTEM is copied byte-for-byte from cd3bd608d755db338ab80543bd094313931bf1ca. UTF-8 SHA-256: 25d004ef5898c5814926aff3b862ceeb34394fd3ccccde158f214eae89aad4e5.

Its three Action Principles are:
- Before expressing the reminder decision, briefly explain your judgment.
- Before calling memory_add, briefly state which information you have selected.
- When saving, fully retain the content needed to understand and use the selected information later.

This supersedes the combined action principle described in PMA_RETRY_ACTION_PROMPT_20261115.md. No production code outside this system constant changes. Retry handling, logging, Task-readable knowledge mirror and notice, tag parsing, hard stages, dynamic prompts, schemas and all other runtime behavior remain identical to the parent. No send_reminder tool is added.

Validation: 212 targeted tests passed; 1 unrelated historical candidate-source test deselected; 3 dependency warnings. Not a whole-repository test pass. No real model, Task, evaluation or Docker execution.
