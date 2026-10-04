# Additional human-monitor trajectories

This package publishes seven historical, task-specific human-monitor records: FBR243, GLZ700, RAT022, SPC34 v2/v3, Grammar Fuzz v2, and TPL40. Each directory contains the available human decision and intervention files plus the corresponding online Task output and research event stream. `MANIFEST.json` records source-relative provenance, source/export SHA-256, byte size, and any redaction counts for every exported file.

These are historical diagnostic records across different tasks and setups, not matched comparisons or evidence of a mechanism's causal effect. The earlier Fyne human-reference intervention package remains at `../manual_fyne_reference/` and is not duplicated here. The Kitex manual-monitor attempt is excluded: it stopped at Task turn 4 after a provider timeout and does not contain a substantive human-monitor decision trajectory.

Publication is deliberately scoped. It excludes task workspace snapshots, provider request bodies and private sessions, trial/container configuration, credentials, hidden tests, solutions, and native-verifier artifacts. `task_online/output.txt` is an online Task transcript, not a complete replayable Supervisor session. Source paths in the manifest are local provenance identifiers; they are not expected to resolve from the remote repository. Task/source excerpts remain attributable to their original projects and licenses.

Do not mount these research artifacts into a live Task or Supervisor workspace. They include historical research context and are for offline audit only.
