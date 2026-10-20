# Offline budget repair: reproduce and prepare only

Run from `E:\longcontext-cqs-v0-20261005`. Python is the existing `E:\LongContext\bench_runtime\pma_native_venv\Scripts\python.exe`; Harbor Python is `E:\LongContext\bench_runtime\m4\harbor-env\Scripts\python.exe`. The Docker fixture needs the already-held `alexgshaw/db-wal-recovery:20251031` image and a running Docker Desktop Linux engine. Every output directory must be new. These commands are offline except the explicitly marked future-live example, which was **not** executed.

## Read-only private SQLite replay and targeted regression

```powershell
$env:CANDIDATE_SQLITE_RAW_RESULT='E:\LongContext\candidate_live_20261020_sqlite_v1\runs\pos-11124237e370473c\control\pos_archive\events.result.json'
& E:\LongContext\bench_runtime\pma_native_venv\Scripts\python.exe -B -m unittest method_discovery.pos_pma_complement_v1_20261019.test_candidate_budget method_discovery.pos_pma_complement_v1_20261019.test_candidate_core method_discovery.pos_pma_complement_v1_20261019.test_memory_adapter method_discovery.pos_pma_complement_v1_20261019.test_worker_fake method_discovery.pos_pma_complement_v1_20261019.test_candidate_ga_seam method_discovery.pos_pma_complement_v1_20261019.test_candidate_auxiliary_transport method_discovery.pos_pma_complement_v1_20261019.test_native_profile_mount_policy -v
Remove-Item Env:CANDIDATE_SQLITE_RAW_RESULT
& E:\LongContext\bench_runtime\pma_native_venv\Scripts\python.exe -B -m unittest method_discovery.pos_pma_complement_v1_20261019.test_candidate_profile_spool -v
```

The second module needs a fresh interpreter because the PoS and PMA test harnesses both install a top-level `episode` package alias. The recorded combined-process import failure is not a product runtime failure or a pass.

## One same-run synthetic lifecycle (already executed)

```powershell
$env:POS_SYNTHETIC_LONG_OUTPUT='1'
& E:\LongContext\bench_runtime\m4\harbor-env\Scripts\python.exe -B -m method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.single_run_fixture --task pos-synthetic-file-http --condition P --research-candidate pos_pma_complement_v1 --output E:\LongContext\pos_pma_budget_offline_20261020_v2 --official-source-git E:\pma-posthoc-official-source-20261014 --task-profile-file E:\LongContext\GenericAgent-main\mykey.py --pma-profile-file E:\LongContext\candidate_profile_docker_20261020_v4\fake_pma_profile.json --ga-source E:\longcontext-cqs-v0-20261005\GenericAgent-main --runtime-root E:\LongContext\bench_runtime\m2\linux --worker-python E:\LongContext\bench_runtime\pma_native_venv\Scripts\python.exe --harbor-python E:\LongContext\bench_runtime\m4\harbor-env\Scripts\python.exe --bench-root E:\longcontext-cqs-v0-20261005\long_context_bench --harbor-source-root E:\LongContext\bench_runtime\m4\harbor-src-pos-clean --candidate-profile-fixture --service-fixture
Remove-Item Env:POS_SYNTHETIC_LONG_OUTPUT
& E:\LongContext\bench_runtime\pma_native_venv\Scripts\python.exe -B -m method_discovery.pos_pma_complement_v1_20261019.verify_budget_chain --evidence method_discovery\pos_pma_complement_v1_20261019\raw_budget_single_run_v2 --committed
```

The first v1 output stopped at Docker image inspect because Docker Desktop was not running. It was not reused; the v2 output and its authorizations are independent. The fake gateway only emits long output when both the synthetic fixture and `POS_SYNTHETIC_LONG_OUTPUT=1` are set; this flag is not part of formal Task execution.

## Actual unarmed preparation (already executed)

