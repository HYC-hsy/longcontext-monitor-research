# M0-F Infrastructure Correctness Stage Report

Date: 2026-08-24

## Goal

Remove infrastructure defects that could invalidate M1 real-task comparisons without changing the frozen M0-v1 judgment policy.

## Timeout diagnosis and correction

The install-windows run passed `timeout_sec=7200` only as an adapter constructor kwarg. Harbor's outer trial phase still used the task-native 3,600-second timeout and cancelled the adapter at exactly 60 minutes.

The runner now passes an outer Harbor `--agent-timeout-multiplier` equal to:

```text
requested adapter timeout / native task agent timeout
```

For install-windows this is `7200 / 3600 = 2.0`. The adapter remains capped at 7,200 seconds and the launcher wait remains longer than Agent plus verifier time.

Evidence:

- runner regression captures `agent_timeout_sec=7200`, `agent_timeout_multiplier=2.0`, and launcher timeout 8,220 seconds;
- the pinned Harbor CLI accepts the flag;
- native `harbor jobs start --print-config` resolves `agent_timeout_multiplier` to `2.0`;
- Harbor `trial.py` applies the resolved multiplier to the native task timeout before `asyncio.wait_for`.

No third-party Harbor source was modified.

## Decision archive diagnosis and correction

The prior SymPy and install-windows reports classified several decision files as invalid JSON. The files were written as valid UTF-8 without BOM. PowerShell's default `Get-Content` decoding misread particular Unicode content; explicit `-Encoding utf8` and Python strict JSON parsing succeed.

Full audit:

- FBR: 83/83 valid;
- SymPy: 119/119 valid;
- install-windows: 57/57 valid;
- total: 259/259 valid UTF-8 JSON.

Therefore no historical data was deleted or rewritten. The two affected reports now record the corrected diagnosis.

For future crash safety, decision and authoritative-state writes now reuse an atomic writer:

1. serialize UTF-8 JSON;
2. parse the exact serialized value before writing;
3. write a sibling temporary file;
4. atomically replace the destination;
5. remove the temporary file if replacement fails.

This changes storage reliability only, not monitor reasoning or decisions.

## Files changed

- `long_context_bench/scripts/run_harbor_tb2_m4.py`: optional validated outer Agent timeout multiplier.
- `long_context_bench/scripts/run_harbor_tb2_m5.py`: derive outer multiplier from requested/native timeout.
- `long_context_bench/tests/test_harbor_tb2_m4.py`: command propagation and invalid multiplier tests.
- `long_context_bench/tests/test_harbor_tb2_m5.py`: two-hour adapter/outer/launcher propagation test.
- `GenericAgent-main/m0_monitor_checkpoint.py`: shared atomic UTF-8 JSON writer.
- `GenericAgent-main/m0_deliberative_monitor.py`: decision/state archives use the atomic writer.
- `GenericAgent-main/tests/test_m0_deliberative_monitor.py`: Unicode, JSON validity, and temporary-file regression.
- `method_discovery/artifacts/m0_h1_cross_task_confirmation_20260823/SYMPY_STAGE_REPORT.md`: corrected false invalid-JSON claim.
- `method_discovery/artifacts/m0_h1_cross_task_confirmation_20260823/INSTALL_WINDOWS_TRUNCATED_STAGE_REPORT.md`: corrected false invalid-JSON claim.
- `M0_V1_1_INFRASTRUCTURE_MANIFEST.md`: patch identity and validation.

## Validation

```text
GenericAgent:
71 passed in 1.35s

long_context_bench:
65 passed in 2.11s

historical archives:
259/259 valid UTF-8 JSON

Harbor config:
agent_timeout_multiplier = 2.0
```

All implementation steps were below 600 changed code lines. The M0 policy diff touches only `_record` persistence calls; `_base_prompt`, review logic, attention rules, intervention validation, and recovery semantics are unchanged.

## Completion gate

- [x] Inner adapter and outer Harbor timeouts are derived from the same requested limit.
- [x] Two-hour configuration reaches both layers.
- [x] Archive validity is checked with explicit UTF-8.
- [x] Future complete JSON objects are written atomically.
- [x] Historical false corruption claims are corrected without mutating raw artifacts.
- [x] M0 semantic behavior is unchanged.
- [x] Targeted and integration regressions pass.
- [ ] A future two-hour real task will provide end-to-end runtime confirmation; this is not required to change the infrastructure patch but must be checked at the first M1 long run.

## Decision

M0-F is complete as an infrastructure stage. The patch is suitable for tag `m0-v1.1`. The first M1 long real-task run must confirm that no 3,600-second outer cancellation recurs.
