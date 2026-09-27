# E0/E1 capability note

The current `AnalysisSessions` path already has process execution, session IDs,
incremental output, cancellation, wait limits, timeout, exit status and
archived output. `code_run` exposes Python and, on Unix, Bash; its production
dispatch is in `monitor_agent_core/agent.py` and execution is in
`process_runner.py`.

That establishes a static contract, not full proof of task-adapter fidelity.
E0 (tool contract, platform, path, receipt and isolation repair) is a common
substrate requirement and cannot be credited as a candidate gain. E1 would be
a future, general low-cost observation capability only if a source audit finds
that version-pinned context, interpreter consistency, or filesystem fidelity
is genuinely absent. No E1 runner or isolation layer is implemented here.
