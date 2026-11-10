# P1 public forecast guidance

Exact parent: `3a8c14fdf32f84687d397a44b105bc4431ab5f51`.
Method: `pma-predictive-read-context` / `pma_predictive_read_context_v1`.

## Plan and scope

1. Make the existing P1 forecast request explicitly ask for a short public summary.
2. Reuse the existing native observer history, including signed/opaque provider
   continuation state. Do not derive public text from native reasoning.
3. Add a soft reminder only to the next P1 request that would already occur.
4. Verify transport, tool semantics, isolation and unchanged scheduling offline,
   then publish a separate branch. Prepare the same five complete task trials;
   do not claim model improvement until they actually run.

Only the read-context P1 production file changes. The GA Task, P2, schemas,
original task, raw trajectory, startup wake, batch cadence, history trimming,
model profiles, provider parameters and uncapped total task/turn policy are
unchanged. No P1-to-P2 merge, fixed forecast fields, separate forecast stage,
extra model call or body-before-tool gate is introduced.

This borrows GA's public-expression instruction and soft-guidance idea, not its
private-thinking-to-display fallback. Existing native thinking retention is
reused without modification. Public output is not synthesized from reasoning.

## Soft reminder semantics

A private Boolean records only whether the last P1 response has lexical public
text. Empty/whitespace/punctuation-only bodies, markup-only bodies and text
wholly inside think/thinking/tool_call tags do not count. `OK` and `Finished.`
DO count as text; this is deliberately not a forecast-quality evaluator.

On the next naturally scheduled P1 request, missing text appends the fixed
reminder below to that request's system, at most once in the system string.
The original task/trajectory and `Continue.` prompts remain byte-for-byte intact.
The state survives wakes and resets with the conversation. It is replaced by
each subsequent response's text-presence result. Repeated missing text uses the
same suffix, never an accumulated reminder history.

An add-only response still writes once and immediately proceeds to P2. An empty
or reasoning-only no-tool response also proceeds to P2. Read/error continuations
retain their existing loop and tool receipts; only these already-existing
continuations may receive a reminder during the same wake. No missing-text
condition retries, blocks, rewrites or rolls back any valid tool operation.

## Exact P1 system

```text
You are a memory manager for the task agent.

Based on the task description and the task agent's trajectory, first anticipate the problems the task agent may encounter or the decisions it may need to make over the next 10 turns, and what information it will need then; organize and save that information accordingly.

Before using memory tools, briefly state in ordinary reply text the upcoming problems or decisions you anticipate and the information you plan to preserve for them. Give a concise public summary, not private reasoning. No special format is needed.

Use memory_add to save information. When you need to look up information already saved, use memory_read with bank_id="knowledge".
```

### P1 Chinese translation (reading aid, not sent to the model)

你是任务智能体的记忆管理者。

根据任务说明和任务智能体的执行轨迹，先预判任务智能体在接下来 10 轮中可能遇到的问题、可能需要作出的决定，以及届时会需要哪些信息；据此整理并保存这些信息。

使用记忆工具前，先在普通回复正文中简要说明你预判接下来会出现哪些问题或决定，以及你打算为此保留哪些信息。给出简洁的公开摘要，不要披露私有推理。不需要特殊格式。

使用 memory_add 保存信息。需要查阅已保存的信息时，使用 memory_read，并设置 bank_id="knowledge"。

## Conditional P1 system suffix

When pending, the actual system is the entire P1 system above, two newlines,
and exactly:

```text
Remember to include a brief public summary of the upcoming problems or decisions you anticipate and the information you plan to preserve. Do not disclose private reasoning.
```

中文：记得简要公开说明你预判接下来会出现的问题或决定，以及你打算保留的信息。不要披露私有推理。

## Exact P2 system (unchanged)

```text
You help the task agent complete its task by reminding it of relevant information from memory at appropriate times.

Review the memory bank alongside the task requirements and the agent's recent trajectory, and decide whether any information can help its current work. You may synthesize information, identify connections, and offer grounded inferences or suggestions; preserve the information's original uncertainty when expressing them.

Default to no intervention. Do not intervene if no reminder is needed now, or if the relevant information is already visible in the recent trajectory and the agent's actions indicate that it has taken it into account. Do not take over the task agent's work.

If a reminder is needed, write:
<context_for_action>
Relevant information to bring to the agent's attention.
</context_for_action>

Otherwise, write:
<no_intervention/>
```

### P2 Chinese translation (reading aid, not sent to the model)

你通过在适当时机提醒任务智能体注意记忆中的相关信息，帮助它完成任务。

