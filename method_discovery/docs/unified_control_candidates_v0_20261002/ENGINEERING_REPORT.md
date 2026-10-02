# UC-OPEN-R5-v0 offline engineering record

Status: implementation candidate, disabled by default. No real Supervisor, Task Agent,
native verifier, independent probe, or scientific record was run. Passing tests is not
evidence of model adoption or method effect.

## Identity and allowed delta

- Frozen parent: `6c72477fce3350c82baf74a9ca8a96c87742be5b`.
- Branch: `unified-control-candidates-v0-20261002` in isolated worktree
  `E:\longcontext-uc-open-r5-v0`.
- Production edits: `monitor_agent_core/agent.py` opt-in bridge, and the new
  `monitor_agent_core/experimental_control/` adapter only.
- Test edit: new `tests/test_experimental_control.py` only.
- Frozen DCEC system/continuation text, working guidance, runtime, loop, provider,
  process runner, workspace, WTV, host contract, public task, and profiles are unchanged.

The additional configuration defaults to `monitor_research_view=off` and
`monitor_research_intent=off`. View choices are `off|flat|framed`; intent choices
are `off|note|routed`. Non-off requires DCEC. Invalid types/enums and historical
DCEC stacking fail before a provider request. The optional window is
`monitor_research_intent_window_requests=4` (1..8 for offline boundary tests).
The seven pre-existing tool schemas remain byte-identical. The two additional
schemas are identical within each matched pair: flat/framed use `work_context`;
note/routed use `work_intent`. Their complete fixed descriptions and the one
fixed guidance are in `experimental_control/adapter.py`.

The new state is one in-process selection and one in-process intention, not a
state file or a second semantic memory. Only the existing ordinary provider
request-local context seam adds an active block; it does not persist that block
into History. Source and intention tool receipts remain in ordinary History.
The continuation/maintenance `tools=[]` path gets no candidate block. No new
model stage, hidden call, control guard, or runtime semantic classifier exists.

## Offline verification

Executed from `GenericAgent-main`:

```text
python -m pytest tests/test_experimental_control.py tests/test_monitor_agent.py tests/test_monitor_agent_workspace.py tests/test_monitor_provider.py tests/test_clean_monitor_runtime.py tests/test_async_monitor_runtime.py tests/test_manual_completion_boundary.py -q --tb=short --basetemp E:\uc_r5_pytest_tmp
```

Result: `156 passed` (final output archived in `offline_tests.xml`; no failed or
skipped cases in this selected suite). The new test file alone has 38 passes.
Tests use the actual `MonitorAgent.review -> run_review -> MonitorProviderClient`
assembly path and replace only the bottom transport with scripted responses.
The off/off equality test executes the exact frozen `agent.py` source loaded
from the parent Git object, not a locally rewritten expected stub. It compares
the entire assembled request, excluding only nondeterministic `review_id`.
The candidate test module blocks `requests.Session.request` for every case.

An attempted full `python -m pytest tests -q` stopped during collection on the
pre-existing unavailable `shortuuid` dependency and `probe_monitor_auto_recovery`
import. No production or historical test was changed to mask this limitation.
The selected suite above includes the directly relevant Monitor/provider/runtime
regressions; it is not a multi-process or real-model run.

### T01–T20 coverage map

