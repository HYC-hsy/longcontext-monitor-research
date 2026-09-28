# M1 versus M1+P — small development pilot proposal

**DRAFT / NOT FROZEN / NOT AUTHORIZED.** Full online tasks, not static replay,
not a D1 retake or renamed D2. R remains a separate backup; E1 is not implemented.
No model, benchmark or verifier has been run for this preparation.

Question: under the same complete M1 loop and resources, does the unchanged P
policy improve selection/execution of useful observation paths and subsequent
control without unjustified blocking or unacceptable cost?

## Concrete task proposal

Two existing public method_dev/dev_pilot tasks; one record per arm per task:
four records, no adaptive repeat. They have historical exposure and are **not
unseen generalization or held-out evidence**. Proposal uses public task scope
and distinct Go/Rust workloads, not historical scores or hidden tests. Exclude
Fyne/Sphinx/FBR discovery cases. No claim that these are favorable to P.

| Task ID | Public scope and reason | Initial source |
|---|---|---|
| `roadmapbench:ktx-0.13.0-roadmap` | Kitex: unified typed streaming, endpoint/transport restructuring, codec fallback, client options and diagnostics. Multiple public local/interface obligations permit source/compiled observations and subsequent whole-task return, without prescribing a blocker. | Original benchmark `environment/repo`, module `github.com/cloudwego/kitex`, not a historical repaired workspace. Target release is not the starting version. Upstream starting commit not yet resolved from the snapshot. |
| `roadmapbench:rat-0.22.0-roadmap` | Ratatui: scrollbar, grouped bars, multiple titles, styling/prelude and const/color changes. Public source/API/rendering behavior permits both direct artifact evidence and executable observations; no intervention is pre-required. | Original benchmark `environment/repo`, Cargo package `ratatui` version `0.21.0`, not target `0.22.0` or a historical patch. |

Public benchmark source for both: `UnipatAI/RoadmapBench`, revision
`59184e779909300a5a0150b06b945d39da81a099`, task directory identified by the
suffix above. Locally available originals:
`long_context_bench/.cache/m12_roadmap_tasks/<suffix>/instruction.md`,
`task.toml`, `environment/repo/`, `environment/Dockerfile`.
SOURCE_INDEX records fresh byte hashes of instructions/configs and split registry.
The original requirement text is authoritative, not this table's summary.

Declared images: `znpt/roadmapbench-ktx-0.13.0-roadmap` and
`znpt/roadmapbench-rat-0.22.0-roadmap`. Image digests and complete initial workspace
hash manifests are **not yet runtime-verified**. Dockerfile declares Go
1.23/bookworm for Kitex and Rust 1.82 for Ratatui, with prefetch/build caches;
these declarations do not prove the images have all offline dependencies.
The source/split identities are inspected; runnable Linux/image readiness is pending.

## Execution process (proposed, not implemented)

Use the existing audited isolated Roadmap launch path:
`long_context_bench/scripts/run_ultralong_m12_proofs.py`, with its bundle,
no-network Unix inference and post-termination native evaluation adapters.
Each record gets a pristine task image/workspace, independent monitor-private
state and normal Task Agent process. No shared mutated workspace between arms.
Do not mount prior trajectories, solutions, verifier artifacts or research docs
into either agent. Native evaluation only after termination, never online.

Supervisor imports the complete frozen M1 tree @ `746a695...` with DCEC and
semantic continuity enabled, view 4000, original continuation/control/history.
M1+P adds only the c6e2 neutral P body via the tested experimental adapter after
native initialization. No R, boundary/strict-slot branch or other candidate.
Both start with identical model-owned initial state; no researcher-authored
better grounds for P. P does not require outputting private reasoning.

The existing experimental adapter has finite offline acceptance, but a full-task
launch entry binding **that exact source and optional policy** is not yet frozen
or authorized. Existing production runner has no demonstrated P launch flag.
Do not silently run current GenericAgent-main instead. A later reviewed thin
launch integration and manifest are readiness requirements, not work authorized
by this draft.

The task process supplies actual later events: wait resumes observation of real
progress; follow-up reviews consume new public events/results. Intervene uses
the native delivery/recovery path and invalidates its old completion proposal.
Only a current new request_id/generation can be approved. Ordinary investigation
is concurrent; no per-turn model approval, simulated repair or fabricated receipt.
Necessary navigation or waiting for reasonable in-flight work can be useful.

Proposed fixed order: Kitex M1, Kitex M1+P, Ratatui M1+P, Ratatui M1.
Fresh records throughout. This balances order only weakly; four records cannot
establish equivalence, statistical effect or cross-task generalization.

## Proposed common budgets — not historical defaults or deployment invariants

