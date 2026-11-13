# memory_add content contract

Base: `9316c10da95fa388257a88a2731035a7ef3b9901`.

## Scope

Only two production schema descriptions change, in `read_context_predictive_memory_agent.py`. Main prompts, reminder transport, stage transitions, wake cadence, storage, arguments and receipts are unchanged. This applies to the existing BANK_TOOLS consumers; imported legacy ADD_TOOLS remains untouched. No new tool, field, content limit, forced completeness check, or source-copy mechanism is introduced.

Tool description:

> Save the text supplied in content to the knowledge bank. Your surrounding reply is not saved by this tool. Call it more than once when needed.

中文：将 content 中提供的文本保存到知识库。此工具不会保存你在调用前后回复中的文字。需要时可以多次调用。

content description:

> The selected information, with the concrete details needed to understand and use it later. Include the information itself, not just its name or a statement that it was saved. This may include original text, code, or formulas.

中文：选中的信息，以及以后理解和使用它所需的具体细节。应包含信息本身，而不只是它的名称或已经保存的声明。内容可以包含原文、代码或公式。

This addresses the distinction between saying what was selected and actually supplying that information to storage. It does not instruct full-trajectory retention or require every detail to be saved.

## Offline validation

Synthetic targeted tests: 93 passed. New tests cover the actual loop request's tool schema, Chinese/code/formula/literal-tag and long-body verbatim persistence, same-response multiple saves, non-persistence of surrounding prose, and read-only reminder-stage tools. An exact-source reversal hash proves the production file equals the parent after reverting these two description assignments; the existing AST mutation guard is updated and retained.

Root suite parent: 407 passed, 6 failed, 4 subtests passed. Candidate final: 410 passed, same 6 failed, 4 subtests passed. Existing failures concern four compression telemetry cases, one source identity-list assertion and one legacy task-label prompt assertion. No claim of all-green validation.

Reproduction from repository root (Python 3.12 pytest environment with repository dependencies):

```sh
export PYTHONPATH="$PWD/method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/vendor/pma_89e5c0d/src:$PWD/method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013:$PWD/tests"
export LITELLM_LOCAL_MODEL_COST_MAP=True
python -m pytest tests -q
```

During setup, a missing PYTHONPATH and an incorrect test import caused collection errors, corrected before validation. Initial candidate tests exposed two expected schema/AST snapshots needing updates. These were updated only for the authorized change; the six parent failures were not altered. A replay-script `--help` attempt failed because that script expects two positional paths; no replay result is claimed for this revision.

Independent read-only review found no blocking issue. No real model calls, Task runs, native evaluations or Windows validation were performed. Synthetic preservation checks do not establish whether a model will select/write more complete content; that remains a real-run comparison question.
