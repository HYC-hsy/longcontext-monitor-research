# Unified limits and direct run

Daily use (from a clean checkout of this branch, with existing environment/profile paths configured):

```bash
# Edit your existing config; select method, tasks and runtime_policy.
python -m experiment_runner run --config /path/to/config.json --output /path/to/new-results
```

`run` prepares a fresh directory automatically, binds the frozen manifest and committed code to the allocated run IDs, and calls the existing serial runner. No manual authorization file or separate approval command is required. A fully prepared directory from the same code/config can also be used. Existing user authorization files are left alone. The temporary `.run_binding.json` exists only during the slot invocation and is removed afterwards. The legacy `audited_code_commit` field means current execution source identity here, not a new human audit. Its provenance is `authorization_source=explicit_experiment_runner_run`, `actor=experiment_runner`.

`plan` and `prepare` remain available and make zero model requests. Preparation checks public assets/local images and committed runtime identity. Daily startup does not require a new historical lifecycle certificate. `runtime_startup_identity.validation` explicitly records `code_identity_only_no_new_lifecycle_certification`; historical certification is not claimed. The original image/source/mount, provider isolation, agent stop, writer stop, resource cleanup and native verifier checks still execute in the existing drivers.

## Configuration

Add or edit only this object in your existing configuration:

```json
"runtime_policy": {
  "agent_timeout": "official",
  "task_turns": 300,
  "verifier_timeout": "official"
}
```

`agent_timeout`: `official`, a positive finite number of seconds, or `uncapped`.
`task_turns`: `method_default`, a positive integer, or `uncapped`.
`verifier_timeout`: only `official`; build/setup and native evaluation semantics are unchanged.

| Methods | Absent runtime_policy | Explicit `{}` | Positive/uncapped |
|---|---|---|---|
| ga-only, pma, pma-v1, pma-d1 | Historical behavior | Official agent seconds, 300 turns | Supported |
| pma-stateful, pma-gap, pma-gap-evidence | Existing automatic `{}` | Official agent seconds, uncapped turns | Supported |
| pos, pos-citation-fixed, pos-pma-complement, pos-pma-shared-view | Historical behavior | Official agent seconds, 300 turns | Supported |

Aliases inherit their binding's behavior. PoS retains its existing frozen task set. Stateful-only transport options remain stateful-only. Invalid combinations fail before inference with the method and field to fix.

Explicit policy wins over shell defaults, cached Harbor overrides and mutable plan-mode limits. Harbor owns the phase-local Agent clock, so setup/build do not consume the Agent budget. Explicit policies have no aggregate host deadline. `uncapped` is represented by `None`, not an artificial large number. A finite per-provider timeout (PoS normally 180 seconds) is independent of the overall Agent budget.

## Read the result

The console labels limits as **planned**, including their sources. It never claims a run has already applied them. `experiment_plan.json` contains the resolved config, dataset identity and method bindings; each slot's manifest includes the committed code identity. The existing `archive/runtime_policy_effective.json` records actual Harbor caches, and `live_command_public.json` records launcher values. No new duplicate runtime log is introduced.

A persistent `run_claim.json`, created exclusively, prevents concurrent/repeated starts. The manifest, plan and run_identity hashes must agree; allocated roots must be exactly `<slot>/runs/<run_id>`. Existing runs or batch results are never silently retried. If validation or execution fails, inspect `selection_preparation.json` / `selection_result.json` and the slot's `batch_result.json`, `live_result.json` and runtime receipt. Use a new output directory for a new attempt; do not delete claims to disguise retries. Serial continuation still requires the existing confirmed cleanup rules.

## Scope and verification

Based on split repair `8c5f6ee0a9d64db39cee82df686bbf616f8e5ff3`. Reuses the applicable GA-only policy approach from `3a353cc5959ec88292461b7a34430804d7afdf39`, generalized to all installed bindings and aliases. GA20 stays on its frozen branch and is not upgraded.

Actual targeted checks in this environment:

- 66 unittest cases passed: policy parsing/cache isolation, every method's plan/prepare matrix and defaults, real PoS manifest resolution/hash, frontend automatic preparation, isolated directories, persistent claim, identity/root tampering, cleanup and summaries.
- 9 pytest cases plus 8 subtests passed: actual GA/PMA loop plan-mode priority, complete-response phase clock, and PoS uncapped/fixed IPC waiting.
- 26 existing response/bridge cases plus 43 subtests passed with loopback scripted HTTP responses, no real provider. Initial sandbox execution failed because local port binding was denied; the permitted local-only rerun passed.
- Initial Python 3.9 run lacked tomllib; switched to installed Python 3.12. Missing sparse-checkout dependencies and test fixtures were restored. Earlier iteration failures are retained in `runtime_limits_validation/`.

No real model, full task, Docker/Harbor lifecycle run or official evaluation was performed. These checks establish engineering wiring, not method effectiveness or fresh container certification. Runtime still needs the configured profiles, fixed benchmark/Harbor sources and a working Docker engine; real platform permissions are unchanged.
