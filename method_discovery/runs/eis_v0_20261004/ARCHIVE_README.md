# EIS-v0 four-trial raw archive

The four fresh trials ran once in the frozen order under implementation `6fdde9d425740a802c34f114c518845b89e8a199` and plan `7eb4551e45e3cc82405862754b53fa044fbcc037`. The plan retains its historical `execution_authorized=false`; the separate authorization files and `EXECUTION_AUTHORIZATION.json` record the run authorization. `host_execution/progress.json` reports four completed trial-integrity states with all five bridge receipts for each slot. This is not a judgment of task correctness or EIS adoption.

| Slot | Task / condition | Task requests / attempts | Supervisor requests / attempts | Task turns | Reviews | Interventions | EIS index: artifact / execution | EIS surface injections | Native phases / reward |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| 01 `e832df5b0a8e4fb2bb2f4d5338ada5d4` | Fyne / BASE | 93 / 93 | 53 / 54 | 93 | 7 | 2 | not enabled | 0 | 4/7; 0.54545 |
| 02 `82b860b44c5e4bb8a81b9d01ead5703c` | Fyne / EIS | 61 / 61 | 43 / 43 | 61 | 9 | 2 | 2 / 4 | 43 | 4/7; 0.54545 |
| 03 `3ab0193ad553424ba1a53b87fdec61e8` | Kitex / EIS | 72 / 72 | 59 / 59 | 72 | 8 | 4 | 0 / 1 | 59 | 2/6; 0.4 |
| 04 `cbbd416ac6794ca38adf5b4c5d31e873` | Kitex / BASE | 121 / 121 | 78 / 78 | 121 | 28 | 8 | not enabled | 0 | 3/6; 0.5 |

All four runner manifests report `agent_phase_completed`; final Supervisor review action is `allow_complete` in all four. Task turns are the maximum `task_turn` in the archived public events, not a gateway-attempt count. Detailed token/cache observations, tool calls, duration, and control facts are in `BLOCK_MECHANICAL_SUMMARY.json` and each record's `MECHANICAL_SUMMARY.json`. The EIS surface count is the number of model-visible audit injection events, not independent reviews or proof that the Supervisor used the contents.

Each `records/<slot>_<run_id>/` retains online Task output/events, public events, Monitor dialogue/provider attempts/usage/reviews/progress, working state, command results, gateway request/control receipts, root checkpoint JSON, bridge capture/release/binding evidence, and terminal native-evaluator artifacts. `EIS_MECHANICAL_INDEX.json` provides event locators without semantic classification. `RAW_FILE_MANIFEST.json` lists copied artifacts and SHA-256; the two large terminal capture tar files per record remain at the listed local paths with byte size and hash. BASE intentionally has no candidate-validation index or EIS-surface artifact.

Native scores are post-run artifacts and were not online feedback. This archive is a four-run exploratory record, not a causal estimate or mechanism-effect conclusion. No trial was rerun, no extra slot was started, and no candidate/config change was made after the first scientific request. A post-run research-only archive counter was made tolerant of JSON-encoded tool arguments; it did not affect any online run.
