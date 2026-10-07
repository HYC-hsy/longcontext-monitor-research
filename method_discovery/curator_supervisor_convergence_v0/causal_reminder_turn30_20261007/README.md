# Fyne Task turn-30 checkpoint feasibility (zero-model correction)

This package certifies the boundary after Task turn 30's
`update_working_checkpoint` tool result and before the turn-31 provider send.
It is bound to source archive `ca3648a925eb709deb09603e36e0f4981a03743a`.
No treatment, control continuation, model call, Task Agent execution, or native
evaluation is authorized here.

The earlier `88c60e02e0e278e6fa11ee80f41cec8587d2d8dea75b2a0c6b78c2b6e3d3cadd`
workspace SHA was **not** the exact historical public workspace: it omitted the
original-task sidecar and `.git`. It is superseded and must not be used as a
checkpoint identity. The corrected ordinary workspace has 2472 files and SHA
`994ed5f372f0ee6fecda6a600dc970ce4c5fbbb1a8c09acfa9ab3748ce323c60`;
`.git` is certified separately in `GIT_STATE_CERTIFICATION.json`.

`materialize.py` copies the exact clean task-image Git-backed `/app`, restores
`.monitor_original_task_acae0ed0dd4346a5a1515a7586ffceed.txt` **before**
replaying mutations, then replays all ten successful public writes/patches
through turn 30. The sidecar is supported by Task turn 2 / archive sequence 4
`ls -la /app`, and its bytes equal the archived original task and the retained
pre-verification tar's same path. No later implementation file is used to fill
the checkpoint. Unsupported shell mutations fail closed. The one prior
`go build -o /tmp/...` is checked against SHA-bound `go.mod`/`go.sum` bytes.
The materialized Git state has historical HEAD and index tree, a clean base
status, and the expected turn-30 status/diff. On Windows, Git certification
uses `core.filemode=false` to avoid extraction-only execute-bit differences;
the historical Git objects/index tree are not rewritten.

`RUNTIME_CHECKPOINT_STATE.json` records the recovered pre-turn31
`backend.history`, `handler.history_info`, current/next turn, pending tool ID,
system/tools/profile semantics, and session/device metadata. It distinguishes
the two ephemeral cache breakpoints in the previous raw provider request from
the persistent backend history. `runtime_checkpoint.py` verifies deployed
`ga.py` anchor rendering, then uses deployed `NativeToolClient.chat` and
`NativeClaudeSession.ask/raw_ask` to construct the next request. It replaces
the send function with a mandatory pre-network stop and compares the resulting
payload with the SHA-bound archived turn-31 raw body. All nine fields compare
exactly; no model-visible field is ignored. The generated request is archived
as `RECONSTRUCTED_NEXT_REQUEST.json`.

`LEAKAGE_AUDIT.json` permits only the observed pre-boundary sidecar and clean
Git repository, excluding later trajectory, final implementation, monitor
private cognition, verifier/hidden tests, and research conclusions. The
original provider-history and working-state identities remain unchanged.

`eligible_exact` in `CHECKPOINT_IDENTITY.json` means only that these mechanical
workspace/Git/runtime/request/leakage gates passed. It is **not** authorization
to perform a causal reminder continuation. Such a run requires a separate
research design and explicit authorization.
