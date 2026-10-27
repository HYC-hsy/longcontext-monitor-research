# PMA citation gate prototype: two modes, shared commit receipt

Status: local implementation and offline validation; publication awaits review. No real model, Task,
evaluator or formal memory execution occurred. Fake verdicts establish flow only.
Parent code: ef773664f74c08619cb76ca2daeb69d0c192df16.

## Contract

Default `pma_gap_evidence_v1` remains the original latest-content behavior with no gate.
Opt in with `citation_review_gate=gate-only` or `gate-one-repair`. Both use exactly
`semantic-support-one-sentence-v1` and the same citation projection/parser. They differ only in
repair opportunity (0/1); both send final control receipts to the next maintenance request.
No new judge, selector, retriever, dependency graph, NLI, or automatic Task action.
Auditor verdicts/explanations are fallible judgments, not ground truth or external facts.
The gate enforces the selected policy; it does not prove supported content true.
Repair feedback is never registered as evidence. Evaluate false accepts/rejects, stale memory
and Task outcomes rather than supported rates; no further prompt tuning is included.

Each original operation is `(cycle_id, op_index)`. At its turn the host forks the currently committed
bank, applies the proposed operation to the isolated draft, and constructs a live envelope (not an
archive identity). The full candidate text must equal the actual draft text and revision hash.
Overlength status is rejected before the original truncating setter; in repair mode it may be
shortened once. Preparation requires every submitted citation to be exact_unique with one valid
candidate. Missing, malformed, fuzzy and multiple bindings have null verdict and no auditor call.
Host checks include role, source ID, visible spans, snippet hash, original source metadata and
pre-cycle memory-source parents. No invisible full source is added to the auditor prompt.

The live envelope stores run/cycle/op/candidate identity, original maintenance hash, source snapshot
metadata, visible spans and preparation. Its own hash is separate from archive hashes. The auditor
only sees the existing whitelist projection: this full operation, its submitted exact quotes and
source roles/identities; normative context stays empty. Task requirements are not execution proof.
Actual request payload hashes include the single-sentence SYSTEM, prompt and tools=None.

Only strict parsed supported publishes. A refusal, ineligible preparation, engineering error or
stale owner generation preserves the old active value (which may itself be stale or wrong).
Existing unreviewed memory remains selectable; the guarantee covers only new gated commits.
Deletion has no citation/reason protocol: both modes return not_reviewed_not_deleted, success=false,
without a model call or repair. This may retain solved/obsolete gaps; closure is not evaluated.

## Repair

Each valid original target/action may receive one text-only call to the same author client after
preparation failure or insufficient/contradicted. Unknown/invalid actions, illegal targets or
argument structures do not receive repair. Reviewer transport/protocol/parse failures stop the
batch and do not trigger repair. Repair failure is engineering failure, not insufficiency.

Repair sees the original frozen maintenance material, original arguments and explicit issue.
It returns exactly replace with complete content/evidence, or withdraw. No action/target fields,
tools or multiple candidates. The original action/category/target is inherited. A new operation
remains memory_id=None and can get a different draft-generated physical ID on attempt 1.
Both attempts share logical op identity; failed drafts/revisions are not retained in active bank.
Each attempt validates against the same original manifest and uses the same auditor request format.
Repair instructions/issues are not new sources. No second repair, no replay of an accepted batch.

Each op completes initial review, optional repair and re-review, then commits or rejects before
starting the next op. Same-ID sequential updates therefore have normal serial semantics. The
actual owner object is never swapped to draft; nested process calls fail before modifying state.
An owner generation change while awaiting a model makes publication fail. Audit/repair calls use
separate phase labels and existing client parameters; one semantic repair is not a claim that the
underlying existing client's HTTP retries are disabled or counted as one physical attempt.

## Final receipt and delivery

Both modes freeze per-cycle control receipts: each op has original-content summary/hash, final
outcome/reason and, when committed, actual memory_id/revision and final-content summary/hash.
Summary text is capped at 240 Python characters and explicitly marked truncated. No operation,
outcome or rejection reason is silently omitted. Full candidates and responses remain in host
logs. Receipt hashes bind content; they do not prove facts.

A dedicated suffix hook adds the receipt before render_source_blocks hashes the actual maintenance
prompt. It is outside the source catalog and never in selection. There is no fabricated token
capacity prediction: actual context errors retain the pending receipt. Nonempty maintenance response
confirms only request inclusion plus response receipt, not model understanding or agreement.
Failed/empty responses preserve R1 for same-ID resend. Only R1 actually carried by a successful
request is consumed; newly generated R2 remains pending. A no-op cycle does not create an empty
replacement receipt. No next cycle means pending_delivery, with no extra model call.

Cancellation records committed versus uncommitted operations and later not-run targets, keeps
pending reporting state, and clears transient drafts/cache. Unexpected final-report generation
errors cannot erase successful operations or replay publication: a minimal fallback commit receipt
is retained and incomplete is explicit. Receipts are runtime/diagnostic state, not bank evidence;
automatic cross-process recovery/resume is not added by this prototype.

## Reuse and changes

Actual reused PMA functions: latest `_apply_operation`, `_operation_draft`, graded alignment/store
validation, prepare_publication/publish generation checks, original vendor process and selection.
Async work occurs in `_call_llm_phase1`; synchronous dispatch consumes the exact response cache once.
No nested asyncio.run or worker thread; vendor source is unchanged.
Actual reused reviewer code: ci.prepare/candidate, cr.projection/parse, shared request formatter,
CapturedTransport and pure prompt_strategy.apply_strategy. Benchmark identities remain unchanged.
POS manager._validate_candidate and strict Sentinel clean/issues/unusable inspired isolation and
one-author-repair ordering; POS functions/whole-belief patch protocol are NOT copied or invoked.
The existing RAG/Sourcecheck/FActScore attribution remains in REUSE; no new upstream claim is made.

## Configuration boundary

single_run prepare flag -> frozen plan/config + gate source hashes -> batch launcher flag ->
live launcher spec/worker argv -> worker constructor -> gate subclass. Worker readiness echoes
mode, and Harbor compares mode with the hash-bound manifest. Gate source bytes are separately
verified. Only evidence-PMA B carrier accepts the option; missing/mismatched modes fail closed.
Older offline launchers that lack this option are unsupported for gate runs (unknown argument),
not substitute baseline execution. Native Harbor execution still requires its existing fresh
source/lifecycle certification and authorization; this offline suite does not manufacture either.
