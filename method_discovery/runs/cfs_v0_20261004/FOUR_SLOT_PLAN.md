# CFS-v0 four-slot plan — NOT AUTHORIZED TO EXECUTE

Implementation: `b73eb12bb1c18cb97568c7048dc4d6a6a22daa44`, parent `2bd9491eba4996ad5817664134783b8acba377f3`. This plan freezes only an exploratory comparison; `execution_authorized=false`. No live session, private deployment profile, bundle, or native evaluation is created by this commit. Actual execution requires separate main-thread authorization and identity checks.

| Order | Task | Arm | Fresh proposed run ID | `monitor_coarse_to_fine_surface` |
|---:|---|---|---|---|
| 01 | `roadmapbench:fyn-2.2.0-roadmap` | BASE | `92e70a3af636d9eb2808ee10b186efe4` | false |
| 02 | `roadmapbench:fyn-2.2.0-roadmap` | CFS | `3a17f894b88de51ca015a2dae6e70c2a` | true |
| 03 | `roadmapbench:ktx-0.13.0-roadmap` | CFS | `fb00171bcd6c5d2816424bece42844a8` | true |
| 04 | `roadmapbench:ktx-0.13.0-roadmap` | BASE | `d05d0ba4ae868580490bdb5b1fd89f9e` | false |

Each would be a fresh independent Task/Supervisor session. No old History, working state, or trial output is restored. Both arms share the same frozen CFS code and all science/runner settings except the single switch. The treatment replaces the dispersed PATH recent-public-event window plus WTV wake prose with one inter-review Situation Surface; it does not change system prompt, seven tools, cadence, controls, completion, or budget.

Common effective Monitor settings: `monitor_dcec=true`, `monitor_path_control_v0=true`, `monitor_verification_loop_v0=true`, `monitor_verification_runtime_managed=false`, `monitor_root_scope_v1=off`, `monitor_executable_interpretation_surface=false`, research view/intent off. Continuous single-session root and manual public verification remain. Task local maximum 300 turns, shared maximum 10000 seconds, Monitor maximum 20 turns per review, and existing completion timeout/retry policy remain. Task/Monitor model identities, private route parameters, public tasks, images, task trees and terminal native evaluator are inherited from the frozen EIS-v0 comparison; the private credentials are not in this plan.

Frozen public Task input/Monitor original-task SHA-256: Fyne `cae5f11a98aa573cf93629b8fb0becc18f395c5bdad25e09b8927d06f0725080`; Kitex `c5fac1db423182fadeb24dac34259f61a22b993ee974a8a9e3a24d690952b61d`. Image IDs: Fyne `sha256:b0da1cb31d367df38d05b81f98e68a94b0f7114efd3c82537633d1d92325efe1`; Kitex `sha256:7ffcd70e49d77031b8e67eaa99226dc8468fa046f33e615118e8922b89fff32e`. The original task/tree/proposal/image identity inventory remains in `method_discovery/runs/eis_v0_20261004/PLAN.json` and its cited readiness files; do not substitute or reconstruct a different task.

The scientific unit would be one complete trial. Low score, no adoption, malformed Task-authored checks, defer, budget exhaustion, or ordinary test failure are outcomes, not rerun triggers. Identity/isolation mismatch, hidden evaluation in online control, or critical trajectory/artifact-binding failure would stop the batch and preserve raw evidence. No outcome-dependent slot selection, extra probe, checker, or new model stage is planned. The historical EIS-v0 raw records used for the offline replay are not controls or additional slots in this comparison.
