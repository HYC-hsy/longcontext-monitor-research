# Continuous-context PMA: two real tasks (2026-11-07)

- Executed code: `507ed5b7264a80bca11a5a2dc6b2e03d658e8fac` (`pma-predictive-context`).
- Dataset: `2fd12b88aafdd04a52c298e3940bcb189f9766d6`.
- Native Harbor: `459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc`.
- Policy: agent timeout uncapped, task turns uncapped, official verifier timeout.
- `rstan-to-pystan`: `pma-010ed5ddbb8c4ed0`, task terminal `CURRENT_TASK_DONE`, native reward 1.0, 6/6 tests passed, launcher/worker exit 0, cleanup confirmed.
- `nginx-request-logging`: `pma-ba7facf7f302470b`, task terminal `CURRENT_TASK_DONE`, native reward 1.0, 8/8 tests passed, launcher/worker exit 0, cleanup confirmed.
- Runs were serial under one selection. This is two single episodes, not a statistical comparison.

The ZIP is a **redacted visible projection, not raw HTTP bytes or a restorable private run**. It includes task-visible events, P1/P2 host events and requests, memory changes, effective runtime policy, terminal/evaluation summaries, and cleanup records. `SOURCE_MAP.json` maps each included projection to the local original's size and SHA-256; `FIELD_EXCLUSIONS.json` lists excluded fields with hashes. Credentials, profile, private endpoint, provider thinking/signatures, hidden verifier test bodies, and task workspaces are not published. Local private originals remain outside this branch.

The first packaging attempt failed because Windows PowerShell redirected the foreground logs as UTF-16; the public projection tool was corrected to decode the BOM. No task was restarted for packaging.
