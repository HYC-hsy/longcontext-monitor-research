# Configurable Claude information-manager temperature

Parent: `038fcbc322872d294e3378c877b08149edb36aca`.
Branch: `candidate/manager-temperature-config-20261117`.

## Scope

Only the Claude information manager for `pma-predictive-read-context` / `pma_predictive_read_context_v1` gains configurable temperature. Edit the private JSON file referenced by `environment.profiles.pma_profile_file`, not the Task profile. Existing `pma_model` and legacy `claude_monitor_opus48` container selection is preserved.

```json
{"pma_model": {"temperature": 0.2}}
```

This is a field-location illustration, not a complete replacement profile. Preserve all other fields, including provider/model/endpoint/key/thinking/reasoning/token/retry settings. Omitted temperature resolves to 1. Explicit values must be finite JSON numbers in [0, 1]; bool, string, null, NaN/infinity and out-of-range values fail. Profile hashes remain hashes of actual private file bytes; resolved manifest metadata records the normalized default. Regenerate source and profile identities for each setting; do not reuse an old hash.

The worker validates the same profile; construction and each manager call/retry explicitly retain its temperature. Task, legacy candidate defaults, GPT Responses restrictions, prompts, tool schemas, auto-choice behavior, thinking, cadence and budgets are unchanged. No global or per-call change to LiteLLM drop_params is made. Existing source manifests already include both changed modules.

## What this does NOT prove

Configurable does not mean the endpoint samples at that value. This patch validates and forwards the requested number to the SDK entry; it does not override SDK/provider restrictions, silently disable thinking, change the model, or repair a downstream proxy.

A zero-network diagnostic on this cloud environment's LiteLLM 1.109.1 found `AnthropicConfig.map_openai_params` drops temperature=0.2 for claude-opus-4-8 when drop_params=True and raises UnsupportedParamsError when False; temperature=1 survives. This is not a test of the user's actual dependency version or route and must not invalidate an independently verified route. The existing Harbor adapter still uses drop_params=True. Final serialized request/proxy behavior therefore requires target-environment inspection before interpreting a non-default run. HTTP 200 alone proves neither parameter preservation nor sampling effect.

## Offline verification

141 focused tests passed: tests/test_manager_temperature.py, tests/test_value_aware_content_prompt.py, tests/test_claude_memory_retry.py, tests/test_reminder_tool_loop.py, tests/test_predictive_tool_recovery.py. New coverage checks default/range/bool/non-finite values, unchanged legacy/GPT behavior, construction, repeated tool-loop calls and retries, no forced tool choice, no Task calls, profile non-mutation, and source identity coverage. Provider replies in these engineering tests are scripted fixtures, NOT evidence of autonomous model tool selection.

Additional historical test_model4_transport.py produced 9 passes, 5 subtest passes and 6 subtest failures: an obsolete expected RemindFirstMemoryAgent class name versus the existing ReminderToolMemoryAgent. The same six failures were reproduced against the unchanged implementation baseline; no assertion was relaxed to obtain a green result. Initial missing toml dependency and a test import issue were resolved in the isolated test environment/test; unrelated dependency deprecation warnings remain. This is not a full-suite green claim. git diff --check passed. No real API request or Task execution.

## Target-environment handoff

1. Pin this branch's final published SHA in an independent clean worktree. Keep the previous Task profile byte-for-byte unchanged. Reuse the existing PMA model/route/thinking and all non-temperature settings. Create separate private PMA profile copies for 1, 0.2, and optionally 0.5; never upload credentials. Verify defaults and resolved manifest values, profile/source hashes, and SDK versions before requests. Rerun the focused offline suite.
2. First trace the actual installed SDK pipeline without sending: profile -> constructed manager -> SDK arguments -> final serialized HTTP body. Do not stop at acompletion kwargs. Check tools and tool-choice semantics also survive; all three real manager tools remain available without forcing a specific call. If temperature is dropped, rewritten or rejected, classify this as a transport capability blocker. Do not label it a successful low-temperature run, silently turn off thinking, change models, downgrade dependencies, or globally change drop_params. Propose a narrow transport-specific correction separately if needed.
3. In the target environment, run only an explicitly authorized bounded live probe, not the two full Tasks automatically. Use the unchanged production system prompt and the same legitimate task/trajectory/initial knowledge for each condition, with fresh isolated state per repetition. Start with temperature 1 versus 0.2, three repetitions each; add 0.5 only if the route preserves it and the live budget is approved. Set an external probe call/time/cost budget up front, report budget-truncated cases as incomplete, and count all actual calls/retries. Do not inject synthetic assistant tool calls or scripted provider replies, force tool_choice, or tell the model the intended tool sequence. Tool operations must be model-selected and executed against the isolated real knowledge bank, with their actual receipts fed back to the same session.
4. Archive redacted requested/resolved/wire temperature, endpoint/model identity, SDK versions, tool schemas/choice, raw responses, native tool-use blocks, executed calls/receipts, continuation, HTTP status and usage/time. If authorized proxy upstream logs are available, compare their parameter to client wire. Keep conclusions separate: configured, transmitted, accepted, autonomous tools worked, and whether server-side sampling actually honored temperature. HTTP 200 and different/same text do not by themselves establish the last claim.
5. Compare matched inputs across conditions for tool selection, per-reminder reads, content/state fidelity, premature closure, distortion, omissions, unnecessary retention, reminder correctness and call/token/time. Repetitions are exploratory, not proof of sampling semantics or stable improvement. Only after transport and autonomous-tool checks pass, and the owner authorizes the batch, prepare the RStan/ARC comparison with the chosen settings, serial once per specified condition and no automatic reruns. Do not replace autonomous behavior evidence with the offline scripted tests.
