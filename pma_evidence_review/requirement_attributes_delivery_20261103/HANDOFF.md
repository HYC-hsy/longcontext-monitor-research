# Windows development thread instructions

Current state: local implementation and offline acceptance complete; **public branch creation and source upload are blocked by automatic approval review**. The planned branch is `pma/requirement-attributes-v1` in `HYC-hsy/longcontext-monitor-research`. Do not assume it exists remotely. A publishing thread must first obtain relevant explicit authorization, retry only the denied connector operations once, then publish/read back and substitute its final remote SHA below. These commands are prepared, not proof of upload or authorization to run real models.

Use a separate checkout, preserve the previous A/DMS worktrees and keep the original six-case archives unchanged. After publication, fetch the independent branch and detach at the **verified remote delivery SHA**. Base is `b831347b4aff9e2802eb3478303ce4af5d0660bf`; source identity was recorded at local source commit `5f1e3f395228412281102f2a12d2eb099a036c4e` and verifies file hashes independently of later documentation commits.

```powershell
$env:PYTHONUTF8 = '1'
$env:LITELLM_LOCAL_MODEL_COST_MAP = 'True'
# In the independent checkout, using the existing PMA-compatible venv:
$py = '.\.venv\Scripts\python.exe'
$delivery = 'pma_evidence_review/requirement_attributes_delivery_20261103'
& $py pma_evidence_review/tools/verify_requirement_delivery.py
& $py pma_evidence_review/tools/run_p1_source_checks.py --requirement-attributes --report E:/PMA-private/requirements-checks-NEW.json
& $py pma_evidence_review/tools/run_p1_requirement_task.py --scenario "$delivery/SCENARIO.json" --script "$delivery/SCRIPTED_RESPONSES.json" --output E:/PMA-private/requirements-scripted-NEW
& $py pma_evidence_review/tools/run_p1_requirement_task.py --scenario "$delivery/SCENARIO.json" --script "$delivery/SCRIPTED_RESPONSES.json" --output E:/PMA-private/requirements-scripted-NEW --resume
```

Expected: verifier passes, 118 offline tests pass, scripted 2-cycle run completes with 3 fake logical calls; completed-cycle resume adds 0. Read `requirement_view.json` for real attributes and same-ID grouping; `bank_after.json` intentionally remains the plain four-key bank. Inspect `results.json`, `run_config.json` request/system/tool hashes and the private archive if needed. Do not upload the whole output directory: `source_links.json` contains the H signing secret and windows may contain unshown bank debug data.

The sample is synthetic public-shaped data, not a real model test. For a future separately authorized real P1 experiment, supply a new `p1-requirement-task-v1` scenario with original task, task ID and continuous cycles, and no `initial_bank`, old windows or evaluator annotations. Start a new private output directory. Use the existing private profile with the original wrapper; do not modify provider/model choices or put its contents in Git. The prepared invocation is:

```powershell
# Execute only after a separate explicit authorization for the real experiment:
& $py pma_evidence_review/tools/run_p1_requirement_task.py --scenario E:/PMA-private/new-task-scenario.json --output E:/PMA-private/requirements-real-NEW --mode real --profile-file E:/PMA-private/existing-profiles.json --authorize-real-p1
```

This is P1-only and does not start Task/P2/evaluation. Startup adds one same-P1 logical call; first successful cycle up to 4, later cycles up to 3, four total source reads but only two serial readable turns and final write-only turn. Explicit failed-startup retries add calls; physical provider retries are unknown. Log all exposed usage and wall time. Do not rerun old methods or claim semantic improvement from fake tests.

Before any archive/config exists, a recorded startup failure at a safe stage with zero attempted/completed calls can be corrected and resumed. Other `--resume` paths require identical scenario and runtime identity, uses the committed bank, and never migrates old banks. For uncertain interrupted maintenance, the CLI intentionally fails: inspect committed operations, then use the documented host API acknowledgement and an explicit fresh cycle. It is not a rollback. No multi-process shared-archive support is claimed. Full group expansion is available in the host export; model prompts retain the old BM25 subset and cannot infer complete coverage from an empty group.
