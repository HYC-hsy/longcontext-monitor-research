# DCEC-v1 CLAW-SWE generalization R1: infrastructure failure

## Status

`INVALID — infrastructure / task container failed before first model response`

This record is retained as the sole attempted launch of the preregistered task
`claw_swe:sphinx-doc__sphinx-8551`. It is not ordinary/DCEC evidence and is not
included in generalization conclusions.

## Frozen identities

- DCEC-v1 implementation: `746a695adac4325d6440941d384d543d1364fef9`
- launch-preparation commit: `cee3bb5`
- run id: `dcec-v1-generalization-claw-swe-sphinx8551-r1`
- Task Agent: `native_claude_cc_vibe / claude-opus-4-6`
- Supervisor: `claude_monitor_opus48 / claude-opus-4-8`
- selected task: `claw_swe:sphinx-doc__sphinx-8551`
- retry count: `0`

The task was selected by the preregistered first-different-benchmark-family
rule. No later result-based task selection occurred.

## Direct failure facts

Readiness completed and identified the pinned SWE-bench image. Docker then
failed while creating the Task Agent container. It attempted to bind mount the
per-run temporary directory at `/opt/genericagent/temp`, but that mount point
did not already exist in the image and the image root filesystem was read-only.
The OCI runtime therefore failed during container initialization.

The later runner exception, `OTel model mismatch: expected claude-opus-4-6,
observed []`, is a secondary consequence of the empty trace, not the initiating
failure.

## Scientific-start boundary

- Task container started: no
- Task Agent model responses: 0
- Supervisor model responses: 0
- gateway transport events: 0 (empty log)
- OTel model traces: 0 (empty trace file)
- native verifier executed: no
- native outcome: unavailable
- DCEC state or behavior observed: no

Because no model response exists, this record contains no condition-specific
scientific behavior. It cannot support or refute DCEC-v1 generalization.

## Preserved artifacts

The public archive preserves the launch manifest, launcher stdout/stderr,
readiness and lock records, immutable run identity, failed state, empty gateway
and OTel logs, and the final launch result. Host-side isolated bundles are not
published because they can contain runtime credentials or other non-public
execution material.

## Stop rule

No code was repaired and the task was not rerun. A replacement scientific run
would require a separate authorization after an infrastructure-only repair and
no-model validation of the CLAW-SWE container mount contract.
