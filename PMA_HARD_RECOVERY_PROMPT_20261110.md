# P1: needed later and difficult to recover

Exact parent: `4964b7dc88135ba2ab527d4aa9bb521cd7a2cb8a`.
Method: `pma-predictive-read-context` / `pma_predictive_read_context_v1`.

## Approved objective and actual prompt

根据任务描述和任务 Agent 的轨迹，整理并保存任务后续会需要、且到时难以重新获得的信息

The two conditions are conjunctive. Difficult recovery is a condition, not a
priority or a possibility qualifier. The complete P1 system prompt is:

```text
Based on the task description and the task agent's trajectory, organize and save information that the task will need later and that will be difficult to recover at that time.

Use memory_add to save information. When you need to look up information already saved, use memory_read with bank_id="knowledge".
```

Only `read_context_predictive_memory_agent.py` changes in production. It removes
the old H10, fidelity/degree-of-certainty, public-explanation and redundant role
sentences. The tool instructions remain. Its deep-copied `memory_add` description
is now `Save information in the knowledge memory bank.` so the schema cannot
silently reintroduce H10. Tool names, parameters and execution are unchanged.
The shared tool definition and other candidates retain their previous behavior.

P2, initial call, W8 cadence, eight-step observation window, GA history policy,
model/provider settings, task inputs, read/add continuation, recovery logic and
4964 tool-receipt audit are unchanged. Existing public text is still recorded
when present; nothing requires or fabricates an explanation. Older dated notes
describe their own versions, not this candidate's active prompt.

## Offline verification

- 353 local baseline files were checked against the fixed 4964 Git blobs.
- Focused prompt, schema, read-loop and receipt tests: **34 passed**.
- Core regression: **157 passed, 15 subtests passed, 5 failed**.
- Same-environment unmodified 4964 baseline: **154 passed, 15 subtests passed,
  the same 5 failed**.
- Existing failures are all in `test_continuous_integrity_repairs.py`: four AST
  fixtures omit `_history_bytes`; one source-list expectation omits
  `responses_memory_llm.py`. They are not fixed in this prompt-only change.
- P1 AST matches 4964 after excluding the system string and local tool-description
  assignment. The other 350 existing files are byte-identical. Compile and
  `git diff --check` pass.

The new tests check the complete system prompt and tool descriptions after the
actual Anthropic conversion and OpenAI SDK serialization, with synthetic replies
and network blocked. They also check legacy-candidate isolation. Existing tests
cover empty text, add-only, read/add continuation, recovery and actual receipts.
These checks do not establish model adherence or task benefit. No live model,
Docker task, Windows acceptance or complete-repository test suite was run.

Reproduce with the project's installed test dependencies and Harbor metadata:

```bash
STAGE=method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013
export PYTHONPATH="$STAGE/vendor/pma_89e5c0d/src:$STAGE/vendor/pma_89e5c0d/external/harbor/src:$STAGE:GenericAgent-main:experiment_runner:.:$PYTHONPATH"
export LITELLM_LOCAL_MODEL_COST_MAP=True
python -m pytest -q tests/test_hard_recovery_prompt.py tests/test_simple_predictive_prompts.py tests/test_predictive_memory_read.py tests/test_predictive_visible_basis.py
python -m pytest -q tests "$STAGE/test_model4_transport.py" experiment_runner/test_context_predictive.py
python -m compileall -q tests "$STAGE/vendor/pma_89e5c0d/src/memory_agent/memory"
git diff --check
```

## Developer validation boundary

Use this exact publication commit, not a moving branch head. Preserve the existing
model, P2, W8, dataset, task set, limits and evaluation setup. Verify the effective
P1 system and both tool descriptions before a real call. Any authorized fresh
trial must use new run IDs, empty banks and new histories; do not continue a 4964
conversation containing the old prompt. Archive actual P1/P2 requests, responses,
tool receipts, saved entries, delivered reminders and native evaluation. Do not
change inputs or evaluation to unblock a run, retry reward-zero tasks, or infer
benefit from saved-entry counts alone. This engineering commit itself does not
authorize a paid trial or control another development conversation.
