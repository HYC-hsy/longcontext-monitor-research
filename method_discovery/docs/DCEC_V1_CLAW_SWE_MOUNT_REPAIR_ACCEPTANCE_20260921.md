# DCEC-v1 CLAW-SWE mount repair acceptance

## Scope

This is an infrastructure-only repair and a zero-model acceptance. It does not
reuse the invalid R1 run id and is not a scientific DCEC-v1 record.

## Exact repair

The isolated GenericAgent bundle deliberately excludes runtime `temp/`
contents. Before the snapshot is mounted read-only at `/opt/genericagent`, the
launcher now creates the empty directory `source_snapshot/temp/`. The existing
`source_snapshot/memory/` directory remains required and is not recreated or
replaced by the repair.

No DCEC-v1 mechanism file, prompt, state contract, task or Supervisor model,
benchmark data, verifier, network rule, credential boundary, or model stage was
changed.

## Deterministic tests

`long_context_bench/tests/test_dcec_v1_claw_swe_mount_fix.py` verifies that the
missing `temp/` mountpoint is created without altering `memory/`, and that a
snapshot missing its required `memory/` tree is rejected.

Result: `2 passed`.

## Real pinned-container acceptance

The acceptance used the production CLAW-SWE `SWEBenchWorkspace`, the production
isolated adapter mount arguments, and pinned image:

`sha256:77f476927410992943a8d2744aea86b3e0c50d8773b61e56ebba9dd0fd4b9db1`

Observed:

- task container created and started: yes
- `/opt/genericagent` source snapshot read-only: yes
- `/opt/genericagent/temp` writable nested mount: yes
- `/opt/genericagent/memory` writable nested mount: yes
- `/testbed` remained a git worktree: yes
- container network interfaces: `lo` only
- effective capabilities: `0000000000000000`
- `NoNewPrivs`: enabled
- Task Agent started: no
- Supervisor started: no
- Task model requests: 0
- Supervisor model requests: 0
- OTel model traces: 0
- container cleanup: successful

The inference gateway, Agent review loop, verifier, and scientific replacement
run were not started.

## Frozen mechanism identity

All eight DCEC-v1 mechanism source hashes exactly match the hashes frozen by
implementation commit `746a695adac4325d6440941d384d543d1364fef9`.

R1 remains archived at public commit `f7061cd` as:

`INVALID — infrastructure / task container failed before first model response`

A replacement run requires separate authorization.
