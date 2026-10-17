# PoS native-unscored offline check and stopped formal launch

From repository root with Python 3.13 and no model credentials needed for the tests:

```powershell
C:\Python313\python.exe -B -m unittest method_discovery.pos_upstream_ga_v1_20261017.test_unscored_continuity -v
```

The independent gate test additionally needs the already prepared, private-local scope path and profile path; the public copies are under `raw_review_v1/preparation`, but the profile contents are never published. The final test output is `acceptance_v15/review_gate_tests_final.txt`. The source-bound synthetic certification is `raw_v12` and passed `verify_evidence(..., require_committed=True)`.

Do not rerun the four-task `serial_live run` command or reuse its one-use authorization. Its sole attempted first task stopped before Harbor with `KeyError: 'official_evaluator_members'` in the shared launcher; three tasks were never launched. A future attempt requires a separate authorized launcher fix, a formal-manifest regression, fresh source-bound certification, and new scope/review/one-use authorizations. It must not reuse this run ID/root or alter these raw records. The full diagnosis, identities and exact counts are in `AUDIT_V15_NATIVE_UNSCORED.txt`.
