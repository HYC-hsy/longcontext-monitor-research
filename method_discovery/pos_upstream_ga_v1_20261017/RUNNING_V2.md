# PoS-on-GA v2: offline checks only

Status: partial adapter repair; not live-ready. Use Python 3.12 with the existing GA dependencies. No private profile is needed for these commands.

```powershell
python -B method_discovery/pos_upstream_ga_v1_20261017/test_offline.py
python -B method_discovery/pos_upstream_ga_v1_20261017/test_ga_seam.py
$env:PYTHONPATH='E:\longcontext-cqs-v0-20261005\GenericAgent-main;E:\longcontext-cqs-v0-20261005'
python -B -m unittest method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.test_synthetic_compat -v
```

`raw_v4/` holds the latest recorded outputs, fake request/response traces and hashes. `raw_v2/` preserves an initial archive-decoding failure; `raw_v3/` and `AUDIT_V2.txt` preserve the pre-summary-protocol-fix rerun. `AUDIT_V3.txt` is the latest online-readable audit with the complete scoped diff. The historical `raw/` and `AUDIT.txt` were not rewritten.

The unarmed four-task plan remains in `plan_four/`; `execution_authorized=false`. `fake-pos` is not native-shared certification. Profile mode is fail-closed, so there is no executable PoS live command yet. Before any future real run, the generic single-run → controller → launcher → Harbor native-shared P path needs source/profile/task/run/budget-bound one-use authorization and a true Docker synthetic file-plus-HTTP-service sentinel, followed by separate user approval. Never use an A/B authorization or `GA_POS_LIVE_AUTHORIZED=1` as a substitute.
