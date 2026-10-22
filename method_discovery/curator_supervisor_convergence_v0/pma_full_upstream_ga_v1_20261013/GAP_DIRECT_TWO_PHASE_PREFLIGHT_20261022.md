# Direct two-phase PMA-gap preflight (offline, 2026-10-22)

Tested source commit: `3f84739f46ac340b2766fcad0dc3737d1ea85684`.
Candidate: B / `pma_gap_memory_v0`; no review, repair, rereview, candidate
acceptance, or stale-control role. The preceding `pma-b51303f481d04569`
reviewed-gap episode and its reward/archives were not modified.

## Bounded repair

- `GapMemoryAgent.process` only matches a `gap_` report ID after checking it is
  a string. Numeric, list and dictionary `memory_delete` IDs retain the
  vendor's failed ordinary-delete result; a prior successful gap save and the
  subsequent Phase2 reminder are not lost during report construction.
- `GapMemoryAgent._execute_tool_calls` follows pinned vendor fallback
  precheck (`any` short circuit), XML fallback, and per-call extraction order.
  Ordinary malformed arguments no longer become synthetic recoverable
  `_argument_error` operations. Only the new gap tool receives its own
  argument validation and direct gap routing. The vendor source is unchanged.

## Offline results

Python: `E:\LongContext\bench_runtime\m4\harbor-env\Scripts\python.exe`,
3.13.14. `LITELLM_LOCAL_MODEL_COST_MAP=True` and local `PYTHONPATH` for the
candidate directory, pinned vendor `src` and `external/harbor/src`.

- `python -B -m unittest discover -s D/tests -p 'test_gap*.py' -v`:
  18 run, 0 failures/errors/skips. (`D` is this directory.)
- `python -B -m unittest method_discovery.pos_pma_complement_v1_20261019.test_memory_adapter -v`:
  6 run, 0 failures/errors/skips.
- Paired fixed responses cover ordinary valid tools, malformed JSON,
  non-object arguments, a prior delete followed by malformed arguments, and
  structured/delete XML fallback. The tests compare ordinary bank effects,
  operation outcomes and whether vendor Phase2 ran. Fixed fake responses do
  not establish semantic gap quality.

## Source-bound Harbor zero-model fixture

Fresh private fixture roots:
`E:\LongContext\gap_direct_fake_a_20261022` and
`E:\LongContext\gap_direct_fake_b_20261022`.
Their distinct run IDs are `pma-5a6fd7cc3fdf450f` (A) and
`pma-212ff71ddf684c77` (B). Both execution identities identify the above
source commit. The official SQLite task source and synthetic verifier were
used; all model replies were finite fake transport responses, not live calls.
The existing exporter produced the 42-file redacted A/B evidence package in
`gap_single_run_cert_direct_20261022/`. `FILE_HASHES.json` distinguishes
public-copy and private-original hashes; the private original roots remain
local. The exporter reported zero secrets exported.

Direct read-only checks of the B private originals:

| cycle_step | ordered calls | formal gaps | Phase2 prompt equals actual transport payload |
| --- | --- | ---: | --- |
| 1 | maintenance, selection | 1 | yes |
| 2 | maintenance, selection | 1 | yes |

Cycle 1 executed `save_gap`; the official gap view is nonempty and the matching
selection request displayed it. A reminder was newly appended to the first
Task request, which has ready/attempt/response records. Cycle 2 selected
silent; the second request has no new reminder ID. Both cycles recorded
`mode=direct_two_phase`. No review/repair/rereview transport phase appeared.
The fixture observed the synthetic tool/evaluation path, worker exit 0,
`cleanup_confirmed=true`, no remaining owned control process/container, and
removed both fake one-time authorization files. Fake reward is not a real
SQLite reward.

This is a source-bound engineering check, not evidence that the model will
identify correct gaps or improve a real task. The older reviewed-gap
certificate does not certify this direct version.
