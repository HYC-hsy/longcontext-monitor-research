# D1 — Formalization Burden Isolation (preparation only)

This directory freezes, but does not execute, the D1 diagnostic requested by
the research constitution. D1 compares one persistent Supervisor with the
same Supervisor plus a strict machine-readable dependency representation.
There is no new production mechanism, completion guard treatment, selector,
checker, or extra model stage.

The future panel is fixed at three case families × two conditions × two
repeats = 12 records. Every record has at most six logical Supervisor calls.
The run order and identities are in `manifest.json`; no dynamic repeat is
permitted.

## Conditions

`FREE` and `PROTOCOL` share the same semantic contract, parent evidence,
tools, model metadata, and budget. `PROTOCOL` adds only the strict dependency
representation contract (`create`, `retain`, `replace`, `discharge`, status,
and receipts). D1 intentionally does not enable a runtime completion guard.

The materializer reads actual provider-ready checkpoint requests (system,
messages, exact tool schemas, root handoff, and model parameters), verifies
all referenced bytes and SHA256 values, and emits deterministic replay inputs.
Case S is read from its immutable checkpoint tar and deterministically
neutralized; it is not reconstructed from
a later archive plus a cutoff field. The materializer never imports a provider
client and never sends a request.

## Frozen cases

- `S`: Sphinx R3, cut at the first completion proposal (`internal_turn=52`,
  event `evt_9921d8a0c1d4425bb3809f90794c0621`). Later task behavior,
  evaluation, and final completion are excluded.
- `F`: the real Fyne DCEC-v1 checkpoint-0001 (`task_turn=86`,
  `request_sequence=57`, request hash recorded in the manifest).
- `C`: the original `synthetic_root_complete` checkpoint from R8, including
  the original task, public events/check, workspace files, and request.

The protocol validator under `vendor/` is a byte-for-byte copy of the frozen
production validator. The diagnostic-local dispatcher materializes a fresh
mutable snapshot per record, applies it only to `monitor/working.md` writes,
and returns recoverable tool errors; FREE uses the same seven-tool surface
without the validator. Completion guard remains disabled. Every logical call
reinjects the current working-state view. `run_d1.py --execute` checks a
separate authorization artifact bound to a canonical bundle hash, re-hashes
immutable checkpoint manifests, creates a fresh dispatcher per record, and
uses the existing `MonitorProviderClient` loop with a six-call counter. No
authorization artifact is present in this preparation commit, so execution
remains fail-closed.

Case labels, expected outcomes, and research scoring are not emitted in the
model-visible envelope.

## Offline checks

Run:

```text
python method_discovery/diagnostics/d1_formalization_burden_20260924/d1_harness.py --self-test
```

The test verifies source existence and recomputed hashes, provider-ready
request parity, the diagnostic-local strict lifecycle validator (including
`op=create,status=requested` and rejection of `op=requested`), 12 fixed
records, six-call budgets, no completion guard, and zero provider-request
behavior. The protocol validator is copied from the frozen production source
only for this diagnostic; production code is not imported or modified.

The runner path is also tested without a provider:

```text
python method_discovery/diagnostics/d1_formalization_burden_20260924/test_run_d1.py
```

The deterministic fake provider uses the same `execute_records()` path and
exercises valid create, invalid-transition tool error, recovery on the next
logical call, current-state reinjection, and terminal approval.
