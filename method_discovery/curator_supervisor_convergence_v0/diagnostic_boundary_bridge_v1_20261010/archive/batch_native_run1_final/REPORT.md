# C02 H/R native-control static batch: mechanical record

Status: stopped on infrastructure/transport ambiguity after three started slots. No replacement or later slot was launched.

- Frozen implementation commit: `a782f811d40ec37eb013bd018036db03b2ac5197`.
- H_full first-request canonical SHA-256: `d4a866f07c8376fd990745dda4d207b87299e7d690117c7584dcf2b28f1fa77b`.
- R_full first-request canonical SHA-256: `58ad93e929c086c78ef5e7094d715481c584bf69f86f1af415c4ebb91b330e56`.
- Historical dialogue 418-line prefix SHA-256 in every started slot: `bf18b5e097813bcdba473eb9bfe1c851a6a546525685d44801a44d7b4a3594a8`.
- Task image: `sha256:b0da1cb31d367df38d05b81f98e68a94b0f7114efd3c82537633d1d92325efe1`.
- Production changes, Task Agent calls, native evaluator calls, training calls, scoring-model calls: 0.

| Slot | Terminal | Outer cycles | Provider requests | Accepted responses | Wall (s) |
| --- | --- | ---: | ---: | ---: | ---: |
| C02-P1-H | Static root intervention recorded; no Task delivery | 31 | 31 | 31 | 527.328 |
| C02-P1-R | Static root intervention recorded; no Task delivery | 3 | 3 | 3 | 66.968 |
| C02-P2-R | Infrastructure/protocol failure; no terminal control | 22 | 22 | 21 | 250.016 |

The last request in C02-P2-R timed out during response reading. Its server-side completion is unknown; the frozen zero-ambiguous-retry policy prevented a resend. Nine planned slots were not started. The two earlier terminal actions are mechanical actions only, not quality judgments. Independent reviewers have not assigned endpoint categories A–D.

Offline checks before launch: 11 bridge tests passed, followed by focused archive and root-wait tests (2 passed); production CRS/RHR/RER regression 48 passed. An initial production-test collection from the repository root failed due to missing Python module path; rerunning from `GenericAgent-main` passed. The latter emitted a Windows temporary-directory atexit warning after exit code 0. Frozen request construction and image/source/profile gates passed before the first model send.

`MECHANICAL_SUMMARY.json` in the ZIP/TXT gives per-slot first control proposal, actual tool-call counts, lifecycle event counts, request usage, root subreviews and raw locators. `RAW_TRACE_INDEX.json` lists original local and exported file hashes. The export redacts one private endpoint occurrence in `C02-P2-R.stderr` only; the unmodified original remains under `E:\c02_hr_native_boundary_static_20261010_run1` with its source SHA in the index. The selected archive does not claim to be a host snapshot; disposable Task-code copies, HOME/TMP/build caches and scratch are excluded as documented in the index.

No causal or diagnostic-quality conclusion is drawn from this partial batch. No later slot, baseline, Task continuation or native evaluation was run.
