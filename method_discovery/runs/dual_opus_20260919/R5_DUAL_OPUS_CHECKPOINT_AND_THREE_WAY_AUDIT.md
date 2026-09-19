# Dual-Opus real checkpoint and three-way diagnostic audit

Date: 2026-09-19

## Frozen identities

- Capture source commit: `679451a`.
- Diagnostic source commit: `037a0ba`.
- Task Agent profile: `native_claude_cc_vibe_opus48`.
- Persistent Supervisor profile: `claude_monitor_opus48`.
- Both resolved to `claude-opus-4-8`; isolated C was configured to inherit the Supervisor profile.
- The source upstream was `cc-vibe.com`; both clients used the isolated local gateway at runtime. Automatic model fallback was disabled.
- The service response metadata did not expose an additional authoritative model name, so no stronger server-side identity claim is made.

## Real checkpoint

- Run: `clean-monitor-fyn-2.2.0-roadmap-dual-opus48-root-capture-20260919-r5`.
- Capture point: first valid root handoff, `completion-1`.
- Provider request position: review `82b7bf855a6d4a4fb1b741a8271b6ce0`, request sequence 45, task turn 44.
- Public archive boundary: one-based `archive_sequence=87`.
- Source kind: `live_request_before_transport`, with `provider_snapshot` History.
- Request contained 95 messages and seven tools.
- Checkpoint manifest contained 2,505 files.
- Restored request SHA-256: `f6d15db25d2229787bbd4bc552b024bd219a9152aab7cf9e944c3b2ea96197cd`.
- Immutable tar SHA-256: `0f75d6ba37265f8f63c5dcd8baf254937fdc1b1e43a7fe62930158920471986f`.
- Production extraction and manifest validation passed. A first extracted copy was deliberately rejected after `git status` refreshed its frozen `.git/index`; the immutable tar was unchanged and a fresh extraction passed.
- No complete task, hidden evaluation, or private parent History is included in this public summary.

## Diagnostic setup

The diagnostic used the same frozen parent History and workspace for all conditions. The common parent History had 95 items, 185,509 characters, and SHA-256 `8892a80f990dd2a5baebf6a6ecfb7e9143bf574e95061a3d5c6077f3cd3beadd`. Group-specific offline instructions and tools were explicit experimental differences.

Public evidence was selected mechanically: original task, public events through cursor 87, and the Go/test/summary files changed at the capture point. The parent could also read its frozen `monitor/state`; isolated C could not. Evaluator answers and post-checkpoint events were not mounted.

## Observed result

| Stage | Status | Logical calls | Successful responses | Recorded provider token units | What happened |
|---|---:|---:|---:|---:|---|
| Ordinary investigation | incomplete | 6 | 6 | 296,769 | Read completion event, requirements, and implementation summary; then attempted `file_patch` and `file_write`, which were absent from the reduced offline tool surface; no final parent decision. |
| Shared question generation | incomplete | 3 | 3 | 157,065 | Used all three calls to read public events and requirements; did not submit a decision-changing question. |
| Parent direct after question | not run | charged shared 3 | — | charged shared 157,065 | Correctly blocked because shared question generation did not finish. |
| Isolated C after same question | not run | charged shared 3 | — | charged shared 157,065 | Correctly blocked because no shared question existed; C was not created. |

Actual unique recorded provider token units were 453,834. These totals include the provider usage fields aggregated by the existing runner and are not dollar cost.

All nine transport calls succeeded. There was no network or model-identity failure. Branch results were persisted independently.

## Interpretation and stopping decision

This run does **not** establish whether C improves decisions, because B and C never reached their divergent investigation stages. It instead identifies two concrete preconditions for a faithful diagnostic:

1. Restoring true persistent Supervisor History while replacing its normal state-maintenance tool surface with only `file_read` and a finish tool creates protocol friction. The model attempted the familiar private-state write operations despite the offline constraint.
2. Under the frozen six-call total and three-call question phase, the shared serial question stage spent its budget acquiring context and did not commit a question.

Per the frozen protocol, the run was not retried with more budget, a different prompt, or a different model. The incomplete branches are retained as experimental results rather than converted into cautious-correct judgments. Any next experiment must first decide whether the diagnostic should preserve sandboxed parent state-maintenance tools or deliberately study a reduced-tool Supervisor; that is a research-design choice, not a silent engineering patch.
