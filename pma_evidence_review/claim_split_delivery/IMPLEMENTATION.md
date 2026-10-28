# Claim split with one closed batch audit — engineering acceptance

## Current contract (supersedes the initial per-claim-call draft)

The user's final clarification fixes the analysis/commit unit at **one original
operation**. For each eligible operation the candidate performs **one split call,
then ONE batch verification call containing all claims and the same B**. It does
not call the reviewer once per claim and does not batch different operations.
One author repair, if allowed, repeats the full split plus one fresh batch.

The baseline is `f97033e98e36386474230ccc14f0c19f8a00e7ce`; its original worktree
remained clean. Default direct `semantic-support-one-sentence-v1` review remains
unchanged. Explicit candidate: `claim-split-same-evidence-v1` via JSON field
`citation_review_strategy` or CLI `--citation-review-strategy`, alongside the
existing `gate-only` or `gate-one-repair` evidence-PMA B gate.

No real model, Task, retrieval or real profile/credential access occurred. Fake
worker/native-Harbor tests are engineering fixtures, not task-effectiveness results.
Initial per-claim-call commits and their logs are intermediate development history,
**not evidence for the final algorithm**. The batch and final-suite logs supersede
them. Focused test counts overlap and must not be added together.

## Safety and semantic boundaries

- Existing literal citation preparation resolves eligible B before any model call.
  Identity, action, memory target, revision and content hash remain host-controlled.
- Split output contains `op_index` and a nonempty claims array. Each item contains
  `claim` plus exact `original_text`; the host resolves a unique exact occurrence.
  Paired optional start/end offsets only disambiguate repetition. Ambiguity,
  mismatch, duplicates, extra fields and empty or uncovered text fail closed.
  Distinct claims may share exactly the same original span.
- Span union covers every non-whitespace character of A. This is **structural
  coverage, not a semantic completeness proof**. The one batch also makes a global
  preservation judgment: completion, relationships, requirements, observations,
  plans, hypotheses, questions, conditions, time and negation cannot be dropped
  or turned into stronger/weaker assertions. No kinds, labels, new roles or
  dependency graph are introduced; no nonfactual claim is silently skipped.
- Batch input includes full A and all claims as **targets, never sources**. The
  exact complete B is rendered once in original order, with existing provenance
  metadata. The actual reused RAG batch/document formatter is given full-corpus
  limits; incompatible generic instructions are replaced, not appended. An
  explicit target header ends the evidence-only section. JSON-encoded claim text
  cannot create false template delimiters. No evidence is truncated or expanded.
- Batch output requires exactly the complete claim-ID set. Duplicates, missing,
  unknown or Boolean IDs fail before mapping. Valid shuffled results are restored
  to input order. Strict verdicts and existing E IDs only; no generated quotes,
  source fields, score, majority or supported/total average.
- Whole-operation publication requires every claim formally supported, structural
  coverage valid and the global preservation judgment true. That semantic
  judgment remains fallible; this implementation does not prove effectiveness.
- Every result includes a host-validated `original_fragment` within its original
  span. Failed feedback is rendered as **Original text “…”: specific evidence
  limitation**, not “claim 2 unsupported.” Global preservation rejection also
  names an exact affected original fragment. The same original-level explanation
  reaches the actual author-repair prompt and receipt. Supported broad spans are
  not announced as wholly supported just because one narrow assertion passed.
- The existing exact JSON fence reader and duplicate-key rejection are reused.
  Known length-stop metadata rejects even well-shaped JSON. Without such client
  metadata the host relies on strict schema/coverage, not a false no-truncation
  guarantee. Any engineering failure blocks publication and records its reason.
- Repair may submit new B′ only from the original frozen maintenance sources;
  every new claim is re-audited together against B′. No prior pass is inherited,
  no third repair/bypass exists. Existing serialized writes, stale-generation
  detection and receipts remain active. Delete protocol remains not applicable.
- Certificate replay rebuilds the exact split and batch requests, reparses all
  results and feedback anchors, and checks the all-required aggregate. Runtime
  strategy and source bytes are bound end-to-end. Old direct certificates cannot
  certify the candidate; changed source requires a new certificate.

## Components

`claim_split.py` owns split/span coverage, batch requests/parsing, original-level
feedback, aggregation and certificate replay. `live_citations.py` and
`citation_gate_agent.py` select the candidate without changing the author/commit
transaction. Runtime plumbing spans frontend, manifest, launcher, worker and
certificate modules. `transport.py` captures candidate call identities and known
truncation; `gate_control.py` keeps detailed control-only failure reasons.

`claim_split_cli.py` provides `export`, `fake`, and explicitly authorized
`run-profile` on the same frozen A+B for direct/candidate comparison. It accepts
an existing validated citation packet or the published call-19/call-61 trace
fixtures. Only `material` enters prompts; historical responses/reference
expectations stay outside. Export contains initial requests only: the one batch
request is generated **after** the actual split is validated. Fake responses are
scripted, never new model results. No CLI branch runs a Task or mutates memory.

`TRACE_FIXTURES.json` and `PROVENANCE.json` preserve actual SQLite A+B and separate
historical baseline outputs/reference expectations. `REUSE.md` names exact
upstream files, functions, commits, licenses and rejected behavior. Delivery
`.gitattributes` preserves hash-bound bytes, tested with a real local Git checkout
under `core.autocrlf=true` and a CRLF-converted unprotected control file.

## Verification

Final tested checkout: `58b820d7a5949028ec1ec7ee25198b4eaa5723bb` (`VERIFICATION_FINAL.json`).
Runtime source remains identical to `9986776af`; the final small test-helper correction
ensures the gate-only fixture truly has zero author repairs. Earlier verification/logs
are retained unchanged, not overwritten.
**344 tests passed: 328 PMA + 16 native Harbor, zero failures/errors/skips and no duplicate test IDs.** The final offline coordinator result and inventories are archived in
`offline_final_helper_fix/`; combined raw output is `FINAL_OFFLINE_TESTS.txt`. Native Harbor is
pinned to `459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc`, verified clean before/after.

Focused batch checks: 11 core tests at the batch-core step; 54 core/host/CLI/direct
regressions at the batch integration step; 14 exact-source certificate/policy
tests; 5 CLI/Windows-byte tests. Tests cover >1 claim in actual worker fixtures,
2/3/101-claim constant two-call behavior, complete-ID failures, time/negation,
omitted completion, same-span claims, source/self-reference boundaries, JSON
fences/duplicates/truncation, whole-operation rejection, original-level actual
repair feedback, complete re-audit, receipts and baseline direct regressions.

Every implementation step respected the 600-line code-delta limit. Raw generated
logs, trace data and prose are separately identified, not counted as code.

## Next experiment gate

Do not rerun HTML. Proposed longer multi-step task: `fix-ocaml-gc`, task-pool
commit `2fd12b88aafdd04a52c298e3940bcb189f9766d6`, chosen for C/OCaml repair,
build and test work, not historical reward. Historical reference
`pma-95d98de7ae9342d6` is developer context, not new model evidence.

First compare direct/candidate offline on identical frozen inputs, then prepare
fresh source/strategy certificates and new task manifests (SQLite and the OCaml
replacement as approved). Prior SQLite/HTML authorizations and certificates do
not authorize a new OCaml/candidate run. Before any real run, present exact source,
task, condition, existing model/runtime policy and comparison objective and obtain
explicit new authorization. No live run or method-effectiveness claim is part of
this implementation delivery.
