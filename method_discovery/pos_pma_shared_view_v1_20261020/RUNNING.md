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

Future real use would require a separate source-bound certification, frozen
manifest/profile/assets, per-run authorization and the existing native-SHARED
stop/evaluate/cleanup chain. No such authorization exists in this package.
