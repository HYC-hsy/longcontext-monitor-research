# Parent-side configuration entry audit

## Scope

This patch adds a configuration-driven public task catalog and serial experiment
entry around the existing single-run driver. It also makes an explicit runtime
policy control Harbor, the GA wrapper, Task turns and outer supervision.

The implementation began against `f777f33422421cf7910b243166ffe2d8c4d04d37`.
Parallel developer changes were inspected and reconciled against
`8660408a447af375d69b9cbfa948c09a97ca440e` before delivery. In particular the
developer's `diagnostic-uncapped-v1` route remains distinct from the new
`runtime-policy-v1` route. The counter, method prompts, old episode records and
published fake/live evidence are not replaced by this patch.

## Executed validation

Command, from the isolated source workspace:

```sh
python -B -m unittest discover -s experiment_runner -t . -p 'test_*.py' -v
```

Result: **61 tests, 0 failures/errors**. These are unique tests in one discovery
run, not the sum of repeated subsets. Python compilation and `git diff --check`
also passed. Tests cover public Git catalog identities, rejected unsupported
methods/options, serial dispatch, prepared bindings, authorization mismatch,
runtime resolution, Harbor cache recomputation, actual adapter command
construction, fake execution boundaries, environment isolation and observed
runtime-policy evidence.

The published old diagnostic's three helper tests were additionally checked in
an AST-isolated dependency harness. They are not included in the 61-test count
and are not represented as a full run of the original integration suite.

Two independent reviews found issues that were corrected before delivery:

1. Inherited method-specific environment values could select an unintended
   bridge. Both launcher subprocess environments and frontend scopes now clear
   them before the selected method is enabled, and restore the caller's scope.
2. Summing Agent + verifier + 600 from before environment setup could truncate
   otherwise valid finite phases. New explicit policies use phase-local
   supervision with no summed outer deadline. Legacy no-policy behavior is
   preserved.

Fixed Harbor source was also inspected: `DockerEnvironment.exec` propagates
`timeout_sec=None` to an unbounded await; its Trial initializes timeout caches
before the existing create hook returns. The overlay explicitly recomputes the
Agent cache after cloning the runtime configuration. Actual task files remain
unchanged on the new policy path.

## Evidence limitations

- No Docker, real Harbor fixture, native count endpoint, model generation,
  benchmark Task or official evaluator was executed in this workspace.
- The existing core 98-test suite was not rerun here. The partial isolated
  workspace does not contain all of its runtime dependencies.
- Tests using fake environments exercise the actual adapter's request/wrapper
  construction, not real container timing or network behavior.
- Existing source-bound Harbor certificates do not certify changed source.
  After integration, run the existing fixture with the chosen policy and
  archive the new source identity before using it for a real run.
- A certificate records the policy exercised. This patch does not enforce a
  separate complete certification for every numeric parameter change, and does
  not claim all such configurations were individually Harbor-tested.

## What this fixes, and what it does not

Task selection, serial order, explicit repeats and switching implemented methods
use configuration instead of editing a launcher. Stateful runtime overrides
are resolved once and frozen into the authorized configuration.

This remains a compatibility front end over existing method-specific drivers.
It does not claim universal future-method plugin support, arbitrary model
selection, parallel scheduling, or completed native provider compatibility.
Those boundaries are explicit in `README.md`, rather than silently accepting a
configuration the execution layer ignores.
