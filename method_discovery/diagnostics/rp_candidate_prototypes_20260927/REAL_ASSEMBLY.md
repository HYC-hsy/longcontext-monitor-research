# Real production-path assembly check

`real_request_harness.py` constructs a fresh `MonitorWorkspace`,
`MonitorProviderClient`, and `MonitorAgent` for each of M1, R, and P. It calls
the production `MonitorAgent.review()` / `run_review()` loop and captures at
the `_anthropic_request()` boundary. `_request_with_recovery` is replaced only
at that boundary by a deterministic fake response transport; no network or
provider API is reachable.

The captured request contains the production Anthropic payload: the system
prompt (M1 contract plus the neutral R or P policy body), persistent history,
the current `monitor/working.md` view, the seven production tool schemas, and
the configured model parameters. The synthetic task is supplied in the first
public wake and remains available at `task/original_task.txt`; the workspace
environment map is the production wake-context path. A working-state write is
made through the ordinary `file_write` tool, and the next captured request
contains the updated state and its tool receipt. Subsequent reviews exercise
`wait`, `intervene`, a new completion generation, and `allow_complete`.

M1, R, and P each use a fresh temporary workspace and provider history. The
same fake response script and the same seven schemas are used. No completion
guard or semantic adequacy classifier is enabled; `monitor_dcec` remains off
for the M1-compatible assembly check. The resulting full payloads are in
`integration_capture.json`; the deterministic summary and schema hash are in
`integration_report.json`.

This proves request assembly, state/history plumbing, and fallback isolation
only. It does not establish observation quality or candidate effectiveness.
