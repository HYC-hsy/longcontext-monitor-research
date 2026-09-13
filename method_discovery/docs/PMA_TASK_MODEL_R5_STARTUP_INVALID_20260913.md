# R5 task-model startup diagnostic

## Disposition

Run `clean-monitor-fyn-2.2.0-roadmap-pma-two-phase-20260913-r5`, trial
`fyn-2.2.0-roadmap__8LPkSrm`, was started with user authorization and stopped
during startup validation. It is an invalid treatment run, not evidence for or
against the task-understanding mechanism. Do not reuse this run ID.

Manifest: `method_discovery/artifacts/pma_two_phase_20260913/fyne_r5_manifest.json`.
Source candidate: `5b213ce`; comparison intended against R4.

## Verified fault

The manifest included `GA_MONITOR_TASK_MODEL=1`, and the GA monitor adapter
understood the flag. However, Harbor's `FORWARDED_ENV_VARS` omitted it.
The running task process's `/proc/153/environ` contained no such variable.
Thus the treatment was not enabled. No task-model effect conclusion is valid.
The inference gateway had accepted monitor requests; this was not API downtime.

Task process 153 and monitor process 165 in the verified R5 container were
terminated deliberately. The outer runner subsequently exited with proof-invalid
errors (unfinished protocol round / unsuccessful wrapper / trial exception).
These are consequences of our diagnostic stop, not a spontaneous model failure.

## Repair

- Forward `GA_MONITOR_TASK_MODEL` into the task container process.
- Include `GA_MONITOR_TASK_MODEL` and `GA_MONITOR_PMA_MEMORY` in manifest-controlled
  reset keys, preventing ambient flags from leaking between conditions.
- Extend the existing forwarding/reset regression to cover both switches.

Validation: `python -m pytest tests/test_run_ultralong_m12_proofs.py -q`
in `long_context_bench`: **48 passed**.

No prompt, memory, model, or control-loop changes. No automatic replacement run.
A new manifest/source digest and distinct run ID are required before a separately
confirmed restart. On restart, inspect the actual task-process environment and
task-model initialization artifact, not just the host manifest.
