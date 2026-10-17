# D1/V1 offline entry points (not authorized for real calls)

Run from the repository root with the existing Python 3.12 PMA environment.
The fixed PMA vendor `src` and `external/harbor/src` directories must be on
`PYTHONPATH`. These commands never create a real authorization.

```powershell
$p = 'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013'
$env:PYTHONPATH = "$(Get-Location);$(Get-Location)/$p;$(Get-Location)/$p/vendor/pma_89e5c0d/src;$(Get-Location)/$p/vendor/pma_89e5c0d/external/harbor/src"
python -m decision_phase2_screen prepare --output "$p/decision_reminder_v1_20261017/new_draft"
python -m decision_phase2_screen fake --manifest "$p/decision_reminder_v1_20261017/new_draft/manifest.json" --output "$p/decision_reminder_v1_20261017/new_fake"
```

The six fixed archived Phase-2 inputs produce an unapproved, ordered 18-call
U/V1/D1 draft. `fake` uses the original PMA Phase-2 call and parser with a
scripted response; it never calls Phase 1, Task, a real provider or a native
evaluator. The committed `screen_draft` and `screen_fake` are one execution of
these commands. Do not treat the draft as execution approval.

To prepare a single *unapproved* D1 run through the real single-run preparation
path, use an unused output directory and the already committed D1 fixture:

```powershell
python -m method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.single_run prepare `
  --task constraints-scheduling --condition B --research-candidate D1 `
  --output E:\pma_d1_prepare_NEW `
  --official-source-git E:\pma_d1_tb2_source_20261017 `
  --task-profile-file E:\LongContext\GenericAgent-main\mykey.py `
  --pma-profile-file E:\LongContext\monitor_config\models.local.json `
  --certification-dir E:\longcontext-cqs-v0-20261005\method_discovery\curator_supervisor_convergence_v0\pma_full_upstream_ga_v1_20261013\decision_reminder_v1_20261017\certification_fixture_d1
```

`--official-source-git` must identify a clean checkout of the fixed TB2 commit
`2fd12b88aafdd04a52c298e3940bcb189f9766d6`; private profile contents
must not be copied into the output or repository. For V1 use
`--research-candidate V1` and `certification_fixture_v1`. U is the default.
The two tested prepare receipts were `execution_authorized=false`:
D1 manifest SHA-256 `6764bc26aff2fdd28baed75d2e325f8f0905de4626aa3144e97aa9ef33f2a54a`;
V1 manifest SHA-256 `ab3f28687d23e3bcf18cdc539d3e8cffa745357e0be072795623b488935a1486`.
Neither was run.

Future real use would require a separate one-use authorization and new approval.
There is no live subcommand in the Phase-2 screen.
