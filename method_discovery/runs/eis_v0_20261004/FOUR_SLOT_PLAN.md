# EIS-v0: four-slot non-execution plan

Status: `execution_authorized=false`. All proposed slots are `not_started`; this file is not a runner manifest or model-run authorization. Candidate implementation: `6fdde9d425740a802c34f114c518845b89e8a199` (parent archived verification-loop code `4e88eb471034aa5ae74528fb4758894549b2592e`).

| Order | Public task | Arm | Fresh proposed run ID | EIS switch | State |
|---:|---|---|---|---|---|
| 01 | `roadmapbench:fyn-2.2.0-roadmap` | BASE | `e832df5b0a8e4fb2bb2f4d5338ada5d4` | `false` | `not_started` |
| 02 | `roadmapbench:fyn-2.2.0-roadmap` | EIS | `82b860b44c5e4bb8a81b9d01ead5703c` | `true` | `not_started` |
| 03 | `roadmapbench:ktx-0.13.0-roadmap` | EIS | `3ab0193ad553424ba1a53b87fdec61e8` | `true` | `not_started` |
| 04 | `roadmapbench:ktx-0.13.0-roadmap` | BASE | `cbbd416ac6794ca38adf5b4c5d31e873` | `false` | `not_started` |

Both arms use the same frozen code, one fresh independent Task/Supervisor session per slot, the same continuous Supervisor History/working and root path, and the same seven tools. Common Monitor configuration: `monitor_dcec=true`, `monitor_path_control_v0=true`, `monitor_verification_loop_v0=true`, `monitor_verification_runtime_managed=false`, `monitor_root_scope_v1=off`, `monitor_research_view=off`, `monitor_research_intent=off`. Only `monitor_executable_interpretation_surface` differs. BASE has no EIS model-visible surface/guidance; EIS adds the bounded event-derived surface and short guidance. Neither arm has runtime-managed verification, an extra checker, or a completion gate.

Shared limits: actual Task local loop `max_turns=300`; shared `max_agent_seconds=10000`; Monitor `max_review_turns=20`; existing 300-second completion review timeout. Keep the same frozen Task and Monitor model roles/profiles, token/retry parameters, public tasks, task images/trees, no-network Unix inference isolation, terminal artifact binding and native evaluation as the current development comparison. The inherited 175-turn Task direction hint is common to both arms. Do not resume old History or alter an earlier trial.

Frozen task identities inherited from `method_discovery/runs/verification_loop_v0_20261004/FOUR_SLOT_PLAN.md`: Fyne Task input and Monitor original task SHA-256 `cae5f11a98aa573cf93629b8fb0becc18f395c5bdad25e09b8927d06f0725080`, tree `36991e23b078c5b14b5ea96b8026592932048abfe5e3321c483f0430578cbe1a`, image `sha256:b0da1cb31d367df38d05b81f98e68a94b0f7114efd3c82537633d1d92325efe1`. Kitex input SHA-256 `c5fac1db423182fadeb24dac34259f61a22b993ee974a8a9e3a24d690952b61d`, tree `be34b5600d7d034554a8a44eb8b2f260d6274f3f71e96c7f8faf78adc97f4804`, image `sha256:7ffcd70e49d77031b8e67eaa99226dc8468fa046f33e615118e8922b89fff32e`.

EIS protocol: the host appends mechanically paired candidate test-file writes and public test-command returns to `task_evidence/candidate_validation_index.jsonl`, with a latest-kind pointer in `candidate_validation_latest.json`. Original public events remain authoritative. Existing review assembly reads only bounded index material and injects at most 3000 characters next to the PATH public-event window. The runtime makes no judgment about adequacy, coverage, behavior or completion; no test event changes review cadence. The Supervisor may read cited original events and decide what to inspect or do. A result is the status of the complete Task command, not a requirement verdict.

If a future run is authorized, execute in the listed order once each, preserve every raw record and terminal result, and do not tune between slots. Low score, no adoption, weak Task tests, ordinary test failure, explicit defer and normal budget exhaustion remain outcomes rather than grounds for rerun. Confirmed source/model/input/isolation mismatch or critical trajectory/artifact-binding failure pauses with raw evidence retained. This four-slot development comparison is not a promotion decision.
