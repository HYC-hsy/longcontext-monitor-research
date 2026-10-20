# Offline running card

`pos_pma_shared_view_v1` is default off. `PLAN_UNAUTHORIZED.json` is a
synthetic example only; `execution_authorized=false` and no live authorization
is created by these commands. Use Python 3.12+ with the existing pinned
dependencies. The synthetic profile must be the isolated fake file whose
endpoint is `https://fake.invalid/no-network`; do not use a private live
profile for this fixture.

From the repository root, run the targeted unit and packed-worker checks:

```powershell
& E:\LongContext\bench_runtime\m4\harbor-env\Scripts\python.exe -B -m unittest method_discovery.pos_pma_complement_v1_20261019.test_shared_view method_discovery.pos_pma_complement_v1_20261019.test_worker_fake method_discovery.pos_pma_complement_v1_20261019.test_candidate_ga_seam
```

For the existing `single_run` synthetic native-SHARED path, choose a fresh
output directory and use `single_run_fixture` with
`--research-candidate pos_pma_shared_view_v1 --candidate-profile-fixture
--service-fixture`. Required fixed paths are the existing official-source
checkout, Task profile source, isolated fake PMA profile, GA checkout,
runtime root, worker Python, Harbor Python/source and bench root. The fixture
forces the final Task/PoS/PMA model hops to finite fake responses, checks the
file and HTTP service with the synthetic sentinel, then removes its temporary
authorization. It must never be run with a real provider profile.

The completed v3 invocation used this command (replace the output with a new
nonexistent directory before any future offline check):

```powershell
& E:\LongContext\bench_runtime\m4\harbor-env\Scripts\python.exe -B -m method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.single_run_fixture --task pos-synthetic-file-http --condition P --research-candidate pos_pma_shared_view_v1 --output E:\LongContext\pos_pma_shared_view_offline_20261020_v3 --official-source-git E:\pma-posthoc-official-source-20261014 --task-profile-file E:\LongContext\GenericAgent-main\mykey.py --pma-profile-file E:\LongContext\candidate_profile_docker_20261020_v4\fake_pma_profile.json --ga-source E:\longcontext-cqs-v0-20261005\GenericAgent-main --runtime-root E:\LongContext\bench_runtime\m2\linux --worker-python E:\LongContext\bench_runtime\pma_native_venv\Scripts\python.exe --harbor-python E:\LongContext\bench_runtime\m4\harbor-env\Scripts\python.exe --bench-root E:\longcontext-cqs-v0-20261005\long_context_bench --harbor-source-root E:\LongContext\bench_runtime\m4\harbor-src-pos-clean --candidate-profile-fixture --service-fixture
```

The Task profile is read only for binding and the finite fake gateway takes
over the final model hop. The fake PMA profile is an isolated fixture, not a
real-role profile. The v3 private output and its authorization-removal receipt
are indexed by `raw_native_v3b/FILE_HASHES.json`.

## Final repair check (2026-10-20)

The final runtime source is commit `52f85a34db52b748f246d6cfd85a4aa686a1d7c5`.
Run the unit command above, plus `test_candidate_core` and the existing PoS
`test_citation_fix`/`test_ga_seam` modules. The PMA `test_episode` suite needs
its pinned vendor roots on `sys.path` and the package `offline_launcher`
alias; the exact invocation and separate raw output are in `AUDIT_REPAIR.txt`
and `raw_tests_repair_v5/`. Mixing PMA's top-level `episode` import with the
PoS `episode` module in one unittest process does not collect that suite.

The final same-run synthetic invocation is the v3 command above with only
`--output E:\LongContext\pos_pma_shared_view_offline_20261020_v6` changed.
Its run ID is `pos-264631de99a64a8f`; published derived records are in
`raw_repair_v6/`. The isolated fake PMA host now makes one valid knowledge
save after the synthetic Task tool result, so the second selection is nonempty.
The earlier v4 failed fixture remains described in `V4_FAILURE.txt`; v5 passed
before the final source-offset bookkeeping patch and is not the final
source-bound certification. Use a *new nonexistent output directory* for any
future offline rerun. These commands never authorize a live experiment.

Future real use would require a separate source-bound certification, frozen
manifest/profile/assets, per-run authorization and the existing native-SHARED
stop/evaluate/cleanup chain. No such authorization exists in this package.

## One authorized SQLite episode (concluded)

`AUDIT_LIVE_SQLITE_20261020.txt` and `raw_live_sqlite_v1/` document the sole
authorized episode `pos-235d5ee3ccf64fa7` under audited runtime commit
`f1c2974bd46aebcaf35114a06cc629e35727295b`. The committed
`certification_v6/` passed the unchanged `verify_evidence` check before
preparation. The new preparation had `execution_authorized=false`; a separate
one-use authorization bound the manifest and run, and was removed after the
episode. Do not rerun this command or use the old authorization. The Task
ended `EXCEPTION` during auxiliary initialization, before any Task action;
the existing same-run deterministic native verifier recorded reward 0 and
cleanup was confirmed. The episode is not a normal method result.
