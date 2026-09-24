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

The materializer emits deterministic request envelopes for offline inspection;
it never imports a provider client and never sends a request.

## Frozen cases

- `S`: Sphinx R3, cut at the first completion proposal (`internal_turn=52`,
  event `evt_9921d8a0c1d4425bb3809f90794c0621`). Later task behavior,
  evaluation, and final completion are excluded.
- `F`: the real Fyne DCEC-v1 checkpoint-0001 (`task_turn=86`,
  `request_sequence=57`, request hash recorded in the manifest).
- `C`: the historical `synthetic_root_complete` correct-control material from
  R12, reused by reference rather than recreated.

Case labels, expected outcomes, and research scoring are not emitted in the
model-visible envelope.

## Offline checks

Run:

```text
python method_discovery/diagnostics/d1_formalization_burden_20260924/d1_harness.py --self-test
```

The test verifies identity/cutoff hashes, 12 fixed records, six-call budgets,
FREE/PROTOCOL parity, treatment-only differences, no label leakage, and zero
provider-request behavior.

