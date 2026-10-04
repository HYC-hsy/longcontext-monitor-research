# DCM-v0 four-slot raw archive

The authorized order ran once: Fyne CFS, Fyne CFS+DCM, Kitex CFS+DCM,
Kitex CFS. Candidate implementation `dd4c180d4adf82ea8cc4229787e4af3fe8b7b645`
was common to all slots; the private Monitor profiles differed only by
`monitor_decision_conditioned_measurement`. The historical
`FOUR_SLOT_PLAN.md` remains unchanged with `execution_authorized=false`;
`EXECUTION_AUTHORIZATION.json` and the four independent `AUTH_*.json` files
record the separate run authorization. Execution identities and the serial
stop rule are in `PLAN.json`, `RUNNER_MANIFEST.json`, and
`host_execution/progress.json`.

Each `records/<ordinal>_<run_id>/` contains the copied runner/trial/Task,
Monitor and raw evaluator material, original public events, provider dialogue
and usage, CFS delta manifests, terminal capture/binding receipts, original
result and verifier outputs. `RAW_FILE_MANIFEST.json` hashes copied files and
lists local-only large terminal tar artifacts with paths, byte sizes and
SHA-256. The tar files were not duplicated in Git. `CFS_MECHANICAL_INDEX.json`,
`DCM_MECHANICAL_INDEX.json`, `EVENT_LOCATORS.json`, and `MECHANICAL_SUMMARY.json`
are derived navigation materials; the original events remain authoritative.
`BLOCK_MECHANICAL_SUMMARY.json` is a roll-up, not a semantic outcome judgment.

The DCM index distinguishes a tool in the same model response as boundary
issuance from a tool in a later model response, after the receipt could be
seen. It does not label any observation discriminating or adequate. The
`extra_model_inputs_after_boundary_upper_bound` is a sequencing upper bound,
not a causal cost estimate. Root handoff identities are linked from original
`root_frame_input` dialogue events.

All four host entries ended `completed` with exit code zero. Each has
`agent_start_identity`, `pre_verification_capture`, `verification_release`,
`trial_end_binding`, and `inference_send_accounting` receipts. The terminal
native evaluator remained downstream of online control. No slot was rerun.

`ARCHIVE_INTEGRITY.json` records SHA-256 rechecks for 289, 224, 272 and 372
copied files respectively, no missing copied paths, verified local-only tar
hashes, and a private gateway-header-value scan over the public archive.
No literal private header value was found. No scientific comparison or
mechanism-effect classification is made here.
