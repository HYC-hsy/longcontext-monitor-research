# Fyne Task turn-30 checkpoint feasibility

This package is a zero-model checkpoint audit, not a reminder treatment or
continuation harness. It is bound to source archive
`ca3648a925eb709deb09603e36e0f4981a03743a` and to the local retained
bridge request bodies by the archive's `first_send` SHA-256 receipts.

The checkpoint is after Task turn 30's `update_working_checkpoint` result and
before the next Task Agent provider send. `TURN30_BOUNDARY_TIMELINE.json` gives
raw event locators and hashes. No Supervisor intervention was delivered between
those two boundaries; earlier delivered interventions remain in the original
provider history and are not removed or reinterpreted.

The complete workspace was materialized at the Git-outside path in
`CHECKPOINT_IDENTITY.json`. `materialize.py` verifies the exact clean task image
and its `/app` tree, copies all 2468 public workspace files without `.git`, then
mechanically replays all 10 successful public `file_write`/`file_patch` calls
through turn 30. It rejects unrecognized shell commands rather than assuming
they did not mutate the workspace. The one `go build -o /tmp/...` before the
boundary was not replayed; its declared output is outside `/app`, and `go.mod`
and `go.sum` at the materialized checkpoint match the retained final snapshot
byte-for-byte. The output is a full 2471-file tree, not a selected-file view.

`reconstruct_next_request.py` starts from the raw turn-30 provider request,
appends the exact public turn-30 assistant/tool blocks and next prompt, and
applies the observed rolling cache-control breakpoint. The raw turn-31 request
is used only as a comparison oracle. All nine request fields are equal; no
transport field is ignored. `TASK_AGENT_PROVIDER_HISTORY_MANIFEST.json` records
every reconstructed item, role, block type, content hash, and tool linkage.
The working checkpoint's relevant in-memory `key_info` and its exact
next-prompt exposure are preserved in `WORKING_CHECKPOINT.json`.

`LEAKAGE_AUDIT.json` lists the model-visible source whitelist and exclusions.
The materialized workspace was derived from the clean image and pre-boundary
public mutations, never from the final post-run workspace. Future trajectory,
native results, reviewer judgments, and monitor-private cognition are not
inserted into the checkpoint. The local image extraction and workspace tree
remain outside Git; their identities and every workspace file hash are frozen
in the manifests here.

This package has no provider call or treatment arm. A later causal continuation
would require separate authorization and a separate execution harness.
