# Task understanding separated from local repair

## Authorization and evidence

User approved implementation after R4 audit and asked whether original task should enter Markdown. Current candidate targets unsupported closure without online checker; no new runtime controller or extra model.
Evidence: R4 D L259 original reverse-write requirement, L288 full read-only Set implementation, L303 monitor's conditional completion promise, L311 PMA adoption of that promise. Initial working.md focused on artifact/signature inventory, while PMA knowledge still retained the missing behavior. The aim is preserving and consuming behavioral understanding, not forcing test-opening ceremony.

## Original task and files

- Canonical full original remains task/original_task.txt (its Markdown content is unchanged). task_model.md explicitly references that accessible path, rather than asking a model to retype it or creating another mutable copy.
- monitor/task_model.md: model-authored natural interpretation of required behaviors, constraints and distinguishing observations. No fixed obligation schema or status scoreboard. Original task outranks the interpretation.
- monitor/working.md: local inquiry, findings and pending observations. Existing ordinary file tools can revise either private file; normal PMA status updates cannot overwrite task_model.md.
- overview.md links the model when present; raw observation layers unchanged.

## Actual implementation

New candidate switch `monitor_task_model` (boolean, default false); GA adapter maps `GA_MONITOR_TASK_MODEL=1`. Requires existing PMA maintenance enabled, fail-fast otherwise. False preserves parent candidate for comparison; not a new parallel agent.

1. First PMA phase-one call also emits `<task_model>natural text</task_model>` alongside existing bank calls. One simple output envelope, not a semantic field schema. Local transport captures the draft and exposes it to the existing phase-two call; author process and bank operations unchanged. No additional LLM call.
2. Both phases succeeding is required before initial file persistence. Missing/ambiguous/empty model output is an explicit phase failure, not silently replaced by a generated default. Failed phase two discards draft and retains previous bank/history. A successfully validated task model is persisted independently before bank snapshot; a subsequent bank I/O failure does not invalidate that interpretation, and retries reuse it.
3. Every later maintenance/comparison sees the current file; normal monitor requests also receive it before revisable bank context. Main file edits are re-read, not cached forever. Ordinary status replacement does not rewrite the file.
4. Model guidance separates local corrective advice from root acceptance; no keyword filtering or mandatory disclaimer.
5. New pending handoff in the same review injects full original task and current interpretation once per changed proposal, explicitly distinguishing completion/question/blocker. Existing root decision remains autonomous. Direct review entry with pending completion and no callback also receives the same material. No added PMA cycle at completion.

Changed modules: task_understanding.py (new), pma_memory.py (local transport/commit), agent.py (configuration/context/boundary guidance), decision_context.py (file link), ga_monitor_adapter.py (one environment mapping). Vendor, provider, compaction, follow/patrol and interrupt lifecycle unchanged. No local API config edits.

## Verification

New test_monitor_task_understanding.py covers initialization in existing calls, phase-two/main consumption, missing output failure, failed comparison rollback, local status preserving model, explicit model revision, per-proposal full-original context, direct completion entry, disabled switch and task separation.

Initial test failures were test construction assigning to frozen ModelResponse; fixed using dataclasses.replace. Final 121 passed in 11.71 seconds across task_understanding, pma_memory, pma_two_phase, decision_context, follow_wait, correction_schedule, agent, core_independence, completion_interrupt_lifecycle, host_contract and provider. diff --check passed. No API/model invocation. Each implementation/test step below 600 added/deleted code lines.

## Limits and gate

File separation guarantees distinct storage/update routes, not complete initialization, faithful interpretation or good judgment. Task model may still omit behavior; model may ignore contradictions. No schema checker certifies semantic coverage. Additional task-model input costs tokens; full original enters explicit handoff context, not every ordinary main request. Simple initialization envelope needs real provider validation. Earlier unrelated legacy runtime fixture failures documented in file-overview stage are not repaired here.

No real task started or new experiment manifest produced. Next run must explicitly enable GA_MONITOR_TASK_MODEL=1, use new identity/source hash, same task/model/budget and fresh isolated workspace, and receive user confirmation. Audit model quality at initialization, surviving unresolved requirements after local repair, actual source checking, final scope and cost; do not accept file existence as evidence of effectiveness.
