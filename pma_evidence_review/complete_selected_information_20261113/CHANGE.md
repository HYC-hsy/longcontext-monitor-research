# Complete selected information: system-prompt-only revision

Base: 7940e4ef65b2b3c9b1e4ca5818240f9c0c78c564.

## Authorized change

Step 2 keeps the eight-turn future presentation-value criterion. Add:
“When saving, fully retain the content needed to understand and use the selected information later.”
Keep the brief pre-save selection statement. Remove the redundant step-entry phrase and the system paragraph about recorded reminder / ordinary-text completion. Remove “available during step 2” from the tool list.

Chinese step 2:
你必须预测本次收到的信息中，哪些在任务继续进行 8 轮之后，仍有展示给任务 Agent、以支持任务后续工作的价值，并将这些信息整理、保存到知识库中。保存时，完整保留所选信息中后续理解和使用所需的内容。保存前，简短说明你选择了哪些信息。

## Unchanged

ORGANIZE_START_PROMPT remains byte-for-byte unchanged, by the user's latest decision.
All recovery/continuation prompts, memory_add schema, provider history, wake interval, remind-first stage lifecycle, decision parser and delivery remain unchanged.
Existing code-fence fidelity, non-terminal decision-tag acceptance, state-aware post-read continuation, and content-based memory_add descriptions are retained.
No mandate to copy whole trajectories; this concerns information already selected.
The SYSTEM_PROMPT.txt file is extracted from the actual Python constant, not a separate configuration.

## Verification

Targeted offline suite: 95 passed. The final full tests run and matching base run are recorded alongside this note.
The new source-restoration SHA test proves the entire production module is unchanged outside REMIND_FIRST_SYSTEM. Three historical prompt/source guards were adapted for this explicitly authorized prompt revision; runtime guards remain intact.
No real Task, model API, native evaluation, Docker execution or effect experiment was run.
Linux offline results do not establish Windows or model-behavior effectiveness.

Final full suite: candidate 412 passed / 6 failed; base 410 passed / the same 6 failed. Four subtests passed on both. No newly failing nodes. Six retained failures concern four compression telemetry cases, a pre-existing source identity list assertion, and a legacy six-turn prompt assertion. Initial sparse-checkout import failures were resolved by materializing committed dependencies; no production code was changed to bypass them.
