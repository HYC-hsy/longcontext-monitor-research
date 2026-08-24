# M1 Engineering Candidate: Pre-Real-Run Report

Date: 2026-08-24
Parent method: `m0-v1.1` (`1a753a4`)
Experiment contract: `f81cc2b`
Status: engineering ready; no real-task treatment evidence yet

## Goal

Implement the smallest independently switchable persistent task--reasoning--
evidence workspace, preserve the M0-v1.1 control path, propagate the treatment
through every selected real-task runner, and stop before paid execution.

## Implemented increment

M1 adds an event-backed open-semantic projection over deployment-visible public
history. The projection contains:

- an immutable root-task reference and exact public-task archive;
- stable, extensible semantic objects with natural-language summaries, public
  source anchors, state labels, and root links;
- open relations between objects;
- deterministic projection of M0's root obligation audit and current repair
  episode;
- monitor-authored deltas for local intent, causal hypothesis, evidence scope,
  open question, repair state, or other task-specific semantic roles;
- active read/search tools and checkpoint reconstruction after restart or
  context compaction;
- append-only workspace update events and OTel-compatible update telemetry.

The workspace is not an online checker and makes no intervention decision.
Invalid rows are ignored and audited. Raw task text, trajectory, workspace
files, and monitor decisions remain available for reconstruction and override a
stale compiled projection.

## Isolation and attribution

The switch is `GA_M1_WORKSPACE_ENABLED=1`. It is rejected unless the persistent
M0 monitor is enabled. When disabled:

- no M1 files are created;
- no M1 state appears in the checkpoint;
- no M1 tools, schema, or guidance appear in the monitor prompt;
- the audited prompt fixture is byte-for-byte equal to `m0-v1.1`:
  SHA-256 `03bf638795998ca9aced47c520830b68536c5af0f99560930f2224ba65fcdf3b`,
  length 8,362 characters.

Thus the prepared control remains M0-v1.1 behavior running from the same source
tree; the treatment adds only the M1 switch and condition/output identities.

## Runtime propagation

The switch is propagated through:

- direct GenericAgent startup;
- CLAW-SWE container execution;
- Harbor GenericAgent and LHTB adapters;
- RoadmapBench/LHTB ultralong runner;
- Terminal-Bench runner.

The prepared manifest contains eight branches: control and treatment for PyG,
FBR, SymPy, and install-windows in the frozen order. It contains no API keys or
authentication tokens and has status `prepared_not_executed`.

Prepared GenericAgent source SHA-256:
`cbeeb7e279c5a567fc3a1c68e17318452682cd4f6534118d7da04d314eab975d`.
The value exactly matches the production runner's `tree_hash(..., ga_mode=True)`
at report time. It must be regenerated if GenericAgent source or behavioral
assets change before launch.

## Files

Core:

- `GenericAgent-main/m1_task_workspace.py`
- `GenericAgent-main/m0_deliberative_monitor.py`
- `GenericAgent-main/agentmain.py`

Runner/adapter propagation:

- `long_context_bench/adapters/harbor_ga_agent.py`
- `long_context_bench/adapters/harbor_ga_lhtb.py`
- `long_context_bench/scripts/run_claw_swe_m2.py`
- `long_context_bench/scripts/run_harbor_tb2_m4.py`
- `long_context_bench/scripts/run_ultralong_m12_proofs.py`

Preparation and evidence:

- `method_discovery/m1_prepare_real_task_batch.py`
- `method_discovery/artifacts/m1_engineering_20260824/real_run_manifest.json`
- associated unit and integration tests.

## Validation

- GenericAgent M0/M1/checkpoint/research suite: 81 passed.
- Benchmark adapter/runner suite: 93 passed.
- M1 manifest suite: 3 passed.
- Combined reported checks: 177 passed.
- Python compilation passed for the modified GenericAgent runtime modules.
- Strict panel/manifest JSON parsing passed.
- Prepared source hash equals the production runner source hash.
- Manifest secret scan found no auth token, API-key field, or long `sk-` token.
- `git diff --check` passed; line-ending warnings are informational CRLF notices.
- Every individual implementation step remained below 600 changed code lines.

## Engineering observations

Two defects were found and corrected before real execution:

1. reused artifact directories could retain an old task-text copy even while
   rejecting the old semantic projection;
2. unchanged obligations initially appeared updated every turn solely because
   `updated_turn` changed.

The final implementation atomically replaces mismatched task text and suppresses
semantically unchanged updates. A separate attribution audit also found and
removed unconditional M1 prompt text from the control path.

## Completion gate

- [x] Independently switchable open-semantic workspace implemented.
- [x] Root task, obligations, local semantic state, evidence anchors, repair,
  root links, lookup, restart, and reconstruction paths implemented.
- [x] No online checker or post-run information introduced.
- [x] M0 control prompt and checkpoint path preserved when disabled.
- [x] Four-source-family runner paths prepared for the frozen panel.
- [x] Cost and state-update telemetry retained.
- [x] Non-paid engineering validation passed.
- [ ] Complete PyG control/treatment real-task pair not yet run.
- [ ] M1 behavioral gain, regression, and cost are unknown.
- [ ] M1 is not accepted and must not receive an `m1` tag.

## Real-run gate

The next authorized action is preflight followed by the first frozen PyG pair.
The experiment must stop as soon as that pair is interpretable or if a model,
image, API, timeout, cost, process/native disagreement, or capability-regression
decision appears. The remaining six prepared runs must not start mechanically.
