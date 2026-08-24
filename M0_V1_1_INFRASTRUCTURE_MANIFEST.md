# M0-v1.1 Infrastructure Manifest

Date: 2026-08-24
Parent method: Git tag `m0-v1` (`3fda924`)
Scope: infrastructure-only patch; M0 semantic policy and prompt are unchanged

## Changes

- Harbor jobs now receive an outer `agent_timeout_multiplier` derived from the requested adapter timeout and the task's native timeout. A 7,200-second M0 run on a task with a 3,600-second native limit therefore sets both the adapter timeout to 7,200 seconds and the Harbor outer phase multiplier to `2.0`.
- Monitor checkpoint, decision, and authoritative-state objects use one atomic UTF-8 JSON writer that validates serialized JSON before replacement and removes temporary files after failure.
- Historical archive diagnosis was corrected: all 259 FBR, SymPy, and install-windows decision files are valid UTF-8 JSON. Earlier failures came from PowerShell default-encoding reads, not corrupted archives.

## GenericAgent identity

- M0-v1.1 GenericAgent source SHA-256: `8011844502ecfd01a176c5072da476e4d9ef807d794579b0dae2044a3d5c332c`

## Validation

- GenericAgent M0/checkpoint/research tests: 71 passed.
- Harbor/Claw/TB2 runner and adapter tests: 65 passed.
- Historical strict UTF-8 archive audit: 259/259 decision files parsed and matched `m0-monitor-decision/1`.
- Harbor native `--print-config` proof: `agent_timeout_multiplier` resolved to `2.0` for the two-hour protocol.
- Diff audit: no M0 base prompt, decision semantics, attention policy, or recovery policy changed.

Large run artifacts and credentials remain outside Git.
