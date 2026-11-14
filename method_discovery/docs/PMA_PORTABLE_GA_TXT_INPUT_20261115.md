# Portable GA TXT input processing (engineering candidate, not effect evidence)

Base: `9eddf5697080b9adf0fc88ff6cb20f8d76b096b9`. No prompt, tool,
first-reminder decision, wake policy, or Task solver changes.

## Mechanism-owned copies and deployment

- `public_trajectory.py` now contains a source copy of GA's pure
  `task_trajectory.py`; it no longer imports a path inside GA.
- `ga_log_adapter.py` copies GA's observer, adding capture of the actual
  Prompt/Response log bodies. The isolated launcher staging directory installs
  this as `ga_trajectory.py`; the original GA source is untouched. This **is**
  a deployment adapter change, not a claim of no wiring change.
- `episode.py` installs the formatter only on the read-context candidate.
  Shared upstream formatting stays unchanged for f838/context candidates; old
  candidate fixtures retain their original compact JSON. Missing raw fields on
  the new candidate fail explicitly, never silently fall back.
- `ga_log_format.py` copies the native Prompt serialization expression
  `json.dumps(message, ensure_ascii=False, indent=2)` and uses `response.raw`
  without rewriting. It does not read/write GA log files. Native Claude GA
  forms raw using `str(content_blocks)`; the adapter does not reconstruct it.
- Capture occurs before spool serialization: the spool sorts JSON keys, so
  reconstructing a Prompt from its decoded object would not preserve order.
  `log_prompt` and `log_response` carry exact strings through that transport.
- Other backends implement the observer/trajectory adapter contract with their
  actual messages, results and complete response log body. A different real
  backend has **not** been connected or validated by this change.

## Deliberate scope and boundaries

The mechanism receives `=== Prompt ===` / `=== Response ===` sections inside
its existing `<task_trajectory>` wrapper. JSON, escaping, source block order,
code and native response representation remain. GA TXT timestamp and model
suffixes are not included. Thus **body equality**, not full-file byte equality,
is the parity claim. Batch separation also retains the existing two-newline
join between steps.

Only the actual Prompt/Response view is rendered. Standalone tool receipts,
framework-input mirrors, selected-call mirrors, statuses and partial-stream
telemetry remain in the audit ledger; they are not duplicated into the model
input. Repeated actual messages are not deduplicated by content.

A tool result reaches a GA TXT Prompt on the next call. The last tool results
of a wake are consequently visible in a later batch, not the current one.
Results without any later Prompt, unflushed final short batches, and outputs
from interrupted attempts for which GA never wrote a Response are not invented
as complete log entries. Existing end/wake behavior is unchanged. This is a
visibility boundary, not a claim that every executed result reaches the model.

GA raw Response can contain provider thinking/redacted-thinking/signature
blocks as well as ordinary text and calls. Per the user's requested runtime
alignment, these strings are not removed from actual mechanism input. This
therefore transmits the log body to the configured mechanism model provider,
not merely into local storage. Real-provider acceptance and utility have not
been tested. Public exports require a separate privacy projection; runtime
parity must never be demonstrated by uploading unprojected real raw bodies.

Old public archives lack `log_prompt` / `log_response`; the renderer fails
explicitly instead of inventing a complete raw response from public blocks.
They cannot retrospectively prove full raw parity.

## Verification

- `tests/test_raw_task_trajectory.py`, `tests/test_portable_ga_log.py`,
  `tests/test_remind_context_prompt.py`: 37 passed. Native GA HTTP fixture,
  file spool, worker and actual mechanism call-input capture exercised at
  batch periods 1, 3, 4, 8, 11. Fixture includes synthetic thinking/signature,
  Chinese, escaping, repeated strings, large tool results and tool identities.
- Original GA `_write_llm_log` function executed directly via AST; copied
  bodies compared character-for-character after excluding metadata headers.
- Independent subprocess imports pure mechanism protocol/formatter without GA
  on its search path; equal-content distinct events and separate ledgers tested.
- Historical first-decision RStan archive: 28 captured input objects serialized
  by original and copied expressions, 0 body mismatches. All 28 raw Response
  strings were absent, and original pre-spool key ordering is not recoverable.
  This historical check is object-replay parity, **not** an original-log proof.
- Same-run actual GA TXT files were also compared section-body-by-section-body
  against captured strings and final mechanism request input (37 tests rerun).
- Existing reminder-loop/natural-transition/code-preservation regressions: 61 passed.
- No additional public-export workflow is included in this candidate, per the
  user's latest direction. Raw runtime input can contain provider-private blocks;
  public archival must still be treated cautiously and must not blindly publish
  these raw strings. Existing exporters are not asserted safe for the new data.
- No model inference, real Task, native evaluation, or efficacy experiment.
  This cloud has no Docker executable, Task profile or API credential variables;
  no real Task was started or interrupted.

Final candidate-dispatch regression: 99 passed, 3 warnings (37.18 s), including
both historical predictive candidates' context assembly and the new candidate's
strict missing-raw rejection. The shared vendor formatter is unchanged from base.
