# CFS-v0 four-slot raw archive

The authorized order completed once: Fyne BASE, Fyne CFS, Kitex CFS, Kitex BASE. Production candidate `74a06444b9f78299dceabdb6a42fa44317462b65` was common to all four; the profiles differed only in `monitor_coarse_to_fine_surface`. The historical `FOUR_SLOT_PLAN.md` remains unchanged and retains `execution_authorized=false`; the separate `EXECUTION_AUTHORIZATION.json` and four `AUTH_*.json` files record this run authorization.

Each `records/<ordinal>_<run_id>/` contains the copied runner/trial/Task/Monitor/raw evaluator material, a `RAW_FILE_MANIFEST.json` with SHA-256 for each copied file and local-only large terminal tar locations, `EVENT_LOCATORS.json`, and `MECHANICAL_SUMMARY.json`. The CFS arms additionally retain every `monitor/audit/cfs_deltas/*.json` and `CFS_MECHANICAL_INDEX.json`. `BLOCK_MECHANICAL_SUMMARY.json` is a mechanical roll-up, not an adoption or correctness judgment. `host_execution/` preserves per-slot entry logs and the serial progress record.

The terminal `/app` tar archives remain at the paths and hashes listed under `local_only_large_artifacts` in each record manifest; they are not duplicated in Git. All four records have pre-verification capture, verification release and trial-end binding receipts. The original native results are in each record's `trial/result.json` and `verifier/` directory, separate from online Task/Supervisor evidence.

Archive integrity check: 203, 225, 319 and 422 copied files respectively had no missing entries or SHA-256 mismatches. Each record lists two local-only large tar artifacts. The pre-verification workspace hash, verification-boundary hash and trial-end captured hash agree within each run; native result binding is present. A scan of the 1,185 archived files found no literal private gateway header value. No scientific interpretation is encoded in these checks.

The archived root request snapshots have identical system and seven-tool payload hashes across all four records (canonical JSON SHA-256 prefixes `7392cfaae5f2c143` and `6375929161fe153c`). The four-slot plan, candidate implementation, tools and prompts were not changed after the block began.