Task: `native_claude_cc_vibe_opus48`, `claude-opus-4-8`. Supervisor:
`claude_monitor_opus48`, `claude-opus-4-8`, Anthropic messages, adaptive thinking,
high effort, temperature 1, max output 8192, context 200000, stream enabled,
timeout 30/read timeout 300. Supervisor values above are from archived Fyne role;
the task profile's complete effective inference fields must be resolved and
frozen before execution, without credentials in archives.

Suggested task response output cap 8192 is a **new common pilot proposal**, not
a claim about historical Task Agent settings. Same caps apply to both arms.
No 1200-token prototype ceiling. Task max 300 logical calls; Supervisor max
120 per record including ordinary review, continuation and any format repair.
Each ordinary review max 20 calls (native constructor limit), also subject to
the remaining record budget. Maintenance consumes budget, never grants extra
calls. A tool-free model response still consumes a logical call.

| Resource | Review | Record | Four-record batch |
|---|---|---|---|
| Logical model completions | Supervisor <=20 ordinary | Task <=300; Supervisor <=120 inclusive | Task <=1200; Supervisor <=480; total <=1680 |
| Transport attempts | <=3 per logical call | <=1260 across both agents | <=5040 |
| Billable usage (including retries, if reported) | Remaining record cap | Input <=4M; output <=1M tokens across both agents | Input <=16M; output <=4M |
| Tool/process time | Analysis command <=60s default, <=120s maximum | Supervisor cumulative <=1200s; task tools share task wall | Supervisor tool time <=4800s |
| Wall | Review <=600s | Task online <=7200s; overall online <=9000s; native evaluation <=1800s | <=43200s sequential online+evaluation, excluding setup |
| Monetary safety cap | Remaining record allowance | Proposed $100 reported usage cap | $400, not a price estimate |

Retry proposal is **two retries**, unlike archived Supervisor max_retries=8;
it is an explicit new common execution-budget setting subject to review, not
an M1 strategy improvement. Log each attempt, latency and usage; no extra
logical call budget for transport recovery. Unknown cost must be reported as
unknown, not zero; monetary enforcement needs a pre-agreed rate table and
accounting boundary. Token/dollar/time caps and exact task settings still need
an enforceable common launch specification before any authorization.

The record/token/dollar caps can terminate before the call maximum. Preserve
the result as bounded unresolved, not implicit completion. Truncated responses,
tool errors, transport failure and budget termination are separately labeled.
Supervisor cumulative provider time <=1800s is proposed; record online wall
still binds. Count actual task barrier time, intervention delivery time, wait
duration, follow-up latency and total elapsed time separately; overlapping
work is not added twice to wall but remains resource usage. A native verifier
timeout is not automatically semantic failure.

## Observation and outcome audit

Keep the full chain distinct: measurement available → actually executed → result
entered model input → result correctly qualified/used → grounds revised →
control action. Availability alone or a pretty two-path plan proves neither
execution nor use. Source/artifact inspection may settle a local premise;
there is no fixed large-test/end-to-end gate.

Audit useful observation paths (including justified navigation), relevance and
discrimination/reach, actual results and source/version, grounds revision,
root return after local repair, wait/intervene/completion identities, false
release, false block and reasonable bounded unresolved. A correct implementation
with insufficient visible evidence is not automatically overblocking. Adequate
evidence plus persistent unjustified delay can be overblocking. Task-first
self-completion with no meaningful P trigger is low-discrimination, not P success.

Keep native outcome alongside these chains and actual model/tool/token/cost/
waiting data; native score or tool use alone cannot establish mechanism benefit.
Human research audit only, no semantic runtime classifier. Full Supervisor raw
history, working revisions, continuation, delivery, provider attempts and OTel
must be archived; absence is an archive limitation, not reconstructed reasoning.

## Freeze and stopping proposal

First resolve the declared readiness gaps, then main thread freezes candidate,
tasks, identities, common budgets and criteria and separately authorizes the
whole four-record batch. No execution authorization exists now. Run once per
listed record; preserve failures; no repeat-to-success, replacement task or
per-task P edit. Infrastructure exceptions go to main-thread validity review,
not automatic reruns. After the batch STOP for aggregate raw audit.

No meaningful differences in a small panel are inconclusive, not equivalence.
Adoption without useful observation/control is not benefit. Improvement only
from materially greater cost is a capability/cost tradeoff, not unqualified
success. Material unjustified blocking, measurement degradation or loss of
M1 root re-evaluation warrants holding/stopping P rather than patching on-task.
If this batch later drives any mechanism revision, it remains development data.

M1 provisional anchor unchanged. D1 closed / no C1 verdict / no retake.
D2 DEFERRED / NOT AUTHORIZED. This draft does not authorize a pilot freeze.
