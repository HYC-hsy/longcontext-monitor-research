# F2 shared-budget search correction (offline only)

Parent: `47f0382110757d6a229b4b04a93140cc3d8e8a22`. This is a child correction to the same candidate, not a new treatment. No model, Task Agent, native verifier, independent probe, or scientific record was run.

## Production change

Only `GenericAgent-main/monitor_agent_core/experimental_control/adapter.py` changes. `_fit_shared_budget` first tests the complete captured packet in both renderers. If it fits, it returns that packet unchanged. Otherwise it tests source-body prefix lengths in descending selected-source order until both actual escaped renderings fit. A zero-body rendering is no longer treated as a lower feasibility bound, and binary search no longer assumes monotonic size. The 14,000-character cap, one raw capture per request, source order, source bytes, and intent/handoff/watch facts are unchanged. A genuinely unrenderable metadata packet still returns explicit `metadata_overflow`.

The descending scan is bounded by the existing 6,000 source-character capture budget. It favors the longest representable ordered prefix, not an arbitrary subset or a semantic summary. This is a bounded prototype search, not an optimal packing algorithm over rearranged sources.

## Actual provider-ready offline boundaries

All new cases use `MonitorAgent.review → run_review → provider-ready assembly` with a zero-network transport stub. The table gives actual block characters and UTF-8 bytes; all displayed test strings here are ASCII.

| Boundary | Full flat/framed chars | Zero-body flat/framed chars | Actual flat/framed chars (bytes) | Effective body |
|---|---:|---:|---:|---|
| 6,000-character full packet, nested pointers | 13,915 / 13,988 | 9,559 / 9,632 | 13,915 / 13,988 | All 6,000 original characters |
| Four one-character sources, long nested pointers | 11,007 / 11,080 | 14,215 / 14,288 | 11,007 / 11,080 | All four original characters; no false metadata overflow |
| Real over-budget, multiline and nonzero offset | >14,000 | — | 13,927 / 14,000 | Shared prefix 1,500 + 262 + 0 + 0 characters |

The last case asserts per-source prefix ordering, `omitted_chars`, fragment SHA-256, and line/offset `next_read`. Both renderer arms receive the same effective packet. Capture counts remain two per path (explicit select and ordinary-request refresh); budget trials do not recapture. The existing provider-retry test checks that request-level retry also does not recapture.

## Synthetic-root sample redaction

Only the offline request generator and its test change. It replaces the synthetic root in ordinary strings and up to three nested JSON-escaped representations before serialization, then checks every representation is absent. The `return_boundary.json` environment-map string now decodes to `<OFFLINE_ROOT>` paths. No task meaning, tool description, or control content is rewritten. This is sample hygiene, not a real-model input-boundary finding.

Complete regenerated, redacted provider-ready requests and their character, byte, and SHA-256 entries are in `provider_ready_samples/MANIFEST.json`. The samples cover frozen/candidate off/off, nonempty R/A, nonempty P/B, combined budget, and return sequencing. The manifest itself is a scripted offline artifact and cannot demonstrate model behavior.

## Regression command and result

From `GenericAgent-main`:

```text
python -m pytest tests/test_experimental_control.py tests/test_experimental_control_samples.py tests/test_monitor_agent.py tests/test_monitor_agent_workspace.py tests/test_monitor_provider.py tests/test_clean_monitor_runtime.py tests/test_async_monitor_runtime.py tests/test_manual_completion_boundary.py -q -s --tb=short --basetemp E:\uc_r5_f2_suite_final --junitxml ..\method_discovery\docs\unified_control_candidates_v0_20261002\offline_tests_f2_search.xml
```

Result: **166 passed, 0 failed (24.91 s)**. Pytest's original JUnit result is `offline_tests_f2_search.xml`. The async runtime suite intentionally prints a simulated failing-worker traceback while its assertions pass; it is not a failure of this run. Off/off frozen provider-ready equality, F1/F3/F4, ordinary tool/control receipt behavior, continuation behavior, and no-network guards remain in the selected regression suite.

Known limit: the prefix search may render up to 6,001 candidates for an over-budget request. It does not fetch sources again, add model stages, modify provider retry, or offer semantic judgments.
