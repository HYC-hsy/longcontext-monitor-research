# D2 — Measurement Substitution (design only)

Status: **design material only; not implemented, not executed**.

This design preserves the D1-R1 final verdict and raw records. It does not
repair or rerun D1, alter PROTOCOL, implement Action-Native control, or modify
production Monitor code.

## 1. Scientific question

With the M1 strategy and semantic representation held fixed, when a preferred
decision-critical measurement is unavailable, can the same persistent
Supervisor choose and execute a replacement measurement whose possible
outcomes still distinguish the control-relevant states?

The intervention is restricted to the availability of one complete measurement
event. It is not a new state representation, selector, checker, or additional
LLM stage.

## 2. Frozen common condition

The anchor is M1/DCEC-v1 at
`746a695adac4325d6440941d384d543d1364fef9`.

The future run would keep the same semantic principles (decision scope,
scope-bound grounds, decision discrimination, relevant measurement boundary,
unfinished evidence not being positive evidence, root re-evaluation, and
relaxation). The Supervisor remains `claude_monitor_opus48` / Claude Opus 4.8
with the ordinary seven Monitor tools. The task/model/tool identity is common
to both measurement conditions. No DCEC-CONTROL protocol is added.

Research labels, state labels, expected outcomes, and candidate names are
research-side only. Model-visible material is a whitelist projection of the
public task, frozen workspace, and public events.

## 3. Candidate public fixture A — FBR CORS wildcard

### Original question

The public task requires wildcard CORS behavior: when `AllowOrigins` contains
`*`, the response must return the literal `*`; wildcard has priority, while
specific origins follow the ordinary matching behavior. The task and source
references are recorded in:

- `method_discovery/artifacts/stage6d/stage6d-fbr243-shadow-v2/lineage_shadow/runtime_bundle/public_task.txt`
- `method_discovery/artifacts/stage6d/stage-r2-presentation-live-v1/i0/branch_bundle/branch_gate_state.json`

The previously cited `STAGE6D_F1_FAILURE_CAUSE_ANALYSIS_20260820.md` is not
present in the current checkout. It is therefore **not** treated as an
available source and is not reconstructed here.

### Defect and correct states

The public defect state is the branch in which the credentials branch echoes
the requesting origin instead of preserving the literal wildcard. The public
correct-state evidence is the subsequent requirement-grounded revision and
public Phase-4 result described in:

- `method_discovery/docs/STAGE6D_R2_EVIDENCE_GUIDED_REVISIT_REAL_GATE_20260821.md`
- `method_discovery/docs/PMA_NATIVE_FBR_R2_AUDIT_20260912.md`

These sources are public development evidence; no hidden test assertion is
used here.

### Paired measurement operations

The preferred measurement is a public behavioral reproduction that exercises
the wildcard decision with a wildcard configuration, a credentials setting,
and a requesting origin, recording the response header/body and warning/error
result. The replacement measurement, used only when that complete execution
event is unavailable, is a public-path source-plus-execution observation that
follows the `AllowOrigins` branch with the same public input and checks the
observable output. It must preserve the distinction “literal wildcard versus
request-origin echo”; a grep of a symbol or a build alone is insufficient.

The existing branch state, public task, and public result documents that are
present above are available now. A paired replay workspace and deterministic
unavailable-event boundary are **planned**, not yet materialized. The missing
failure-analysis document is an explicit source limitation, not a substituted
result.

## 4. Candidate public fixture B — DuckDB optimizer closure

### Original question

The public task requires an approximate optimizer implementation, a minimum
geomean speedup, correctness, and delivery of the named artifacts. The public
task and trajectory sources are:

- `long_context_bench/.cache/m12_lhtb_repo/tasks/duckdb-optimizer-closure/instruction.md`
- `method_discovery/artifacts/stage6b/cross_task/duckdb/full_public_stream.json`
- `method_discovery/docs/STAGE_6B_CROSS_TASK_VALIDATION_RESULT_20260818.md`

### Defect and correct states

The same public trajectory contains an intermediate state with earlier failed
performance/correctness checks and a later state reporting 22/22 correctness,
1.3298x speedup, and all required artifacts. The later public success-control
record is also summarized in:

- `method_discovery/artifacts/stage6d/discrepancy_offline_screen_claude_v2/duckdb-supported-delivery-control/public_input.json`
- `method_discovery/artifacts/stage6d/cross_task_adjudication/duckdb-delivery-success-control/d0_span_joint/result.json`

This is an existing public success/defect trajectory, not a newly hand-written
fixture. The exact intermediate failure slice to be used in D2 remains a
planning item until source bytes and a cutoff are frozen.

### Paired measurement operations

The preferred measurement is the public benchmark/correctness execution and
artifact inspection that can distinguish “performance/correctness and required
delivery are satisfied” from “one or more remain unmet.” The replacement is a
smaller public measurement that reaches the same decision-relevant distinction:
for example, an available correctness/performance subcheck plus direct
inspection of the required output artifacts. Artifact existence alone is not a
substitute for performance or correctness.

The public task, full stream, adjudication rows, and success-control inputs are
available now. A two-state cutoff and a deterministic unavailable preferred
measurement event are **planned**, not yet materialized.

## 5. Proposed panel and budget

Proposed diagnostic panel: two fixture families × two states (defect/correct or
intermediate/success) × two measurement regimes (preferred available / preferred
unavailable with replacement opportunity) × two independent repeats = 16
records. Each record would use at most six logical Supervisor calls, with
provider retries reported separately. This is a proposal only; no records are
authorized by this document.

The central paired comparison is within the same frozen state and evidence
boundary. The only intervention is whether the complete preferred measurement
event is available; the replacement opportunity is held explicit and public.

## 6. Execution-deviation taxonomy and stop rule

Pre-registered deviation classes would be:

- `fixture_identity` — source bytes/cutoff/hash mismatch;
- `semantic_state` — M1 working state absent or altered;
- `tool_contract` — exposed operation not executable or schema mismatch;
- `measurement_unavailable` — deterministic execution fact only;
- `transport/runtime` — provider or replay infrastructure failure;
- `model_control` — valid trajectory behavior, not an invalidation;
- `archive` — missing raw evidence.

Only identity, tool-contract, transport/runtime, or archive failures that make
the trajectory uninterpretable can invalidate a record. Model failure to design
or use a replacement measurement remains scientific evidence. A single
record is never rerun; no tuning follows an observed result. The panel stops
after the fixed records, or earlier only for a pre-registered systemic
infrastructure failure, which is preserved for independent adjudication.

## 7. What is available versus planned

Available now: public task text, source/workspace references, FBR public branch
and result documents, DuckDB full public stream and adjudication artifacts,
M1 identity, model/tool identity, and the D1 raw archive/audit pointer.

Planned only: D2 request materialization, exact state cutoffs, paired
measurement-unavailable events, replacement-operation scripts, isolation tests,
runner implementation, authorization, and any model execution.

No held-out task, hidden verifier detail, Sphinx hidden assertion, or post-hoc
gold label is used in this design.
