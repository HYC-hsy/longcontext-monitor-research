# UC-OPEN-R5-v0 F1–F4 offline correction

This correction is a child of implementation `a09135b9904f1855ebcb66d09ee1801c6508aff1`.
The earlier engineering report remains an historical implementation record;
this file supersedes its descriptions of hash-only candidate-input audit and
whole-block overflow behavior. No scientific model record was run.

## Exact implementation delta

- `experimental_control/adapter.py` only in production: immutable private
  `raw_capture` and `request_render` JSON artifacts link review ID, logical
  request, selection/intent revisions, packet/block SHA-256, file path, UTF-8
  byte count, and character count. Explicit select/read and automatic refresh
  each archive the full bounded raw packet. Actual rendered block and the
  effective post-budget packet are archived separately. Error/unavailable
  blocks are archived too. No key or profile configuration is serialized.
- One shared, pre-render allocation checks **both** flat and framed lengths
  using actual JSON escaping, together with the same current intent/return
  block. It keeps earlier selected text before later text. A clipped item has
  recomputed fragment hash, byte/char counts, `truncated`, `omitted`, and
  `next_read`; no source is re-read during fitting. Both renderers receive
  identical effective source items. The fixed extra-block limit remains
  14,000 characters. If even the zero-source metadata does not fit, the
  explicit metadata-overflow result is archived; it is not reported as a
  normal rendering.
- `return` retains its original tool receipt. The one-time next ordinary
  request block distinguishes `at_return_snapshot` from **that request's**
  `current_handoff` and `current_watch_state`. The watch is a read-only peek;
  `analysis.read` is not invoked.
- Source identity uses `MonitorWorkspace._parts` to match the existing path
  syntax. Original pointers remain unchanged. Repeated separators classify
  the same original task, working note, or mount; traversal remains denied by
  the existing workspace read boundary.
- `agent.py`, the original prompts, tool schemas, provider/loop/runtime,
  WTV, and all Task-side behavior are unchanged in this correction commit.

## Tests and original results

From `GenericAgent-main`:

```text
python -m pytest tests/test_experimental_control.py tests/test_experimental_control_samples.py tests/test_monitor_agent.py tests/test_monitor_agent_workspace.py tests/test_monitor_provider.py tests/test_clean_monitor_runtime.py tests/test_async_monitor_runtime.py tests/test_manual_completion_boundary.py -q --tb=short --basetemp E:\uc_r5_pytest_tmp --junitxml ..\method_discovery\docs\unified_control_candidates_v0_20261002\offline_tests_f1_f4.xml
```

The complete JUnit result is `offline_tests_f1_f4.xml`. The selected suite has
162 passing tests and zero failures. Real Supervisor/Task Agent/verifier/probe
requests: all zero. The candidate tests replace only bottom provider transport
with scripted replies and block network access; they execute the real
`MonitorAgent.review -> run_review -> provider-ready assembly` path.

| Requirement | Behavioral regression |
|---|---|
| F1 raw select, changed-source auto refresh, old render after clear | `test_f1_select_auto_refresh_and_old_render_are_reconstructible` |
| F1 error/fallback output archival | `test_f1_error_and_unavailable_render_artifacts_match_sent_text` |
| F2 shared inventory under four-source escaped-content pressure, max question/intent, elapsed window, in-flight session | `test_f2_shared_budget_preserves_same_effective_inventory_for_flat_and_framed` |
| F3 return snapshot vs later root/session facts | `test_f3_return_snapshot_and_next_request_current_facts_are_distinct` |
| F4 repeated-separator identity and traversal | `test_f4_workspace_canonical_path_identity_and_traversal` |
| Full provider-ready samples and recomputable hashes | `test_complete_redacted_samples_have_recomputable_hashes` |
| Off/off frozen equality, retry, continuation, receipts, no semantic oracle | Earlier `test_experimental_control.py` regressions, rerun in the same JUnit suite |

## Complete scripted provider-ready request originals

`provider_ready_samples/` contains eight complete assembled request JSON
objects, not a selected-field summary: frozen and candidate off/off, nonempty
R/A and P/B, combined budget, and return/root timing. `MANIFEST.json` gives
each object's SHA-256, UTF-8 bytes, and character count. Its SHA-256 is
`ee062a3cb96bb24ee10aa756164f7c283d940740adcd42d70f242651bc139f87`.
Only the synthetic absolute temporary root is replaced by
`<OFFLINE_ROOT>` recursively; no semantic text, provider tool, prompt, or
model parameter is removed. There are no profile secrets/API keys in these
objects. Review IDs and capture times remain real scripted-run mechanical
identities. The off/off comparison normalizes only nondeterministic review ID;
the full remaining assembled objects are equal to the frozen Git source path.

Observed request-character costs in these scripted samples:

| Sample | Full JSON chars / UTF-8 bytes | Last active-context chars / UTF-8 bytes |
|---|---:|---:|
| off candidate | 18,226 / 18,226 | 838 / 838 |
| R flat | 25,312 / 25,320 | 2,459 / 2,463 |
| A framed | 25,455 / 25,463 | 2,595 / 2,599 |
| P note | 21,473 / 21,473 | 1,258 / 1,258 |
| B routed | 21,559 / 21,559 | 1,337 / 1,337 |
| combined budget | 74,584 / 74,584 | 14,839 / 14,839 |
| return boundary | 24,006 / 24,006 | 1,805 / 1,805 |

The 14,839 combined active context includes the unchanged 838-character DCEC
block, a two-character separator, and the **13,999-character candidate block**;
the candidate cap is not exceeded. Full provider requests also include prior
History and standard tool receipts, so their sizes are not candidate-block
sizes or token estimates. Provider usage is scripted and does not estimate
real-model token cost.

## Remaining limits

- Per-source reads are sequential live reads, not one atomic workspace
  snapshot. Archive identity and hashes reproduce what was captured and sent,
  not semantic truth or current applicability.
- A raw packet's *metadata itself* can exceed 14,000 characters (for example,
  several extremely long path/error strings). That request gets a clearly
  archived metadata-overflow notice, not partial normal output. This does not
  increase the existing cap or invent a new source summary.
- Offline assembly does not establish whether a real Supervisor chooses these
  operations or interprets them well. No model run or scientific preregistration
  is authorized by this result.
