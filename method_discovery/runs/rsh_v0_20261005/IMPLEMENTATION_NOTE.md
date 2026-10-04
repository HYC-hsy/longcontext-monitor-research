# RSH-v0 zero-model implementation note

RSH is opt-in through `monitor_release_support_horizon=true`. It requires CFS,
DCM, continuous manual verification, and EIS off. Its only model-visible change
is a bounded mechanical horizon appended to the first valid root
`allow_complete(result=resolve)` DCM tool receipt. The local patrol receipt,
second root allow, system prompt, seven tools, cadence, and completion
freshness checks are unchanged.

The root-review collector starts at the current handoff, records tool calls and
results with dialogue line locators, and promotes a completed `file_read` or
`code_run` result to fresh only after a subsequent provider request containing
that receipt successfully returns a model response. Task paths are required for
fresh file reads; private Monitor reads are excluded. The latest full CFS
Situation must have a successful injection receipt. Prior local/root reviews,
unreturned calls, and same-response tools after a release are not promoted.
Every horizon preserves the full original-task-in-root-input fact without
claiming any requirement is verified. Root exit discards the collector.

Audit events: `rsh_root_started`, `rsh_direct_observation_visible`,
`rsh_horizon_emitted`, `rsh_root_ended`. These contain provenance and rendered
text, not adequacy or defect labels. The cap is 1800 extra characters; omitted
direct-observation rows remain in the full audit event with locators.

Offline command (no network/provider inference):

`$env:PYTHONPATH='GenericAgent-main'; python -m pytest -q GenericAgent-main/tests/test_rsh_v0.py GenericAgent-main/tests/test_dcm_v0.py GenericAgent-main/tests/test_cfs_v0.py`

Observed: `27 passed in 3.29s` (exit code 0). The Windows Python process also
printed an unrelated pre-existing pytest atexit temp-directory permission
warning after the completed result.

Historical projection command (read-only DCM raw inputs; writes only replay
output under this directory):

`$env:PYTHONPATH='GenericAgent-main'; python method_discovery/diagnostics/rsh_v0_replay.py`

Limitations: this horizon does not inspect semantic support, validate test
quality, infer requirement coverage, or change terminal native evaluation.
Successful provider response is the conservative visibility boundary; a
timed-out send with unknown remote consumption is not counted. A completed
`code_run` read of a session started before the root may lack its original
command in this review and will show `unknown/not_available`.
