# DCM-v0 four-slot exploratory plan — NOT AUTHORIZED TO EXECUTE

`execution_authorized=false`. Implementation: `dd4c180d4adf82ea8cc4229787e4af3fe8b7b645`.
The scientific code difference is traceable to frozen CFS candidate
`74a06444b9f78299dceabdb6a42fa44317462b65`. No model, Task Agent,
native verifier, or independent probe is run by this plan. Each proposed slot
would be a fresh, independent Task/Supervisor session, without historical
History or working-state restoration.

| Order | Task | Arm | Fresh proposed run ID | `monitor_decision_conditioned_measurement` |
|---:|---|---|---|---|
| 01 | `roadmapbench:fyn-2.2.0-roadmap` | CFS | `3361dec4537bdbac59a89b2982a5d20e` | false |
| 02 | `roadmapbench:fyn-2.2.0-roadmap` | CFS+DCM | `caea820b492d9a880dddf13a0649f2fd` | true |
| 03 | `roadmapbench:ktx-0.13.0-roadmap` | CFS+DCM | `20c3ea3c5675f07f201f6b1d48762011` | true |
| 04 | `roadmapbench:ktx-0.13.0-roadmap` | CFS | `db2086fac2811aff752f70f7a73f2d5e` | false |

Both arms use `monitor_dcec=true`, `monitor_path_control_v0=true`,
`monitor_verification_loop_v0=true`,
`monitor_verification_runtime_managed=false`, `monitor_root_scope_v1=off`,
`monitor_executable_interpretation_surface=false`,
`monitor_coarse_to_fine_surface=true`, and research view/intent off. The only
treatment switch is DCM. CFS Situation, system prompt, seven tools, Task
prompt, cadence, wake rules, control authority, and completion freshness checks
are common. Task local maximum is 300 turns; shared maximum is 10000 seconds;
Monitor maximum is 20 model turns per review. Provider timeout/recovery and
terminal native evaluation remain as in the frozen CFS exploratory comparison.

Task/Monitor model and route configuration, public task bytes, task tree,
images, isolation, terminal artifact capture, and evaluator are inherited from
the frozen CFS-v0 plan and its cited EIS readiness identities. Public Task
input/Monitor original-task SHA-256: Fyne
`cae5f11a98aa573cf93629b8fb0becc18f395c5bdad25e09b8927d06f0725080`;
Kitex `c5fac1db423182fadeb24dac34259f61a22b993ee974a8a9e3a24d690952b61d`.
Image IDs: Fyne
`sha256:b0da1cb31d367df38d05b81f98e68a94b0f7114efd3c82537633d1d92325efe1`;
Kitex
`sha256:7ffcd70e49d77031b8e67eaa99226dc8468fa046f33e615118e8922b89fff32e`.
This plan does not create deployment profiles, bundles, or valid execution
authorizations. Those identities require a separate run authorization.

The analysis unit would be a complete session, not a review. Mechanical audit
would count DCM boundaries, immediate repeated releases, boundaries followed
by `file_read`/`code_run`, intervention, or follow; local patrol and root
releases; extra Monitor requests/time, Task turns, and terminal native outcome.
The audit must preserve original tool/result and control locators, not infer
measurement adequacy by keywords.

Research-side interpretation is reserved for raw-trajectory review at four
levels: decision contrast, measurement selection, control effect, and
outcome/cost. Prespecified possible failures include immediate repetition at
every boundary (non-effect), indiscriminate broad testing (over-tightening),
more observations without changed false closure (measurement reasoning
failure), or cost growth without decision-quality gain. The harness will not
classify these. Low score, nonadoption, weak tests, defer, budget exhaustion,
or ordinary test failure are outcomes, not replacement triggers. Identity,
isolation, hidden-evaluation leakage, or critical trajectory/artifact-binding
failure would pause a future batch and preserve raw evidence. No outcome-based
rerun or extra slot is proposed.
