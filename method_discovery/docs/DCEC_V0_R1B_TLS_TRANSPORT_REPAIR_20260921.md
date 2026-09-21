# DCEC-v0 R1b TLS transport equivalence repair

Date: 2026-09-21

## Scope and frozen scientific boundary

R1 remains permanently archived at
`method_discovery/runs/dcec_v0_discrimination_r1_launchprep/` and is classified as:

`INVALID — infrastructure / TLS transport failure before first model response`

R1b was authorized because all preregistered R1 records failed identically in the
transport layer before any model response was produced. No model outcome or
condition-specific behavior from R1 was available for method tuning. The scientific
mechanism, fixture, order, budgets, and pass criteria remain unchanged.

This change is limited to reproducing the frozen production provider profile's TLS
trust semantics in the isolated inference gateway. It does not change DCEC, its
prompt, `monitor/working.md`, the fixture, model parameters, run order, deadlines,
review limits, repair transition, no-retry rule, or evaluation gate.

## Production TLS and proxy audit

The local `claude_monitor_opus48` profile resolves to these non-secret properties:

- provider: `anthropic`
- API base host: `cc-vibe.com`
- `verify`: boolean `true`
- effective trust source: the production Python `requests/certifi` CA bundle
- effective CA bundle SHA256:
  `fd3d97554bdaed3f35967c3e2f0e2ff12a7466ec83d050967c791bab60592499`
- proxy configured: `false`

No API key, authorization header, proxy credential, or CA content is included in the
public artifacts. The CA file is copied only into the temporary gateway directory,
mounted read-only, and is not copied into the experiment archive.

## Repair

The production client passes `verify=True` to `requests`. The isolated gateway now
receives the same production `requests/certifi` bundle and constructs its TLS context
with `ssl.create_default_context(cafile=...)`. Certificate-chain and hostname
verification remain enabled. A configured production proxy causes a pre-request
failure because proxy equivalence is not implemented; the current frozen profile has
no proxy.

The gateway still forwards the same model request. TLS configuration exists only in
the host/gateway transport configuration and is not model-visible.

## Zero-model verification

Deterministic local HTTPS tests exercise the real gateway context builder:

- a server certificate signed by the configured test CA succeeds;
- a server certificate without its signing CA fails;
- a trusted certificate with a mismatched hostname fails.

The real upstream transport probe performs TCP plus TLS handshake only. It does not
send an HTTP request to `/v1/messages`, a completion, or any model input. The observed
result was:

- TLS handshake attempts: `1`
- TLS handshake success: `true`
- peer hostname: `cc-vibe.com`
- TLS version: `TLSv1.3`
- verification enabled: `true`
- provider HTTP requests: `0`
- model API calls: `0`

R1b is frozen at
`method_discovery/runs/dcec_v0_discrimination_r1b_tls_recovery/`. It remains absent
and unauthorized in this change. A separate zero-model preflight archive is required
before any launch authorization.
