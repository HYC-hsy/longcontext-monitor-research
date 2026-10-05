# Single Kitex CQS-off diagnostic baseline

Run `32a93bfa62564ff9a7530510f259540d` is the only authorized Stage-2 diagnostic baseline. It used the frozen CQS-v0 code tree with `monitor_control_question_state=false`; no Supervisor mechanism was edited. The separate [execution note](EXECUTION_NOTE.md), [plan](PLAN.json), [manifest](RUNNER_MANIFEST.json), and authorization preserve the pre-run identity.

The complete copyable raw record is under `records/01_32a93bfa62564ff9a7530510f259540d/`. Its `RAW_FILE_MANIFEST.json` lists source, archive path, byte count and SHA-256 for every copied item. Large terminal `/app` tar captures remain at the listed local-only paths with size and SHA-256; they are not silently omitted. `ARCHIVE_INTEGRITY.json` verifies all 350 copied files, both local captures and a scan for private gateway header values. It reports zero missing paths.

`PROVIDER_INPUT_EXPOSURE_AUDIT.json` counts the actual gateway request bodies containing the bounded DCEC working-state block. Persistent `provider_history.json` removes request-local active-context entries after each request, so it is not the sole proof of what was sent. CQS events and provider-ready CQS blocks are zero in this record.

The raw terminal result is under `verifier/`; `bridge/evidence/pre_verification_capture.json`, `verification_release.json`, and `trial_end_binding.json` bind it to the captured `/app`. The native evaluator ran only after the online agent phase. No semantic judgment about the baseline or comparison is made here.
