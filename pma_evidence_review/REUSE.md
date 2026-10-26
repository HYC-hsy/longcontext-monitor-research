# Fixed-source reuse and adaptation ledger

This is a standalone offline evidence-support research component, not a PMA
reproduction and not an online completion gate. No original method was modified.

## Sources actually inspected

- `eea/rag-facts-check` **b78a08213ba7e6d9e587bfa3134ba9047cfaf677**;
  MIT, European Environment Agency 2026. `vendor/RAG_LICENSE` is preserved verbatim.
- `aberaio/sourcecheck` **d81493d239ea084c6063695b6e762c2626dd5646**;
  MIT, Mikias Abera 2026. `vendor/SOURCECHECK_LICENSE` is preserved verbatim.
- `shmsw25/FActScore` **f28272deffcf33efc1f1117d5479c10bb75221a9**;
  MIT, Sewon Min 2023. Inspected `factscore/atomic_facts.py`; no code copied.
- Host archive **72152913f545ca36a75b68e8796e24a6e24f9f81**, with executed
  source **90a4eb7a77ed6c05101fda7a929cd5cf609bf626** as an ancestor.
  Remote `main` was **be17a5c913c9dae7a3821c89f52f925af835dd29** when checked;
  it is not the relevant source-window research lineage. This branch starts at
  the specified archive rather than pretending main contains these artifacts.

The supplied Library source-study ZIP could not be materialized: this consumer
runtime exposed Library creation/upload tools but no read/search/materialize tools.
No parent filesystem path was treated as transferred. Therefore `READ_FIRST.txt`
and the four study reports were **not read**, and the ZIP SHA was **not verified**.
The authorized fallback fetched all three official repositories and checked out
exact SHAs above. Findings here are fresh static inspection plus local fake tests,
not claims about the unavailable reports or their probes.

## Function-level reuse

| Upstream symbol / file | Local location | Adaptation and reason |
|---|---|---|
| RAG `models.Span`, `EvidenceSpan`, `Claim`, `VerificationResult`; `EvidenceSpan.to_dict` | `vendor/rag_models.py` | Original class/function bodies retained; future annotations added for available Python 3.9.6. Unused aggregate score/report classes omitted. |
| RAG `prompts._load` | `vendor/rag_prompts.py` | Same loader; packaged prompt directory changed to adjacent `prompts/`. |
| RAG `format_claim_extraction_prompt` | same file, called by `review.extraction_request` | Original formatter and original prompt files; append explicit operation/coverage/kind contract. |
| RAG `format_claim_verification_evidence_first_prompt` | same file, called by `review.verification_requests` | Original formatter and actual evidence-first instructions; this is the default single-claim path. |
| RAG `format_claim_verification_batch_prompt` | same file | Actual upstream batch prompt selected only with explicit `--mode batch`; never silently bypass evidence-first via default batch_size=20. |
| RAG `format_documents` | same file | Body retained except `zip(strict=True)` removed for 3.9 (the two arrays are built from the same input); caller passes full corpus budget so no silent cap is activated. |
| RAG `ClaimExtractor._extract_chunk` / `extract` invocation skeleton | `review.extraction_request`, `review.review`, `transport.CapturedTransport.send` | Retain format -> call -> parse -> Claim sequence; replace LLM.generate adapter with host llm.call, no automatic retries/refinement, raw capture on each call. Not a verbatim class transplant. |
| RAG `ClaimExtractor._to_claim_objects` | `review.parse_claims` | Actual enumerate/original fragment/span/Claim construction adapted to operation-local exact spans. No fuzzy claim highlighting and no same-span deduplication; conditions/dependencies retained. |
| RAG `ClaimVerifier._single_verify` | `review.verification_requests`, `review.review` | Retain actual evidence-first formatter -> call -> result parse flow, with host call envelope and explicit mode. Agent/self-consistency/retrieval branches omitted. |
| RAG `ClaimVerifier._single_batch_verify` indexed_claims and Claim/VerificationResult alignment | `review.verification_requests`, `review.parse_results` | Retain input-order reconstruction keyed by claim index; reject duplicate/unknown indices before mapping; missing results are engineering errors, not not_enough_info. |
| RAG permissive `_parse_text_result`, `_parse_batch_response` parsing | deliberately not reused | Exact JSON enums only; UNSUPPORTED/NOT SUPPORTED never match supported. Duplicate JSON keys rejected. |
| Sourcecheck `types.Verdict`, `ReasonCode` | `vendor/sourcecheck_types.py`, used by `review.py` | Original enums copied. Public report maps NOT_VERIFIABLE concept to insufficient; operational failures remain separate with null verdict. No score-threshold gate imported. |
| Host `gap_evidence.render_source_blocks` | format consumed by `inputs.visible_sources` | Builder validates request SHA and uses ordered manifest spans to slice the actual submitted prompt; no final retained-sources reconstruction. |
| Host `graded_evidence_alignment.align_graded_evidence` and dependencies | imported directly by `location.locate` | Original exact/normalized/fuzzy hierarchy, limits and ambiguity handling unchanged. A transient registry contains only visible slices; candidates translate back to original source IDs/offsets. Full-source digest is explicitly unavailable, never fabricated. |
| Host `candidate_transport_worker._durable`, `TransportEpisode.handle` call/capture skeleton | `transport.durable`, `CapturedTransport.send` | Durable JSONL and request-before-call/response-after-call flow retained; remove event spool, task identity and tool execution; capture only sanitized error type. |
| Host `episode.construct_upstream` and profiled_call | `transport.load_profile_client` | Direct call to existing factory with explicit existing profile, only in authorized real execution path; reuse `_memory_llm`, do not call memory process, Task, judgment or evaluator. |
| PoS `provider_capture.inspect_provider_capture` | inspected, not called | Requires PoS-specific run/task/condition/branch identities and native ledgers. Fabricating those for this independent reviewer would be misleading. Report client boundary calls; future HTTP retry accounting must use native capture. |

