# Continuous P1 with on-demand memory_read

Publication note: this report records the implementation and validation before GitHub publication. Source and synthetic tests are published together with the subsequent common integrity repairs. Local test-output archives are intentionally not included in this source branch. See `PMA_CONTINUOUS_GITHUB_RUN_GUIDE.md` for the current checkout and run procedure.

## Scope and selection

This is an independent, opt-in engineering variant based on
`research/pma-predictive-context-unified-20261106` at
`507ed5b7264a80bca11a5a2dc6b2e03d658e8fac`.

- Runner method: `pma-predictive-read-context`.
- Research candidate: `pma_predictive_read_context_v1`.
- Existing `pma`, `pma-predictive-f838`, `pma-predictive-context`, and other methods remain available. Their prompt/agent implementations are unchanged.
- No real model request, Docker experiment, evaluation, developer-thread contact, or remote write was performed.

## P1 prompt and tools

The complete P1 system prompt is:

> You organize information from the task execution.
>
> Based on the task description and the task agent's trajectory, organize and save information expected to be useful within the next 10 turns. Use memory_read when you need to look up information already saved.

`memory_add(content)` keeps its existing schema and flat-bank save behavior.
`memory_read()` has no arguments and returns every saved entry, including IDs and unchanged content, from the existing flat bank. It introduces no search, pagination, deletion, selection, scoring, or new store. Unexpected read arguments produce a failed tool receipt, not a search or a silently ignored parameter.

P1 first receives the exact original task from the host. Later wakes append only the newly accumulated actor trajectory. Saved bank contents are not automatically included in a new P1 prompt. They become visible when P1 asks to read them. Earlier read results can remain in the conversation as ordinary historical receipts; a new read returns the current bank.

## Execution paths

- No tool calls: one P1 request, then the unchanged P2 request.
- Add-only response: additions execute once; the actual call IDs and receipts remain in P1 history for the next wake. One P1 request, then P2, as before.
- Any read response: execute the batch in declared order, append native receipts, and continue P1 in the same wake. Further read/add calls receive receipts until P1 returns without tools. Only then run P2. A read, add, finish sequence therefore makes three P1 requests and one P2 request.
- Read-only response followed by finish: two P1 requests and one P2 request. Reading alone never writes the bank.
- Add then read in one batch includes that addition in the read result. Read then add returns the pre-add snapshot.

Every native envelope is checked before any mutations. Missing/duplicate IDs and malformed arguments fail closed. IDs are never invented. XML-looking prose cannot override a valid native read. Text-only tool calls are rejected in this new variant because they lack native identities. Ordinary tool errors have matching failed receipts. P1 transport failure, missing signed continuation data, or cancellation cannot silently become a normal P2 decision.

## Continuity and unchanged behavior

P1 reuses the existing GA `trim_messages_history` and history conversion functions, including their 30,000 nominal context-window setting, 0.6 retention target, five-call tag compression, and leading old-tool-result sanitization. A narrow wrapper restores the exact original task and the current active wake after applying that policy to a copy. Older history therefore follows GA's policy rather than a new whole-wake retention rule. Native IDs remain paired, and signed provider blocks stay opaque.

The 90,000-character value is a GA trimming trigger, not a new hard rejection limit. A large original task, current eight-step window, or full-bank read result is passed through intact even when those protected inputs exceed the estimate. Provider context limits still apply; no new local size or call ceiling is introduced. The count is an estimate, not provider-native token accounting.

P2 still uses the existing context agent's system prompt, updated full-bank prompt, separate history, response parsing, and trimming. Host scheduling remains the initial task wake followed by each eight new actor steps, with no extra final-tail wake. Lookup adds internal P1 requests only when requested. The existing runtime cancellation/deadline policy remains in charge; this variant does not add an arbitrary fixed P1 call ceiling.

Task resets clear P1/P2 conversation state and call identities. Existing host bank-reset settings remain separate. P1 and P2 histories and different agent instances do not share mutable state. History is in-process continuation state; durable worker restart/resume was not added.

Signed provider thinking is forwarded unchanged only as opaque continuation metadata. Existing private audit exclusion remains in place. Public task, actor trajectory, bank text, call IDs, and tool receipts are not redacted in live requests.

## Wiring

The new candidate is included in the registry, explicit host construction, initial/eight-step episode path, actor public projection, worker CLI, launcher/runtime identity, preparation, fixture selection, and source-certification selection. Its source manifest includes the new module. It does not reuse an old method's certification identity.

## Validation and limits

See `implementation_evidence/` for exact commands, environment versions, results, and source hashes. Tests use synthetic data only. The real pinned `harbor.llms.lite_llm.LiteLLM.call` and installed LiteLLM Anthropic request translator are exercised with only the final completion function replaced. This validates request construction and response extraction without contacting a provider.

No Docker executable was available, so a complete Docker/Harbor lifecycle or production provider run was not executed or certified. Passing these tests establishes engineering behavior, not research effectiveness, reminder quality, live provider acceptance, or readiness to start a real experiment.

The local source was materialized at the verified GitHub commit through the authorized connector because shell cloning lacked credentials. Exact Git commit/tree identities and unchanged tree references are preserved, but this is a partial checkout, not a complete repository clone. Apply the delivered patches to a normal checkout of the base commit for normal Git workflows. No push was attempted.
