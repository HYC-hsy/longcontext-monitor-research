# M0-v1 Freeze Manifest

Freeze date: 2026-08-24  
Status: capability-baseline snapshot; not the final paper method

## Identity

- Method name: `M0-v1`
- Role: runnable, no-checker, high-capability teacher monitor and upper-bound baseline
- Task Agent used in cross-task confirmation: `claude-opus-4-6`
- Monitor used in H1 confirmation: `gpt-5.6-sol`, reasoning effort `high`
- GenericAgent M0 source identity used by the latest run: `bd15829b36edb871a22bfb2b06c6ab54d93d8fea4979514895f7dc994b0a62ec`

## Frozen behavioral contract

- one persistent monitor identity;
- deployment-visible evidence only, with no native-verifier or hidden-test feedback;
- synchronous online pause and read-only inspection;
- `SHADOW` and `DELIBERATE` attention modes;
- intervention followed by continuous uptake/residual tracking;
- root task, local subtask, and repair episode remain distinct;
- Agent-authored tests, reports, and verifiers are provisional evidence rather than authority;
- verbal acceptance is not repair evidence;
- `UNKNOWN` alone does not force intervention or block release;
- root completion receives a fresh audit against the original public task.

## Evidence status

- FBR: completed normally, native reward `1.0`; demonstrates multi-episode correction and release.
- SymPy: native `resolved=true`, but reached the 120-minute limit; demonstrates useful correction plus scope inflation.
- install-windows-3.11: useful behavioral evidence but invalid as a 120-minute confirmation because Harbor truncated the Agent at 60 minutes; native reward `0.0`.

These runs establish a reusable capability baseline, not a causal or statistical claim that M0 improves all tasks.

## External runtime artifacts

Large task artifacts are intentionally not committed. Their authoritative locations are:

- `long_context_bench/output/m0_h1_cross_task_fbr_v2_120m/`
- `long_context_bench/output/m0_h1_cross_task_sympy_v1_120m/`
- `long_context_bench/output/m0_h1_cross_task_install_windows_v2_120m/`

The committed stage reports identify the exact trial, monitor, trace, patch, verifier, and manifest paths.

## Security boundary

Credentials and local provider configuration are deliberately excluded, including `GenericAgent-main/mykey.py`, environment-variable values, caches, logs, images, and generated task workspaces.

## Versioning rule

All later method versions must descend conceptually and experimentally from this M0-v1 baseline. Each incremental version must be exercised on complete real tasks and evaluated both for its intended gain and for regression of the frozen M0 behavioral contract.