## Tests actually adapted

`tests/test_review.py` ports the assertions and fixture shape of RAG
`TestClaimExtractor.test_extract_claims_basic`, `test_extract_claims_multiple`,
`test_extract_calls_llm`, and `TestClaimVerifier.test_verify_contradicted` to
stdlib unittest, strict JSON contracts and captured fake clients. These are
**adapted tests**, not a claim that the full upstream suites ran. The same-span
case is an additional regression, not an upstream behavior guarantee. Sourcecheck's
three-state/reason distinction is checked directly; its NLI/policy tests are not
reported as executed.

## Rejected components and static findings

Sourcecheck's scientific search, NLI downloads and default policy are omitted.
Its NLI thresholds and policy thresholds are separately configured, so their
composition must not be assumed calibrated for PMA. No NLI score is generated here.
FActScore's generator sets biography behavior and loads demos JSON; its old client,
biography postprocessing and normalization can drop qualifiers or change technical
identifiers. `is_num`, `text_to_sentences`, `normalize_answer`, and date/entity
helpers were inspected but add no needed capability to this JSON/span workflow.
They were not copied merely to increase reuse counts.

No RAG general-purpose highlight locator replaces the host's graded locator.
Lexical alignment is always distinct from evidence entailment, and a normalized
or fuzzy association does not validate the claim semantically.

Independent-review repair: canonical model-material projection now lives in
`inputs.model_material` (imported as `review.material`). Source identity checks reuse
the exact `gap_evidence._key`/SHA formulas without importing model/runtime packages.
The archive adapter checks existing INDEX hashes; no new source ledger was introduced.

## Source-boundary repair (2026-10-26)

Re-read at the pinned upstream revisions above:

