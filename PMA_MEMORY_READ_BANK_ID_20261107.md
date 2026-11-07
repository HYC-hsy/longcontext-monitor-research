# PMA memory_read: required bank identifier

## Scope and baseline

- Exact parent: `cdb32d3c60b7471f2b6dfb00b29049ffb6b55e8c`.
- Parent tree: `62ee1eea8f335945db0bd4bc3ddd00d3060333f0`.
- Independent delivery branch: `dot/fix-pma-read-bank-id-20261107`.
- This contract replaces the no-argument read contract described in the older
  `PMA_TWO_TOOL_REPAIR_20261107.md`. Earlier reports remain historical evidence.
- The parent's Windows asyncio socketpair test fix is retained unchanged.
- This is an engineering interface repair, not evidence of real-task benefit.

## Canonical interface

The only valid call is:

```json
{"bank_id": "knowledge"}
```

Actual tool description:

> Read all information currently saved in the knowledge memory bank.

The `bank_id` parameter is a required string with enum `["knowledge"]` and
description `Memory bank to read. Use knowledge.` No additional properties are
allowed. This follows GA's existing native function schema structure: concise
tool description, named properties, and a string enum. The inherited PMA
`memory_add` schema already uses a required property.

`knowledge` names the existing single flat bank, not a filtered storage bucket.
The implementation still calls the unchanged `_format_memory_bank()`, which
returns all `knowledge + procedural` entries in their existing order, with the
same IDs and full content. There is no query, filtering, pagination, storage
migration, dummy field, `_noargs` alias, or no-argument compatibility path.

An invalid argument object produces the matching native tool-result receipt:

```text
memory_read requires exactly {"bank_id": "knowledge"}
```

The existing same-wake continuation and three-consecutive-error-round limit are
unchanged. A corrected read can succeed immediately in that wake. Invalid reads
do not modify memory. The existing whole-envelope integrity check still prevents
any writes when a native call envelope is malformed. This does not introduce
transactional rollback for otherwise valid calls in a mixed response.

## Changed files

1. `read_context_predictive_memory_agent.py` under the vendored PMA memory module:
   tool description, required schema, and exact argument validation only.
2. `tests/test_predictive_memory_read.py`: explicit canonical calls, schema
   assertion, and complete-bank/content/ID preservation checks.
3. `tests/test_predictive_memory_read_integration.py`: explicit canonical calls
   in existing adapter, history, cancellation, and integration tests.
4. `tests/test_predictive_tool_recovery.py`: empty/missing field, incorrect ID,
   incorrect type, extra-field and legacy-alias rejection; corrected same-wake
   read; real offline LiteLLM/Anthropic conversion and complete-bank receipts.
5. This report.

Production change: 7 inserted and 5 removed lines. Total source/test delta:
87 inserted and 24 removed lines. No P1 system text, P2 code or prompt, actor
content/projection, history trimming, scheduling, eight-turn cadence, model,
budget, registry, runner, or persistent storage implementation was changed.

## Verification

The local test projection contains 210 files, individually checked against the
actual parent tree's Git blob IDs before edits. It is not a full repository
checkout. Publication overlays only these five files onto the exact full parent
tree, not onto the projection. The 206 other materialized files remained byte
identical. All nine agent methods except `_record_p1_response` remained AST
identical; that method changes only argument validation.

Environment: Python 3.12.14, pytest 9.2.0, LiteLLM 1.108.1, Pydantic 2.14.3,
httpx 0.28.1. Dependencies were already available in an isolated test directory.

- Focused tests: **80 passed**, 3 Pydantic warnings, 3.26 seconds.
- Expanded selected regression: **262 passed, 156 subtests passed**,
  3 Pydantic warnings, 4.67 seconds.
- Independent read-only review reran focused tests: **80 passed**, no blocking
  findings; whitespace check clean.
- `compileall` and `git diff --check`: passed.

The transport tests invoke the real Harbor LiteLLM adapter and actual Anthropic
`_map_tools`, `transform_request`, and `transform_response`. Only the provider
completion is replaced with synthetic responses. They check required/enum/
additionalProperties on the outgoing Anthropic schema, valid arguments on the
wire, empty and populated reads, both storage lists, signed thinking preservation,
matching tool-use/result IDs, invalid-call feedback, and P2 remaining tool-free.
Socket connections are blocked for these tests, except stdlib local socketpair
construction retained from the parent Windows fix.

Reproduce from the repository root with dependencies installed:

```bash
STAGE=method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013
export PYTHONPATH="$STAGE/vendor/pma_89e5c0d/src:$STAGE/vendor/pma_89e5c0d/external/harbor/src:$STAGE:GenericAgent-main:experiment_runner:.:$PYTHONPATH"
export LITELLM_LOCAL_MODEL_COST_MAP=True
python -m pytest -q tests experiment_runner/test_context_predictive.py experiment_runner/test_runner_frontend.py experiment_runner/test_runtime_policy.py experiment_runner/test_runtime_compatibility.py experiment_runner/test_policy_evidence.py experiment_runner/test_runtime_integration.py experiment_runner/test_runtime_reuse.py experiment_runner/test_dataset_catalog.py experiment_runner/test_export_ga_visible_audit.py experiment_runner/test_evaluation_cache.py
python -m compileall -q tests "$STAGE/vendor/pma_89e5c0d/src/memory_agent/memory/read_context_predictive_memory_agent.py"
git diff --check
```

## Limits and next step

No real model/provider requests, Docker runs, or real tasks were started. The
whole repository suite and the user's Windows/provider environment were not
tested. Offline conversion does not prove live-provider compatibility or task
reward. The existing three Pydantic TypedDict `ReadOnly` warnings did not fail
tests. A real second-task run is a separate, manually forwarded developer action
using the published fixed SHA and the established launch gate; it is not part
of this implementation's claimed validation.
