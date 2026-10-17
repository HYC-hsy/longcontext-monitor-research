# PoS GA input-contract v1 — audit commands

Run from `E:\longcontext-cqs-v0-20261005` with Python 3.13, the existing
Docker/Harbor setup, and the fixed checked-out task assets. The current
four-task run is stopped: the one authorized compatibility probe failed final
progress validation. These commands describe evidence reproduction; they do
not authorize another provider probe or formal task.

```powershell
C:\Python313\python.exe -B -m method_discovery.pos_upstream_ga_v1_20261017.test_role_contract
C:\Python313\python.exe -B method_discovery/pos_upstream_ga_v1_20261017/test_offline.py
C:\Python313\python.exe -B method_discovery/pos_upstream_ga_v1_20261017/test_ga_seam.py
C:\Python313\python.exe -B -m method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.test_live_wiring
C:\Python313\python.exe -B -c "from pathlib import Path; from method_discovery.pos_upstream_ga_v1_20261017.certification import verify_evidence; print(verify_evidence(Path('method_discovery/pos_upstream_ga_v1_20261017/raw_v11'), require_committed=True))"
```

Fresh Docker fixture command, executed once for this code and retained only
as provenance (do not rerun to replace the record):

```powershell
C:\Python313\python.exe -B -m method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.single_run_fixture --condition P --task pos-synthetic-file-http --research-candidate PoS --output E:\LongContext\pos_native_synthetic_20261018_v14 --official-source-git E:\pma_d1_tb2_source_20261017 --task-profile-file E:\LongContext\GenericAgent-main\mykey.py --ga-source E:\longcontext-cqs-v0-20261005\GenericAgent-main --runtime-root E:\LongContext\bench_runtime\m2\linux --worker-python C:\Python313\python.exe --harbor-python E:\LongContext\bench_runtime\m4\harbor-env\Scripts\python.exe --bench-root E:\longcontext-cqs-v0-20261005\long_context_bench --harbor-source-root E:\LongContext\bench_runtime\m4\harbor-src-pos-clean
```

The source-bound certification is `raw_v11/FILE_HASHES.json`; the new probe
and prepared-but-unstarted task identities are in `raw_compat_v3/`. The probe
used the private profile only in its original local location; public copies
contain no key or private endpoint. The probe failed, so `serial_live run`
was not invoked and no per-task formal authorization was generated. Any later
real run requires a separate new scope, new one-use authorization and the
existing full source/profile/task/certification binding gates; the old v1/v2
probes and this failed v3 result cannot release it.
