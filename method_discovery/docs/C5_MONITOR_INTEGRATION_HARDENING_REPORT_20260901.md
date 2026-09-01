# C5 Monitor Integration Hardening Report (2026-09-01)

## Scope

This stage addressed concrete integration defects found after the source-independence migration. It did not
change the research problem, add a checker, run a benchmark task, or select a new research mechanism.

## Changes

1. Enabling the clean Monitor now activates root-completion review even when research telemetry and the
   historical completion gate are both absent.
2. A Task Agent's final no-tool response and public completion proposal are appended to Layer-2 evidence
   before the Monitor reviews completion. The Monitor is told only that the cursor advanced and must inspect
   the archived evidence itself.
3. The default Monitor configuration is `native_oai_cc_vibe_gpt56_sol_high` (`gpt-5.6-sol`, Responses API,
   high reasoning).
4. The independent Provider now has a deliberately wide engineering history baseline. For a 200k context
   configuration, compaction begins at about 700k serialized UTF-8 bytes. It preserves the initialization
   exchange and the latest 16 messages, first bounds old tool results, and then removes the oldest complete
   user/assistant pairs if needed. Original task evidence remains externally recoverable.
5. Provider usage and every history transformation are persisted under `monitor/audit/`.
6. Corrupted model-visible fallback text and the C4 report encoding were repaired.

## Explicit code-run decision

By user decision, `code_run` remains the local general executor for now. The private working directory and
disposable `.task_view` remain, but no Docker sandbox, command whitelist, or hard filesystem isolation was
added. This is an accepted engineering risk and must not be described as a proven read-only boundary.

## Verification

- Minimal live Provider check: `gpt-5.6-sol` high successfully called `wait(after_turns=1)` through the
  independent OpenAI Responses client; 339 input tokens, 19 output tokens, 358 total tokens.
- Focused completion/integration tests: 20 passed.
- Focused Monitor regression after all changes: 36 passed.
- Full GenericAgent suite: 332 passed in 23.60 seconds.
- Source compilation, forbidden-dependency checks, whitespace audit, and model-visible encoding audit passed.
- No full real task or Docker benchmark was started.

## Remaining gate

The next step is a separately authorized short real task using the clean Monitor with GPT-5.6-sol high. Its
purpose is to validate startup, active observation, completion evidence visibility, intervention delivery,
history/usage artifacts, and absence of obvious capability regression. Engineering completion does not
pre-judge that behavioral result.
