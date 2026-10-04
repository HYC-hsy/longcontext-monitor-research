# verification_loop_v0 four-trial raw archive

The four fresh trials ran once in the frozen order under implementation `05f56739e32ba95737f7f3e0298f2f9c77906981`. `PLAN.json` remains `execution_authorized=false`; separate `AUTH_<run_id>.json` files record this batch's authorization. Host `host_execution/progress.json` records four `completed` trial-integrity states and all five bridge receipts for each slot. These statuses do not judge task correctness or mechanism effectiveness.

| Slot | Task / mode | Task requests / attempts | Supervisor requests / attempts | Task turns | Reviews | Interventions | Last root action | Native phases / reward |
|---|---|---:|---:|---:|---:|---:|---|---|
| 01 `4fda7c19e6aa43afb92faf387f901347` | Fyne / MANUAL | 103 / 103 | 53 / 53 | 103 | 10 | 4 | `allow_complete` | 4/7; 0.54545 |
| 02 `1b371fb767124c228590893fa7e80407` | Fyne / LOOP | 40 / 40 | 48 / 48 | 40 | 9 | 2 | `incomplete_delivery` | 2/7; 0.27273 |
| 03 `3ec43bf898b846c2b3b36ed7ca6cc649` | Kitex / LOOP | 114 / 114 | 90 / 90 | 114 | 23 | 6 | `incomplete_delivery` | 3/6; 0.5 |
| 04 `72a82ab393ce4b70ac87f55f3336b825` | Kitex / MANUAL | 127 / 127 | 102 / 102 | 127 | 30 | 4 | `allow_complete` | 2/6; 0.4 |

Terminal Task codes were `CURRENT_TASK_DONE`, `EXITED`, `EXITED`, and `CURRENT_TASK_DONE`. In the two LOOP records, runtime `verification_selected` and `verification_result` event counts were both 0; this is a mechanical registration/execution count, not an explanation. MANUAL has no runtime registration; its `code_run` calls numbered 29 and 44, without automatically classifying which were selected public checks. Full token/cache observations, duration, control counts and termination codes are in `BLOCK_MECHANICAL_SUMMARY.json` and each `records/<slot>_<run_id>/MECHANICAL_SUMMARY.json`.

Each record retains Task research events/output, complete public events and synopsis, Monitor dialogue/provider history/attempts/usage/reviews/progress, working note, command scripts/output, runtime and bridge receipts, raw gateway requests, root request checkpoint JSON, native evaluator files, and original runner/trial results. `VERIFICATION_EVENT_INDEX.json` and `INTERVENTION_FOLLOW_INDEX.json` give raw line locators without semantic classification. `RAW_FILE_MANIFEST.json` lists every copied file's SHA-256; no listed source was missing. Original large terminal capture tar files remain only at the listed local paths with bytes and SHA-256 in that manifest. Native results were terminal artifacts, not online feedback to either model.

This archive is a four-run exploratory record, not an efficacy conclusion or a causal estimate. No trial was rerun, no extra slot was started, and no candidate/config change was made after the first scientific request.
