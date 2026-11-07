# Continuous PMA integrity repairs

## Scope and identity

Both methods coexist in one source revision:

- `pma-predictive-context` / `pma_predictive_context_v1`: existing continuous P1/P2 with its existing full-bank prompts.
- `pma-predictive-read-context` / `pma_predictive_read_context_v1`: independent on-demand `memory_read` continuous variant.

Parent: `eb134b655e9c3af4eb071b8a8652e4f112ed048f`, which is based on `507ed5b7264a80bca11a5a2dc6b2e03d658e8fac`. The local engineering revision is `c3bcb4f2cbc30e7cbb3ba2d6bf1ce4a73cb2560d`; the published commit is constructed directly on the verified GitHub base tree. See `PMA_CONTINUOUS_GITHUB_RUN_GUIDE.md`. The implementation and validation were local engineering work only. This publication adds source and synthetic tests to a separate GitHub branch on explicit request; no model/provider request, real task, Docker lifecycle, developer-thread operation, or historical-result rewrite has been performed.

## Repairs

### 1. Failed phases no longer become ordinary no-intervention

The continuous class now executes the existing phase prompts, tool operations, and decision parser with a fail-stop phase boundary. Ordinary P1/P2 errors become `PMAPhaseError`, with safe phase and cause-type metadata, while original exceptions are retained as causes. P1 failure prevents P2. P2 failure produces no MemoryAgentResult, no reminder, and no normal no-op count. The read variant inherits both protections, including later same-wake read continuations.

The exception remains a `GAHistoryIntegrityError` subtype, crossing the historical vendor process/host `except Exception` handlers. Cancellation and existing history-integrity failures still propagate. Unsuccessful tool-operation receipts retain their existing semantics; this repair does not reinterpret every failed memory operation as a transport failure.

The dispatcher writes a safe error receipt before re-raising fatal errors. This also releases a standalone uncapped actor bridge; the normal launcher's dead-worker guard remains in place. `worker_exit.json` records phase, safe cause type, and `decision_produced:false` for typed phase failures. No prompt, bank, raw error message, or private provider block enters these new diagnostics.

Historical noncontinuous `predictive_memory_agent.py` is byte-for-byte unchanged. This does not introduce an error retry, bank rollback, or resume protocol; an aborted run remains an aborted run. Partial bank writes may survive in failure archives and must not be scored as a successful wake.

### 2. Compression telemetry matches post-transform state

The under-cap return now recomputes message count, serialized-character count, and SHA-256 after periodic compression. `changed` compares before/after hashes rather than unconditionally reporting false. The host-side copied trimmer receives the same telemetry-only fix; its telemetry stays disabled as before.

Compression implementation, global compression counter, 30,000 context setting, 0.6 target, five-call interval, nine-message floor, pruning, and leading-tool sanitization are unchanged. The legacy field named `bytes` still measures serialized characters, not UTF-8 bytes or billed tokens. No new hard cap is imposed.

### 3. Provenance is audit-only; no visible text or label changes

`_ensure_text_block` is unchanged. Its summary text, insertion position, visible stream, assistant history, and later GA input remain identical. PMA continues to receive the same postprocessed GA-visible text.

A separate `public_blocks_provenance` event field records output block index, `provider_native` versus `ga_synthetic_summary`, original provider index where applicable, and the deterministic synthesis source/transformation. It never includes thinking text or signatures. This sidecar travels through the GA bridge into `events.jsonl`, but is excluded from accumulated observations and trajectory formatting. It is not inserted into `public_blocks`, phase histories, prompts, tools, or provider requests. Native text that happens to contain a `<summary>` tag remains correctly labeled provider-native.

The existing trajectory section labels are unchanged. No new summary label is shown to either GA or PMA.

### 4. Source identity binds both repaired variants

Both existing source manifests now also bind `event_spool.py`. The read variant retains its distinct additional source file and method identity. Old certificates cannot silently certify changed source. No new experimental arm, prompt, scheduling condition, or evaluation policy was added.

## File changes

