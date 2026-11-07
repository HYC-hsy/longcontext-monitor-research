# PMA two-tool interoperability and error recovery

## Scope and source

Current revision: the no-argument follow-up to `9be9eeccc0800aeeb0161de3f1a209dd24882e44`. That commit is based on `b0a4b5140f23fa06ab0ac4bf79f86803e9b1fe9f`, the Windows test-path fix after `41be615b9ad769159ea7ec1242f5656847224fb5`.

This repair changes only the two-tool `pma_predictive_read_context_v1` implementation, its tests, and this verification material. It does not change the one-tool context method, historical PMA, actor input, history compression, P2, trigger cadence, or experiment budgets. No live task or paid model request was run.

## Diagnosis and GA comparison

The archived rstan/read-context run at `42f1dc73f1dd019012321964d41b4f4ece527b48` advertised `memory_read` with empty properties and `additionalProperties: false`, then received `{"_noargs":"unused"}`. The dispatcher correctly rejected that input under the old contract. The archive is a redacted visible projection, not raw provider HTTP, so the historical producer of `_noargs` remains unknown.

Offline inspection of the available LiteLLM 1.108.1 request and full response transformations found no insertion of `_noargs`: empty input stays empty, and an existing placeholder is preserved. GA's exact schema converter likewise only maps `parameters` to `input_schema`. These observations do not establish the historical Windows SDK version or gateway behavior.

The stable `memory_add` and ordinary GA tools declare meaningful fields. GA's `start_long_term_update` does have an empty schema, but GA does not prohibit additional properties there, and its handlers receive the argument dictionary. This is not evidence that arbitrary unknown arguments should be silently accepted in PMA.

GA also treats unknown tools as nonterminal: its dispatcher supplies an error and `should_exit=False`. PMA already had a matching-ID structured error receipt, but its P1 loop continued only after a read call. Consequently the archived failed read was followed by its receipt immediately, whereas the later unsupported `code_run` receipt waited until the next P1 wake, after P2 had already run. The unsupported code was never executed.

## Repair

1. `memory_read()` has one meaning and one accepted argument shape: `{}` reads all information currently saved in the memory bank. The description explicitly says it takes no arguments; its object schema has empty properties and prohibits additional properties. The user pointed out that the optional `scope="all"` in 9be9ee was redundant and ambiguous, so that field has been removed, not retained as an alternative. There is no search, filtering, extra read mode, or special `_noargs` interpretation.
2. Unsupported names or arguments receive their original call ID and an explicit failure receipt, then get a same-wake P1 correction opportunity. Original received arguments remain unchanged in history. Supplied `_noargs`, `scope`, and every other field fail the first call with an instruction to use `{}`. The repair preserves immediate correction; it does not silently accept the archived invalid input or claim the model will no longer emit it.
3. The two-tool copy of `memory_add` now declares and enforces only `content`. Extra keys are errors rather than silently discarded. The shared one-tool schema and implementation remain unchanged.
4. Error recovery stops after **three consecutive model-response rounds containing at least one failed tool operation**. An entirely successful round resets the counter. Mixed success/error rounds count as error-bearing rounds. At the third consecutive error-bearing round, `PMAPhaseError` exposes `PMAToolRecoveryExhausted` and P2 is not entered. The last receipt is retained in local history, but there is no fourth correction request. Successful operations already executed in a mixed batch are not rolled back.
5. Successful add-only P1 still finishes without an extra P1 request. Successful read/add continuation is not newly capped. Malformed JSON/envelopes, missing or replayed IDs, missing signed continuation blocks, cancellation, and transport failures retain their fail-closed behavior.

No system prompt was expanded. No Task tools were granted to P1, and no task text or trajectory term was screened out.

## Verification

The original test projection was checked against 203 exact base Git blobs. Before this follow-up, all seven previously published files were checked against the exact 9be9ee blobs. This follow-up changes one production file, two existing tests, and verification/report material. Publication uses the exact 9be9ee GitHub tree, not the incomplete local projection; both earlier published branches remain unchanged.

The selected regression command in `tool_repair_evidence/commands.txt` passes **240 tests and 156 subtests**. Three non-failing Pydantic warnings concern ReadOnly TypedDict annotations in the installed LiteLLM dependency. Compilation and whitespace checks also pass.

Coverage includes:

- Actual vendored Harbor `LiteLLM.call`, installed LiteLLM `_map_tools`, `transform_request`, and full `transform_response` against in-memory Anthropic HTTP responses. No SDK transform is replaced with a handwritten approximation.
- Final provider tool schemas, the sole valid `{}` read shape against empty and populated banks, original `_noargs` and removed `scope` failures followed immediately by corrected reads, unsupported `code_run`, matching native call/result IDs, signed thinking-block preservation, and both plain and cached text-block receipts.
- Rejection of extra/invalid arguments, no unintended code execution, no duplicate write replay, whole-envelope validation before mutation, consecutive-error reset and exhaustion, and mixed-result batches.
- Existing successful add-only cadence, repeated reads, read failures, cancellation, large exact inputs, pinned task/active history, candidate isolation/source identity, worker failure propagation, and runner/runtime/cache regressions.

The new transport tests block socket connections. The available validation environment is Python 3.12.14 with LiteLLM 1.108.1, not the original Windows runtime. Docker/Harbor task lifecycle, historical provider parity, and task reward improvement are **not** established by these offline tests. The clarified no-argument interface and recovery still require the requested real reruns. Offline validity does not prove the historical tool problem or downstream task failure has disappeared.

## Development rerun handoff

Use this independent repair branch's exact commit in a clean target checkout. Keep the existing run archives unchanged and create new run IDs. Recheck the target environment's real dependency versions and source identity before running the same two tasks with `--method pma-predictive-read-context`. Do not add a one-tool rerun, change the task inputs/budgets, or claim strict official agent budgets for the earlier diagnostic override without separate authorization. Real execution and user-visible terminal handling belong to the separately authorized development run.
