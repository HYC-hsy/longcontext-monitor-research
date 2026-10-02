# UC-OPEN-R5-v0 comparison — frozen preregistration protocol

Status: **not authorized for execution**. `PREREGISTRATION.json` is formal research-side allocation and analysis policy, not a runner-compatible experiment manifest. Existing preparation evidence is at `../uc_r5_cmp_readiness_20261003/`. No scientific session has started. Production candidate is `232281d650d062bdc6a6030f40ccb904c1ac0851`; the frozen production C0 source comparison is `6c72477fce3350c82baf74a9ca8a96c87742be5b`. All five assigned conditions run the candidate source, differing only in the configured view/intent keys; C0 means both research keys off.

## Assignment and fixed conditions

The accepted `SLOT_DRAFT.json` is referenced **by its unchanged SHA-256**, not redrawn. `SLOT_EXECUTION_CHECKLIST.json` repeats its 30 opaque IDs, six blocks, task/repetition/position/order and `not_started` state verbatim. Each task has three complete-session repetitions per condition. No previous run enters the new C0 group, and no old History/session is restored. The fixed order is b01 Kitex rep2 `RP C0 RB AB AP`; b02 Kitex rep1 `RB RP AB C0 AP`; b03 Kitex rep3 `RP C0 RB AP AB`; b04 Fyne rep1 `AB RB RP AP C0`; b05 Fyne rep2 `RP RB AB C0 AP`; b06 Fyne rep3 `C0 RB AP AB RP`.

| Group | View | Intent |
|---|---|---|
| C0 | off | off |
| RP | flat | note |
| AP | framed | note |
| RB | flat | routed |
| AB | framed | routed |

DCEC is on throughout; working view 4000 characters; intent window 4 logical requests; source body 6000 characters total, 1500 per source, additional block 14000. Task and Monitor model profiles, temperature, context, caching and request-retry policy are common except for the two treatment keys. The planned ceilings are `GA_MAX_TURNS=180`, `max-agent-seconds=10000`, 20 Monitor review turns, 300-second completion timeout, 10000-second Monitor deadline, 7200-second task.toml agent timeout times `10000/7200`, and a 10900-second outer launcher timeout. These are ceilings, not target durations. Logical requests, provider attempts/retries, token/cache buckets, source reads, artifact I/O, tool time, blocking latency and wall time are kept separately where observed; unavailable fields remain null.

## Outcomes, contrasts and interpretation

The complete fresh session is the analysis unit; its reviews are not independent samples. Every allocated slot stays in the ledger, including non-adoption and incomplete formation. For each task and each repetition, report separately: native weighted completion score; valid final allow with bound pre-evaluation artifact and every native phase passed; valid final allow with a bound artifact but not every phase passed; incomplete/budget/candidate/system/external outcomes; and Task/Supervisor requests, attempts, token/cache and available control costs. A native pass is not a proof of every public semantic requirement. If final allow, evaluator validity or scored-artifact binding is unknown, `false_allow` stays `unknown`/null, never filled with `false`.

For **each outcome scale separately**, calculate A = `((AP-RP)+(AB-RB))/2`, B = `((RB-RP)+(AB-AP))/2`, interaction = `AB-AP-RB+RP`, shared operation increment = `RP-C0`, and total combined increment = `AB-C0`. Report within-task/repetition results before an equal-weight summary across Kitex and Fyne. Do not invent a weighted winner score, call this held-out generalization, or make a promotion decision from this development comparison.

The mechanical adoption chain is: configuration available → model `select`/`set` → actual block enters a later ordinary provider-ready request → that request returns → later locatable use in the dialogue/control record. Merely calling a new tool is not adoption or effect. Archive direct public evidence and contemporaneous control grounds before looking at terminal evaluation. The development thread locates events but does not classify semantic correctness.

## Retention and stopping

Normal low score, absent adoption, bad tool arguments, ordinary task-test failure, candidate-handled missing/truncation/overflow and normal budget exhaustion remain scientific results; no result-driven rerun, skipping or early stop. Candidate crash, confirmed external fault, or identity/isolation failure preserve the record and pause pending main-thread decision; do not jump to the next slot. Normal provider request-level recovery is counted as attempts, not a record-level rerun. Preserve the old runner's `valid`, `validation_errors` and `exception_info`; `valid=false` alone is not an exclusion rule. Missing allow logs are not evidence of `allow=false`. `not_started`, `unknown` and observed failure are distinct. No native outcome goes back to the online Task Agent or Supervisor.

`START_GATE.md` defines the separate pre-request identity/isolation gate. `TERMINAL_BINDING.md` defines what the terminal artifact chain must prove and flags its unresolved pre-scoring capture seam. This preregistration does not satisfy or bypass either gate. A future main-thread authorization and an executable, separately frozen runner manifest are required before any scientific request.
