# Profiled Claude manager call retries

Parent: `7da7b63003f14f61709e4c7100a8daf15bc9617d`. This branch does not include the later reminder-tool variant. No Task, model, or evaluation was run.

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

Focused tests cover recovery, exhaustion including max_retries=8, nonretryable errors, missing-status InternalServerError, cancellation during request and wait, bounded Retry-After, exact inner-retry controls, safe attempt records and archive field projection. A real constructed manager with mocked provider recovers from two failures, processes read/decision/add/completion normally, and executes the successful knowledge write once; another verifies no multiplied Tenacity attempts. No real model calls, native evaluations, Docker runs or changed running experiments.

## Running

Use the existing unified experiment runner and a fresh run directory/identity for this commit. Retain the same tasks, model, dataset, Harbor, method prompts, wake interval, Task limits and profile parameters as the intended 7da rerun. Do not resume/overwrite an old failed run. Verify the deployed manager code and profile max_retries/read_timeout before starting. Archive `memory_retry_attempts.jsonl` alongside the existing logical requests/responses, tool receipts, memory and native results. Report wrapper attempts separately from HTTP attempts; do not silently rerun entire tasks when retries exhaust.