| Function / contract | Repair reuse and adaptation |
| --- | --- |
| RAG `FactChecker.check(answer, documents)` / `_check`, `ClaimVerifier.verify(claim, documents)` | Restore its actual separation: `extraction_request` formats only operation targets; `verification_requests` passes only independently identified visible source slices as documents. Preserve vendored Claim/VerificationResult and explicit single/batch paths. |
| RAG `format_claim_verification_evidence_first_prompt`, `format_documents` | Continue executing the copied formatter. Use its supported title/text dictionaries: titles carry source identity, role, visibility and offsets. Its zero-based `document_index` is consumed for a single unique quote; multiple quotes need individual citation indices. Conflicting first indices fail. No document text truncation introduced. |
| Sourcecheck `verify_claim`, `_resolve_and_fetch` | Adapt the resolve-then-fetch contract in `evidence_policy.bind`: resolve local request document identity before grounding. No remote store, resolver, scholarly search, default NLI or thresholds copied. Existing vendored verdict/reason types remain active. This contract adaptation is not presented as copying its entire verifier. |
| FActScore `FactScorer._get_score` | Read its actual atom-as-Input versus independently retrieved passage-as-Text construction. Apply this separation to local visible sources. No new FActScore functions copied; no biography extraction, demos, retrieval, old client or permissive binary parsing introduced. |
| Host `align_graded_evidence` | Still called through `location.locate`, now restricted to the already resolved citation slice. Strict citation offsets/text checks precede it; original locator hierarchy itself is unchanged. |
| Host profile and capture adapters | Same client path and arguments; capture additionally stores policy version and actual payload SHA256. No profile data read in this repair. |

`inputs.model_material` remains the frozen input identity projection, but is no longer
passed wholesale to either model template. MIT notices and upstream files are unchanged.


v2.1 correction: `evidence_policy.context(include_sources=True)` retains all existing
visible source records for interpretation across scopes, including original event order,
field path, handle and visibility identity. It does not add these records to a scope's
citation registry. This preserves the command conditions needed to interpret receipts
without conflating command submission with successful execution. No inferred links added.

## Citation protocol v3 (2026-10-26; supersedes v2/v2.1 citation/scope rules)

Pinned actual code, not just README/types, was reviewed before the change:

