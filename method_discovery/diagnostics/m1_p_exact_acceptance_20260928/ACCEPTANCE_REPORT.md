# Finite acceptance report

Evidence: `published_receipts_v2/acceptance_summary.json` and four full session traces.
All actions are scripted fake responses, not model-selected observations.

| item | status | evidence / limit |
|---|---|---|
| A frozen M1 identity | PASS (Windows) | each trace source_identity and all loaded_dependencies; clean frozen tree; patches=[] |
| A native vs candidate-closed | PASS | full request equality after declared mechanical mappings; identical control targets |
| B M1+P only declared increment | PASS | each of 9 requests differs only in system after mapping; exact c6e2 P body once |
| C task/state/receipt loop | PASS | read-task, write-state tool results; revised DCEC view at next request; tool_use_id consumption |
| D wait/new events/proposal identity | PASS | pending wait returns handoff_pending; approve-old returns native stale-handoff error; approve-new targets proposal-new |
| E native continuation | PASS | one no-tool maintenance request; DCEC continuation contract; native compaction commit; resumed review |
| F counterexamples | PASS | actual wrong checkout and DCEC-off failures plus mutated request/config/tool/strategy rejection cases |
| historical Linux/Bash platform | NOT COVERED | Linux Docker daemon unavailable; Windows schema is explicitly distinct |
| real-model behavior / Fyne capability / P effect | NOT COVERED | zero external requests; no task/evaluator run |

There is no unconditional overall historical-environment PASS. Core frozen-M1
Windows identity/request/control tests passed; historical Linux tool/platform
parity remains the explicit environmental gap. No M1 core patch was applied.

Counters are derived from the executed network deny hooks. Full requests are
deep copied at the provider-ready send boundary. Synthetic usage is not real
model cost. M1 remains provisional anchor; D1 stays closed without C1 verdict;
D2 stays DEFERRED / NOT AUTHORIZED. No panel or future budget was frozen.
