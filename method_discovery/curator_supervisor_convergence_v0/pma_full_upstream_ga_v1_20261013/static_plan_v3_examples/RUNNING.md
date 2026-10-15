# Static PMA plan v3 (not authorized)

Edit only the ordered `slots` array in a copy of an example. Each row names a registered `case_id`, `variant` (`U`, `S2`, or `R2`), positive `occurrence`, and consecutive one-based `order`. Repeats use distinct occurrences. The fixed asset registry is `SOURCE_MEMORY_STATIC_SCREEN_V2_DRAFT.json`; a plan cannot supply paths, hashes, or cutoffs. Examples: `single_r2.json`, `subset_heap.json`, `repeat_r2.json`, `original_six.json`, and `reordered.json`. These are unauthorized selections, not real-run permissions.

Run the following from this directory, with the repository root, `GenericAgent-main`, this directory, and the fixed PMA vendor `src` and `external/harbor/src` on `PYTHONPATH`. The pinned research Python environment is also required. Replace paths and fresh output names as appropriate. Commands shown here do not contact a provider:

```powershell
$env:PYTHONPATH = "E:\longcontext-cqs-v0-20261005;E:\longcontext-cqs-v0-20261005\GenericAgent-main;E:\longcontext-cqs-v0-20261005\method_discovery\curator_supervisor_convergence_v0\pma_full_upstream_ga_v1_20261013;E:\longcontext-cqs-v0-20261005\method_discovery\curator_supervisor_convergence_v0\pma_full_upstream_ga_v1_20261013\vendor\pma_89e5c0d\src;E:\longcontext-cqs-v0-20261005\method_discovery\curator_supervisor_convergence_v0\pma_full_upstream_ga_v1_20261013\vendor\pma_89e5c0d\external\harbor\src"
$py = "E:\LongContext\bench_runtime\pma_native_venv\Scripts\python.exe"
& $py -m static_source_screen --manifest static_plan_v3_examples\single_r2.json --output E:\LongContext\static_fake_single_new --mode fake
& $py -m freeze_source_v2_batch --plan static_plan_v3_examples\single_r2.json --manifest-out E:\LongContext\static_prepared_new.json --output-root E:\LongContext\static_future_runs_new
```

The fake result is under `<output>/<unique run_id>/`; `summary.json` is updated after each slot. The preparation command verifies public projections and creates only a manifest with `execution_authorized=false`; it does not create an authorization file or the output root. Use new paths for each invocation. The same two commands work unchanged for any listed example or another valid slot selection.

Only after separate future approval and a frozen code/profile identity, the existing one-use protocol is: `python -m freeze_source_v2_batch --authorize --manifest-out <frozen.json> --authorization-out <new-private-auth.json> --output-root <same-unused-output-root> --profile <private-profile.json> --authorization-source <approval-id>`, followed by `python -m static_source_screen --mode live --manifest <frozen.json> --authorization <private-auth.json> --profile <private-profile.json> --output <same-unused-output-root>`. **No such approval or live authorization exists for this work.** The authorization is consumed after the attempted run; a changed slot list, code, profile, asset identity, output root, or binding requires a new freeze and authorization.

After a future run, the archive entry is `python -m archive_source_v2_batch --run-root <output-root> --archive-root <new-archive-root> --manifest <frozen.json> --profile <private-profile.json> --run-code-commit <frozen-SHA> [--comparison-baseline <SHA>]`. Results are in `SLOT_SUMMARY.json`, readable first requests in `REQUEST_SAMPLES.txt`, complete raw records in `raw_trajectories.zip`, and file identities in `FILE_HASHES.tsv`. Completed, started-but-incomplete, and not-started slots are separate states; missing observations are unknown. Fake transport is not provider compatibility or method effectiveness evidence.
