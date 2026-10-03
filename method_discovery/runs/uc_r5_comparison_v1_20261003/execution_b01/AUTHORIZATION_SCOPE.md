# UC-R5 b01 staged execution authorization

Main research thread authorized only block `b01`, task `roadmapbench:ktx-0.13.0-roadmap`, repetition 2, in frozen order RP, C0, RB, AB, AP. Each run is one fresh session through `method_discovery.uc_r5_execution_entry` in its own process. The five `AUTH_*.json` files are independent per-slot authorizations bound to the exact shared `RUNNER_MANIFEST.json` bytes.

The 30-slot preregistration, master manifest, checklist, and execution addendum remain unchanged, including their `execution_authorized=false` fields. This staged authorization does not cover the other 25 slots or any rerun. The host records condition labels; the runner receives `GA_BASELINE_CONDITION=original` and the frozen private Monitor profile for each condition. No group-specific model-facing hint is added.

Stop after the fifth slot or on an identity/isolation failure, candidate crash, confirmed external failure, or execution-bridge failure. Preserve the failed slot; do not skip, replace, or rerun it. Normal low score, non-adoption, invalid tool arguments, ordinary task test failure, and normal budget exhaustion remain results. Native evaluation is terminal only and never fed back to an online model.

Before any real request, `python -m method_discovery.uc_r5_b01_check` validates the authorization/manifest hashes, private profile hashes, five view/intent assignments, and the original runner's manifest-to-adapter argument expansion without contacting a provider. The observed model identity and terminal artifact binding remain runtime facts, not prelaunch assumptions.
