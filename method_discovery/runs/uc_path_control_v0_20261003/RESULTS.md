# Path-first control v0: raw four-trial archive

Frozen candidate: `7911aefd770788d78041e324c4033a16e607fba4`.
Frozen four-slot plan: `PLAN.json` (raw-byte SHA-256
`c0adff8322d99848bd19fe04acae1387cf725889e4c60fcdf3db07b71afee7bb`).
All four fresh sessions ran once in the registered order, with no record-level
rerun. Original runner trial outcome: `agent_phase_completed` in all four.
All four bridge captures and verification releases were present; each
verification-boundary workspace hash matched the captured hash. The native
evaluator ran only after agent termination and release.

| Order | Task | Condition | Run ID | Task requests | Monitor requests / reviews | Interventions | PATH windows in actual provider-ready requests | Native phases; weighted reward |
|---:|---|---|---|---:|---:|---:|---:|---|
| 1 | Fyne | BASE | `22f1466b3f774bfda712ab0f` | 134 | 77 / 17 | 4 | 0 | 1/7; 0.09090909090909091 |
| 2 | Fyne | PATH | `e45eafa42e9a4dad940167e7` | 60 | 43 / 8 | 3 | 43 | 1/7; 0.09090909090909091 |
| 3 | Kitex | PATH | `2a9c70067b474377af1ca049` | 141 | 89 / 44 | 4 | 89 | 1/6; 0.3 |
| 4 | Kitex | BASE | `78364051ac074b4e85760c3b` | 130 | 93 / 20 | 6 | 0 | 2/6; 0.4 |

Counts and observed token/cache buckets, working-note mutations/maximum,
completion proposals, durations, and tool calls are in
`BLOCK_MECHANICAL_SUMMARY.json` and each record's `MECHANICAL_SUMMARY.json`.
One Task provider-usage observation is absent in each Kitex record; observed
token sums cover only recorded usage and do not impute missing values.
Monitor provider attempts and gateway send identities remain distinct from
logical requests in the raw files.

Each `records/NN_<run-id>/` contains copied public events, complete Monitor
dialogue/history/attempts/usage, Task research events and trace, working note,
runtime/delivery receipts, root request checkpoint metadata, native evaluator
output, bridge identity/capture/release/binding receipts, and compressed raw
gateway request/receipt files. `RAW_FILE_MANIFEST.json` gives source paths,
bytes and SHA-256 for each copied original. Large terminal workspace tars
remain at their recorded local paths with size and SHA-256; no source tar was
overwritten. `EVENT_LOCATORS.json` is mechanical: review, window, control,
intervention, subsequent public-event and workspace-observation locators. It
does not classify correctness or effect. `REQUEST_ASSEMBLY_CHECK.json` binds
the actual gateway request bodies to the PATH window and confirms the expected
system guidance and original seven atomic tools.

`dialogue.jsonl`'s `model_input` event is recorded before request-local active
context injection. For that reason, the provider-ready PATH visibility check
uses the gateway's archived request bodies, not the earlier `model_input`
snapshot. No gateway credential values or private profile files are copied
into this archive; an exact-value scan against the private gateway headers
found zero hits in the copied research files.

These four trajectories are development records, not a causal estimate.
No further trial is authorized by this archive.