```powershell
& E:\LongContext\bench_runtime\pma_native_venv\Scripts\python.exe -B -m method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.single_run prepare --task sqlite-with-gcov --condition P --research-candidate pos_pma_complement_v1 --task-complete-response --occurrence 1 --output E:\LongContext\candidate_budget_plan_sqlite_20261020_v1 --official-source-git E:\pma-posthoc-official-source-20261014 --task-profile-file E:\LongContext\GenericAgent-main\mykey.py --pma-profile-file E:\LongContext\monitor_config\models.local.json --certification-dir method_discovery\pos_pma_complement_v1_20261019\raw_budget_single_run_v2
& E:\LongContext\bench_runtime\pma_native_venv\Scripts\python.exe -B -m method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.single_run prepare --task adaptive-rejection-sampler --condition P --research-candidate pos_pma_complement_v1 --task-complete-response --occurrence 1 --output E:\LongContext\candidate_budget_plan_sampler_20261020_v1 --official-source-git E:\pma-posthoc-official-source-20261014 --task-profile-file E:\LongContext\GenericAgent-main\mykey.py --pma-profile-file E:\LongContext\monitor_config\models.local.json --certification-dir method_discovery\pos_pma_complement_v1_20261019\raw_budget_single_run_v2
```

Both outputs have `execution_authorized=false` and no `authorization.json` or run directory. Their public exact-byte copies and hash index are `raw_budget_plans_v1/`. The private profiles are used only for identity hashing and are not copied into that directory.

## Future live serial commands — not authorized here and not executed

Only after separate approval, generate fresh one-use bound authorization files for each existing plan. The existing `single_run run` checks method, code/source hashes, profile, asset, output root, complete-response policy and Task deadline before sending. Merely setting the environment variable cannot authorize a run. The following illustrates the same generic entry and fixed order; the placeholder authorization paths do not exist in this delivery.

```powershell
$env:GA_TASK_COMPLETE_RESPONSE='1'
$common = @('--ga-source','E:\longcontext-cqs-v0-20261005\GenericAgent-main','--runtime-root','E:\LongContext\bench_runtime\m2\linux','--task-profile-file','E:\LongContext\GenericAgent-main\mykey.py','--pma-profile-file','E:\LongContext\monitor_config\models.local.json','--worker-python','E:\LongContext\bench_runtime\pma_native_venv\Scripts\python.exe','--harbor-python','E:\LongContext\bench_runtime\m4\harbor-env\Scripts\python.exe','--bench-root','E:\longcontext-cqs-v0-20261005\long_context_bench','--official-source-git','E:\pma-posthoc-official-source-20261014','--harbor-source-root','E:\LongContext\bench_runtime\m4\harbor-src-pos-clean')
& E:\LongContext\bench_runtime\m4\harbor-env\Scripts\python.exe -B -m method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.single_run run --output E:\LongContext\candidate_budget_plan_sqlite_20261020_v1 --authorization <NEW_SQLITE_ONE_USE_AUTHORIZATION> @common
if ($LASTEXITCODE -ne 0) { throw 'SQLite failed: do not start sampler' }
# An approved operator must also confirm the existing native-SHARED archive,
# evaluator and cleanup continuation gate, even when the official reward is 0.
& E:\LongContext\bench_runtime\m4\harbor-env\Scripts\python.exe -B -m method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.single_run run --output E:\LongContext\candidate_budget_plan_sampler_20261020_v1 --authorization <NEW_SAMPLER_ONE_USE_AUTHORIZATION> @common
Remove-Item Env:GA_TASK_COMPLETE_RESPONSE
```

The `<...>` tokens are illustrative and cannot pass as authorization. A future authorized serial controller must enforce the existing stop rule after SQLite: normal completion/known budget exhaustion with sound evaluation, archive and cleanup may continue regardless of reward; transfer, identity, required capture, evaluator infrastructure or cleanup faults stop sampler. This document neither mints authorization nor starts either formal task.
