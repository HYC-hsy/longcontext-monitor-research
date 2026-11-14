# Prompt-guided reminder and memory loop

Base: `ff992e93a4e8f90d7e4185d31c29420b7920ac10`.

The same manager and continuous native conversation remain. The system prompt still asks it to recall/decide first, then predict/save information with future presentation value after eight task turns. Program-enforced stages have been removed.

- Both `memory_read` and `memory_add` are available on every request.
- Each response's reminder tag is extracted independently of its tool calls; tools run and their actual receipts return normally.
- The first valid reminder/no-intervention decision per wake is retained. Later tags are still recorded but do not replace it; tools remain independent. Missing or unparseable tags do not claim the first decision. If no valid reminder was supplied, no text is injected; this is not evidence the model explicitly chose no intervention.
- Tool calls continue the conversation with `Continue.`. A normally completed response without tool calls ends the wake, even if it repeats a reminder tag. No stage handoff, forced read, decision-lock, or stage-recovery messages are inserted.
- The host still delivers the resulting reminder only after the wake completes. Existing native-history and transport error handling remain; tool argument validation and reminder code-body fidelity are unchanged.
- No memory schema or scientific prediction criterion changed. No live Task/model/native evaluation was run.

## Historical replay caveat

The three archived responses at RStan steps 16/20 and ARC step 20 contain four `memory_add` calls, each with an extra `bank_id` parameter. They previously failed at the stage gate. With that gate removed, their exact arguments fail the existing content-only contract instead. Tests preserve this actual failure, and separately show the same content-only calls save their text verbatim. This patch does not silently broaden the schema or claim the exact historical calls now succeed.

The old tests that required stage blocking/frozen reminders were replaced with tests for the user-requested free flow. Historical source-hash guards were updated for the explicitly authorized implementation change; these guards alone are not behavior validation. Synthetic provider/native-history and host delivery tests independently exercise production code.

## Verification

Final expanded offline suite: **120 passed** (loop, native-provider simulation, exact archived early-call replay, code preservation, host delivery/audit failures, file-spool worker lifecycle, raw GA trajectory batches). Historical comparator prompt/source guards: **13 passed** separately. `git diff --check` passed. No real model or task calls were made. The class and `loop_mode="remind_first"` remain unchanged compatibility identifiers; they no longer imply enforced stages.

The attempted entire `tests/` suite was not completed: sparse checkout lacked historical dependency `causal_reminder_turn30_20261007` and `pma_evidence_review` modules; an intermediate broader run also reported existing compression/name and prompt assertions. It is not a full-suite pass. Changed-loop fixture expectations were updated to the new free flow, and the final expanded tests above were rerun after those changes.

Reproduce from repo root (activate a Python environment with pytest, PMA/Harbor dependencies):

```sh
P=method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013
export PYTHONPATH="$PWD/tests:$PWD/$P/vendor/pma_89e5c0d/src:$PWD/$P/vendor/pma_89e5c0d/external/harbor/src:$PWD/$P:$PWD/GenericAgent-main:$PWD"
export LITELLM_LOCAL_MODEL_COST_MAP=True
python -m pytest -q tests/test_remind_first_loop.py tests/test_natural_reminder_transition.py tests/test_memory_content_contract.py tests/test_complete_save_prompt.py tests/test_remind_context_prompt.py tests/test_reminder_code_preservation.py tests/test_predictive_unified_wiring.py tests/test_predictive_unified_lifecycle.py tests/test_raw_task_trajectory.py
python -m pytest -q tests/test_coherent_unified_prompt.py
```

## First-decision follow-up

Based on uploaded `5785edc4f0d7297afd60d7d0031c75a661cfdab1`, only decision acceptance changed. System prompt, tool schema, free tool execution, normal no-tool completion, and the existing tag parser are unchanged. The prompt asks for the reminder in step 1 and organization in step 2; it does not prevent a model from repeating a tag during organization. Such later tags no longer change the wake's decision. No new stage, retry, or validation gate was added.

Offline exact-response replay uses the public five-task archive: RStan wake 4 (calls 5–7, context then no-intervention) retains the original reminder; ARC wake 12 (calls 11–14, no-intervention then context) retains no-intervention. The fixture includes original public text, tool arguments/IDs, source paths and file hashes. This is protocol replay, not a rerun of a Task or an evaluation of reminder quality. Additional tests cover fenced examples, preserved code payloads, same-response reminder plus save, tool errors, and reset on the next wake. Three source-hash guards are repinned for this authorized runtime change, separately from behavioral tests.

Follow-up verification: **136 passed**, 3 dependency warnings, in the combined targeted suite above; `git diff --check` passed. No live model, Task, or native evaluation was started.
