# verification_loop_v0 — offline candidate

Parent: `6388decad764775ec8ca8f17290bfb825ea3ea7f`. This is an opt-in
engineering candidate, not a scientific result. No real Supervisor, Task Agent,
native verifier or independent-probe run was started for this change.

Set `monitor_verification_loop_v0=true` with PATH/DCEC and
`monitor_root_scope_v1=off`. `monitor_verification_runtime_managed=true` enables
the selected-check scheduler; `false` keeps the same seven-tool, single-History
Supervisor surface but leaves follow-up and retesting model-organized. Neither
mode creates a second Supervisor. The root handoff changes decision scope and
provides the original public task and current artifacts; it does not copy,
clear or restore History or `working.md`. The accepted Task-turn budget view
continues in ordinary and root requests.

The optional `code_run.verification` fields select one current command and
its public basis, question, scope and 1–8 live source paths. Registration is
queued, not a pass. The existing AnalysisSessions runs the command from the
private monitor cwd; the model must use the actual task workspace path in
project commands. `wait(mode=follow)` arms the check for the selected Task-turn
boundary. The Task-side turn-end callback holds only the next foreground action
while the existing analysis process runs; it does not cancel the completed
tool. A pending root handoff permits the check to run before the next root
model request. The result, command, output excerpt, full output path, Task
turn and selected-path before/after hashes enter the next request. The runtime
does not decide whether the test is sufficient for the public requirement.

One current definition has a version and ID. New definition bytes invalidate
old receipts. Rechecks coalesce observed input changes and use at least five
actual Task turns between ordinary executions; root or first feedback can
bypass this cooling period. An unchanged selected-path set reuses the prior
receipt; failed or timed-out checks are not retried without a new change.
`wait(mode=patrol)` records resolve/withdraw/revise/defer for an active local
follow-up. `allow_complete` requires a current successful root-scope receipt
and explicit resolve; defer yields an incomplete, verification-limited delivery,
not a supported allow. A local pass is never promoted merely by changing scope.

Limits: the barrier serializes foreground Task actions only. It cannot prove a
whole-container snapshot or stop legitimate background writers. Stability is
checked only for the explicitly selected input paths; unlisted dependencies
remain the Supervisor's judgment. A result can be incomplete if the analysis
process or monitor exits. No hidden verifier or semantic checker enters online
control. The existing terminal evaluation path and budget ceilings are
unchanged. The proposed 300-turn comparison is not configured or authorized
here.

Offline command (from `GenericAgent-main`):

`python -m pytest -q tests/test_verification_loop_v0.py tests/test_root_scope_v1.py tests/test_path_control_v0.py tests/test_clean_monitor_runtime.py tests/test_monitor_agent.py tests/test_monitor_dcec.py tests/test_research_agent_loop.py tests/test_m0_deliberative_monitor.py`

Result: **182 passed**, process exit code 0. Python's pytest atexit cleanup
also printed an existing Windows temporary-directory `PermissionError`; it
occurred after the passing result and did not affect the test exit status.
