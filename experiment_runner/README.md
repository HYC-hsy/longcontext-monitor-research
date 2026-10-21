# Configuration-driven experiment entry

This entry reuses the existing GA/Harbor single-run driver and serial controller.
It separates task selection, method names, machine paths, and runtime policy.
It does **not** replace the method algorithms, model transport, or evaluator.

## Everyday use

From the repository root (Python 3.11+):

```sh
python -m experiment_runner catalog --config experiment.local.json --output catalog.json
python -m experiment_runner plan --config experiment.local.json --output resolved.json
python -m experiment_runner prepare --config experiment.local.json --output runs/selection-01
python -m experiment_runner run --config experiment.local.json --output runs/selection-01
```

`catalog` and `plan` only read pinned public Git metadata. They do not load
private profiles as code, start Docker, call a provider, or execute an evaluator.
Their `--output` is a **new JSON file**. `prepare` and `run` use a **selection
directory**. Preparation requires the existing local assets/runtime dependencies.

Copy `examples/sqlite.stateful.relaxed.json` to your own local configuration and
replace the machine paths once. Relative paths are relative to the configuration
file, not the current shell directory. Never put API keys or endpoint contents
in this JSON. The local resolved plan contains machine/profile paths; do not
publish it blindly.

To select tasks, edit `slots`. List order is execution order. For an explicit
repeat, add another slot with a different positive `occurrence`. Slots may
override the top-level `method`. Only serial execution is implemented;
`execution: parallel` is rejected rather than silently run serially.

Supported compatibility driver names are:

- `ga-only`: A / U
- `pma`: B / U
- `pma-v1`, `pma-d1`: existing V1/D1 candidates
- `pma-stateful`: B / pma_stateful_memory_v1
- `pos`, `pos-citation-fixed`, `pos-pma-complement`, `pos-pma-shared-view`

Changing names selects an already implemented driver. The registry refuses an
invented candidate that would otherwise silently dispatch to old PMA. Runtime
method flags and stale method-specific environment values are cleared before
the bound launcher enables the chosen method. The caller's environment is
restored, including on failure.

## Runtime policy: one resolved value, not multiple hidden defaults

Explicit `runtime_policy` is currently supported by `pma-stateful` only.
Other compatibility drivers reject it. For `pma-stateful`, omitting the field
resolves and passes the explicit official-Agent/method-default-turns policy.
Other legacy drivers retain their existing behavior; no claim is made that
their old defaults are official benchmark defaults.

```json
{
  "agent_timeout": "uncapped",
  "task_turns": "uncapped",
  "verifier_timeout": "official"
}
```

- `agent_timeout`: `official`, `uncapped`, or positive finite seconds.
- `task_turns`: `method_default`, `uncapped`, or a positive integer.
- `verifier_timeout`: only `official` in this version.
- Missing fields get the explicit defaults above. JSON `null`, zero, booleans,
  negative numbers, NaN, Infinity and unknown fields are rejected.

The resolved policy is placed in `manifest.config.runtime_policy` **before** its
configuration hash is computed. Run uses that frozen policy, not a new CLI or
shell override. A changed task/method/configuration/manifest requires a fresh
preparation and matching existing authorization; it cannot reuse the old run.

An explicit policy controls all relevant boundaries:

1. Harbor's Agent phase, including its cached timeout after Trial construction.
2. The GA adapter's shell wait loop and environment exec timeout.
3. GA's effective turn limit, without plan-mode resetting it to 100.
4. The outer supervisor: explicit policies use phase-local supervision, not
   `Agent + verifier + 600` counted from before environment setup.

The Harbor overlay uses its pinned private timeout API at commit
`459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc`. It clones the runtime configurations,
recomputes the Agent cache, and leaves task files, verifier, build and setup
limits unchanged. `runtime_policy_effective.json` records original/effective
values and the authorized config hash. Uncapped operation still responds to
cancellation, process failure, per-request timeouts and normal termination.

`diagnostic_agent_override` is **not** an original-time-limit benchmark score.
It uses the same task contents and evaluator with a disclosed Agent policy
override. No monetary, cumulative call or cumulative token cap is added here.

## Authorization and failure

Preparation never creates a real authorization. Each prepared slot still needs
its matching `authorization.json` under its slot directory, using the existing
one-use authorization process. This frontend neither grants more runs nor
retries an accepted/unknown run. An existing run directory is not reused.

The serial controller stops at a failed/incomplete slot and lists remaining
slots as not started. A completed run with reward zero remains a completed
experiment, not permission to rerun until success. Frontend bindings include
the prepared plan and manifest hashes; `GA_TASK_COMPLETE_RESPONSE` is scoped
from the method adapter, not a hidden manual shell prerequisite.

## Certification and tests

New runtime code changes invalidate certificates bound to old code. Do not edit
old evidence. The existing `single_run_fixture` now accepts
`--runtime-policy-file policy.json`, so the same formal Harbor fixture can
exercise this policy without writing another launcher. The existing collector
includes its effective-policy receipt; the verifier checks identity and effect.

Ordinary configuration-only changes do not alter source identity. Each real run
still gets its own configuration/authorization binding and effective-policy
receipt. A certificate records the policy actually exercised; it does not claim
that every conceivable configuration or future method was tested.

Offline test command:

```sh
python -B -m unittest discover -s experiment_runner -t . -p 'test_*.py' -v
```

These tests use temporary Git repositories, synthetic profiles/assets, fake
Harbor objects and a fake environment around the actual GA adapter. They make
no provider/Docker/evaluator calls. They do not replace a source-bound actual
Harbor fixture on the development machine.

## Honest boundaries of this slice

- Catalog reads compatible task packages at arbitrary pinned local Git commits;
  the legacy **execution** driver remains pinned to its existing official
  Terminal-Bench commit. Other dataset formats need another adapter.
- Existing driver-specific worker, packaging and termination branches remain
  behind this entry. This is not a completed universal GA plugin system.
- A new algorithm still needs an implemented host adapter and its tests. Adding
  a registry name alone is intentionally insufficient. Existing aliases can be
  registered programmatically without changing the dispatcher.
- Existing model/profile names remain fixed by the legacy driver. This patch
  does not pretend arbitrary model switching is supported.
- Both Task and auxiliary profile paths are currently required by the legacy
  preparation API, including GA-only. No profile contents enter public plans.
- This patch does not fix or certify a provider's native count endpoint. Those
  startup issues remain separate from the configuration interface.

The delivered objective is that task choice, ordering, explicit repeats,
supported method selection and supported runtime overrides no longer require
editing the launcher for each experiment.