- `GenericAgent-main/llmcore.py`: accurate under-cap telemetry and response provenance sidecar.
- `GenericAgent-main/agent_loop.py`: forwards sidecar for normal and terminal predictive events.
- `GenericAgent-main/pma_upstream_bridge.py`: carries sidecar without modifying visible data.
- Stage `context_predictive_memory_agent.py`: isolated continuous phase failure boundaries.
- Stage `read_context_predictive_memory_agent.py`: typed P1 failure consistent with inherited P2 handling.
- Stage `ga_context_history.py`: telemetry-only parity fix.
- Stage `event_spool.py`: safe fatal error receipt, then re-raise.
- Stage `worker_main.py`: safe failure diagnosis in worker exit.
- Stage `single_run_certification.py`: bind event-spool source in both manifests.
- `tests/test_continuous_integrity_repairs.py`: deterministic regression coverage, synthetic data only.

Stage denotes `method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013`; memory modules are under its vendored `src/memory_agent/memory` directory.

## Verification and limits

The final focused/expanded relevant suite passes 181 tests and 151 subtests, including 39 new tests for both variants' failures and cancellation, actual host handler propagation, dispatcher/uncapped bridge failure receipts, worker-exit evidence, valid decisions, telemetry on all exits, actual GA session visible/history parity, and audit-only provenance. Existing pinned LiteLLM/Anthropic translation tests use synthetic completion replacements, not providers.

Independent review also compared actual pre-repair and repaired GA code in five cases: empty output, native text, long synthetic summary, whitespace-first-line, and thinking after a tool. Visible stream, response text, public blocks, and full history matched exactly. No production blocker was found; a test-thread cleanup issue identified in review was fixed.

Full repository regression was attempted, not claimed green. This partial checkout lacks Harbor agent modules, other source/fixture files, and portions of the Git object database. With identical import-mode settings, baseline has 27 failures, 23 errors, 174 passes, 6 skips, and 167 passing subtests; repaired source has the exact same failing/error test identities and 213 passes (39 new), 6 skips, and 167 passing subtests. First default collection also found package-relative import issues. Full test logs remain local; this branch intentionally contains no generated test-output archives. Applying patches to a complete checkout and rerunning its full offline suite is required before calling full-environment validation complete.

No live provider, complete Docker/Harbor lifecycle, official evaluator, four-run comparison, or research-effectiveness result is established here. Per-call PMA public response/tool-receipt/token audit completeness remains the previously identified separate gap; it was not silently expanded into this scope.

## GitHub source delivery

The dedicated GitHub branch is built directly on the complete verified tree of `507ed5b7264a80bca11a5a2dc6b2e03d658e8fac`, with the accumulated source/test changes from the local read variant and integrity repairs. The partial local checkout and its local-only parent commits are not pushed. Existing branches and historical results are untouched. Generated test logs/payloads are excluded; checked-in tests contain synthetic fixtures only.

Use a complete clean checkout of the published branch and pin its exact remote commit. Both methods must use that same revision. Do not copy only one agent module or reuse old source certificates. The source manifests bind the repaired runtime files, including `event_spool.py`. Target paths, runtime, model profiles, dataset, and secrets remain target-local. See the run guide for commands and validation gates. Publication does not authorize experiments.

## Four-run comparison: prepared instructions, not executed

After the user separately requests the runs, use one complete repaired checkout, one pinned dataset/Harbor revision, identical actor/PMA profiles and model parameters, and the same explicit budget policy for both methods. Preserve the original task text and all existing summary behavior. Retain initial/every-eight-new-step scheduling and no extra final-tail wake.

Planned commands using the verified runner interface (placeholders require target-machine paths):

```
python -m experiment_runner run --config experiment.local.json --method pma-predictive-context --task rstan-to-pystan --task nginx-request-logging --output runs/context-repaired-UNIQUE
python -m experiment_runner run --config experiment.local.json --method pma-predictive-read-context --task rstan-to-pystan --task nginx-request-logging --output runs/read-context-repaired-UNIQUE
```

Each command runs its two tasks serially. Use new directories/run IDs, never overwrite/replay historical runs. Read-only `plan` can be used first with its own new output JSON path. Do not run these commands before authorization. Source installation alone is not execution approval.

Before startup: complete target offline checks, confirm exact source hashes for both methods, runtime/profile hashes, pinned dataset and Harbor, visible running terminal, and user-approved turn/time/cost bounds. Record all four identities and outcomes, treating phase failures as failures rather than negative decisions. Use the same limits for both methods; do not silently introduce or remove a cap. The read variant can make additional internal P1 calls and has no new local call ceiling. Continuous histories may exceed their nominal context trigger because protected/current inputs and message floors remain. Two tasks with one run per arm remain a descriptive comparison, not statistical proof.