| ID | Offline behavioral test |
|---|---|
| T01 | `test_t01_t02_frozen_off_provider_ready_equality_and_no_state`; `test_t01_dcec_disabled_off_off_matches_frozen_provider_ready_request` |
| T02 | same; `test_invalid_config_fails_before_provider_request`; `test_historical_candidate_exclusion_is_unchanged` |
| T03 | `test_t03_t04_t05_t06_source_packet_render_and_errors` |
| T04 | same; `test_t04_read_after_source_moves_is_unavailable_not_positive`; `test_t04_t17_four_source_and_combined_block_budget` |
| T05 | `test_t03_t04_t05_t06_source_packet_render_and_errors` |
| T06 | same; `test_t14_t15_t16_multi_tool_and_no_semantic_oracle` |
| T07 | `test_t07_t08_actual_dispatch_request_local_and_continuation` |
| T08 | same; `test_t08_render_idempotent_per_logical_request_and_no_recapture_on_retry`; `test_t08_provider_retry_does_not_recount_or_recapture` |
| T09 | `test_t09_root_handoff_anchor_changes_and_existing_guard`; `test_t09_mid_review_new_root_receives_current_anchor_without_new_stage` |
| T10 | `test_t10_window_counts_distinct_logical_requests`; `test_t10_actual_provider_requests_route_on_fifth_after_set` |
| T11 | `test_t11_t12_t13_intent_session_peek_and_return` |
| T12 | same |
| T13 | `test_t13_elapsed_intent_does_not_consume_or_cancel_analysis_session` |
| T14 | `test_t14_t15_t16_multi_tool_and_no_semantic_oracle`; `test_t14_no_tool_and_limit_preserve_production_receipts`; `test_t14_registration_failure_does_not_replay_successful_ordinary_tool` |
| T15 | `test_t14_t15_t16_multi_tool_and_no_semantic_oracle` |
| T16 | same; `test_t17_all_configurations_share_original_tools_and_optional_schema` |
| T17 | `test_t17_all_configurations_share_original_tools_and_optional_schema`; `test_bounded_combined_block_and_independent_clear`; `test_t04_t17_four_source_and_combined_block_budget` |
| T18 | autouse `no_external_transport` fixture in the candidate test module; `test_t18_no_network_and_t19_cost_audit` |
| T19 | `test_t19_reference_and_candidate_assembled_cost_fields_are_real`; `test_t18_no_network_and_t19_cost_audit` |
| T20 | `test_t01_t02_frozen_off_provider_ready_equality_and_no_state` (`git show` exact frozen object) |

## Actual provider-ready assembly sample

One scripted two-request `framed+routed` review sent both optional tools in the
first model response; the *second* ordinary request was captured at the real
provider assembly seam. This is a compact field extract, not a synthetic schema:

```json
{
  "request_sequence": 2,
  "root_handoff": null,
  "tool_names": ["file_read", "file_write", "file_patch", "code_run", "wait", "intervene", "allow_complete", "work_context", "work_intent"],
  "model_parameters": {"model": "offline-model", "api_mode": "responses", "max_tokens": 8192, "reasoning_effort": null, "thinking_type": "", "temperature": 1},
  "system_sha256": "e9f33294eeef56c8e6aaa5588befd6e351ac85bf9c62573fb05de097fff6aa0c",
  "active_context_chars": 2459,
  "contains_dcec": true,
  "contains_selected_source": true,
  "contains_intent": true
}
```

The literal active context is request-local. Source packet items include source
characters and UTF-8 bytes separately, live SHA-256 and fragment SHA-256,
per-item capture time, range, `next_read`, omission/truncation/error, provenance
kind and selected order. A 1,500-Chinese-character fragment measured 4,500
UTF-8 bytes in the test. The same mock host snapshot/time produces identical
flat/framed source inventories; only the renderer changes.

## Cost and failure telemetry

Private `monitor/audit/experimental_control.jsonl` records configuration,
sanitized model-parameter hash, exact tool and guidance hashes, review
system/tool hashes, operations/revisions, packet and rendered-block hashes,
source char/byte counts and repeats, request sequence, handoff, and mechanical
session status. Provider usage/attempts remain in existing audit files. It
does not log API keys or a semantic verdict. Ordinary-tool registration failure
does not replay a completed operation; existing loop receipts remain authoritative.

Defaults: source text 6,000 characters total, at most four items of 1,500 each;
additional candidate block 14,000 characters. On overflow the entire optional
block is explicitly unavailable instead of silently dropping omitted-source or
unfinished-session facts. Reads are live and sequential, not a coherent global
snapshot. Changed paths/hashes are not semantic validity judgments. The
analysis-session peek never advances stdout cursor. No multi-process
`MonitorRuntime`/scientific trace was executed in this offline phase.
