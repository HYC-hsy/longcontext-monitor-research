# Generic GA / original PMA single-run base (offline draft)

`execution_authorized=false`. This directory prepares fixed Terminal-Bench 2
assets and a 12-task selection; it is not approval for any real model call or
official verifier. The underlying single-run path is `single_run.py` → existing
`batch_controller.py` → `live_launcher.py` → pinned Harbor / GA. Condition A
does not create a PMA worker; B uses the unchanged vendored U PMA.

Run from the repository root with the existing Harbor Python and installed
dependencies. Paths below are examples: substitute the fixed local Git checkout
at commit `2fd12b88aafdd04a52c298e3940bcb189f9766d6`, the two **private**
profiles, and an unused output directory. Never put profile contents in a plan
or public log.

```powershell
$py = 'E:\LongContext\bench_runtime\m4\harbor-env\Scripts\python.exe'
$source = 'E:\LongContext\Ref_Benchmark\Terminal-Bench'
$taskProfile = 'E:\LongContext\GenericAgent-main\mykey.py'
$pmaProfile = 'E:\LongContext\monitor_config\models.local.json'
$module = 'method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013'
& $py -m "$module.single_run" prepare --task constraints-scheduling --condition A --occurrence 1 --output E:\unused-single-run --official-source-git $source --task-profile-file $taskProfile --pma-profile-file $pmaProfile
```

Preparation checks fixed Git blob bytes, the local official image identity,
profiles by byte hash, and the per-task native timeouts. It creates an unarmed
plan, manifest and random run identity, and sends no requests. It requires an
unused output directory. For a selected subset, repetitions or reordered
selection, edit only `slots` in `EXAMPLE_SUBSET_DRAFT.json` and invoke the same
single-run preparation through `run_selection.py`:

```powershell
& $py -m "$module.run_selection" --mode prepare --plan path\to\selection.json --output E:\unused-selection --official-source-git $source --task-profile-file $taskProfile --pma-profile-file $pmaProfile
```

`DISCOVERY_12_DRAFT.json` contains the requested 24 ordered A/B invocations
over only the 12 newly selected tasks. It is data for the thin selector, not a
rule inside the run core. A single task/condition, any registered subset,
positive occurrence numbers for independent repeats, and reordering all use
the same one-slot preparation. The supplied `EXAMPLE_SUBSET_DRAFT.json` shows
a repeated condition. Every invocation receives a fresh run ID, container,
output root and (for B) empty memory bank. An existing output is refused.

The offline Harbor/Docker fake fixture runs through the same controller and
launcher with a fake-only authorization that is removed afterward:

The ordered fake exercise uses the same output root for prepare then run,
retains `selection_preparation.json`, writes a separate exclusive
`selection_result.json`, and removes every temporary fake authorization:

```powershell
& $py -m "$module.selection_fixture" --plan E:\longcontext-cqs-v0-20261005\method_discovery\curator_supervisor_convergence_v0\pma_full_upstream_ga_v1_20261013\generic_single_run_20261015\EXAMPLE_ORDERED_OFFLINE_AUDIT.json --output E:\unused-ordered-fixture --official-source-git $source --task-profile-file $taskProfile --pma-profile-file $pmaProfile --ga-source E:\longcontext-cqs-v0-20261005\GenericAgent-main --runtime-root E:\LongContext\bench_runtime\m2\linux --worker-python E:\LongContext\bench_runtime\pma_native_venv\Scripts\python.exe --harbor-python $py --bench-root E:\longcontext-cqs-v0-20261005\long_context_bench --harbor-source-root E:\pma-harbor-459ff6e-clean
```

This is a synthetic evaluator and fake provider only. A future real run must
use a new output root and separately committed A/B evidence whose recorded
execution source identities match the running source. An un-certified draft
cannot be turned into an authorization by this fixture.

```powershell
& $py -m "$module.single_run_fixture" --task constraints-scheduling --condition B --output E:\unused-fixture --official-source-git $source --task-profile-file $taskProfile --pma-profile-file $pmaProfile --ga-source E:\longcontext-cqs-v0-20261005\GenericAgent-main --runtime-root E:\LongContext\bench_runtime\m2\linux --worker-python E:\LongContext\bench_runtime\pma_native_venv\Scripts\python.exe --harbor-python $py --bench-root E:\longcontext-cqs-v0-20261005\long_context_bench --harbor-source-root E:\pma-harbor-459ff6e-clean --service-fixture
```

This uses a synthetic `test.sh`, never an official hidden assertion. A future
real run requires an independently approved, one-use authorization bound to
the exact one-slot manifest, code, profiles, image and run/output identity,
plus committed A/B lifecycle certification. This module cannot mint that
authorization. Only then use `single_run run --output ... --authorization ...`
with the same GA/Harbor/worker path arguments as above; the thin selector's
`--mode run` additionally requires a distinct authorization in each selected
slot directory and stops at the first non-completed disposition.

After a run, read `batch_result.json`, then the run root's `archive/live_result.json`,
`archive/agent_end_native.json`, `archive/writer_termination_check.json`,
`archive/native_test_execution.json` and the Harbor job `result.json`.
Failures and cleanup uncertainty remain separate from native reward. Actual
provider requests and private memory logs remain in the private run root;
public exports are redacted projections. Task model identity, PMA mechanism,
source commit, Harbor commit, image digest, profile bytes, or lifecycle code
changes require re-preparation and re-certification before future authorization.
