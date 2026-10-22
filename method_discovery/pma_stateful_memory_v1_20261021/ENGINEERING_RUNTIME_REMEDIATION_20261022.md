# Stateful runtime remediation: offline engineering handoff

Base: `83af2a7cd2a157b93f41a84d482853202133f227`.
Scope: optional native-count/capture dependencies and two demonstrated contract
boundary defects. No method redesign, PoS migration, new role, extra repair
credit, model change, provider endpoint/header change, or real run.

## Changes

1. `audit.py` validates nested model values before hashing or dictionary access.
   Wrong snapshot/target shapes, boolean revisions and malformed closure entries
   become `ContractError`, not accidental `TypeError`/`AttributeError`. Existing
   shared-credit correction and fail-closed behavior remain in force.
2. `proposal.py` checks every `scope.entity_ids` reference using the existing
   visibility boundary. Visible existing entities and mapped same-proposal local
   entities remain allowed. An existing but invisible entity is rejected.
3. Task and auxiliary sessions can explicitly disable the additional native count
   HTTP request. Disabled means no counter construction/invocation and no native
   window prerequisite, not a fabricated count of zero or preflight success.
4. Optional research capture can be best effort without weakening complete Task
   response or auxiliary response validation. Capture loss is reported as an
   evidence gap. State journal, CAS, spool receipts and delivery acceptance are
   not optional research files and still fail normally.

## Exact configuration interface

The existing `single_run prepare` entry accepts:

```text
--native-context-policy off
--research-capture-policy best_effort
```

Choices/defaults:

- `native_context_policy`: `required` (legacy default) or `off`.
- `research_capture_policy`: `required` (legacy default) or `best_effort`.

These keys enter the existing frozen manifest configuration before hashing.
Authorization, run spec, worker readiness and initialization must agree. The
worker receives the same-named CLI flags. Task environment names are
`GA_STATEFUL_NATIVE_CONTEXT_POLICY` and `GA_STATEFUL_RESEARCH_CAPTURE_POLICY`.
The actual underlying Task backend receives `stateful_native_context_policy`
and `research_capture_policy`; setting them only on a wrapper is insufficient.

Use these with the existing stateful condition-B/complete-response/relaxed-Agent
diagnostic options and normal local paths. Non-stateful opt-outs are rejected.
Do not mutate an existing frozen manifest, restart an old run ID, or reuse a
consumed authorization. This patch does not create an authorization.

The separate `experiment_runner` integration should project these two values
into this existing prepare API. This patch deliberately does not edit that
frontend while the development thread is integrating it. No additional launcher
or alternate provider path is needed.

## Behavior and limits

- No replacement counting service or approximate native-count fallback is added.
- Local TokenProxy/working-set selection remains unchanged. It is not the
  external native count request and does not become an exact Claude counter.
- Real generation HTTP errors, provider context limits, malformed tool arguments,
  truncated responses, per-request timeouts and user cancellation still apply.
- Disabling count does not establish that generation will be accepted; the prior
  count 403 was not a generation 403 and its supplier cause remains unresolved.
- Best-effort mode still attempts research capture. It does not pretend missing
  artifacts exist, clear failures into success, or retransmit accepted/unknown
  requests to recover evidence.
- Capture failures are not retried as transport errors, including usage capture
  during parsing. Current call identity is established before fallible capture;
  request-view overlays are restored even if required capture fails.
- The new policy helper is included in host staging and certification source
  lists. Existing source-bound certificates do not certify the changed code.

## Validation

Final combined local run: **192 tests passed, 226 subtests passed**, 86.91 seconds.
Subtests and overlapping worker/reviewer runs are not additional experiments.

```sh
python -m pytest --import-mode=importlib -q \
  method_discovery/pma_stateful_memory_v1_20261021 \
  method_discovery/tests/test_optional_transport_policies.py \
  GenericAgent-main/tests/test_task_complete_response.py \
  GenericAgent-main/tests/test_partial_response_recovery.py \
  GenericAgent-main/tests/test_pma_capture_boundary.py \
  GenericAgent-main/tests/test_stateful_native_preflight.py \
  method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/test_stateful_runtime_policy.py \
  method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/test_stateful_policy_config.py \
  method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/test_stateful_role_provider.py \
  method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/test_stateful_worker.py
```

The 121-test core subset also passed with socket connections forbidden. The
transport tests use mocks or local scripted HTTP, not a real model provider.
Core negative tests fail on the original code, establishing regression sensitivity.
Actual NativeToolClient/NativeClaudeSession integration verifies one mocked
generation request, zero native counts and accepted complete response even when
research capture fails. Required mode, invalid-policy rejection and real response
integrity checks remain tested.

Initial local attempts exposed missing dependencies, missing unchanged historical
fixtures, or import-path collection errors. These were resolved in the isolated
test environment, not by weakening tests. Independent reviews found and corrected
wrapper/backend propagation, usage-capture retries, stale usage attribution and
overlay-restoration defects before this final test run.

No Docker, actual Harbor run, model API or official evaluator was executed here.
After merging the separately developed frontend, run one final source-bound
formal fake chain in the existing development environment. A new real episode
requires its own explicit authorization; this handoff does not grant one.

## Delivery discipline

Implementation is split into coherent code/test steps below 600 changed lines:
core boundaries (236), transport (503), policy wiring (491). Documentation is
separate. Downloaded unchanged source/fixtures, private configuration, caches and
large local test logs are not new deliverables. Prior experiment archives remain
unchanged.
