# DCEC-v0 Fyne long-run R1: infrastructure-invalid result and TLS repair

## Status

The single authorized run `clean-monitor-fyn-2.2.0-roadmap-dcec-v0-longrun-20260921-r1`
is permanently classified as:

`INVALID — infrastructure / missing TLS route semantics before first model response`

It ran for about 65 seconds. Both the Task Agent path and the persistent Supervisor path
failed before producing a valid model response. The native 0/7 evaluation is therefore not
a scientific DCEC result and must not be used as ordinary/DCEC evidence. No retry was run.

## Direct evidence

The Task Agent output returned HTTP 400 with:

`TLS verification semantics are not configured`

The Supervisor audit likewise recorded a first-attempt `ProviderError` carrying the same
HTTP 400 response. The local artifact hashes are recorded in
`method_discovery/runs/dcec_v0_fyne_longrun_20260921/infrastructure_invalid_r1.json`; full
runtime artifacts remain in the immutable local job directory.

## Root cause

The audited isolated transport requires every gateway model route to contain an explicit
`tls` object. The dedicated DCEC record/smoke isolation path already supplied this object,
but the older generic long-run builder in `long_context_bench/scripts/isolated_run_bundle.py`
still emitted only `base`, credentials, paths and model. `create_tls_context()` therefore
rejected the route before an upstream connection was attempted.

This was a launch-path equivalence gap. It is not a provider certificate failure, a Fyne
task failure, or observed DCEC behavior.

## Minimal repair

The generic long-run builder now mirrors the already audited production TLS contract for
both Task Agent and Supervisor routes:

- `verify=True` uses the production `requests`/certifi CA bundle;
- `verify=<path>` uses that explicit CA bundle;
- `verify=False` is reproduced only when the production profile already says so;
- a configured proxy is still rejected pending an explicit isolation review;
- CA files are copied only into the private, read-only gateway mount;
- the network-less task container cannot read gateway configuration, credentials or CAs.

No DCEC source, prompt, working-state contract, task fixture or model configuration changed.

## Zero-model verification

- `long_context_bench/tests/test_isolated_transport.py` plus the existing TLS regression:
  32 passed.
- `long_context_bench/tests/test_run_ultralong_m12_proofs.py`: 57 passed.
- An actual dual-Opus long-run bundle was materialized without starting Docker inference.
  Both routes contained verified TLS, the expected production certifi hash, an existing
  private CA mount, and `production_proxy_present=false`.
- API requests: 0.
- Model calls: 0.

The unrelated local pytest shutdown warning/optional dependency collection issue is not on
the modified path and did not change the passing targeted results.

## Launch boundary

This repair does not authorize another Fyne run. A new run, if approved, must use a new run
identity and output directory; R1 and its artifacts remain immutable.