结合任务要求和智能体近期的执行轨迹审阅记忆库，并判断其中是否有信息能够帮助它当前的工作。你可以综合信息、发现关联，并提出有依据的推断或建议；表达时应保留这些信息原有的不确定性。

默认不干预。如果当前不需要提醒，或者相关信息已经出现在近期轨迹中，且智能体的行动表明它已将这些信息考虑在内，就不要干预。不要接管任务智能体的工作。

如果需要提醒，请写：
<context_for_action>
需要提请智能体注意的相关信息。
</context_for_action>

否则，请写：
<no_intervention/>

## Other prompt parts (unchanged)

P1 initial user message: `[Task Description]\n{original_task}`.
Periodic P1 user message: the exact current public trajectory batch, with no
new wrapper or appended guidance. Existing read/error loop user message:
`Continue.`. P1 gets its own retained history and the unchanged `memory_add`
and `memory_read` schemas. It receives no new native/private reasoning text.

P2's user message still contains the step, updated bank, original task and
current public trajectory. P1's public summary is not automatically passed to
P2: only information actually saved into the bank reaches it through that bank.
P2 keeps its own history, with no P1 soft reminder and no memory tools.

## Offline verification

Compileall passed. Focused ten-suite regression: **213 passed**. It covers cross-wake reminders,
reset, lexical placeholders, successful empty-body add, read/error continuation,
reasoning-only completion, native signatures/opaque items, actual OpenAI SDK and
Anthropic request serialization with synthetic responses, public-audit exclusion,
raw trajectory preservation, tool receipts, batch configuration and isolation.

Extended candidate: **390 passed, 140 subtests passed, 12 failed**.
Same environment and base projection: **365 passed, 140 subtests passed,
12 failed**. The failure identities match exactly; **0 new failures**.
The 12 shared failures consist of five old test expectations, two fixtures
without PMA transport configuration, and five tests missing unrelated historical
projection dependencies/scripts. Full repository/CI and live benchmarks are not
certified. Details are in the accompanying verification JSON.

The first new fixture run had 39 passes and one test-only assertion failure:
the Anthropic helper already returned the translated wire body, not a LiteLLM
messages envelope. The assertion was corrected to inspect exact system/native
blocks, then the whole focused suite passed. No production workaround was added.

All responses above are synthetic. This proves engineering behavior, not a
higher real-model public-forecast rate, forecast accuracy or benchmark reward.
The split response content/tool_calls fields cannot establish strict within-
response native block ordering. Report co-occurrence, not proof of internal
thinking order. Public text, substantive future-oriented content and correctness
must be evaluated separately on the real traces.

To reproduce with installed test dependencies:

```bash
S=method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013
export PYTHONPATH="$S/vendor/pma_89e5c0d/src:$S/vendor/pma_89e5c0d/external/harbor/src:$S:GenericAgent-main:experiment_runner:."
export LITELLM_LOCAL_MODEL_COST_MAP=True
python -m pytest -q tests/test_p1_public_forecast_guidance.py tests/test_simple_predictive_prompts.py tests/test_predictive_memory_read.py tests/test_predictive_memory_read_integration.py tests/test_predictive_tool_recovery.py tests/test_observer_history_retention.py tests/test_raw_task_trajectory.py tests/test_pma_batch_configuration.py tests/test_predictive_visible_basis.py tests/test_predictive_native_history.py
```

## Five full-task trial plan: NOT EXECUTED by this change

Use the new exact publication commit and the same five tasks, once each,
serially: `kv-store-grpc`, `reshard-c4-data`, `rstan-to-pystan`,
`largest-eigenval`, `filter-js-from-html`. Do not replace a full task with a
short scripted fixture or retry a reward-zero task. Keep the previous frozen
Task/P1/P2 profiles and provider settings, dataset and Harbor versions, batch
rounds, official native verifier and the existing uncapped agent/turn policy.
No model or total-task time cap is introduced here.

```bash
python -m experiment_runner run --config <verified-private-config.json> --method pma-predictive-read-context --task kv-store-grpc --task reshard-c4-data --task rstan-to-pystan --task largest-eigenval --task filter-js-from-html --output <new-output-directory>
```

Before launch, verify the exact source/profile identities, Docker engine,
dataset/evaluation setup, costs and a genuinely user-visible running terminal,
then obtain the repository-required launch confirmation. Use fresh banks,
histories, environments and run IDs. Preserve actual requests/responses, tool
receipts, reminders, subsequent Task requests, evaluation and cost/token evidence.
Export only public records, never native/private reasoning or credentials.
Compare to the prior five-task archive descriptively, not as a controlled causal
A/B result. No real model or benchmark task was started during this change.
