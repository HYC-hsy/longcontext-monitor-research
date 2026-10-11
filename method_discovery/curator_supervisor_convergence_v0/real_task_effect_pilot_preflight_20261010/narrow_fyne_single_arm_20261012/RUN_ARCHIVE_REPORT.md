# Fyne narrow_v1 single-arm run: mechanical archive

This is one exposed development-task run, not a contemporaneous T/N comparison. No judgment of intervention quality or causal effect was made for this archive.

## Binding and execution

- Run ID: `pilot-narrow-fyne-20261012-r1`; task: `roadmapbench:fyn-2.2.0-roadmap`; actual route: `S`; variant: `narrow_v1`.
- Run-code commit: `32eb30f9e0d6d4c95cc02d1afa6e594ad2e14202`.
- Frozen manifest raw SHA-256: `544bf8dea094aeee1f69620918ec865308295b4a0980b5d569dea6b6ea46b137`; one-time authorization raw SHA-256: `36efc675d8373c886b3315b81ce310ff14b81747dee306064d931f229064056b`.
- Task image ID: `sha256:b0da1cb31d367df38d05b81f98e68a94b0f7114efd3c82537633d1d92325efe1`; initial task Git HEAD: `7229e889d49c81a83b0b7e09400837f67f6ddad5`. Detailed package/profile identities are in the frozen manifest and raw startup files. Credentials and endpoint literals are excluded.
- Harbor trial began `2026-10-11T16:07:53.104659Z` and ended `2026-10-11T16:43:49.875858Z`. The agent phase ran from `16:08:03.132707Z` to `16:42:50.349876Z`; the single native verifier ran from `16:43:15.347006Z` to `16:43:29.184348Z`.

## Mechanical termination and evaluation

- `pilot_result.json`: returncode `0`, `timed_out=false`, `spool_errors=[]`, `frozen_product=true`, `harbor_verifier_released=true`.
- `agent_end_frozen.json`: terminal `CURRENT_TASK_DONE`, `legal_agent_end=true`, `writers_stopped=true`, `sidecar_clean=true`, `task_terminal_identity_valid=true`. The agent wrapper returncode is `0`; the recorded stopped GA process returncode is `143`. These are distinct fields, not alternative task verdicts.
- Frozen tar is `112259584` bytes, SHA-256 `1d979f6811501c5f6562efd302961361a2ca0cdfab421149bc29d28f6511ad2f`. `pre_evaluation_app.tar.gz` is a byte-exact compressed copy; `FINAL_WORKSPACE_MANIFEST.json` lists its files and source comparison, and `FINAL_WORKSPACE.diff` provides the text patch. This is the frozen product, not a claim that all additions are implementation files.
- Native reward record: `reward=0.09090909090909091`, `phases_passed=1`, `total_phases=7`. Verifier command, stdout/stderr and trial results are under `raw/job/trial/verifier/` and `raw/job/trial/result.json`. This report does not compare that result with either historical Task-only run.

## Request and control counts

- Task public research events record `113` provider attempts, `113` responses and `113` usage records. Last internal Task turn is `113`. Task selected `118` tool calls: `code_run=43`, `file_read=35`, `update_working_checkpoint=5`, `file_patch=27`, `file_write=8`.
- Task recorded token fields summed over usage records: input `160842`, output `44894`, cache-creation input `203112`, cache-read input `2055282`. These are reported fields, not a price estimate.
- Supervisor audit records `73` request attempts and `73` usage records. It records `109` tool calls: `file_read=50`, `code_run=36`, `file_write=1`, `wait=13`, `intervene=8`, `allow_complete=1`.
- Supervisor recorded token fields summed over usage records: input `147818`, output `28896`, cache-creation input `3166535`, cache-read input `1126056`.
- Seven `curator_echo_delivery_confirmed` records are present. One of the eight `intervene` calls received `A current handoff requires the root decision frame before control.` and was not delivered. `INTERVENTION_EVENT_INDEX.json` locates all eight original proposals; original tool results, delivery receipts, later public Task events and provider evidence remain in the raw trace. A delivery acknowledgement is not proof of uptake or repair.
- No additional Task, Supervisor, reviewer, PMA, scoring-model or evaluator runs were started for the archival work. This completed arm itself used Task and Supervisor models and one native evaluator, as counted above.

## Archive inventory and limits

- `RAW_FILE_MANIFEST.json` provides SHA-256 and byte length for every copied or derived file and separately identifies large local-only live checkpoints by path, byte count and hash. `RAW_TRACE_INDEX.json` points to the principal trajectories. `RAW_TRAJECTORIES.zip` preserves the copied text/raw event files; its CRC, member sizes and per-file hashes were checked.
- `pre_evaluation_app.tar.gz` is separate because it is a binary frozen workspace. It is not a post-hoc reconstruction from final patch text.
- The complete task wire request bodies are not newly inferred from the Task-side research-event hashes. Available Task request hashes/events and Supervisor pre-send/provider audit files are preserved at their actual capture granularity. Missing Task wire bytes must not be treated as archived.
- The 5,015 large `live_checkpoints` files were not copied into Git; their exact local paths, sizes and hashes are recorded in `RAW_FILE_MANIFEST.json`. Those local-only files are not represented as remotely downloadable. No complete host snapshot is claimed.
- Archive-side secret screening compared text files to the existing private profile markers and generic token patterns before copying. Original private profile files and endpoint credentials were not copied. The activity authorization contains no credential and is included verbatim only as an execution binding.
- The archive changes are research-only. No production source, method prompt, frozen run manifest or historic run artifact was edited during this post-run archival step. Unrelated untracked `__pycache__` directories were left untouched.

## Primary raw evidence locations

- `raw/archive/agent_start_identity.json`, `agent_end_frozen.json`, `pilot_result.json`, `verification_released.json`, and Harbor stdout/stderr.
- `raw/job/trial/agent/research_events.jsonl`, `output.txt`, agent stdout/stderr, terminal file and trial result.
- `raw/monitor/audit/dialogue.jsonl`, `request_attempts.jsonl`, `provider_usage.jsonl`, `provider_history.json`, and `provider_pre_send/`.
- `raw/monitor/task_evidence/public_events.jsonl`, monitor private state, controlled spool receipts, and trusted audit files.
- `raw/job/trial/verifier/` for the one native evaluation's command, logs and result.

The prelaunch zero-model test record is `PRELAUNCH_ZERO_MODEL_AUDIT.txt`. It is preparatory evidence, not a second real run.
