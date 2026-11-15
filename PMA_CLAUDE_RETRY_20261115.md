# Profiled Claude manager call retries

Parent: `e5fcdb435b3c7e9380d15ed540cb8af312319662`. This branch ports the bounded Claude request retry from `a7b6fa250ef2a30a86fa76440d792987bade4852` onto the independent reminder-tool variant. The send_reminder loop, tool contracts, knowledge mirror and path notice remain unchanged; the prompt and tool description clarify ordered nonreplacement as described below. No Task, model, or evaluation was run.

## Change and limits

- Only profiled Claude manager transport is changed. The same asynchronous Harbor/LiteLLM adapter is retained. Its fixed Tenacity decorator is bypassed with `__wrapped__` so retry counts do not multiply.
- `profile.max_retries` now means **additional attempts**, so 8 means at most 9 wrapper-layer calls. An older Claude profile without this field preserves 2 additional attempts (3 total). Current read-context profile validation already requires this field. No profile or credentials are edited by this patch. `read_timeout` remains unchanged.
- Each adapter call receives `max_retries=0` and `num_retries=0` to request no inner retries. Tests verify these arguments reach `litellm.acompletion`. They do not prove the user's deployed dependency/provider/relay performs no internal HTTP retries. Underlying HTTP attempt count is explicitly unknown. Harbor's existing extra-body compatibility fallback is also unchanged.
- Retry temporary connection/timeouts (including LiteLLM InternalServerError without a status wrapping ServerDisconnectedError) and transport-like status codes adapted from GA: 408,409,425,429,500,502,503,504,520–527,529. Do not retry ordinary parameter/authentication errors, context/output length errors, local parse/storage errors or cancellation. Explicit protocol and aiohttp SSL configuration errors are excluded.
- GA-like exponential backoff starts at 1.5 seconds and caps at 30 seconds. Retry-After seconds or HTTP-date takes precedence, also bounded to 0.5–30 seconds. Sleep and requests remain cancellable. This copies the small classification/backoff approach, not GA's synchronous SSE transport.
- Retry only the currently failing provider call, not a whole wake or Task. Tools execute after the adapter returns a complete response. Successful earlier knowledge writes are not replayed. A server may have accepted a disconnected request and billed it; duplicate server work/cost cannot be ruled out.

## Audit

`memory_retry_attempts.jsonl` records per logical `call_sequence`, wrapper attempt start/end, duration, exception class, exception-carried status code, wait, and success/failure/cancel outcome. No exception message, endpoint, key, prompt or response body is recorded. `exception_status_code` is not asserted to be observed HTTP status; `observed_http_status` and `underlying_http_attempts` remain unknown. Existing logical-call audit remains unchanged. Public exporter includes these records as `pma_retry_attempts_public.json`.

Audit failures propagate rather than generating further requests. No retry success is reported if a complete response was not obtained. Retry exhaustion keeps the original failure path and does not become a no-reminder decision.

## Verification

Focused tests cover recovery, exhaustion including max_retries=8, nonretryable errors, missing-status InternalServerError, cancellation during request and wait, bounded Retry-After, exact inner-retry controls, safe attempt records and archive field projection. A real constructed manager with mocked provider recovers from two failures, processes read/reminder-and-add/completion normally, and executes the successful knowledge write once; another verifies no multiplied Tenacity attempts. No real model calls, native evaluations, Docker runs or changed running experiments.

## Running

Use the existing unified experiment runner and a fresh run directory/identity for this commit. Retain the same tasks, model, dataset, Harbor, method prompts, wake interval, Task limits and profile parameters as the intended reminder-tool run. Do not resume/overwrite an old failed run. Verify the deployed manager code and profile max_retries/read_timeout before starting. Archive `memory_retry_attempts.jsonl` alongside the existing logical requests/responses, tool receipts, memory and native results. Report wrapper attempts separately from HTTP attempts; do not silently rerun entire tasks when retries exhaust.

## Combined-variant verification

241 focused tests passed, 1 historical integration test explicitly deselected because its imported causal_reminder_turn30_20261007 module is unavailable in this workspace. Tests additionally cover a successful reminder+add batch followed by two disconnected requests and recovery without replaying either tool, and exhaustion after that batch with no pending Task reminder. The knowledge mirror contains one entry. Public step export now preserves actual unified/remind_first/reminder_tool loop_mode, loop_rounds and termination (the older exporter only projected unified). Source identity additionally covers the unchanged task_knowledge_file.py. Native tool batch handling, history compression, GA and mirror implementation remain byte-identical to e5. The system prompt and send_reminder schema description additionally clarify the user-approved existing behavior: every successful reminder is delivered in call order after normal wake completion, without replacement.