- [RAG `ClaimVerifier._single_verify` and batch alignment](https://github.com/eea/rag-facts-check/blob/b78a08213ba7e6d9e587bfa3134ba9047cfaf677/rag_facts_check/checker.py#L522-L554): retain formatter → call → parse and indexed claim alignment; actual local adapter remains `review.py`.
- [RAG per-quote `EvidenceSpan`](https://github.com/eea/rag-facts-check/blob/b78a08213ba7e6d9e587bfa3134ba9047cfaf677/rag_facts_check/models.py#L46-L69) and [checker per-quote construction](https://github.com/eea/rag-facts-check/blob/b78a08213ba7e6d9e587bfa3134ba9047cfaf677/rag_facts_check/checker.py#L1156-L1191): reuse the per-quote association concept, not more model-supplied provenance fields. Host derives source identity, role, visibility and normally coordinates.
- [RAG `find_evidence_spans`](https://github.com/eea/rag-facts-check/blob/b78a08213ba7e6d9e587bfa3134ba9047cfaf677/rag_facts_check/spans.py#L240-L277) falls back from preferred document to any document/first match. This is deliberately NOT reused. Local `evidence_policy.bind` resolves the selected visible slice only, rejects mismatches/overlapping repeated matches, and invokes the existing host locator within that exact source/span.
- [Sourcecheck `verify_claim` resolve/fetch → grounding](https://github.com/aberaio/sourcecheck/blob/d81493d239ea084c6063695b6e762c2626dd5646/src/sourcecheck/verifier.py#L56-L86) and [abstention failures](https://github.com/aberaio/sourcecheck/blob/d81493d239ea084c6063695b6e762c2626dd5646/src/sourcecheck/abstention.py#L32-L61): reuse boundary ordering, separate operational failure from semantic insufficiency. Do not import remote fetch/NLI/threshold policy or claim their lexical grounding proves entailment.
- [FActScore `FactScorer._get_score`](https://github.com/shmsw25/FActScore/blob/f28272deffcf33efc1f1117d5479c10bb75221a9/factscore/factscorer.py#L209-L261): atom/query and independent passages are separate; no model-classification source gate or reusable citation resolver. Inspected only, not imported.

RAG's actual formatter displays Document 1..N while upstream verification templates
request a zero-based index for only the FIRST quote. Appending a second `citations`
contract left both schemas in the request. V3 keeps the formatter, modifies the three
vendored verification template files explicitly, and emits only evidence objects
`{document_index: 1, quote: "..."}`. Index is one-based everywhere on this wire and
in derived report citations. Both original MIT notices remain unchanged. This is a
necessary contract adaptation, not an unmodified upstream reproduction.

All original visible typed sources are now citable independently of legacy extraction
`evidence_scope`. Legacy scope is preserved only when supplied in old output, in the diagnostic report;
no default label is synthesized and no scope label enters new verification prompts.
It neither filters sources nor splits batches. Role is provenance, NOT an entailment decision.
Extraction still targets only operations and preserves deletion tombstones. Core packet,
Phase1 implementation, original history visibility and existing locator are unchanged.
No additional model, semantic rule engine, dependencies graph or online gate was added.

## Direct-operation v4 (2026-10-26)

Re-read actual fixed checkouts: RAG b78a08213ba7e6d9e587bfa3134ba9047cfaf677,
Sourcecheck d81493d239ea084c6063695b6e762c2626dd5646 and FActScore
f28272deffcf33efc1f1117d5479c10bb75221a9. Existing MIT files remain unchanged.

| Function / type | Actual direct-path reuse and adaptation |
| --- | --- |
| RAG `ClaimVerifier.verify` and `_single_verify` (522–554) | Its direct evidence-first formatter → client → parse skeleton does not require extraction. `operation_requests` calls the existing vendored evidence-first formatter with full operation target and independent documents; operation loop invokes the existing transport. No artificial Claim or claim_index is created. |
| RAG `format_documents`, evidence-first prompt files | Existing v3 adapted formatter/templates execute unchanged; one-based Document N aligns with per-evidence document_index. Full source text budget retained. |
| RAG `EvidenceSpan.to_dict` | `operation_review.review` instantiates EvidenceSpan after v3 binding, serializes using upstream method, explicitly translates its zero-based internal document index to the public one-based protocol. Coordinates remain original visible-source offsets. |
| RAG Claim/VerificationResult/ClaimExtractor | Remain in explicit `legacy_review` and regression tests. Not used to invent operation claims; direct parser adapts strict verdict/evidence validation to op_index and keeps raw output/model verdict. |
| Sourcecheck `verify_claim`, `_resolve_and_fetch` | Existing `evidence_policy.documents/bind` resolve-before-grounding contract reused unchanged; identity/range resolution precedes original locator. No external source store, NLI, search or threshold stack. |
| FActScore `FactScorer._get_score` | Rechecked Input atom separated from retrieved Text passages. Keep independent-source construction; no new extraction/retrieval functions copied, no biography machinery or permissive boolean parser. |
| Host input/locator/profile | Full packet validation, revision chains and identity unchanged; direct review calls the same graded locator and captured profile client. Capture adds strategy/op_index only, not credentials. |

`review.review` now dispatches to direct operation review; `review.legacy_review` is
explicitly named and old tests target it. This avoids silently interpreting historical
claim reports as operation reports. No upstream full suite or semantic validation claimed.


v4.1 supersedes the v4 template row above: direct `operation_requests` executes
vendored `format_documents` only, with its original title/text handling and full budget.
Evidence-first reasoning steps are adapted into one operation-specific template, not
concatenated with the legacy claim output example. One complete example carries the
actual op_index and the same four fields required by the parser. Legacy templates remain
used only by the explicit legacy path. EvidenceSpan and source/locator reuse are unchanged.
CapturedTransport now preserves available response text before rejecting unexpected tool
calls, using ResponseProtocolError to distinguish received invalid responses from call
failures; it never executes or serializes tool/client/profile objects.

## Single-factor entailment prompt candidate (2026-10-26)

Rechecked pinned RAG b78a082 prompts/claim-verification-evidence-first-system.txt:
extract relevant evidence → compare to the judgment → supported/contradicted/insufficient.
This sequence was already adapted; the candidate refines comparison, not a new mechanism.
Rechecked Sourcecheck d81493 backends/entailment.py `score_sentences`: pairs are
(source_sentence, claim), not reversed. `decide_grounding` separates insufficient support
from actual contradiction; its thresholds, lexical/numeric guards and NLI are NOT copied,
loaded or run. This is prompt-design inspiration only, not new code reuse or calibration.
Rechecked FActScore f28272 `FactScorer._get_score`: assess the whole stated fact against
independent passages. No atomizer, retrieval, binary averaging or new client introduced.

Production diff is only the comparison paragraph of CONTRACT and STRATEGY in
operation_review.py. Existing RAG format_documents/EvidenceSpan, Sourcecheck-derived
local resolution contract, host validation/locator and transport execute unchanged.
Explanation uses the existing field to describe the narrowest evidence-backed scope,
conditions and missing necessary premise. No new output type, classifier, few-shot or
semantic fixture set. Fake isolation tests are not evidence of semantic effectiveness.
MIT notices remain unchanged.

## Whole A + verbatim focus v5

Whole payload restored to A=77f0f91d, not the former entailment-prompt candidate.
Re-read RAG b78a082 `ClaimVerifier._single_verify`: fixed target + independent documents
→ client → parsed result. This actual skeleton/format_documents/EvidenceSpan remain
active; execute_request extracts the existing parse/bind/capture path for shared calls.
Result alignment is host-bound per request/op/focus, without invented Claim objects.
RAG `split_answer_into_chunks` strips chunks and can repeat table headers, so it is NOT
copied for lossless coordinates. `_aggregate` support ratios/thresholds are not reused.
Sourcecheck d81493 resolve/fetch→grounding remains adapted in local source binding.
Its `_sentences` regex strips and drops short strings; it is not used for code/path/Unicode
spans. FActScore f28272 per-item verification with original-text linkage inspires local
focus/context, but its free atomic extraction and binary averaging are not restored.

New focus_spans is a small standard-library conservative partitioner, not an upstream
algorithm presented under a new name: character offsets, protected blocks and literal
slicing retain all text. No atomization or semantic completeness guarantee. Focus request
instructions are a new adaptation of the evidence-first flow with one output contract.
Whole/local isolation is input isolation only. No consensus, voting, third evaluator,
rewriting, support rate, NLI, retrieval or automatic revision. Existing MIT notices intact.

v5.1 local FOCUS_SYSTEM is an explicit adaptation for the current verbatim interval.
It no longer inherits whole.SYSTEM's complete-operation target. Shared source/safety
principles remain; whole SYSTEM/payload are unchanged. No parser, locator or transport
change; the test inspects both message layers, not just the appended user prompt.

## Submitted literal citations v1

Re-inspected pinned Sourcecheck d81493d239ea084c6063695b6e762c2626dd5646:
verify_claim(claim,citation) -> _resolve_and_fetch -> grounding is the closest interface
contract. Its resolver supplies summary/full content, NOT a quote-only guarantee. Our
citation_inputs.prepare/candidate adapt that contract to recorded per-write alignment
and literal visible excerpts. No resolver network fallback, NLI, thresholds or retrieval
code is newly copied. Aggregate bound is not sufficient: each item must be exact_unique
and have exactly one candidate. Host inferred binding is not model-selected citation.

RAG b78a08213ba7e6d9e587bfa3134ba9047cfaf677 ClaimVerifier.verify/_single_verify
accept caller-provided target/documents. This separation inspires the new fixed-operation
and submitted-only projection; neither check/extractor nor its quote-generating prompt
is invoked. Existing strict json_value adaptation and CapturedTransport are actually
reused, as are inputs.validate/build/load_indexed/digest and phase/revision/source checks.
No fake Claim or VerificationResult is introduced for operation identities. New three-field
response template/parser are explicit local adaptations, not upstream verbatim code.

FActScore f28272deffcf33efc1f1117d5479c10bb75221a9 _get_score re-retrieves per atom.
That chain is deliberately not used in closed submitted-evidence review. No new FActScore
component copied; independent target/source principle is design reference only.
Existing upstream MIT notices/licenses remain intact. These references establish no
measured semantic effectiveness. Old whole/focus production code remains unchanged.
