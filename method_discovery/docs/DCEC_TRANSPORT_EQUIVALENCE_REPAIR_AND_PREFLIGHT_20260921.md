# DCEC isolated transport equivalence repair and zero-model preflight

Date: 2026-09-21  
Baseline: `d44cfef`  
Transport-fix commit: `285e3a6`  
Preflight: `method_discovery/runs/dcec_v0_transport_equivalence_preflight_20260921/preflight.json`

## Frozen invalid batches

- R1 remains permanently archived as
  `INVALID — infrastructure / TLS transport failure before first model response`.
- R1b remains permanently archived as
  `INVALID — infrastructure / upstream transport failure before first model response`.

Neither batch contains condition-specific model behavior. Neither is DCEC effectiveness
evidence, and neither was overwritten or reused.

## Confirmed gateway defects and transport repair

R1b's immediate 502 cause was a deterministic gateway wiring error: the live POST path
called `create_tls_context(route)` although `route` had not been bound. The broad gateway
exception handler converted that `NameError` to the generic 502 response, so the formal
requests did not reach an upstream HTTP exchange.

The repaired gateway obtains the validated route from the same resolver that produces
the upstream URL and credentials. It also restores two production application headers
that the previous gateway did not preserve:

- `x-model-route: monitor` remains available for internal fixed-route selection and is
  also forwarded upstream;
- `User-Agent: longcontext-monitor/1.0` is forwarded upstream.

Arbitrary route values remain invalid. Model output cannot modify request headers.
Credential values are never logged or written to public diagnostics.

Gateway URL construction now mirrors production `monitor_agent_core.provider._url`
semantics for ordinary bases, versioned bases, bases already ending in the requested
operation, and the explicit `$` endpoint form. The frozen production profile resolved
identically in both paths:

- scheme: `https`
- host: `cc-vibe.com`
- port: `443`
- path: `/v1/messages`
- query key: `beta`
- URL semantics equal: `true`

## Safe transport-stage diagnostics

Gateway diagnostics contain only stage, success/error status, exception class, optional
HTTP status, timestamp and thread identity. They never contain credentials, headers,
request body, system/messages, model output, full URL, or raw exception text.

The recorded stage vocabulary is:

`resolve → connect → request_send → response_headers → response_stream`

Host isolation code collects only these whitelisted JSON events from `docker logs`
before container cleanup and stores them separately from model-visible files.

## Zero-model application equivalence

A local trusted HTTPS upstream received the actual frozen ordinary request body through
the real gateway `Handler`. The comparison passed for:

- method and path/query;
- Content-Type, Accept, anthropic-version and anthropic-beta;
- User-Agent and x-model-route;
- credential scheme (value excluded);
- canonical JSON body semantics.

The successful local lifecycle was:

`resolved → connected → request_sent → response_headers_received → response_stream_completed`

No request was sent to the real provider in this fixture. The separate real-upstream
probe performed TCP plus verified TLS handshake only and succeeded with TLS 1.3 using
the production requests/certifi CA bundle and hostname verification.

## Frozen scientific identity

- DCEC mechanism implementation:
  `1cd7048c5742ca7415937ec5142cc28fd2bcaf22`
- fixture SHA256:
  `d5e5980bedd178cc111ed355e56137a8d819063cf8f877e7381181f1c9e07748`
- ordinary request SHA256:
  `c75d019092c1551e5b8901666c23b58fb764fabe783cfc38f12fafc53e40021b`
- DCEC request SHA256:
  `40b5ff9a3b062cd48071b917abd6f7c324669f28c6f9cf4f070b5f7ee30030f0`

The request hashes are unchanged from R1/R1b. DCEC mechanism and fixture files were not
modified.

## Verification and next gate

The deterministic suite passed 64 tests before the archived preflight. The preflight
also revalidated filesystem/code_run isolation, provider deadline propagation, request
invariance and real TLS handshake.

The frozen smoke manifest is
`method_discovery/artifacts/dcec_v0_20260921/infra_smoke_manifest.json` and remains:

- `execution_authorized=false`;
- `INFRASTRUCTURE SMOKE — NOT A SCIENTIFIC RECORD`;
- one logical call and one provider request maximum;
- no transport retry;
- no DCEC or scientific fixture.

Provider HTTP requests during this repair/preflight: `0`.  
Model API calls: `0`.  
The smoke was not executed, and no R1c manifest or authorization was created.
