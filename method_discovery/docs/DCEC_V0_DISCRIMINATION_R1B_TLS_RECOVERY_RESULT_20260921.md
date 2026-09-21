# DCEC-v0 R1b TLS-recovery replacement batch: factual archive

Date: 2026-09-21  
Authorization-only commit: `dd5d341`  
Mechanism implementation: `1cd7048c5742ca7415937ec5142cc28fd2bcaf22`  
TLS transport repair: `52cc73b`  
Zero-model preflight archive: `fde6241`  
Formal output: `method_discovery/runs/dcec_v0_discrimination_r1b_tls_recovery/`

## Classification boundary

All four preregistered records ran exactly once in the frozen order. No record was
retried or replaced.

The R1 certificate failure did not recur. The frozen gateway completed its configured
TLS setup, but every attempted model request received HTTP 502 from the gateway's
generic upstream-exception path. Each record exhausted the unchanged provider recovery
policy before any model response or usage record was produced. The archived artifacts
do not expose a more specific upstream exception, so they do not establish that the
provider accepted an HTTP request.

Accordingly, R1b contains no scientific observation of ordinary or DCEC behavior. It
must not be treated as a DCEC failure or as evidence comparing the two conditions.
The batch is retained as a system-wide provider/transport infrastructure failure after
the separately verified TLS-handshake repair.

R1 remains permanently preserved at
`method_discovery/runs/dcec_v0_discrimination_r1_launchprep/` with its original
classification:

`INVALID — infrastructure / TLS transport failure before first model response`

## Frozen-order record facts

| Record | Sequence / condition | Status / stop reason | Logical calls | Transport attempts | Successful usage responses | Supervisor wall | Host elapsed / cleanup | Deadline |
|---|---|---|---:|---:|---:|---:|---:|---|
| 01 | latent / ordinary | error / worker_review_error (`ProviderRecoveryExhausted`) | 1 | 18 | 0 | 131.878s | 135.000s / 0.375s | 900s; not exceeded |
| 02 | latent / DCEC-v0 | error / worker_review_error (`ProviderRecoveryExhausted`) | 1 | 18 | 0 | 132.960s | 136.078s / 0.453s | 900s; not exceeded |
| 03 | correct / DCEC-v0 | error / worker_review_error (`ProviderRecoveryExhausted`) | 1 | 18 | 0 | 131.893s | 135.063s / 0.375s | 900s; not exceeded |
| 04 | correct / ordinary | error / worker_review_error (`ProviderRecoveryExhausted`) | 1 | 18 | 0 | 131.865s | 134.953s / 0.360s | 900s; not exceeded |

The 18 transport attempts per record are transport retries/recovery attempts inside one
logical model call. Tokens and monetary usage are unknown because no provider usage
response was obtained; they are not reported as zero cost. Task blocking latency is
not applicable because the task side is a scripted frozen fixture.

## Preregistered mechanism chain

### A stage

No model response was produced. There was no A diagnosis, intervention, frozen repair,
or post-repair direct observation in any record.

### Concern lifecycle

The two DCEC records assembled the request-time bounded active view (784 characters)
from an initially absent `working.md`. There was no model-authored concern, state
write/patch, recovering/resolved transition, continuation transition, or out-of-band
state change. This request assembly is not evidence that the lifecycle mechanism ran.

### Root investigation and evidence use

No record reached root review. B never became a focal uncertainty; no model tool action,
discriminating observation, grounds revision, or completion control occurred.

### Correct control

The correct-control records also failed before the first model response, so false
blocking, UNKNOWN behavior, repeated investigation, and approval behavior cannot be
evaluated.

## Archive completeness

Each record preserves its result, frozen task/workspace, dialogue, provider history,
request attempts, progress, reviews, working-state timeline, transport projection, and
worker result. Top-level `results.json` records `finished_once_no_retries`. No prompt,
mechanism, fixture, budget, transport retry policy, or later record input was changed
during execution.

This report stops at the factual boundary and makes no recommendation about another
batch or a mechanism change.
