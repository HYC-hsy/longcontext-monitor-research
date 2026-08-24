# M1.0 Real-Task Panel and Experiment Contract Freeze

Date: 2026-08-24
Parent method: `m0-v1.1` (`1a753a4`)

## Goal

Freeze the first M1 causal increment, real-task panel, runtime identity,
evaluation separation, evidence fields, acceptance rule, and stopping points
before implementation changes the method.

## Frozen increment

The only intended treatment difference is an independently switchable,
persistent task--reasoning--evidence workspace attached to M0-v1.1. The
workspace may preserve open-semantic task, intent, hypothesis, public evidence,
UNKNOWN, repair, and root/local relation objects and reconstruct them from raw
public history. It may not use an online checker or pre-implement later M2--M6
mechanisms as an inseparable bundle.

## Frozen panel

1. `roadmapbench:pyg-2.3.0-roadmap`: primary target and rotating task not used to
   tune the M1 increment; historical unsupported closure passed only 2/12 phases.
2. `roadmapbench:fbr-2.43.0-roadmap`: M0 capability-regression control with a
   prior full, sparse, multi-turn M0 success.
3. `claw_swe:sympy__sympy-13091`: cross-source reasoning and persistent-
   constraint stress case.
4. `tb2:install-windows-3.11`: cross-domain long-horizon case and first real
   confirmation of M0-F's two-hour outer timeout.

All four are `method_dev/dev_pilot`, cover three sources, and have historically
available post-run evaluators. No `stage_validation` or `final_holdout` task was
selected.

## Files

- `method_discovery/m1_real_tasks/panel.json`
- `method_discovery/docs/M1_PERSISTENT_WORKSPACE_EXPERIMENT_CONTRACT_20260824.md`
- `method_discovery/artifacts/m1_0_contract_freeze_20260824/STAGE_REPORT.md`

## Validation

The panel was parsed as strict JSON and joined against all frozen R0 task rows.
The validation established:

- task count: 4;
- unique sources: 3 (`claw_swe`, `roadmapbench`, `tb2`);
- every task occurs exactly once in R0;
- every task is `method_dev/dev_pilot`;
- every task has `historically_available` evaluation;
- no validation errors;
- `git diff --check` passed.

Hashes before this report was added:

- panel SHA-256:
  `EDB68150939620105E1D3D7F8E83088535D5424163291516E0B2F297E92E960A`;
- contract SHA-256:
  `CC4A7E5E20BA8A03205E19D1009A6A2C46A55F1374C05E51C4FE7548170DCF0A`.

## Completion gate

- [x] M1 increment and non-goals frozen.
- [x] R0-compliant four-task panel frozen.
- [x] Runtime/model/budget identity frozen.
- [x] Online and post-run evidence separated.
- [x] Process, native outcome, regression, and cost evidence specified.
- [x] Acceptance and mandatory stopping points specified.
- [x] No method code or paid API run performed.

## Next gate

M1.1 may implement the smallest independently switchable workspace. Its
engineering tests do not promote the mechanism; M1.3 complete real-task runs
own acceptance. API spending and the eight-run exploratory batch require the
appropriate later user gate.
