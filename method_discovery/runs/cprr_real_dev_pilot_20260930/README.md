# CPRR real development pilot — execution archive

Preregistration: `method_discovery/diagnostics/cprr_real_dev_pilot_20260930/PREREGISTRATION.json` (`b33edfe21a5b597e0413b216cfc84df5975cfacf`). The four Stage 1 Roadmap records each ran once, in the frozen order. Stage 2 Sphinx records 05 and 06 were **not started**: an independent, no-model readiness check failed before any model request because the local Docker Linux daemon was unavailable. No record-level rerun or post-result mechanism edit occurred.

| Record | Arm | Task | Native result | Trial end | Task attempts | Supervisor attempts | Completion proposals / interventions | Final control |
|---|---|---|---|---|---:|---:|---:|---|
| 01 | M1 | Fyne | 2/7; reward 0.181818 | agent_phase_completed | 99 | 82 | 3 / 3 | allow_complete |
| 02 | CPRR | Fyne | 1/7; reward 0.090909 | agent_phase_completed | 62 | 73 | 2 / 3 | allow_complete |
| 03 | CPRR | Kitex | 2/6; reward 0.4 | agent_phase_completed | 158 | 85 | 1 / 3 | allow_complete |
| 04 | M1 | Kitex | 4/6; reward 0.7 | agent_phase_completed | 142 | 87 | 2 / 3 | allow_complete |

These are objective execution facts, not a CPRR effectiveness verdict. The Task attempt counts include provider attempts; Task usage rows are 98, 62, 158, and 141 respectively, so unrecorded usage is unknown, not zero. Supervisor attempt and usage rows match at 82, 73, 85, and 87; all recorded Supervisor attempts succeeded. The complete raw dialogue, provider histories, attempt/usage logs, receipts, task events, native verifier outputs and source identities are under `r1`–`r4`. `RAW_FILE_MANIFEST.json` indexes each published raw file by byte count and SHA-256; published raw files retain their original bytes (`.gitattributes` disables text conversion).

The original full run root remains local at `E:\LongContext\long_context_bench\output\cprr_real_dev_pilot_20260930`. Eight large checkpoint tarballs are not uploaded; their exact paths, sizes and hashes are in `LOCAL_CHECKPOINTS.md`. The public archive includes their checkpoint request/identity/manifest metadata. Private source bundles and gateway credential configuration remain local and are not published. No secret credential contents were intentionally included.

## Mechanical Stage 1 treatment-fidelity gate

Both CPRR records reached root completion. In record 02, first root review `ecced244920b45c89b2833e445d5248b` contains a bounded root support cover in `working.md`, then a direct read of `driver/desktop/app.go` (`toolu_Q3U758KRhJISKnb7095sS7`), a concrete task-grounded contrast between required `SetSystemTrayIcon` and observed `SystemTrayMenu` (`toolu_qQ9dqDG5YM4qIEtWJupnVK`), and a delivered correction (`toolu_6sBXb18Ok3WcZxfjMKQJSP`) that invalidated completion-1. These locations show substantive treatment adoption for the preregistered Stage 2 gate; they do not establish that CPRR improved task outcomes. No strict-slot-style protocol friction was observed. The full scientific interpretation belongs to the independent research audit.

## Stage 2 stop

The Sphinx readiness wrapper was tried only with `--prepare-only`. The first invocation used the wrong local interpreter and failed at Python 3.9 parsing of `Path | None`; the second used `bench_runtime/m2/host-env/python.exe` and reached Docker preparation, which failed on `npipe:////./pipe/dockerDesktopLinuxEngine` because the Docker Linux daemon was unavailable. Both failed before model requests, task runs or verifier. Per the preregistered infrastructure stop rule, 05 and 06 remain `NOT STARTED / ENVIRONMENT BLOCKED`; there is no Sphinx score. The diagnostic wrapper is preserved separately in the experiment directory, but it has not passed a live container check.

The archive script is `method_discovery/diagnostics/cprr_real_dev_pilot_20260930/archive_stage1.ps1`. It copies selected original-byte raw artifacts, verifies each source/destination hash, and writes `RAW_FILE_MANIFEST.json`; it does not synthesize missing trajectories.
