# Offline candidate commands

From the repository root, Python 3.13 with the existing GA dependencies:

```powershell
C:\Python313\python.exe -B -m unittest -v method_discovery.pos_upstream_ga_v1_20261017.test_citation_fix method_discovery.pos_pma_complement_v1_20261019.test_memory_adapter method_discovery.pos_pma_complement_v1_20261019.test_candidate_core method_discovery.pos_pma_complement_v1_20261019.test_worker_fake method_discovery.pos_pma_complement_v1_20261019.test_candidate_ga_seam
C:\Python313\python.exe -B -m unittest -v method_discovery.pos_pma_complement_v1_20261019.test_candidate_auxiliary_transport method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.test_live_wiring
C:\Python313\python.exe -B method_discovery/pos_upstream_ga_v1_20261017/test_ga_seam.py -q
$env:PYTHONPATH='E:\longcontext-cqs-v0-20261005;E:\longcontext-cqs-v0-20261005\method_discovery\curator_supervisor_convergence_v0\pma_full_upstream_ga_v1_20261013\vendor\pma_89e5c0d\src;E:\longcontext-cqs-v0-20261005\method_discovery\curator_supervisor_convergence_v0\pma_full_upstream_ga_v1_20261013\vendor\pma_89e5c0d\external\harbor\src'
E:\LongContext\bench_runtime\m4\harbor-env\Scripts\python.exe -B -m unittest -q method_discovery.pos_pma_complement_v1_20261019.test_candidate_profile_spool
$env:CANDIDATE_PROFILE_TEST_ROOT='E:\LongContext\candidate_profile_docker_FRESH'
E:\LongContext\bench_runtime\m4\harbor-env\Scripts\python.exe -B method_discovery/pos_pma_complement_v1_20261019/test_candidate_profile_worker_docker.py
```

The generic preparer selects `--condition P --research-candidate
pos_pma_complement_v1` with a fresh output directory and the existing fixed
official-source checkout, private Task/PMA profiles and image. `prepare` sets
`execution_authorized=false`; it is not permission to run a formal Task.
The analogous `PoS` and `PoS-citation-fixed` identities remain independent.

The zero-model Docker fixture uses the existing `single_run_fixture` command,
the registered `pos-synthetic-file-http` synthetic package and
`--research-candidate pos_pma_complement_v1`. Its fake transport has no
provider fallback; its Task service and sentinel are synthetic. It requires
the fixed Harbor source, current Docker daemon and the pre-existing runtime.
The output directory must not exist. Exact command and result belong in the
audit TXT, not in a live authorization.

Future profile execution requires independent authorization, source-bound
certification, frozen actual Task/PMA profiles, and the existing one-use
authorization gate. The profile code path is implemented but this document
does not create or consume a live authorization. The isolated Docker profile
test uses a local fake HTTP service for PoS and launches the actual separate
host PMA worker entry in another process. Its test-only wrapper replaces only
the final LiteLLM network call with four finite fake returns. The host parses
and SHA-checks a synthetic profile, performs real event-spool dispatch, writes
bound receipts and exits through its normal stop barrier. A post-exit command
confirms unknown receipt without replay. It is not provider compatibility
evidence and is not a substitute for the separately certified
single_run/native-SHARED synthetic lifecycle.
