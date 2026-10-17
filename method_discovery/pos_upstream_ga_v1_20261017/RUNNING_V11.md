# PoS-on-GA scoped offline closure

Run from the repository root with Python 3.12+, fixed official Git checkout
`2fd12b88aafdd04a52c298e3940bcb189f9766d6`, existing Harbor checkout
`459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc`, existing fixed image,
Linux runtime, and local private Task profile. Do not publish the profile.

```powershell
C:\Python313\python.exe -B -m unittest method_discovery.pos_upstream_ga_v1_20261017.test_scoped_fixes
$env:PYTHONPATH='E:\longcontext-cqs-v0-20261005'
C:\Python313\python.exe -B method_discovery\pos_upstream_ga_v1_20261017\test_ga_seam.py
C:\Python313\python.exe -B -c "from pathlib import Path; from method_discovery.pos_upstream_ga_v1_20261017.certification import verify_evidence; print(verify_evidence(Path('method_discovery/pos_upstream_ga_v1_20261017/raw_v8')))"
```

The already-executed synthetic command used the existing
`single_run_fixture --condition P --research-candidate PoS
--task pos-synthetic-file-http` with a fresh output directory
`E:\LongContext\pos_native_synthetic_20261018_v11`. It used finite fake
Task/PoS responses, executed one synthetic code_run and one synthetic
sentinel, and made no provider or official evaluation calls. Do not rerun
into that directory. Raw public receipts are in `raw_v8/`.

Future real runs still require the existing `single_run prepare` and
one-use authorization binding source, profile, task, evaluator, budget,
run ID and output root. Supply `raw_v8` as the committed certification
directory only after verifying its index. The four-task plan remains
`execution_authorized=false`; this note grants no real-run permission.
