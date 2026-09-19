# R5 diagnostic checkpoints (2026-09-19)

This file freezes three offline diagnostic slices from the valid R5 pair.  It
does not start a new model run and does not expose complete task contents.
Ranges refer to the private local artifacts under
`long_context_bench/output/independent_c_online_20260919`.

## Common provenance

- task: `roadmapbench:fyn-2.2.0-roadmap`
- task model: `claude-opus-4-8`
- GenericAgent source SHA: `6f75466428b52f98ad1b1571c366b9b94bef74932944bb94d75275954cb64be2`
- execution harness SHA: `f75673d48d61c385a16b1d01ce85deca4897117c32046cef2947b6f612bfb029`
- C wiring repair commit: `98f718e`
- source and workspace are the same task checksum in both trials

## Frozen slices

| diagnostic state | source slice | purpose |
|---|---|---|
| `semantic_repair_before` | C-on `public_events.jsonl` lines 113–121 (task turns 57–61), plus C-on `dialogue.jsonl` around the matching intervention and subsequent `file_write`/`file_patch` calls | A concrete semantic mismatch before the validator correction; the original requirement, wrong implementation, monitor correction, and repair are all observable. |
| `wrong_completion_before` | C-off `public_events.jsonl` lines 169–179 (task turns 85–90), C-off final `runtime_receipts.jsonl`, and C-off `test-stdout.txt` lines 228–234 | The Agent's global completion claim and the monitor's allow decision before native output shows only `2/7`. |
| `correct_local` | C-on `public_events.jsonl` lines 65–72 (task turns 33–36), with the post-run phase-5 lines 174–184 in `test-stdout.txt` | A local Toolbar implementation segment that subsequently passes its phase; no known defect is injected into the question. |

The `correct_local` label is an evaluation label established by the native
post-termination verifier, not information available to the online model.

## Supporting artifact hashes

| condition | public events | monitor dialogue | runtime receipts | native output |
|---|---|---|---|---|
| C-off trial `fyn-2.2.0-roadmap__pYPV9Wi` | `f847cb2c25570b9ab943bdfd70bfcc2ee3b8c50013164a190d1bb4aaf914e615` | `cc3def9a66e76b4e64daf3f5b43b380e9e0cfbf82be38b8b31719cc2ab8646d5` | `3b9a43d11e84fcf7153fd3acca63e61b5962255079a2927a2d42e678a0ee61f8` | `79f5295822d90fd0aaefb3f8f3320e0a3c697bf2ac44498c2f77afb1b59a8014` |
| C-on trial `fyn-2.2.0-roadmap__gfdkWrS` | `ff34591144575bae58ae67d3d64d89fe304124fee63992bbae61c870e8cd2078` | `b1a1a8ce661750c40cd0b0362e56cd49eaf0fc3c228f73c203a10da935a426de` | `3210294794b01762ed4dec45d41da79c4b0e484424247c3234512c082d2172ea` | `82555c2de652ffdbe8691b8841da456665eadf332dbee9f85ba1b55e479418a4` |

Relative paths for all four files are respectively:

```text
agent/monitor/task_evidence/public_events.jsonl
agent/monitor/monitor_private/audit/dialogue.jsonl
agent/monitor/runtime_receipts.jsonl
verifier/test-stdout.txt
```

## Interpretation boundary

These slices support a three-way follow-up comparison:

1. parent Supervisor continues ordinary investigation;
2. parent Supervisor states a decision-changing unresolved premise, then investigates directly;
3. the same kind of premise is passed to an isolated C verifier.

The hidden native labels and the phrase “validator”, “Desktop”, or “Binding”
must not be supplied to the model when reconstructing the slices.  The labels
above are for offline evaluation only.  The current R5 C-on trajectory made no
actual C call, so these slices do not yet measure C's incremental value.

