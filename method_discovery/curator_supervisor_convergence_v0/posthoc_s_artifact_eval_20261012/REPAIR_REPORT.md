# Bounded infrastructure repair (no live model calls)

Baseline: original run code `155d30e12e261417f9fa14a86689850221b40056`;
original archive `ea3261b7a1ef8426e744bb2351404183861f0d8b`.
The worktree HEAD at start was that archive commit. The unrelated pre-existing
untracked `__pycache__` directories were left untouched.

Changed infrastructure files:

- `real_task_effect_pilot_preflight_20261010/pilot_analysis_bridge.py`:
  bounded scratch observation (20,000 entries or 5 seconds), explicit
  `snapshot_incomplete`, skipped-path/reason reporting for a Go temporary
  file/directory disappearing during scan. Optional observation failures no
  longer erase an already known command result. Fixed mount-source identity
  remains a hard gate. Exact-session shutdown still checks Docker inspect and
  daemon state; watcher `cleanup_error` cannot receive a clean certificate.
- `GenericAgent-main/monitor_agent_core/provider.py`: opt-in
  `incomplete_stream_recovery_v1` (default absent/false). Only an Anthropic
  stream ending without a complete `message_stop` may retry. The same logical
  request has at most three actual attempts, with 2- and 5-second waits,
  regardless of `max_retries` or `recovery_batches`. No incomplete content is
  committed to provider history or dispatched as tools. The payload hash must
  remain identical before a replay send. Other remote failures are not
  replayed by this option. Native deadline, stop event and cancellation remain
  mandatory. Request-attempt records carry logical ID, attempt, request SHA,
  timing, error chain, partial usage if provided, and unknown server-execution
  status. No future run manifest enables the option in this stage.

Tests actually executed (all zero-model):

| Command | Exit | Result |
|---|---:|---|
| `python -m pytest -q tests/test_monitor_incomplete_stream_recovery.py` from `GenericAgent-main` | 0 | 6 passed |
| `python -m pytest -q method_discovery/.../posthoc_s_artifact_eval_20261012/test_scratch_observation.py` from repo root | 0 | 3 passed; unrelated pytest atexit temp-path PermissionError after result |
| `python -m unittest method_discovery.curator_supervisor_convergence_v0.real_task_effect_pilot_preflight_20261010.test_pilot_analysis_bridge -q` | 0 | 4 passed in 63.457 s, real pinned Docker images, no model |
| `python -m pytest -q tests/test_monitor_continuation_diagnostics.py tests/test_monitor_continuation_repair.py tests/test_monitor_continuation_purpose_boundary.py` from `GenericAgent-main` | 1 | 20 passed, 1 collection/runtime failure: pre-existing optional `shortuuid` dependency unavailable in local Python 3.9; no production code adjusted to mask it |

The scratch regression injects an actual disappearing-file read into the
receipt path and checks that a known command result survives, the diff is
marked incomplete, and the accepted request is never executed twice. It also
checks mount identity remains fatal and cleanup-error cannot be certified.
The provider regression covers partial-then-complete, three-attempt exhaustion,
cross-layer cap despite `max_retries=4` and `recovery_batches=2`, non-stream
failure no-replay, cancellation, deadline, default-off behavior, and partial
usage from an incomplete parser stream. The original Docker bridge suite
exercises the production Monitor dispatch through the fixed read-only port on
both pinned task images.

Remaining technical limits: no real provider call was authorized or made;
stream-recovery behavior is verified with fake transport only. A mid-stream
socket exception, as distinct from a structurally ended-but-incomplete
Anthropic stream, is not replayed by the new opt-in. A scratch observation
marked incomplete cannot be used as a complete clean diff. Native evaluation
of Fyne's exact failure tar does not prove it was an atomic final workspace.

Actual calls in this stage: Task Agent 0; Supervisor/model/provider 0;
training/scoring model 0; native deterministic evaluator 2 (one per fixed
artifact). No old Task was resumed and no new batch was launched.
