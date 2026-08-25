# M1-C provider retry repair report

## Trigger

FBR r3 active reconstruction terminated during an open root repair episode when the relay returned:

`HTTP 400 {"error":{"message":"Upstream request failed","type":"upstream_error"}}`

The shared HTTP layer treated every 400 as permanent and therefore performed no retry, although this response explicitly represented a temporary upstream failure.

## Repair

- Added a narrow `_retryable_http_error(status_code, body)` classifier.
- Existing retryable status codes remain unchanged.
- HTTP 400 is retryable only when its body explicitly contains `type=upstream_error` or `Upstream request failed`.
- Invalid request, authentication, permission, and other ordinary 4xx responses remain non-retryable.
- Monitor sessions now have a floor of four bounded provider retries because they sit on the synchronous control boundary of a long task.
- Task-Agent retry configuration is unchanged.
- Retry telemetry marks relay-wrapped upstream errors explicitly.
- Exhausted retries still fail closed; an unavailable monitor does not silently release an open repair episode.

## Verification

- Static compilation: passed.
- Relevant test suite: 92 passed.
- Classification tests cover wrapped upstream 400, 429, 503, invalid-request 400, 401, 403, and 404.
- End-to-end fake HTTP test confirms a wrapped upstream 400 retries through a subsequent 200 response.
- End-to-end fake HTTP test confirms an invalid-request 400 performs exactly one request and returns the error.
- No paid API call or Docker task was started.

## Scope

This is an experiment-reliability patch. It does not change monitor judgment, active reconstruction, task state, evidence semantics, online-checker boundaries, or method acceptance criteria.
